import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas import VerifyRequest
from app.services import claim_verification as pipeline, nli_models
from app.services.providers import ProviderError
from app.services.structured_checks import check_claim
from app.services.extract import extract_document


class Models:
    def __init__(self, scores=None):
        self.scores = scores or {'entailment': .92, 'contradiction': .03, 'neutral': .05}
        self.pairs = []
    def fits(self, text):
        return len(text) <= 500
    def encode(self, texts):
        return [[1., 0.] for _ in texts]
    def score(self, premise, hypothesis):
        self.pairs.append((premise, hypothesis))
        return self.scores(premise, hypothesis) if callable(self.scores) else self.scores


def client_for(summary, claims=None):
    return SimpleNamespace(complete=Mock(return_value=json.dumps({'claims': claims if claims is not None else [
        {'text': summary, 'summary_quote': summary}
    ]})))


def verify(source, summary, models=None, **kwargs):
    return pipeline.verify(source, summary, client_for(summary), models or Models(), Settings(_env_file=None), **kwargs)


@pytest.mark.parametrize(('source', 'summary'), [
    ('The school opened.', 'The school opened.'),
    ('विद्यालय खुल गया।', 'विद्यालय खुल गया।'),
    ('school khul gaya.', 'school khul gaya.'),
    ('दिल्ली में दस विद्यालय खुले।', 'Ten schools opened in Delhi.'),
])
def test_languages_and_nli_direction(source, summary):
    models = Models()
    out = verify(source, summary, models)
    assert models.pairs == [(source, summary)]  # evidence is premise, claim is hypothesis
    claim = out['claims'][0]
    assert claim['status'] == 'supported'
    assert claim['support_score'] == 92
    assert claim['confidence'] is None and claim['score_calibrated'] is False
    assert out['metrics']['support_rate'] == 1
    assert out['metrics']['mean_claim_score'] == 92


def test_similarity_is_not_support():
    out = verify('The school opened.', 'The school opened.', Models({'entailment': .03, 'contradiction': .02, 'neutral': .95}))
    assert out['claims'][0]['evidence_passages'][0]['retrieval_similarity'] == 1
    assert out['claims'][0]['status'] == 'unsupported'


def test_conflicts_and_independent_contradiction_warning():
    def scores(premise, hypothesis):
        return {'entailment': .02, 'contradiction': .95, 'neutral': .03} if 'not' in premise else {'entailment': .95, 'contradiction': .02, 'neutral': .03}
    out = verify('The school opened. The school did not open.', 'The school opened.', Models(scores))
    c = out['claims'][0]
    assert c['status'] == 'uncertain' and c['conflicting_evidence']
    assert c['contradiction_warning'] and c['support_score'] == 95


def test_contradiction_and_aggregation():
    out = verify('The school did not open.', 'The school opened.', Models({'entailment': .01, 'contradiction': .97, 'neutral': .02}))
    assert out['claims'][0]['status'] == 'contradicted'
    assert out['metrics']['contradiction_count'] == 1
    assert out['metrics']['mean_claim_score'] == 1


def test_no_passages_and_no_claims():
    assert verify('', 'The school opened.')['claims'][0]['status'] == 'unsupported'
    out = pipeline.verify('The school opened.', 'Hello!', client_for('Hello!', []), Models(), Settings(_env_file=None))
    assert out['metrics']['n_claims'] == 0
    assert out['metrics']['support_rate'] is None
    assert out['metrics']['mean_claim_score'] is None


def test_top_three_exact_offsets_and_page_refs():
    source = 'One passage.\nTwo passages. Three passages. Four passages.'
    pages = [{'page': 2, 'start': 0, 'end': 12}, {'page': 4, 'start': 13, 'end': len(source)}]
    out = verify(source, 'One passage.', source_pages=pages)
    evidence = out['claims'][0]['evidence_passages']
    assert len(evidence) == 3
    for p in evidence:
        assert source[p['start']:p['end']] == p['text']
        assert p['page'] in (2, 4)
    assert verify('One passage.', 'One passage.')['claims'][0]['evidence_passages'][0]['page'] is None


def test_passage_token_budget_no_truncation():
    models = Models()
    models.fits = lambda text: len(text) <= 12
    source = 'एक बहुत लंबा अनुच्छेद जिसमें अनेक शब्द हैं।'
    result = pipeline.passages(source, None, models)
    assert all(models.fits(p['text']) for p in result)
    assert ''.join(p['text'] for p in result) == source


@pytest.mark.parametrize('rows', [None, ['bad'], [{'text': 'Invented', 'summary_quote': 'absent'}], [{'text': '', 'summary_quote': 'summary'}]])
def test_invalid_extraction_rejected(rows):
    client = SimpleNamespace(complete=lambda *a, **kw: json.dumps({'claims': rows}))
    with pytest.raises(ProviderError):
        pipeline.extract_claims('summary', client)


def test_atomic_extraction_single_call():
    summary = 'The school opened and the library closed.'
    rows = [{'text': 'The school opened.', 'summary_quote': 'The school opened'},
            {'text': 'The library closed.', 'summary_quote': 'the library closed'}]
    client = client_for(summary, rows)
    assert len(pipeline.extract_claims(summary, client)) == 2
    client.complete.assert_called_once()


def test_atomic_extraction_retries_nonverbatim_quote_once():
    summary = 'The school opened.'
    client = SimpleNamespace(complete=Mock(side_effect=[
        json.dumps({'claims': [{'text': summary, 'summary_quote': 'The school opened today.'}]}),
        json.dumps({'claims': [{'text': summary, 'summary_quote': summary}]}),
    ]))

    claims = pipeline.extract_claims(summary, client)

    assert claims == [{'text': summary, 'summary_quote': summary}]
    assert client.complete.call_count == 2


def test_atomic_extraction_retries_malformed_json_once():
    summary = 'The school opened.'
    client = SimpleNamespace(complete=Mock(side_effect=[
        'not valid json',
        json.dumps({'claims': [{'text': summary, 'summary_quote': summary}]}),
    ]))

    claims = pipeline.extract_claims(summary, client)

    assert claims == [{'text': summary, 'summary_quote': summary}]
    assert client.complete.call_count == 2


def test_llm_verifier_retries_malformed_json_once():
    from app.services.verification import Retriever, llm_verify_claims

    source = 'The school opened.'
    client = SimpleNamespace(complete=Mock(side_effect=[
        'not valid json',
        json.dumps({'results': [{
            'id': 0,
            'status': 'supported',
            'evidence': source,
            'explanation': 'The source states this.',
        }]}),
    ]))

    result = llm_verify_claims(client, source, [source], Retriever(source))

    assert result[0]['status'] == 'supported'
    assert result[0]['evidence_grounded'] is True
    assert client.complete.call_count == 2


@pytest.mark.parametrize(('claim', 'evidence', 'name', 'outcome'), [
    ('Seven schools opened.', 'Ten schools opened.', 'numbers', 'mismatch'),
    ('Seven schools cost 10 rupees.', 'Ten schools cost 10 rupees.', 'numbers', 'mismatch'),
    ('सात विद्यालय खुले।', 'दस विद्यालय खुले।', 'numbers', 'mismatch'),
    ('saat schools khule.', 'das schools khule.', 'numbers', 'mismatch'),
    ('do schools khule.', 'teen schools khule.', 'numbers', 'mismatch'),
    ('The cost was 1.5 crore rupees.', 'The cost was 15 million rupees.', 'units', 'match'),
    ('The road is 1 km.', 'The road is 1000 meters.', 'units', 'match'),
    ('The cost was 10 dollars.', 'The cost was 10 rupees.', 'units', 'mismatch'),
    ('Opened in June 2025.', 'Opened in July 2025.', 'dates', 'mismatch'),
    ('The school will open.', 'The school was opened.', 'temporal_relationships', 'mismatch'),
    ('The school opened before the library.', 'The school opened after the library.', 'temporal_relationships', 'mismatch'),
    ('The school did not open.', 'The school opened.', 'negation', 'mismatch'),
    ('Mumbai opened a school.', 'Delhi opened a school.', 'entities', 'review'),
    ('Ten schools opened.', 'Schools opened.', 'numbers', 'missing'),
])
def test_structured_checks(claim, evidence, name, outcome):
    checks = check_claim(claim, evidence)
    assert next(c for c in checks if c['name'] == name)['outcome'] == outcome


def test_structured_mismatch_downgrades_entailment():
    out = verify('Ten schools opened.', 'Seven schools opened.')
    assert out['claims'][0]['status'] == 'uncertain'
    assert out['claims'][0]['support_score'] == 92


def test_api_persistence_and_pages(client, use_llm, monkeypatch):
    use_llm(lambda s, u: json.dumps({'claims':[{'text':'The school opened.', 'summary_quote':'The school opened.'}]}))
    monkeypatch.setattr(nli_models, 'get_models', lambda *a: Models())
    run = client.post('/api/summarize', json={'text':'The school opened.', 'source_pages':[{'page':3,'start':0,'end':18}]}).json()
    # The fake generation above returned JSON: use a standalone summary for verification.
    response = client.post('/api/verify', json={'source':'The school opened.', 'summary':'The school opened.', 'method':'claim_nli', 'run_id':run['id']})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['claims'][0]['evidence_passages'][0]['page'] == 3
    assert data['claims'][0]['status'] == 'supported'
    assert client.get(f"/api/history/{run['id']}").json()['verification']['method'] == 'claim_nli'


def test_local_model_failure_before_groq(client, use_llm, monkeypatch):
    fake = use_llm(lambda *a: pytest.fail('Groq must not be called'))
    def unavailable(*args):
        raise AppError('Local models unavailable', 503)
    monkeypatch.setattr(nli_models, 'get_models', unavailable)
    response = client.post('/api/verify', json={'source':'The school opened.', 'summary':'The school opened.', 'method':'claim_nli'})
    assert response.status_code == 503 and not fake.calls


@pytest.mark.parametrize('pages', [[{'page':1,'start':1,'end':18}], [{'page':1,'start':0,'end':99}], []])
def test_bad_page_metadata(pages):
    with pytest.raises(ValidationError):
        VerifyRequest(source='The school opened.', summary='It opened.', source_pages=pages)


def test_pdf_page_offsets(monkeypatch):
    import pypdf
    reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda:' First page. '), SimpleNamespace(extract_text=lambda:''), SimpleNamespace(extract_text=lambda:'Third page.')])
    monkeypatch.setattr(pypdf, 'PdfReader', lambda _: reader)
    document = extract_document('test.pdf', b'fake')
    assert document['text'] == 'First page.\nThird page.'
    assert [p['page'] for p in document['pages']] == [1, 3]
    for p in document['pages']:
        assert document['text'][p['start']:p['end']] in ('First page.', 'Third page.')


def test_model_score_validation():
    with pytest.raises(AppError):
        pipeline.validate_scores({'entailment':float('nan'), 'contradiction':0, 'neutral':0})


def test_legacy_benchmark_accepts_new_labels():
    from app.services.evaluation import _verifier_eval
    result = _verifier_eval([('supported', 'uncertain'), ('unverifiable', 'unsupported')])
    assert result['confusion']['supported']['uncertain'] == 1


def test_nli_adapter_uses_declared_labels_and_full_pair(monkeypatch):
    import sys
    from contextlib import nullcontext
    tokenizer = Mock()
    tokenizer.model_max_length = 512
    tokenizer.return_value = {'input_ids': SimpleNamespace(shape=(1, 8))}
    model = Mock()
    model.config = SimpleNamespace(model_type='xlm-roberta', max_position_embeddings=514,
                                   id2label={0:'neutral', 1:'entailment', 2:'contradiction'})
    # Plain Mock does not implement tensor indexing, so provide that small boundary explicitly.
    class Logits:
        def softmax(self, dim):
            return self
        def __getitem__(self, index):
            return SimpleNamespace(tolist=lambda:[.1, .8, .1])
    model.return_value = SimpleNamespace(logits=Logits())
    embedder = SimpleNamespace(tokenizer=SimpleNamespace(encode=lambda text, **kw:list(text)), max_seq_length=12)
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, 'sentence_transformers', SimpleNamespace(SentenceTransformer=Mock(return_value=embedder)))
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=Mock(return_value=tokenizer)),
        AutoModelForSequenceClassification=SimpleNamespace(from_pretrained=Mock(return_value=model))))
    adapter = nli_models.LocalModels('embed', 'xlmr', True)
    sys.modules['transformers'].AutoTokenizer.from_pretrained.assert_called_once_with('xlmr', local_files_only=True, use_fast=False)
    assert adapter.score('premise', 'hypothesis') == {'neutral':.1,'entailment':.8,'contradiction':.1}
    tokenizer.assert_called_once_with('premise','hypothesis',return_tensors='pt',truncation=False)
    assert adapter.fits('short') and not adapter.fits('x'*13)
    tokenizer.return_value = {'input_ids':SimpleNamespace(shape=(1, 513))}
    with pytest.raises(AppError, match='context window'):
        adapter.score('premise','hypothesis')


def test_passage_splits_preserve_word_boundaries():
    models = Models()
    models.fits = lambda text: len(text) <= 18
    source = 'विद्यालय छात्र विद्यालय छात्र विद्यालय छात्र।'
    result = pipeline.passages(source, None, models)
    assert ''.join(p['text'] for p in result) == source
    for p in result:
        assert models.fits(p['text'])
        if p['start']:
            assert source[p['start'] - 1].isspace()

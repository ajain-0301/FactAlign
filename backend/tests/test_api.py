import io
import re

import pytest

from tests.conftest import EN_DOC, HI_DOC, HINGLISH_DOC


class RuleAwareNLI:
    def fits(self, text):
        return True

    def encode(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 128
            for token in re.findall(r"[\w\u0900-\u097f]+", text.lower()):
                vector[sum(ord(char) for char in token) % len(vector)] += 1
            vectors.append(vector)
        return vectors

    def score(self, premise, hypothesis):
        from app.services.verification import Retriever, _source_facts, _verify_rule_passage

        retriever = Retriever(premise)
        start, end, score = retriever.best(hypothesis, top=1)[0]
        result = _verify_rule_passage(
            hypothesis,
            retriever,
            _source_facts(premise),
            (start, end, score, 0.0),
        )
        if result["status"] == "supported":
            return {"entailment": 0.94, "contradiction": 0.03, "neutral": 0.03}
        if result["status"] == "contradicted":
            return {"entailment": 0.03, "contradiction": 0.94, "neutral": 0.03}
        return {"entailment": 0.05, "contradiction": 0.05, "neutral": 0.9}


@pytest.fixture(autouse=True)
def local_rule_nli(monkeypatch):
    from app.services import nli_models

    monkeypatch.setattr(nli_models, "get_models", lambda *args, **kwargs: RuleAwareNLI())


# ------------------------------------------------------------------ health & validation
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["database"] == "ok" and body["mode"] == "demo"


@pytest.mark.parametrize("payload", [
    {}, {"text": ""}, {"text": "   \n  "}, {"text": "two words"},
    {"text": EN_DOC, "strategy": "magic"}, {"text": EN_DOC, "length": "huge"}, {"text": EN_DOC, "language": "fr"},
])
def test_summarize_validation(client, payload):
    assert client.post("/api/summarize", json=payload).status_code == 422


def test_malformed_json_body(client):
    r = client.post("/api/summarize", content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_input_too_long(client, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setenv("MAX_INPUT_CHARS", "100")
    get_settings.cache_clear()
    r = client.post("/api/summarize", json={"text": EN_DOC * 3})
    assert r.status_code == 413 and "too long" in r.json()["detail"]


def test_verify_validation(client):
    assert client.post("/api/verify", json={"source": "", "summary": "x y"}).status_code == 422
    assert client.post("/api/verify", json={"source": "a b c", "summary": "  "}).status_code == 422
    assert client.post("/api/verify", json={"source": "a b c", "summary": "x y z", "run_id": 999}).status_code == 404


# ------------------------------------------------------------------ demo summarization
@pytest.mark.parametrize("doc,lang", [(HI_DOC, "hinglish"), (EN_DOC, "en"), (HINGLISH_DOC, "hinglish")])
def test_demo_summarize_languages(client, doc, lang):
    r = client.post("/api/summarize", json={"text": doc, "length": "short"})
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] == "demo" and d["provider"] == "demo-extractive"
    assert d["language_detected"] == lang
    assert 0 < d["summary_words"] < d["source_words"]
    assert d["compression_ratio"] == pytest.approx(d["summary_words"] / d["source_words"], abs=1e-3)
    assert d["inference_ms"] >= 0
    assert "engine_note" in d["extra"]


def test_pure_hindi_detection_and_devanagari_digits(client):
    text = "भारत में प्रदूषण का स्तर लगातार बढ़ रहा है। सरकार ने १२ मार्च २०२४ को नई योजना की घोषणा की। योजना पर ५० करोड़ रुपये खर्च होंगे।"
    d = client.post("/api/summarize", json={"text": text}).json()
    assert d["language_detected"] == "hi"
    assert "12 March 2024" not in str(d["analysis"]["dates"])  # raw dates are reported folded
    assert any("12" in x for x in d["analysis"]["dates"])


def test_strategies_differ_and_are_recorded(client):
    a = client.post("/api/summarize", json={"text": EN_DOC, "strategy": "standard"}).json()
    b = client.post("/api/summarize", json={"text": EN_DOC, "strategy": "factuality"}).json()
    assert a["strategy"] == "standard" and b["strategy"] == "factuality"
    assert a["id"] != b["id"]


def test_compare_demo(client):
    r = client.post("/api/summarize/compare", json={"text": EN_DOC, "length": "short"})
    assert r.status_code == 200
    res = r.json()["results"]
    assert [x["strategy"] for x in res] == ["standard", "factuality"]
    assert res[0]["compare_id"] == res[1]["compare_id"] == r.json()["compare_id"]


# ------------------------------------------------------------------ LLM mode (mocked)
def test_llm_prompt_selection(client, use_llm):
    fake = use_llm(lambda s, u: "A short summary of the document.")
    client.post("/api/summarize", json={"text": EN_DOC, "strategy": "standard"})
    client.post("/api/summarize", json={"text": EN_DOC, "strategy": "factuality"})
    std, fact = fake.calls[0]["system"], fake.calls[1]["system"]
    assert "ONLY facts" in fact and "Preserve negation" in fact and "OMIT" in fact
    assert "ONLY facts" not in std
    d = client.post("/api/summarize", json={"text": EN_DOC, "strategy": "factuality"}).json()
    assert d["mode"] == "real" and d["model"] == "fake-model"


def test_output_language_instruction(client, use_llm):
    fake = use_llm(lambda s, u: "सारांश")
    client.post("/api/summarize", json={"text": EN_DOC, "output_language": "hi"})
    assert "Hindi (Devanagari" in fake.calls[0]["system"]


def test_long_document_is_chunked_not_truncated(client, use_llm, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setenv("CHUNK_CHARS", "300")
    fake = use_llm(lambda s, u: "partial summary text")
    long_text = " ".join(f"Sentence number {i} mentions the figure {1000 + i} clearly." for i in range(40))
    d = client.post("/api/summarize", json={"text": long_text}).json()
    assert d["extra"]["chunks"] > 1
    user_inputs = " ".join(c["user"] for c in fake.calls[:-1])
    for i in (0, 20, 39):  # content from the start, middle and end all reached the model
        assert f"{1000 + i}" in user_inputs
    assert "PARTIAL SUMMARIES" in fake.calls[-1]["system"].upper()


def test_chunk_text_preserves_content():
    from app.services.summarizer import chunk_text
    text = " ".join(f"This is sentence {i}." for i in range(50)) + " " + "x" * 700
    chunks = chunk_text(text, 200)
    assert all(len(c) <= 200 for c in chunks)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_provider_failure_is_reported_not_hidden(client, use_llm):
    from app.services.providers import ProviderError

    def boom(s, u):
        raise ProviderError("The model request timed out.", 504)
    use_llm(boom)
    r = client.post("/api/summarize", json={"text": EN_DOC})
    assert r.status_code == 504 and "timed out" in r.json()["detail"]
    assert client.get("/api/history").json()["total"] == 0  # nothing fabricated or stored


def test_compare_failure_leaves_nothing_behind(client, use_llm):
    from app.services.providers import ProviderError
    state = {"n": 0}

    def flaky(s, u):
        state["n"] += 1
        if state["n"] == 2:
            raise ProviderError("rate limited", 429)
        return "A summary."
    use_llm(flaky)
    r = client.post("/api/summarize/compare", json={"text": EN_DOC})
    assert r.status_code == 429
    assert client.get("/api/history").json()["total"] == 0


# ------------------------------------------------------------------ missing credentials
def test_real_mode_without_key(client):
    client.put("/api/settings", json={"provider_mode": "real"})
    r = client.post("/api/summarize", json={"text": EN_DOC})
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["detail"]
    s = client.get("/api/settings").json()
    assert s["effective_mode"] == "unavailable" and s["mode_problem"]


def test_llm_verifier_without_key(client):
    r = client.post("/api/verify", json={"source": EN_DOC, "summary": "Markets did not react sharply.", "method": "llm"})
    assert r.status_code == 503


def test_test_connection_without_key(client):
    r = client.post("/api/settings/test-connection", json={})
    assert r.status_code == 503
    assert client.get("/api/settings").json()["connection"]["verified"] is False


def test_connection_verified_only_after_success(client, use_llm):
    use_llm(lambda s, u: "OK")
    assert client.get("/api/settings").json()["connection"]["verified"] is False
    r = client.post("/api/settings/test-connection", json={})
    assert r.status_code == 200 and r.json()["ok"] is True
    conn = client.get("/api/settings").json()["connection"]
    assert conn["verified"] is True and conn["model"]
    client.put("/api/settings", json={"model": "llama-3.1-8b-instant"})  # changing model invalidates
    assert client.get("/api/settings").json()["connection"]["verified"] is False


def test_secret_never_exposed(client, use_llm):
    use_llm(lambda s, u: "OK")
    s = client.get("/api/settings")
    assert "sk-test" not in s.text and s.json()["api_key_configured"] is True


# ------------------------------------------------------------------ verification
SRC = ("The plan will cost 250 crore rupees and will be completed by December 2026. Commissioner Meera Rao announced it on "
       "12 March 2024. The corporation will install 40 monitoring stations. The plan does not include a ban on private cars. "
       "The Reserve Bank of India funded part of the work.")


def verify(client, summary, source=SRC):
    r = client.post("/api/verify", json={"source": source, "summary": summary})
    assert r.status_code == 200, r.text
    return r.json()


def status_of(client, claim, source=SRC):
    return verify(client, claim, source)["claims"][0]["status"]


def test_verify_supported(client):
    d = verify(client, "The corporation will install 40 monitoring stations.")
    assert d["claims"][0]["status"] == "supported" and d["claims"][0]["evidence"]
    assert d["claims"][0]["confidence"] is None  # no calibrated confidence in rule mode
    assert d["is_ai_verification"] is True and "local XLM-R NLI" in d["method_label"]
    assert "not a guarantee" in d["limitations"]


def test_rule_verification_uses_local_xlm_r(client, monkeypatch):
    from app.services import nli_models

    calls = []

    class ContradictionNLI(RuleAwareNLI):
        def score(self, premise, hypothesis):
            calls.append((premise, hypothesis))
            return {"entailment": 0.02, "contradiction": 0.92, "neutral": 0.06}

    def load_models(*args, **kwargs):
        assert kwargs["local_only"] is True
        return ContradictionNLI()

    monkeypatch.setattr(nli_models, "get_models", load_models)
    claim = "The corporation will install 40 monitoring stations."
    result = verify(client, claim)["claims"][0]
    assert result["status"] == "contradicted"
    assert result["checks"][-1]["name"] == "nli"
    assert calls and all(hypothesis == claim for _, hypothesis in calls)
    assert (result["evidence"], claim) in calls


def test_semantic_retrieval_finds_paraphrased_support(client, monkeypatch):
    from app.services import nli_models

    class ParaphraseNLI(RuleAwareNLI):
        def encode(self, texts):
            aliases = {
                "city": 1, "municipality": 1,
                "banned": 2, "prohibited": 2,
                "private": 3,
                "car": 4, "cars": 4, "automobiles": 4,
            }
            vectors = []
            for text in texts:
                vector = [0.0] * 128
                for token in re.findall(r"[\w\u0900-\u097f]+", text.lower()):
                    if token in aliases:
                        vector[aliases[token]] += 1
                vectors.append(vector)
            return vectors

        def score(self, premise, hypothesis):
            calls.append(premise)
            if "prohibited private automobiles" in premise.lower():
                return {"entailment": 0.94, "contradiction": 0.03, "neutral": 0.03}
            if "world bank" in premise.lower():
                return {"entailment": 0.03, "contradiction": 0.94, "neutral": 0.03}
            return {"entailment": 0.05, "contradiction": 0.05, "neutral": 0.9}

    model = ParaphraseNLI()
    monkeypatch.setattr(nli_models, "get_models", lambda *args, **kwargs: model)
    calls = []
    source = (
        "The city owns private cars. The municipality prohibited private automobiles. "
        "The World Bank funded 900 schools in 1980."
    )
    result = verify(client, "The city banned private cars.", source)["claims"][0]

    assert result["status"] == "supported"
    assert "prohibited private automobiles" in result["evidence"]
    assert not any(
        "world bank" in premise.lower() and "prohibited private automobiles" not in premise.lower()
        for premise in calls
    )


def test_factual_checks_wait_for_relevant_evidence():
    from app.services.verification import Retriever, _source_facts, _verify_rule_passage

    source = "The clinic opened in 2019."
    retriever = Retriever(source)
    result = _verify_rule_passage(
        "The school enrolled 60 students in 2024.",
        retriever,
        _source_facts(source),
        (0, 1, 0.0, 0.0),
    )

    assert [check["name"] for check in result["checks"]] == ["relevance"]


def test_atomic_split_inherits_only_a_confident_subject():
    from app.services.verification import _atomic_components

    assert _atomic_components(
        "The council approved the plan and allocated 40 million for it."
    ) == ["The council approved the plan", "The council allocated 40 million for it."]
    assert _atomic_components("Rapidly increased and became popular.") == [
        "Rapidly increased and became popular."
    ]
    assert _atomic_components("The school opened but not implemented.") == [
        "The school opened but not implemented."
    ]
    assert _atomic_components("The school not only opened but also welcomed students.") == [
        "The school not only opened but also welcomed students."
    ]
    assert _atomic_components("The plan will cost 250 crore and be completed by December 2026.") == [
        "The plan will cost 250 crore",
        "The plan will be completed by December 2026.",
    ]


def test_atomic_split_preserves_hindi_and_hinglish_context():
    from app.services.verification import _atomic_components

    assert _atomic_components("सरकार ने 250 करोड़ रुपये खर्च किए और 10 स्कूल बनाए।") == [
        "सरकार ने 250 करोड़ रुपये खर्च किए",
        "सरकार ने 10 स्कूल बनाए।",
    ]
    assert _atomic_components(
        "Government ने 100 crore rupees ka fund announce किया और 10 school build किए।"
    ) == [
        "Government ने 100 crore rupees ka fund announce किया",
        "Government ने 10 school build किए।",
    ]
    assert _atomic_components(
        "योजना में निजी कारों पर प्रतिबंध शामिल नहीं है और निगम 40 केंद्र लगाएगा।"
    ) == [
        "योजना में निजी कारों पर प्रतिबंध शामिल नहीं है",
        "निगम 40 केंद्र लगाएगा।",
    ]


def test_multilingual_number_month_and_name_normalization():
    from app.services.verification import _entity_keys, _multilingual_facts, _normalized_tokens

    assert _multilingual_facts("five crore rupees")[1][0]["value"] == "50000000"
    assert _multilingual_facts("पाँच करोड़ रुपये")[1][0]["value"] == "50000000"
    assert _multilingual_facts("paanch karod rupaye")[1][0]["value"] == "50000000"
    assert _multilingual_facts("15 agast 2023")[0][0]["key"] == "2023-08-15"
    assert _entity_keys("श्रीमती मीरा राव") == _entity_keys("Meera Rao")
    assert "nahi" in _normalized_tokens("Yojana mein ban nahi hai", drop_stop=True)


def test_missing_entity_in_relevant_passage_is_not_a_contradiction():
    from app.services.verification import Retriever, _source_facts, _verify_rule_passage

    source = "The school opened in 2024. The clinic opened in 2019."
    retriever = Retriever(source)
    result = _verify_rule_passage(
        "The school opened in Delhi in 2024.",
        retriever,
        _source_facts(source),
        (0, 1, 1.0, 0.0),
    )

    assert result["status"] == "unverifiable"


def test_atomic_api_results_keep_component_evidence_and_nli(client):
    source = "The council approved the plan. The council allocated 40 million for it."
    result = verify(
        client,
        "The council approved the plan and allocated 40 million for it.",
        source,
    )["claims"][0]

    assert result["status"] == "supported"
    assert len(result["atomic_results"]) == 2
    for component in result["atomic_results"]:
        assert component["evidence"]
        assert component["nli_scores"]["entailment"] > 0.9
        assert component["checks"]
        assert component["explanation"]


def test_verify_changed_number(client):
    d = verify(client, "The corporation will install 60 monitoring stations.")
    c = d["claims"][0]
    assert c["status"] == "contradicted" and "40" in c["explanation"]


def test_verify_changed_date(client):
    assert status_of(client, "The plan will be completed by December 2025.") == "contradicted"
    assert status_of(client, "Commissioner Meera Rao announced it on 14 March 2024.") == "contradicted"


def test_unrelated_source_date_does_not_mask_evidence_conflict(client):
    source = (
        "The school opened in 2024. The clinic opened in 2019. "
        "The museum closed in 2023. Another event occurred in 2025."
    )
    result = verify(client, "The school opened in 2025.", source)
    assert result["claims"][0]["status"] == "contradicted"
    assert "2024" in result["claims"][0]["explanation"]


def test_unrelated_source_number_does_not_mask_evidence_conflict(client):
    source = (
        "The school enrolled 40 students. The clinic opened in 2019. "
        "The museum closed in 2023. A bridge is 60 meters long."
    )
    result = verify(client, "The school enrolled 60 students.", source)
    assert result["claims"][0]["status"] == "contradicted"
    assert "40" in result["claims"][0]["explanation"]


def test_unrelated_passage_negation_does_not_contradict_claim(client):
    source = "The school opened in 2024. The school did not close successfully."
    assert status_of(client, "The school opened successfully.", source) == "unverifiable"


def test_not_only_is_not_treated_as_negation(client):
    source = "The school not only opened but also welcomed students."
    assert status_of(client, "The school opened.", source) == "supported"


def test_conflicting_retrieved_passages_are_unverifiable(client):
    source = "The school opened in 2024. The school opened in 2025."
    result = verify(client, "The school opened in 2025.", source)["claims"][0]
    assert result["status"] == "unverifiable"
    assert "passages conflict" in result["explanation"]


def test_entity_matching_uses_word_boundaries(client):
    source = "The plan was approved annually."
    assert status_of(client, "The plan was approved by Ann.", source) == "unverifiable"


def test_hindi_and_english_entity_aliases_match(client):
    source = "दिल्ली में 40 monitoring stations स्थापित किए गए।"
    claim = "New Delhi में 40 monitoring stations स्थापित किए गए।"
    assert status_of(client, claim, source) == "supported"


def test_verify_negation_flip(client):
    assert status_of(client, "The plan includes a ban on private cars.") == "contradicted"


def test_verify_entity_substitution(client):
    assert status_of(client, "The World Bank funded part of the work.") == "contradicted"


def test_verify_unsupported_is_unverifiable(client):
    assert status_of(client, "The state government approved a new tourism law last week.") == "unverifiable"


def test_verify_hindi_changed_number_and_negation(client):
    src = "योजना पर 250 करोड़ रुपये खर्च होंगे। योजना में निजी कारों पर प्रतिबंध शामिल नहीं है। निगम 40 निगरानी केंद्र लगाएगा।"
    assert status_of(client, "योजना पर 250 करोड़ रुपये खर्च होंगे।", src) == "supported"
    assert status_of(client, "योजना पर 520 करोड़ रुपये खर्च होंगे।", src) == "contradicted"
    assert status_of(client, "योजना में निजी कारों पर प्रतिबंध शामिल है।", src) == "contradicted"
    assert status_of(client, "योजना को राज्य सरकार ने मंज़ूरी दे दी है।", src) == "unverifiable"


def test_verify_devanagari_digits_equal_ascii(client):
    src = "सरकार ने 15 अगस्त 2023 को घोषणा की। खर्च 40 करोड़ रुपये है।"
    assert status_of(client, "सरकार ने १५ अगस्त २०२३ को घोषणा की।", src) == "supported"


def test_verify_code_mixed(client):
    src = "Government ने 100 crore rupees ka fund announce किया। Yeh plan December 2025 tak complete hoga।"
    assert status_of(client, "Government ने 100 crore rupees ka fund announce किया।", src) == "supported"
    assert status_of(client, "Government ने 200 crore rupees ka fund announce किया।", src) == "contradicted"
    assert status_of(client, "Yeh plan December 2026 tak complete hoga।", src) == "contradicted"


def test_verify_metrics_formula(client):
    d = verify(client, "The corporation will install 40 monitoring stations. The corporation will install 60 monitoring stations. "
                       "Parliament passed a law on fisheries.")
    m = d["metrics"]
    assert m["n_claims"] == 3 and m["supported"] == 1 and m["contradicted"] == 1 and m["unverifiable"] == 1
    assert m["support_rate"] == pytest.approx(1 / 3, abs=1e-3)


def test_llm_verification_and_hybrid_override(client, use_llm):
    import json

    def judge(system, user):
        if "fact-checking" in system:
            # LLM naively says everything is supported (wrongly)
            n = user.count("\n") - user.split("CLAIMS:")[0].count("\n")
            return json.dumps({"results": [{"id": i, "status": "supported", "evidence": "The corporation will install 40 monitoring stations.",
                                            "explanation": "ok"} for i in range(8)]})
        return "x"
    use_llm(judge)
    r = client.post("/api/verify", json={"source": SRC, "summary": "The corporation will install 60 monitoring stations.", "method": "hybrid"})
    c = r.json()["claims"][0]
    assert r.json()["is_ai_verification"] is True
    assert c["status"] in ("contradicted", "unverifiable") and c.get("disagreement") is True  # rule check overrode the LLM
    r2 = client.post("/api/verify", json={"source": SRC, "summary": "The corporation will install 60 monitoring stations.", "method": "llm"})
    assert r2.json()["claims"][0]["status"] == "supported"  # pure LLM mode trusts the (mock) model


def test_llm_verifier_malformed_output(client, use_llm):
    use_llm(lambda s, u: "I cannot comply")
    r = client.post("/api/verify", json={"source": SRC, "summary": "The plan costs money.", "method": "llm"})
    assert r.status_code == 502 and "malformed" in r.json()["detail"]


def test_llm_evidence_must_be_grounded(client, use_llm):
    import json
    use_llm(lambda s, u: json.dumps({"results": [{"id": 0, "status": "supported", "evidence": "TOTALLY INVENTED QUOTE", "explanation": "x"}]}))
    c = client.post("/api/verify", json={"source": SRC, "summary": "The corporation will install 40 monitoring stations.", "method": "llm"}).json()["claims"][0]
    assert "INVENTED" not in c["evidence"] and c["evidence_grounded"] is False


# ------------------------------------------------------------------ history
def test_history_persistence_and_delete(client):
    run = client.post("/api/summarize", json={"text": HI_DOC, "title": "मेरा दस्तावेज़"}).json()
    lst = client.get("/api/history").json()
    assert lst["total"] == 1 and lst["items"][0]["id"] == run["id"]
    v = client.post("/api/verify", json={"source": run["source_text"], "summary": run["summary"], "run_id": run["id"]}).json()
    detail = client.get(f"/api/history/{run['id']}").json()
    assert detail["source_text"] == HI_DOC and detail["summary"] == run["summary"]
    assert detail["title"] == "मेरा दस्तावेज़"
    assert detail["verification"]["metrics"]["n_claims"] == v["metrics"]["n_claims"]
    assert client.delete(f"/api/history/{run['id']}").status_code == 200
    assert client.get(f"/api/history/{run['id']}").status_code == 404
    assert client.delete(f"/api/history/{run['id']}").status_code == 404
    assert client.get("/api/history").json()["total"] == 0


def test_history_filters_search_export(client):
    client.post("/api/summarize", json={"text": EN_DOC, "strategy": "standard", "title": "rates"})
    client.post("/api/summarize", json={"text": HINGLISH_DOC, "strategy": "factuality", "title": "climate"})
    assert client.get("/api/history", params={"q": "climate"}).json()["total"] == 1
    assert client.get("/api/history", params={"language": "en"}).json()["total"] == 1
    assert client.get("/api/history", params={"strategy": "factuality"}).json()["total"] == 1
    assert client.get("/api/history", params={"date_from": "2999-01-01"}).json()["total"] == 0
    csv_ = client.get("/api/history/export", params={"format": "csv"})
    assert csv_.status_code == 200 and "text/csv" in csv_.headers["content-type"] and "rates" in csv_.text
    assert len(client.get("/api/history/export", params={"format": "json"}).json()) == 2


def test_auto_save_off_requires_explicit_save(client):
    client.put("/api/settings", json={"auto_save": False})
    run = client.post("/api/summarize", json={"text": EN_DOC}).json()
    assert run["saved"] is False and client.get("/api/history").json()["total"] == 0
    assert client.post(f"/api/history/{run['id']}/save").status_code == 200
    assert client.get("/api/history").json()["total"] == 1


# ------------------------------------------------------------------ uploads
def test_upload_txt_and_errors(client):
    ok = client.post("/api/extract", files={"file": ("a.txt", "भारत में बारिश हुई।".encode(), "text/plain")})
    assert ok.status_code == 200 and "भारत" in ok.json()["text"]
    assert client.post("/api/extract", files={"file": ("a.exe", b"zzz", "application/octet-stream")}).status_code == 415
    assert client.post("/api/extract", files={"file": ("empty.txt", b"   ", "text/plain")}).status_code == 422


def test_upload_docx_and_size_limit(client, monkeypatch):
    from docx import Document
    from app.core.config import get_settings
    buf = io.BytesIO()
    d = Document()
    d.add_paragraph("Heavy rain hit the district on 18 July 2024.")
    d.save(buf)
    r = client.post("/api/extract", files={"file": ("a.docx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 200 and "18 July 2024" in r.json()["text"]
    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()
    assert client.post("/api/extract", files={"file": ("a.txt", b"hello world again", "text/plain")}).status_code == 413

import pytest

from app.services import metrics
from app.services.evaluation import _verifier_eval
from app.services.language import cmi, detect_language
from tests.conftest import EN_DOC, HINGLISH_DOC


def test_compression_ratio():
    assert metrics.compression_ratio(200, 50) == 0.25
    assert metrics.compression_ratio(0, 5) == 0.0


def test_rouge_identity_and_zero():
    a = "the cat sat on the mat"
    r = metrics.rouge(a, a)
    assert r["rouge1"]["f1"] == 1.0 and r["rouge2"]["f1"] == 1.0 and r["rougeL"]["f1"] == 1.0
    z = metrics.rouge("alpha beta", "gamma delta")
    assert z["rouge1"]["f1"] == 0.0


def test_rouge_known_value():
    r = metrics.rouge("the cat sat", "the cat sat down")
    assert r["rouge1"]["precision"] == 1.0 and r["rouge1"]["recall"] == 0.75
    assert r["rouge1"]["f1"] == pytest.approx(2 * 1.0 * 0.75 / 1.75, abs=1e-3)


def test_rouge_hindi_tokens_keep_matras():
    r = metrics.rouge("प्रदूषण बढ़ रहा है", "प्रदूषण बढ़ रहा है")
    assert r["rouge1"]["f1"] == 1.0
    assert metrics.rouge("बारिश हुई", "बारिश नहीं हुई")["rouge1"]["recall"] == pytest.approx(2 / 3, abs=1e-3)


def test_prf_from_counts():
    m = metrics.prf_from_counts(8, 2, 4)
    assert m["precision"] == 0.8 and m["recall"] == pytest.approx(8 / 12, abs=1e-3)
    assert m["f1"] == pytest.approx(2 * 0.8 * (8 / 12) / (0.8 + 8 / 12), abs=1e-3)
    assert metrics.prf_from_counts(0, 0, 0)["precision"] is None  # undefined, not faked as 0


def test_fact_metrics_detects_unsupported_numbers():
    m = metrics.fact_metrics("The rate was 7.5% in March 2023.", EN_DOC)
    assert m["fact_precision"] < 1.0 and "7.5" in m["unsupported_facts"]
    ok = metrics.fact_metrics("The rate was raised to 6.5% on 8 February 2023.", EN_DOC)
    assert ok["fact_precision"] == 1.0
    assert ok["fact_recall_ref"] is None  # no reference -> no recall is reported


def test_fact_recall_needs_reference():
    m = metrics.fact_metrics("Repo rate is 6.5%.", EN_DOC, reference="The repo rate rose to 6.5% on 8 February 2023.")
    assert m["fact_recall_ref"] == pytest.approx(0.5, abs=0.01)


def test_lexical_cosine_bounds():
    assert metrics.lexical_cosine("alpha beta gamma", "alpha beta gamma") == pytest.approx(1.0)
    assert metrics.lexical_cosine("alpha", "omega") == 0.0


def test_verifier_eval_confusion_math():
    rows = [("supported", "supported"), ("supported", "unverifiable"), ("contradicted", "contradicted"),
            ("unverifiable", "supported"), ("unverifiable", "unverifiable"), ("contradicted", "unverifiable")]
    e = _verifier_eval(rows)
    assert e["n_labeled_claims"] == 6 and e["accuracy"] == pytest.approx(3 / 6, abs=1e-3)
    assert e["per_class"]["supported"]["tp"] == 1 and e["per_class"]["supported"]["fp"] == 1 and e["per_class"]["supported"]["fn"] == 1
    # unsupported detection: positives = gold not supported (4), predicted not supported = 4 of 5
    u = e["unsupported_detection"]
    assert (u["tp"], u["fp"], u["fn"]) == (3, 1, 1)


def test_language_and_cmi():
    assert detect_language("भारत में प्रदूषण का स्तर लगातार बढ़ रहा है।") == "hi"
    assert detect_language("भारत में pollution का level लगातार increase हो रहा है।") == "hinglish"
    assert detect_language(EN_DOC) == "en"
    assert cmi("The rate rose.") == 0.0
    assert cmi(HINGLISH_DOC) > 15


# ------------------------------------------------------------------ API: metrics/evaluation
def test_metrics_empty_state_has_no_fabricated_numbers(client):
    m = client.get("/api/evaluation/metrics").json()
    assert m["totals"] == {"n_runs": 0} and m["by_strategy"] == {} and m["latest_evaluation"] is None
    assert m["formulas"]["compression_ratio"]


def test_metrics_reflect_stored_runs(client):
    client.post("/api/summarize", json={"text": EN_DOC, "strategy": "standard", "reference_summary": "The repo rate rose to 6.5%."})
    client.post("/api/summarize", json={"text": EN_DOC, "strategy": "factuality"})
    m = client.get("/api/evaluation/metrics").json()
    assert m["totals"]["n_runs"] == 2 and set(m["by_strategy"]) == {"standard", "factuality"}
    assert m["totals"]["n_with_reference"] == 1 and m["totals"]["rougeL_f1"] is not None
    assert m["totals"]["claim_support_rate"] is None  # nothing verified yet -> not invented
    assert m["counts"]["demo"] == 2 and m["counts"]["real"] == 0
    assert client.get("/api/evaluation/metrics", params={"strategy": "standard"}).json()["totals"]["n_runs"] == 1
    assert len(m["series"]) == 2


def test_evaluation_run_demo(client):
    r = client.post("/api/evaluation/run", json={"strategies": ["standard", "factuality"], "length": "short"})
    assert r.status_code == 200, r.text
    d = r.json()
    res = d["results"]
    assert d["mode"] == "demo" and d["model"] == "rule-based extractive"
    assert len(res["items"]) == 18  # 9 docs x 2 strategies
    v = res["verifier"]["overall"]
    assert v["n_labeled_claims"] == 36 and v["accuracy"] is not None
    assert set(res["verifier"]["by_language"]) == {"hi", "en", "hinglish"}
    assert {g["strategy"] for g in res["code_mixing_gap"]} == {"standard", "factuality"}
    assert res["code_mixing_gap"][0]["n_pairs"] == 3
    assert any("Demo mode" in n for n in res["notes"])
    m = client.get("/api/evaluation/metrics").json()
    assert m["latest_evaluation"]["id"] == d["id"] and m["counts"]["evaluation"] == 18
    # evaluation runs must not pollute the user's history
    assert client.get("/api/history").json()["total"] == 0


def test_verifier_on_benchmark_is_reasonable(client):
    """Guards the rule verifier against regressions on the labelled claims (hi/en/hinglish)."""
    v = client.post("/api/evaluation/run", json={"strategies": ["standard"], "length": "short"}).json()["results"]["verifier"]
    assert v["overall"]["accuracy"] >= 0.8
    assert v["overall"]["unsupported_detection"]["recall"] >= 0.85


def test_evaluation_export(client):
    assert client.get("/api/evaluation/export", params={"kind": "benchmark"}).status_code == 404
    client.post("/api/summarize", json={"text": EN_DOC})
    c = client.get("/api/evaluation/export", params={"kind": "runs", "format": "csv"})
    assert c.status_code == 200 and "compression_ratio" in c.text
    assert client.get("/api/evaluation/export", params={"kind": "runs", "format": "json"}).json()[0]["strategy"]
    client.post("/api/evaluation/run", json={"strategies": ["factuality"], "language": "hi"})
    assert "rougeL_f1" in client.get("/api/evaluation/export", params={"kind": "benchmark", "format": "csv"}).text


# ------------------------------------------------------------------ experiments
def test_experiment_lifecycle(client):
    r = client.post("/api/experiments", json={"name": "Hinglish baseline", "language": "hinglish", "length": "short"})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["status"] == "completed" and e["results"]["n_runs"] == 6 and len(e["runs"]) == 6
    assert set(e["results"]["by_strategy"]) == {"standard", "factuality"}
    assert e["results"]["by_strategy"]["standard"]["claim_support_rate"] is not None
    assert client.get("/api/experiments", params={"q": "baseline"}).json()["total"] == 1
    assert client.get("/api/experiments", params={"language": "hi"}).json()["total"] == 0
    assert client.get(f"/api/experiments/{e['id']}").json()["name"] == "Hinglish baseline"
    assert client.get("/api/history").json()["total"] == 0  # experiment runs are not history items
    assert client.delete(f"/api/experiments/{e['id']}").status_code == 200
    assert client.get(f"/api/experiments/{e['id']}").status_code == 404


def test_experiment_custom_documents_and_validation(client):
    ok = client.post("/api/experiments", json={"name": "custom", "dataset": "custom", "strategies": ["factuality"],
                                               "documents": [{"text": EN_DOC}, {"text": HINGLISH_DOC}]})
    assert ok.status_code == 200 and ok.json()["results"]["n_runs"] == 2
    assert client.post("/api/experiments", json={"name": "x", "dataset": "custom", "documents": []}).status_code == 422
    assert client.post("/api/experiments", json={"name": "", "strategies": ["standard"]}).status_code == 422
    assert client.post("/api/experiments", json={"name": "x", "strategies": []}).status_code == 422


def test_experiment_provider_failure_marks_failed(client, use_llm):
    from app.services.providers import ProviderError

    def boom(s, u):
        raise ProviderError("Groq rejected the API key (authentication failed).", 502)
    use_llm(boom)
    e = client.post("/api/experiments", json={"name": "will fail", "language": "en"}).json()
    assert e["status"] == "failed" and "authentication" in e["error"] and e["results"]["n_runs"] == 0


def test_samples_endpoint(client):
    s = client.get("/api/samples").json()
    assert {i["language"] for i in s["items"]} == {"hi", "en", "hinglish"} and "SYNTHETIC" in s["note"]

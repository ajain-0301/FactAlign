import os
import tempfile

# Must be set before the app is imported. Individual tests override these via monkeypatch.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/boot.db")
os.environ["GROQ_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import providers  # noqa: E402

HI_DOC = ("भारत में 2023 में प्रदूषण 12 प्रतिशत बढ़ा। सरकार ने 15 अगस्त 2023 को नई नीति की घोषणा की। "
          "Dr. Singh said the plan will not cost more than 500 crore rupees. Reserve Bank of India approved it.")
EN_DOC = ("The Reserve Bank of India raised the repo rate to 6.5% on 8 February 2023. Governor Shaktikanta Das said "
          "inflation is expected to ease to 5.3% next year. The committee voted 4-2 for the increase. Markets did not react sharply.")
HINGLISH_DOC = ("Climate change ki wajah se temperature continuously increase ho raha hai. WHO ke mutabik 2022 mein 3.5 million "
                "log heat se prabhavit hue. Government ne 100 crore rupees ka fund announce kiya. Yeh plan December 2025 tak complete hoga.")


class FakeLLM:
    name = "fake"
    model = "fake-model"

    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def complete(self, system, user, max_tokens=1024):
        self.calls.append({"system": system, "user": user})
        return self.handler(system, user)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("PROVIDER_MODE", "auto")
    get_settings.cache_clear()
    providers.set_llm_factory(None)
    providers.reset_connection()
    with TestClient(create_app()) as c:
        yield c
    providers.set_llm_factory(None)
    get_settings.cache_clear()


@pytest.fixture
def use_llm(client, monkeypatch):
    """Switch the app to 'real' mode with a fake LLM. Call use_llm(handler) -> FakeLLM."""
    def _use(handler):
        monkeypatch.setenv("GROQ_API_KEY", "sk-test-not-real")
        get_settings.cache_clear()
        fake = FakeLLM(handler)
        providers.set_llm_factory(lambda settings, model: fake)
        return fake
    return _use


@pytest.fixture(autouse=True)
def block_live_groq(monkeypatch):
    """Tests must use fake clients; never consume the user's Groq quota."""
    import groq

    def blocked(*args, **kwargs):
        raise AssertionError("Live Groq calls are disabled in tests. Mock the client instead.")

    monkeypatch.setattr(groq, "Groq", blocked)

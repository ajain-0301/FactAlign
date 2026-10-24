"""Explicit setup step: download/cache local models. Never calls Groq."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.nli_models import get_models

if __name__ == '__main__':
    settings = get_settings()
    get_models(settings.embedding_model, settings.nli_model, local_only=False)
    print('Embedding and XLM-R models cached. No Groq requests were made.')

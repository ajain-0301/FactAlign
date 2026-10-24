"""User preferences (stored in DB) + resolution of the effective provider mode."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories import misc
from app.services.providers import ProviderError

DEFAULT_PREFS = {
    "provider_mode": None,        # None -> use PROVIDER_MODE from the environment
    "model": None,                # None -> use GROQ_MODEL from the environment
    "default_strategy": "factuality",
    "default_length": "medium",
    "default_language": "auto",
    "default_output_language": "same",
    "auto_save": True,
    "verifier": "auto",
}
MODEL_OPTIONS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


def load_prefs(db: Session) -> dict:
    return {**DEFAULT_PREFS, **misc.get_setting(db, "preferences")}


def update_prefs(db: Session, patch: dict) -> dict:
    prefs = load_prefs(db)
    for k, v in patch.items():
        if k in ("provider_mode", "model"):
            prefs[k] = v or None  # empty string / None resets to environment default
        elif v is not None:
            prefs[k] = v
    misc.put_setting(db, "preferences", prefs)
    return prefs


@dataclass
class Effective:
    mode: str       # demo | real
    model: str
    prefs: dict


def resolve(db: Session, settings: Settings, model_override: str | None = None) -> Effective:
    prefs = load_prefs(db)
    pm = prefs.get("provider_mode") or settings.provider_mode
    if pm not in ("auto", "demo", "real"):
        pm = "auto"
    model = model_override or prefs.get("model") or settings.groq_model
    if pm == "demo":
        return Effective("demo", model, prefs)
    if pm == "real":
        if not settings.has_api_key:
            raise ProviderError(
                "Real AI mode is selected but GROQ_API_KEY is not configured on the server. "
                "Add it to backend/.env and restart, or switch to Demo/Auto mode in Settings.", 503)
        return Effective("real", model, prefs)
    return Effective("real" if settings.has_api_key else "demo", model, prefs)

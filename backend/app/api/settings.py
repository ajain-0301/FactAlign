from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core import db as dbm
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.schemas import SettingsUpdate
from app.services import providers, settings_service

router = APIRouter(prefix="/api/settings")

SETUP = [
    "Copy backend/.env.example to backend/.env.",
    "Set GROQ_API_KEY=<your key> (from console.groq.com). The key stays on the server; the browser never sees it.",
    "Restart the backend (close its window and run start.bat again).",
    "Open this page and press 'Test connection'. The app only reports 'verified' after a real API call succeeds.",
    "Leave the key empty to keep using Demo mode (rule-based extractive engine, no internet or API cost).",
]


def _state(db: Session, settings: Settings) -> dict:
    prefs = settings_service.load_prefs(db)
    try:
        eff = settings_service.resolve(db, settings)
        effective, problem, model = eff.mode, None, eff.model
    except AppError as e:
        effective, problem, model = "unavailable", e.message, prefs.get("model") or settings.groq_model
    return {
        "provider": "groq",
        "api_key_configured": settings.has_api_key,  # boolean only - the key itself is never returned
        "provider_mode": prefs.get("provider_mode") or settings.provider_mode,
        "effective_mode": effective, "mode_problem": problem,
        "model": model, "model_options": settings_service.MODEL_OPTIONS,
        "connection": providers.connection_state(),
        "preferences": prefs, "setup_instructions": SETUP,
        "limits": {"max_input_chars": settings.max_input_chars, "max_upload_mb": settings.max_upload_mb,
                   "chunk_chars": settings.chunk_chars, "llm_timeout_seconds": settings.llm_timeout_seconds},
        "database": settings.database_url.split("://")[0],
    }


@router.get("")
def get_settings_state(db: Session = Depends(dbm.get_session), settings: Settings = Depends(get_settings)):
    return _state(db, settings)


@router.put("")
def update_settings(body: SettingsUpdate, db: Session = Depends(dbm.get_session), settings: Settings = Depends(get_settings)):
    patch = body.model_dump(exclude_unset=True)
    before = settings_service.load_prefs(db).get("model")
    settings_service.update_prefs(db, patch)
    if "model" in patch and patch["model"] != before:
        providers.reset_connection()  # a new model must be re-tested
    return _state(db, settings)


@router.post("/test-connection")
def test_connection(model: str | None = Body(default=None, embed=True), db: Session = Depends(dbm.get_session),
                    settings: Settings = Depends(get_settings)):
    prefs = settings_service.load_prefs(db)
    use_model = model or prefs.get("model") or settings.groq_model
    return providers.test_connection(settings, use_model)

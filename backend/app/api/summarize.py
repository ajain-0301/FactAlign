from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core import db as dbm
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.repositories import runs as runs_repo
from app.schemas import CompareRequest, SummarizeRequest
from app.services import engine, settings_service
from app.services.extract import extract_document

router = APIRouter(prefix="/api")


def _kw(req: SummarizeRequest) -> dict:
    return dict(text=req.text, title=req.title, language=req.language, output_language=req.output_language,
                length=req.length, reference_summary=req.reference_summary,
                source_pages=[p.model_dump() for p in req.source_pages] if req.source_pages else None)


@router.post("/summarize")
def summarize(req: SummarizeRequest, db: Session = Depends(dbm.get_session), settings: Settings = Depends(get_settings)):
    eff = settings_service.resolve(db, settings)
    saved = req.save if req.save is not None else bool(eff.prefs["auto_save"])
    run = engine.make_run(db, settings, eff, strategy=req.strategy, saved=saved, **_kw(req))
    return engine.run_out(run)


@router.post("/summarize/compare")
def compare(req: CompareRequest, db: Session = Depends(dbm.get_session), settings: Settings = Depends(get_settings)):
    eff = settings_service.resolve(db, settings)
    saved = req.save if req.save is not None else bool(eff.prefs["auto_save"])
    cid = engine.new_compare_id()
    client = engine.get_client(settings, eff)
    created = []
    try:
        for st in ("standard", "factuality"):
            created.append(engine.make_run(db, settings, eff, strategy=st, saved=saved, compare_id=cid,
                                           client=client, **_kw(req)))
    except Exception:
        for r in created:  # do not leave half of a comparison behind
            runs_repo.delete(db, r.id)
        raise
    return {"compare_id": cid, "results": [engine.run_out(r) for r in created]}


@router.post("/extract")
async def extract(file: UploadFile = File(...), settings: Settings = Depends(get_settings)):
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise AppError(f"File is larger than the {settings.max_upload_mb} MB limit.", 413)
    document = extract_document(file.filename or "", data)
    text = document["text"]
    if len(text) > settings.max_input_chars:
        raise AppError(f"The extracted text has {len(text):,} characters; the limit is {settings.max_input_chars:,}.", 413)
    return {"filename": file.filename, "text": text, "chars": len(text), "words": len(text.split()), "pages": document["pages"]}

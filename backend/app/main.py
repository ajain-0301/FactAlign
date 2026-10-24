import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.api import evaluation, experiments, health, history, settings as settings_api, summarize, verify
from app.core import db as dbm
from app.core.config import get_settings
from app.core.errors import AppError
from app.services.providers import ProviderError

log = logging.getLogger("FactAlign")


@asynccontextmanager
async def lifespan(app: FastAPI):
    dbm.init_db(get_settings().database_url)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="FactAlign API", version=__version__, lifespan=lifespan,
                  description="Factuality-aware summarization for Indic and code-mixed languages.")
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(AppError)
    async def _app_error(_: Request, e: AppError):
        return JSONResponse({"detail": e.message}, status_code=e.status)

    @app.exception_handler(ProviderError)
    async def _provider_error(_: Request, e: ProviderError):
        return JSONResponse({"detail": e.message, "kind": "provider_error"}, status_code=e.status)

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_: Request, e: SQLAlchemyError):
        log.exception("database error")
        return JSONResponse({"detail": "A database error occurred. Check the backend console for details."}, status_code=500)

    for r in (health, summarize, verify, history, experiments, evaluation, settings_api):
        app.include_router(r.router)
    return app


app = create_app()

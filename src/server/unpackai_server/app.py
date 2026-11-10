"""The UnpackAI HTTP server.

The browser never sends or receives the API key. It calls these endpoints,
and the server makes every call to Claude with the key from the Docker secret
(see secret_store.py).
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .db import Database
from .safe_logging import configure_logging
from . import secret_store
from .unpack import INDEX_HTML, UnpackError, Unpacker, parse_source, source_from_key

log = logging.getLogger("unpackai.http")

DEFAULT_DB = "/data/unpackai.sqlite3"  # the unpackai-data volume

# Credentials can only come from the Docker secret. Removing the environment
# variables stops the SDK from picking up a second credential.
for _name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_LOG"):
    os.environ.pop(_name, None)


class UnpackRequest(BaseModel):
    url: str | None = Field(default=None, description="arXiv link or id, PDF URL, or blog URL")
    text: str | None = Field(default=None, description="Full text of the paper, if there is no URL")


def create_app(db_path: str | Path | None = None, unpacker: Unpacker | None = None, model: str | None = None) -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = unpacker.db if unpacker else Database(db_path or DEFAULT_DB)
        # A paper left "running" by a stopped server will never finish.
        for p in db.list_papers():
            if p["status"] in ("queued", "running"):
                db.set_status(p["id"], "failed", "The server stopped before the unpack finished. Send the request again.")
        app.state.db = db
        app.state.unpacker = unpacker or Unpacker(db, model=model or os.environ.get("UNPACKAI_MODEL", "claude-opus-5-5"))
        yield

    app = FastAPI(title="UnpackAI", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        # Only the method, path, status, and time are logged. Headers, query
        # strings, and bodies are never logged.
        started = time.monotonic()
        response = await call_next(request)
        log.info("%s %s %s %.0fms", request.method, request.url.path, response.status_code, (time.monotonic() - started) * 1000)
        return response

    @app.get("/")
    def index():
        return FileResponse(INDEX_HTML)

    @app.get("/api/health")
    def health():
        return {"ok": True, "api_key_configured": secret_store.key_is_configured()}

    @app.post("/api/unpack", status_code=202)
    def unpack(body: UnpackRequest, background: BackgroundTasks, request: Request):
        try:
            source = parse_source(body.url, body.text)
        except UnpackError as exc:
            raise HTTPException(400, str(exc))
        db: Database = request.app.state.db
        paper_id, queued = db.upsert_paper(source.key, source.kind)
        if queued:
            background.add_task(request.app.state.unpacker.run, paper_id, source)
        return {"paper_id": paper_id, "queued": queued, "paper": db.get_paper(paper_id)}

    @app.get("/api/papers")
    def papers(request: Request):
        return request.app.state.db.list_papers()

    @app.get("/api/papers/{paper_id}")
    def paper(paper_id: int, request: Request):
        db: Database = request.app.state.db
        p = db.get_paper(paper_id)
        if not p:
            raise HTTPException(404, "No paper with that id.")
        return {
            **p,
            "step": request.app.state.unpacker.last_step.get(paper_id),
            "calls": db.list_calls(paper_id),
            "dossier": db.latest_dossier(paper_id),
        }

    @app.post("/api/papers/{paper_id}/retry", status_code=202)
    def retry(paper_id: int, background: BackgroundTasks, request: Request):
        db: Database = request.app.state.db
        p = db.get_paper(paper_id)
        if not p:
            raise HTTPException(404, "No paper with that id.")
        try:
            source = source_from_key(p["source"], p["source_kind"])
        except UnpackError as exc:
            raise HTTPException(400, str(exc))
        if not db.requeue_failed(paper_id):
            raise HTTPException(409, "Only a failed unpack can be started again.")
        background.add_task(request.app.state.unpacker.run, paper_id, source)
        return {"paper_id": paper_id, "queued": True, "paper": db.get_paper(paper_id)}

    @app.get("/api/papers/{paper_id}/generations")
    def generations(paper_id: int, request: Request):
        db: Database = request.app.state.db
        if not db.get_paper(paper_id):
            raise HTTPException(404, "No paper with that id.")
        return db.list_generations(paper_id)

    return app

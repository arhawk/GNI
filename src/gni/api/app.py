"""FastAPI surface for React dashboard (Event Intelligence + metrics overview)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from gni import __version__
from gni.events.service import get_event_detail, list_events, overview_payload, rebuild_proto_events
from gni.infrastructure.db import ensure_schema, session_scope

app = FastAPI(title="GNI API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    ensure_schema()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/overview")
def api_overview(days: int = Query(30, ge=1, le=365)) -> dict:
    with session_scope() as session:
        return overview_payload(session, days=days)


@app.get("/api/events")
def api_events(limit: int = Query(50, ge=1, le=200)) -> dict:
    with session_scope() as session:
        return {"events": list_events(session, limit=limit)}


@app.get("/api/events/{event_id}")
def api_event_detail(event_id: str) -> dict:
    with session_scope() as session:
        detail = get_event_detail(session, event_id)
        if not detail:
            raise HTTPException(status_code=404, detail="event not found")
        return detail


@app.post("/api/events/rebuild")
def api_rebuild_events(min_articles: int = Query(1, ge=1, le=20)) -> dict:
    with session_scope() as session:
        return rebuild_proto_events(session, min_articles=min_articles)

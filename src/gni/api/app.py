"""FastAPI surface for GNI Intelligence Presentation Layer (decoupled domain routers)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gni import __version__
from gni.api.routers.alerts_system import router as alerts_system_router
from gni.api.routers.articles import router as articles_router
from gni.api.routers.assessments import router as assessments_router
from gni.api.routers.countries import router as countries_router
from gni.api.routers.dashboard import router as dashboard_router
from gni.api.routers.events import router as events_router
from gni.api.routers.narratives import router as narratives_router
from gni.api.routers.reports import router as reports_router
from gni.api.routers.sentiment_stance import router as sentiment_stance_router
from gni.api.routers.topics import router as topics_router
from gni.infrastructure.db import ensure_schema
from gni.reports.daily import SCHEMA_VERSION as DAILY_SCHEMA_VERSION

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
    return {
        "status": "ok",
        "version": __version__,
        "daily_schema": DAILY_SCHEMA_VERSION,
        "api_version": "v2.0-phase7",
    }


app.include_router(dashboard_router)
app.include_router(reports_router)
app.include_router(assessments_router)
app.include_router(events_router)
app.include_router(topics_router)
app.include_router(countries_router)
app.include_router(narratives_router)
app.include_router(sentiment_stance_router)
app.include_router(articles_router)
app.include_router(alerts_system_router)

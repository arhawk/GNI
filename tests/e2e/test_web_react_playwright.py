"""Playwright E2E: React Event Intelligence UI (Vite + FastAPI)."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect, sync_playwright

from gni.core.config import get_settings
from gni.events.service import rebuild_proto_events
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import Article, Country, Organization, Source

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_http(url: str, timeout: float = 60.0) -> None:
    import urllib.request

    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.4)
    raise RuntimeError(f"server not ready: {url} ({last})")


@pytest.fixture(scope="module")
def react_stack(tmp_path_factory):
    if not (WEB / "node_modules").exists():
        pytest.skip("web/node_modules missing — run: cd web && npm install")

    db_path = tmp_path_factory.mktemp("e2e_web") / "gni_web.sqlite"
    db_url = f"sqlite+pysqlite:///{db_path}"
    os.environ["GNI_DATABASE_URL"] = db_url
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()

    with session_scope() as session:
        session.merge(Country(id="US", code="US", name="United States"))
        session.merge(Country(id="DE", code="DE", name="Germany"))
        session.merge(
            Organization(id="org_us", country_id="US", name="OrgUS", organization_type="media")
        )
        session.merge(
            Organization(id="org_de", country_id="DE", name="OrgDE", organization_type="media")
        )
        for sid, cid, name in (("src_us", "US", "US Wire"), ("src_de", "DE", "DE Wire")):
            session.merge(
                Source(
                    id=sid,
                    organization_id=f"org_{cid.lower()}",
                    country_id=cid,
                    name=name,
                    source_type="news",
                    access_method="rss",
                    adapter_type="rss_adapter",
                    active_status="active",
                    language="en",
                )
            )
        now = datetime.now(timezone.utc)
        for sid, title in (
            ("src_us", "China trade talks resume in Brussels"),
            ("src_de", "China trade talks resume amid tariffs"),
        ):
            aid = str(uuid4())
            session.add(
                Article(
                    id=aid,
                    source_id=sid,
                    title=title,
                    url=f"https://example.test/{aid}",
                    language="en",
                    processing_status="done",
                    quality_status="processed",
                    exclude_from_metrics=False,
                    china_relevance_level="substantial",
                    china_relevance_weight=0.65,
                    analysis_status="completed",
                    content_hash=aid[:16],
                    published_at=now,
                    first_seen_at=now,
                )
            )
        session.flush()
        rebuild_proto_events(session, min_articles=1, limit=10)

    api_port = _free_port()
    web_port = _free_port()
    env = os.environ.copy()
    env["GNI_DATABASE_URL"] = db_url
    env["GNI_API_PROXY"] = f"http://127.0.0.1:{api_port}"
    env["PATH"] = "/opt/homebrew/bin:" + env.get("PATH", "")

    api = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import uvicorn; uvicorn.run('gni.api.app:app', host='127.0.0.1', "
            f"port={api_port}, log_level='warning')",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    web = subprocess.Popen(
        [
            "npm",
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(web_port),
            "--strictPort",
        ],
        cwd=str(WEB),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        _wait_http(f"http://127.0.0.1:{api_port}/health")
        _wait_http(f"http://127.0.0.1:{web_port}/")
        yield {"api": api_port, "web": web_port}
    finally:
        for proc in (web, api):
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        reset_engine()
        get_settings.cache_clear()


@pytest.mark.e2e
def test_react_overview_events_detail(react_stack):
    web = react_stack["web"]
    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(f"http://127.0.0.1:{web}/", wait_until="networkidle")
        expect(page.get_by_text("GNI", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Overview")).to_be_visible()
        expect(page.get_by_text("A · Snapshot")).to_be_visible(timeout=15000)
        expect(page.locator(".kpi-grid")).to_be_visible()
        expect(page.get_by_text("Monitoring countries")).to_be_visible()
        expect(page.get_by_text("China-set countries")).to_be_visible()
        expect(page.get_by_role("button", name="1 month")).to_be_visible()
        page.get_by_role("button", name="3 months").click()
        expect(page.get_by_role("button", name="Event geography (Where)")).to_be_visible()
        page.get_by_role("button", name="Reporting sources (Who)").click()
        expect(page.get_by_role("button", name="Reporting sources (Who)")).to_have_class(
            re.compile(r"active")
        )

        page.get_by_role("link", name="News & Events").click()
        expect(page.get_by_role("heading", name="News & Events")).to_be_visible()
        first = page.locator(".event-list a").first
        expect(first).to_be_visible(timeout=10000)
        first.click()
        expect(page.get_by_role("tab", name="Geographic (Where)")).to_be_visible()
        page.get_by_role("tab", name="Country (Who reports)").click()
        expect(page.get_by_role("heading", name="Who reports")).to_be_visible()
        page.get_by_role("tab", name="Narrative (How they frame)").click()
        expect(page.get_by_role("heading", name="How they frame")).to_be_visible()
        page.get_by_role("tab", name="Timeline").click()
        expect(page.get_by_role("heading", name="Timeline")).to_be_visible()

        assert not errors, f"page errors: {errors}"
        browser.close()

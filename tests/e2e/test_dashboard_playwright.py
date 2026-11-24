"""Playwright E2E: Streamlit dashboard loads and pages switch without exceptions."""

from __future__ import annotations

import os
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
from gni.dashboard.data import NAV_PAGES
from gni.infrastructure.db import ensure_schema, reset_engine, session_scope
from gni.infrastructure.models import Article, Country, Organization, Source

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src" / "gni" / "dashboard" / "app.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def dashboard_server(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("e2e") / "gni_e2e.sqlite"
    db_url = f"sqlite+pysqlite:///{db_path}"
    os.environ["GNI_DATABASE_URL"] = db_url
    get_settings.cache_clear()
    reset_engine()
    ensure_schema()

    with session_scope() as session:
        session.merge(Country(id="US", code="US", name="United States"))
        session.merge(
            Organization(id="org_e2e", country_id="US", name="E2E Org", organization_type="media")
        )
        session.merge(
            Source(
                id="src_e2e",
                organization_id="org_e2e",
                country_id="US",
                name="E2E Source",
                source_type="news",
                access_method="rss",
                adapter_type="rss_adapter",
                active_status="active",
                language="en",
            )
        )
        now = datetime.now(timezone.utc)
        session.add(
            Article(
                id=str(uuid4()),
                source_id="src_e2e",
                title="China trade policy update for E2E",
                url=f"https://example.test/e2e/{uuid4()}",
                language="en",
                processing_status="done",
                quality_status="processed",
                exclude_from_metrics=False,
                china_relevance_level="substantial",
                china_relevance_weight=0.65,
                analysis_status="completed",
                content_hash="e2ehash",
                published_at=now,
                first_seen_at=now,
            )
        )

    port = _free_port()
    env = os.environ.copy()
    env["GNI_DATABASE_URL"] = db_url
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(APP),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError(f"Streamlit exited early:\n{out}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                ready = True
                break
        except OSError:
            time.sleep(0.4)
    if not ready:
        proc.kill()
        raise RuntimeError("Streamlit did not become ready in time")

    # Give Streamlit a moment to finish first script run
    time.sleep(2)
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    get_settings.cache_clear()
    reset_engine()


@pytest.mark.e2e
def test_dashboard_overview_and_nav(dashboard_server):
    url = dashboard_server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Streamlit app shell
        page.wait_for_selector("text=GNI Monitor", timeout=60000)
        # Overview content
        expect(page.get_by_role("heading", name="Overview", exact=True)).to_be_visible(
            timeout=60000
        )
        # Must not show the previous schema failure
        assert page.locator("text=UndefinedColumn").count() == 0
        assert page.locator("text=processing_status does not exist").count() == 0
        # KPI present
        expect(page.get_by_text("Article Count (raw)")).to_be_visible(timeout=30000)

        # Navigate through all pages via sidebar radio
        nav = page.get_by_test_id("stSidebar").get_by_test_id("stRadio")
        for name in NAV_PAGES:
            nav.get_by_text(name, exact=True).click()
            page.wait_for_timeout(800)
            expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible(
                timeout=45000
            )
            assert page.locator("text=UndefinedColumn").count() == 0
            assert page.locator("text=Exception:").count() == 0

        browser.close()

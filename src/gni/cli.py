"""CLI entrypoint for GNI Phase 1-A/B/C/D/E."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from gni import __version__
from gni.core.config import get_settings
from gni.core.logging import setup_logging


def cmd_health(_: argparse.Namespace) -> int:
    settings = get_settings()
    payload = {
        "status": "ok",
        "version": __version__,
        "env": settings.env,
        "llm_provider": settings.llm_provider,
        "llm_api_configured": bool(settings.llm_api_key),
        "database_url_scheme": settings.database_url.split("://", 1)[0],
        "phase": "1E",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def cmd_db_upgrade(_: argparse.Namespace) -> int:
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        print(
            "SQLite URL detected — use `gni db init` instead of alembic upgrade.",
            file=sys.stderr,
        )
        return 2
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root,
        check=False,
    )
    return result.returncode


def cmd_db_init(_: argparse.Namespace) -> int:
    """Create schema via SQLAlchemy metadata (SQLite local / emergency bootstrap)."""
    from gni.infrastructure.db import ensure_schema
    from gni.infrastructure.models import Base

    altered = ensure_schema()
    print(
        json.dumps(
            {
                "status": "ok",
                "tables": sorted(Base.metadata.tables.keys()),
                "sqlite_columns_added": altered,
            },
            indent=2,
        )
    )
    return 0


def cmd_sources_seed(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import session_scope
    from gni.sources.seed import seed_sources

    path = Path(args.file) if args.file else None
    with session_scope() as session:
        counts = seed_sources(session, path)
    print(json.dumps({"seeded": counts}, ensure_ascii=False, indent=2))
    return 0


def cmd_sources_list(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import session_scope
    from gni.sources.seed import list_sources

    with session_scope() as session:
        rows = list_sources(session, active_only=args.active)
        payload = [
            {
                "id": s.id,
                "country_id": s.country_id,
                "name": s.name,
                "active_status": s.active_status,
                "verification_status": s.verification_status,
                "adapter_type": s.adapter_type,
                "feed_or_api_url": s.feed_or_api_url,
            }
            for s in rows
        ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_ingest_run(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import session_scope
    from gni.ingestion.service import run_ingestion

    with session_scope() as session:
        jobs = run_ingestion(session, source_id=args.source)
        payload = [
            {
                "job_id": j.id,
                "source_id": j.source_id,
                "status": j.status,
                "error": j.error,
                "stats": j.stats,
            }
            for j in jobs
        ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    failed = sum(1 for j in payload if j["status"] != "success")
    return 1 if failed and not args.allow_partial else 0


def cmd_process_run(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import ensure_schema, session_scope
    from gni.processing.service import run_processing

    ensure_schema()
    with session_scope() as session:
        job = run_processing(
            session,
            limit=None if args.article else args.limit,
            source_id=args.source,
            article_id=args.article,
            skip_fetch=args.skip_fetch,
            reprocess=args.reprocess,
        )
        payload = {
            "job_id": job.id,
            "status": job.status,
            "error": job.error,
            "stats": job.stats,
        }
        status = job.status
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if status in {"success", "partial"} else 1


def cmd_events_rebuild(args: argparse.Namespace) -> int:
    from gni.events.service import rebuild_proto_events
    from gni.infrastructure.db import ensure_schema, session_scope

    ensure_schema()
    with session_scope() as session:
        stats = rebuild_proto_events(
            session,
            min_articles=args.min_articles,
            limit=args.limit,
            extract=not bool(getattr(args, "skip_extract", False)),
        )
    print(json.dumps({"status": "ok", **stats}, ensure_ascii=False, indent=2))
    return 0


def cmd_events_extract(args: argparse.Namespace) -> int:
    from gni.events.extract import extract_for_articles
    from gni.infrastructure.db import ensure_schema, session_scope

    ensure_schema()
    with session_scope() as session:
        stats = extract_for_articles(session, limit=args.limit)
    # cards are not JSON-serializable
    out = {k: v for k, v in stats.items() if k != "cards"}
    print(json.dumps({"status": "ok", **out}, ensure_ascii=False, indent=2))
    return 0


def cmd_alerts_run(_: argparse.Namespace) -> int:
    from gni.alerts.service import run_alert_engine
    from gni.infrastructure.db import session_scope

    with session_scope() as session:
        out = run_alert_engine(session)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_search_reindex(_: argparse.Namespace) -> int:
    from gni.infrastructure.db import session_scope
    from gni.search.sync import reindex_all

    with session_scope() as session:
        out = reindex_all(session)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


def cmd_reports_daily(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import ensure_schema, session_scope
    from gni.reports.daily import build_daily_report, write_daily_files

    ensure_schema()
    with session_scope() as session:
        payload = build_daily_report(
            session,
            day=args.date,
            analyze=bool(getattr(args, "analyze", False)),
            analyze_tasks=getattr(args, "task", None) or None,
            force_analyze=bool(getattr(args, "force", False)),
        )
    paths = write_daily_files(payload, out_dir=args.out_dir)
    sections = payload.get("sections") or {}
    ameta = payload.get("assessments_meta") or {}
    print(
        json.dumps(
            {
                "status": "ok",
                "period": payload.get("period"),
                "schema_version": payload.get("schema_version"),
                "generator": payload.get("generator"),
                "files": paths,
                "missing_analysis": (sections.get("quality") or {}).get("missing_analysis"),
                "events": len(sections.get("major_events") or []),
                "assessments_status": ameta.get("status"),
                "assessments_meta": ameta.get("meta"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_reports_weekly(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import ensure_schema, session_scope
    from gni.reports.weekly import build_weekly_report

    ensure_schema()
    with session_scope() as session:
        payload = build_weekly_report(
            session,
            end_day=args.end,
            analyze=bool(getattr(args, "analyze", False)),
            analyze_tasks=getattr(args, "task", None) or None,
            force_analyze=bool(getattr(args, "force", False)),
        )
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"weekly_report_{payload.get('period')}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    else:
        out_path = None
    ameta = payload.get("assessments_meta") or {}
    print(
        json.dumps(
            {
                "status": "ok",
                "period": payload.get("period"),
                "schema_version": payload.get("schema_version"),
                "generator": payload.get("generator"),
                "article_count": payload.get("article_count"),
                "file": str(out_path) if out_path else None,
                "assessments_status": ameta.get("status"),
                "assessments_meta": ameta.get("meta"),
                "validation_ok": (payload.get("validation") or {}).get("ok"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_reports_monthly(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import ensure_schema, session_scope
    from gni.reports.monthly import build_monthly_report

    ensure_schema()
    with session_scope() as session:
        payload = build_monthly_report(
            session,
            month=args.month,
            analyze=bool(getattr(args, "analyze", False)),
            analyze_tasks=getattr(args, "task", None) or None,
            force_analyze=bool(getattr(args, "force", False)),
        )
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"monthly_report_{payload.get('period')}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    else:
        out_path = None
    ameta = payload.get("assessments_meta") or {}
    print(
        json.dumps(
            {
                "status": "ok",
                "period": payload.get("period"),
                "schema_version": payload.get("schema_version"),
                "generator": payload.get("generator"),
                "article_count": payload.get("article_count"),
                "file": str(out_path) if out_path else None,
                "assessments_status": ameta.get("status"),
                "assessments_meta": ameta.get("meta"),
                "validation_ok": (payload.get("validation") or {}).get("ok"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_api_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Run: pip install -e '.[api]'", file=sys.stderr)
        return 2
    uvicorn.run(
        "gni.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def cmd_metrics_run(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import ensure_schema, session_scope
    from gni.metrics.service import metric_run_to_dict, run_metrics

    ensure_schema()
    with session_scope() as session:
        run = run_metrics(
            session,
            days=args.days,
            country=args.country,
            source_id=args.source,
            target=args.target,
            timezone_name=args.timezone,
        )
        payload = metric_run_to_dict(run)
        status = run.status
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if status == "success" else 1


def cmd_metrics_snapshot(args: argparse.Namespace) -> int:
    from datetime import datetime, timedelta, timezone

    from gni.infrastructure.db import ensure_schema, session_scope
    from gni.metrics.service import run_v1_stat_snapshots

    ensure_schema()
    end = (
        datetime.fromisoformat(args.end)
        if args.end
        else datetime.now(timezone.utc)
    )
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if args.start:
        start = datetime.fromisoformat(args.start)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
    else:
        start = end - timedelta(days=args.days)

    with session_scope() as session:
        payload = run_v1_stat_snapshots(
            session,
            period_start=start,
            period_end=end,
            persist=not args.no_persist,
        )
    out = {k: v for k, v in payload.items() if k != "evidence_by_article"}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_analyze_run(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import ensure_schema, session_scope
    from gni.analysis.service import run_analysis

    ensure_schema()
    provider = args.provider
    with session_scope() as session:
        per_country = getattr(args, "per_country", None)
        # When capping per country, raise the default total limit so 5×10 is reachable.
        limit = None if args.article else args.limit
        if per_country and not args.article and args.limit == 20:
            limit = max(args.limit, per_country * 20)
        run = run_analysis(
            session,
            limit=limit,
            source_id=args.source,
            article_id=args.article,
            provider=provider,
            reanalyze=args.reanalyze,
            reanalyze_legacy=getattr(args, "reanalyze_legacy", False),
            per_country=per_country,
        )
        payload = {
            "run_id": run.id,
            "status": run.status,
            "provider": run.provider,
            "model_name": run.model_name,
            "schema_version": run.schema_version,
            "taxonomy_version": run.taxonomy_version,
            "relevance_weight_version": run.relevance_weight_version,
            "token_usage": run.token_usage,
            "estimated_cost_usd": run.estimated_cost_usd,
            "error": run.error,
            "stats": run.stats,
        }
        status = run.status
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if status in {"success", "partial", "budget_exhausted"} else 1


def cmd_ingest_health(_: argparse.Namespace) -> int:
    from sqlalchemy import select

    from gni.infrastructure.db import session_scope
    from gni.infrastructure.models import Source, SourceHealth

    with session_scope() as session:
        rows = session.execute(
            select(Source, SourceHealth)
            .outerjoin(SourceHealth, SourceHealth.source_id == Source.id)
            .order_by(Source.id)
        ).all()
        payload = []
        for source, health in rows:
            payload.append(
                {
                    "source_id": source.id,
                    "active_status": source.active_status,
                    "last_success_at": health.last_success_at.isoformat()
                    if health and health.last_success_at
                    else None,
                    "last_failure_at": health.last_failure_at.isoformat()
                    if health and health.last_failure_at
                    else None,
                    "success_count": health.success_count if health else 0,
                    "failure_count": health.failure_count if health else 0,
                    "success_rate": health.success_rate if health else None,
                    "error_message": health.error_message if health else None,
                }
            )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    parser = argparse.ArgumentParser(prog="gni", description="Global Narrative Intelligence CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_health = sub.add_parser("health", help="Print local health JSON")
    p_health.set_defaults(func=cmd_health)

    p_version = sub.add_parser("version", help="Print package version")
    p_version.set_defaults(func=cmd_version)

    p_db = sub.add_parser("db", help="Database commands")
    db_sub = p_db.add_subparsers(dest="db_command", required=True)
    p_up = db_sub.add_parser("upgrade", help="Run alembic upgrade head (PostgreSQL)")
    p_up.set_defaults(func=cmd_db_upgrade)
    p_init = db_sub.add_parser("init", help="Create tables via metadata (SQLite/local)")
    p_init.set_defaults(func=cmd_db_init)

    p_sources = sub.add_parser("sources", help="Source registry commands")
    sources_sub = p_sources.add_subparsers(dest="sources_command", required=True)
    p_seed = sources_sub.add_parser("seed", help="Seed countries/orgs/sources from YAML")
    p_seed.add_argument("--file", help="Path to sources_seed.yaml")
    p_seed.set_defaults(func=cmd_sources_seed)
    p_list = sources_sub.add_parser("list", help="List sources")
    p_list.add_argument("--active", action="store_true", help="Only active sources")
    p_list.set_defaults(func=cmd_sources_list)

    p_ingest = sub.add_parser("ingest", help="Ingestion commands")
    ingest_sub = p_ingest.add_subparsers(dest="ingest_command", required=True)
    p_run = ingest_sub.add_parser("run", help="Run ingestion once for active sources")
    p_run.add_argument("--source", help="Limit to one source_id")
    p_run.add_argument(
        "--once",
        action="store_true",
        default=True,
        help="Run a single batch (default; cron-friendly)",
    )
    p_run.add_argument(
        "--allow-partial",
        action="store_true",
        help="Exit 0 even if some sources fail",
    )
    p_run.set_defaults(func=cmd_ingest_run)
    p_ihealth = ingest_sub.add_parser("health", help="Show source_health rows")
    p_ihealth.set_defaults(func=cmd_ingest_health)

    p_process = sub.add_parser("process", help="P1-B article processing")
    process_sub = p_process.add_subparsers(dest="process_command", required=True)
    p_prun = process_sub.add_parser("run", help="Extract/clean/dedup/L1 for pending articles")
    p_prun.add_argument("--source", help="Limit to one source_id")
    p_prun.add_argument("--article", help="Process a single article id")
    p_prun.add_argument("--limit", type=int, default=50, help="Max articles (default 50)")
    p_prun.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Do not HTTP-fetch; use RSS stub text only (offline/dev)",
    )
    p_prun.add_argument(
        "--reprocess",
        action="store_true",
        help="Include already processed articles",
    )
    p_prun.add_argument(
        "--once",
        action="store_true",
        default=True,
        help="Single batch (default)",
    )
    p_prun.set_defaults(func=cmd_process_run)

    p_analyze = sub.add_parser("analyze", help="P1-C L2/L3 + relevance + six-dim analysis")
    analyze_sub = p_analyze.add_subparsers(dest="analyze_command", required=True)
    p_arun = analyze_sub.add_parser("run", help="Screen fulltext, extract spans, assess weight, analyze")
    p_arun.add_argument("--source", help="Limit to one source_id")
    p_arun.add_argument("--article", help="Analyze a single article id")
    p_arun.add_argument("--limit", type=int, default=20, help="Max articles (default 20)")
    p_arun.add_argument(
        "--per-country",
        type=int,
        default=None,
        metavar="N",
        help="Max articles per source country (e.g. 10 for trial); combines with --limit",
    )
    p_arun.add_argument(
        "--provider",
        choices=["heuristic", "deepseek"],
        default=None,
        help="Analyzer backend (default: heuristic unless GNI_LLM_API_KEY set with llm_provider)",
    )
    p_arun.add_argument(
        "--reanalyze",
        action="store_true",
        help="Include already analyzed articles",
    )
    p_arun.add_argument(
        "--reanalyze-legacy",
        action="store_true",
        help="Re-analyze only articles whose latest analysis is pre-V1.0 legacy schema",
    )
    p_arun.add_argument(
        "--once",
        action="store_true",
        default=True,
        help="Single batch (default)",
    )
    p_arun.set_defaults(func=cmd_analyze_run)

    p_metrics = sub.add_parser("metrics", help="P1-D research/weighted/ops metrics")
    metrics_sub = p_metrics.add_subparsers(dest="metrics_command", required=True)
    p_mrun = metrics_sub.add_parser("run", help="Compute metrics for a time window")
    p_mrun.add_argument("--days", type=int, default=7, help="Rolling window in days (default 7)")
    p_mrun.add_argument("--country", help="Country id filter (e.g. US)")
    p_mrun.add_argument("--source", help="Source id filter")
    p_mrun.add_argument("--target", default="china", help="Target scope (default china)")
    p_mrun.add_argument("--timezone", default="UTC", help="Display timezone label (data filtered in UTC)")
    p_mrun.set_defaults(func=cmd_metrics_run)

    p_msnap = metrics_sub.add_parser(
        "snapshot", help="Compute and persist V1.0 traceable stat_snapshots (methodology_v1.0)"
    )
    p_msnap.add_argument("--days", type=int, default=7, help="Rolling window in days (default 7)")
    p_msnap.add_argument("--start", help="ISO start datetime (UTC)")
    p_msnap.add_argument("--end", help="ISO end datetime (UTC)")
    p_msnap.add_argument(
        "--no-persist",
        action="store_true",
        help="Compute without writing stat_snapshots rows",
    )
    p_msnap.set_defaults(func=cmd_metrics_snapshot)

    p_events = sub.add_parser("events", help="Event Intelligence / fingerprint commands")
    events_sub = p_events.add_subparsers(dest="events_command", required=True)
    p_ereb = events_sub.add_parser(
        "rebuild", help="Rebuild events via fingerprint match"
    )
    p_ereb.add_argument("--min-articles", type=int, default=1, help="Min articles per cluster")
    p_ereb.add_argument("--limit", type=int, default=50, help="Max events to keep")
    p_ereb.add_argument(
        "--skip-extract",
        action="store_true",
        help="Skip writing new article_event_candidates (use existing / on-the-fly)",
    )
    p_ereb.set_defaults(func=cmd_events_rebuild)
    p_eext = events_sub.add_parser("extract", help="Extract event fingerprint candidates")
    p_eext.add_argument("--limit", type=int, default=500, help="Max articles to extract")
    p_eext.set_defaults(func=cmd_events_extract)

    p_reports = sub.add_parser("reports", help="Daily / weekly / monthly report generation")
    reports_sub = p_reports.add_subparsers(dest="reports_command", required=True)
    p_rdaily = reports_sub.add_parser(
        "daily", help="Build daily report JSON+Markdown (daily_report_schema_v4)"
    )
    p_rdaily.add_argument("--date", help="YYYY-MM-DD (Asia/Shanghai); default today")
    p_rdaily.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: ./data)",
    )
    p_rdaily.add_argument(
        "--polish",
        action="store_true",
        help="Optional LLM polish for narrative one-liners only (never changes numbers)",
    )
    p_rdaily.add_argument(
        "--analyze",
        action="store_true",
        help="Run LLM Intelligence Narrative Layer (with per-task DB caching)",
    )
    p_rdaily.add_argument(
        "--task",
        action="append",
        help="Run or retry only specific narrative task(s) (repeatable)",
    )
    p_rdaily.add_argument(
        "--force",
        action="store_true",
        help="Bypass task cache and regenerate LLM narrative tasks",
    )
    p_rdaily.set_defaults(func=cmd_reports_daily)

    p_rweekly = reports_sub.add_parser("weekly", help="Build weekly report with optional LLM analysis")
    p_rweekly.add_argument("--end", help="Week end date YYYY-MM-DD (report TZ)")
    p_rweekly.add_argument("--out-dir", default=None, help="Optional output directory for JSON")
    p_rweekly.add_argument("--analyze", action="store_true", help="Run LLM Intelligence Narrative Layer")
    p_rweekly.add_argument("--task", action="append", help="Run/retry specific narrative task(s)")
    p_rweekly.add_argument("--force", action="store_true", help="Bypass task cache")
    p_rweekly.set_defaults(func=cmd_reports_weekly)

    p_rmonthly = reports_sub.add_parser("monthly", help="Build monthly report with optional LLM analysis")
    p_rmonthly.add_argument("--month", help="YYYY-MM (report TZ)")
    p_rmonthly.add_argument("--out-dir", default=None, help="Optional output directory for JSON")
    p_rmonthly.add_argument("--analyze", action="store_true", help="Run LLM Intelligence Narrative Layer")
    p_rmonthly.add_argument("--task", action="append", help="Run/retry specific narrative task(s)")
    p_rmonthly.add_argument("--force", action="store_true", help="Bypass task cache")
    p_rmonthly.set_defaults(func=cmd_reports_monthly)

    p_alerts = sub.add_parser("alerts", help="Persisted A/B alert center")
    alerts_sub = p_alerts.add_subparsers(dest="alerts_command", required=True)
    p_arun_alerts = alerts_sub.add_parser("run", help="Run rule engine upsert by dedupe_key")
    p_arun_alerts.set_defaults(func=cmd_alerts_run)

    p_search = sub.add_parser("search", help="Search index (Meilisearch)")
    search_sub = p_search.add_subparsers(dest="search_command", required=True)
    p_sre = search_sub.add_parser("reindex", help="Full rebuild of Meili article/event indexes")
    p_sre.set_defaults(func=cmd_search_reindex)

    p_api = sub.add_parser("api", help="HTTP API for React UI")
    api_sub = p_api.add_subparsers(dest="api_command", required=True)
    p_aserve = api_sub.add_parser("serve", help="Run FastAPI (uvicorn)")
    p_aserve.add_argument("--host", default="127.0.0.1")
    p_aserve.add_argument("--port", type=int, default=8000)
    p_aserve.add_argument("--reload", action="store_true")
    p_aserve.set_defaults(func=cmd_api_serve)

    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()

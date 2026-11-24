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


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Launch Streamlit dashboard (requires optional [dashboard] extra)."""
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print(
            "Streamlit not installed. Run: pip install -e '.[dashboard]'",
            file=sys.stderr,
        )
        return 2
    app = Path(__file__).resolve().parent / "dashboard" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app),
        "--server.headless",
        "true",
    ]
    if args.port:
        cmd.extend(["--server.port", str(args.port)])
    return subprocess.run(cmd, check=False).returncode


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


def cmd_analyze_run(args: argparse.Namespace) -> int:
    from gni.infrastructure.db import ensure_schema, session_scope
    from gni.analysis.service import run_analysis

    ensure_schema()
    provider = args.provider
    with session_scope() as session:
        run = run_analysis(
            session,
            limit=None if args.article else args.limit,
            source_id=args.source,
            article_id=args.article,
            provider=provider,
            reanalyze=args.reanalyze,
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

    p_dash = sub.add_parser("dashboard", help="Launch Streamlit dashboard (P1-E)")
    p_dash.add_argument("--port", type=int, default=8501, help="Server port (default 8501)")
    p_dash.set_defaults(func=cmd_dashboard)

    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()

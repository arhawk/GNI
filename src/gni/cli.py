"""Minimal CLI entrypoint for health checks (Phase 0)."""

from __future__ import annotations

import argparse
import json

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
        "note": "Phase 0 skeleton — no live ingestion or LLM calls",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    parser = argparse.ArgumentParser(prog="gni", description="Global Narrative Intelligence CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_health = sub.add_parser("health", help="Print local health JSON (no network)")
    p_health.set_defaults(func=cmd_health)

    p_version = sub.add_parser("version", help="Print package version")
    p_version.set_defaults(func=cmd_version)

    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()

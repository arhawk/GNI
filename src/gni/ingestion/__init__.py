"""Ingestion adapters and orchestration."""

from gni.ingestion.base import BaseAdapter
from gni.ingestion.rss_adapter import RssAdapter, parse_feed_xml
from gni.ingestion.service import get_adapter, ingest_source, run_ingestion, upsert_article

__all__ = [
    "BaseAdapter",
    "RssAdapter",
    "parse_feed_xml",
    "get_adapter",
    "ingest_source",
    "run_ingestion",
    "upsert_article",
]

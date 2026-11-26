def test_package_version():
    import gni

    assert gni.__version__ == "0.1.7"


def test_core_and_interfaces_importable():
    from gni.analysis.provider import BaseLLMProvider, NullLLMProvider
    from gni.core import get_settings, setup_logging
    from gni.core.contracts import (
        ArticleIntelligenceContract,
        EventIntelligenceContract,
        EvidencePackageContract,
        MetricSnapshotContract,
        NarrativeIntelligenceContract,
        ReportPackageContract,
        SignalRecordContract,
    )
    from gni.ingestion.base import BaseAdapter

    assert get_settings is not None
    setup_logging("INFO")
    assert issubclass(NullLLMProvider, BaseLLMProvider)
    assert hasattr(BaseAdapter, "fetch")
    assert all(
        c is not None
        for c in (
            ArticleIntelligenceContract,
            EventIntelligenceContract,
            NarrativeIntelligenceContract,
            MetricSnapshotContract,
            SignalRecordContract,
            EvidencePackageContract,
            ReportPackageContract,
        )
    )


def test_layer_dependency_direction():
    """Lower layers must never import upper layers (reports / api / dashboard)."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src" / "gni"
    lower_packages = ("core", "infrastructure", "ingestion", "processing", "analysis", "metrics", "events")
    forbidden_prefixes = ("gni.reports", "gni.api", "gni.dashboard")
    violations: list[str] = []

    for pkg in lower_packages:
        for py in (root / pkg).rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(forbidden_prefixes):
                            violations.append(f"{py.relative_to(root)} -> {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith(forbidden_prefixes):
                        violations.append(f"{py.relative_to(root)} -> {node.module}")

    # Known pre-Phase-4 legacy coupling (overview_payload in events/service.py); no new inversions allowed.
    known_legacy = {"events/service.py -> gni.dashboard.data"}
    unexpected = [v for v in violations if v not in known_legacy]
    assert not unexpected, f"Layer dependency violations: {unexpected}"

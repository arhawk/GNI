def test_package_version():
    import gni

    assert gni.__version__ == "0.1.4"


def test_core_and_interfaces_importable():
    from gni.analysis.provider import BaseLLMProvider, NullLLMProvider
    from gni.core import get_settings, setup_logging
    from gni.ingestion.base import BaseAdapter

    assert get_settings is not None
    setup_logging("INFO")
    assert issubclass(NullLLMProvider, BaseLLMProvider)
    assert hasattr(BaseAdapter, "fetch")

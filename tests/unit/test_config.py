from gni.core.config import Settings, get_settings


def test_settings_defaults():
    s = Settings(llm_api_key="")  # type: ignore[call-arg]
    assert s.env == "dev"
    assert s.timezone == "UTC"
    assert s.llm_provider == "deepseek"
    assert s.daily_article_limit == 500


def test_get_settings_cached():
    get_settings.cache_clear()
    a = get_settings()
    b = get_settings()
    assert a is b
    get_settings.cache_clear()

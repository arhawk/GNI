from datetime import datetime, timedelta, timezone

import pytest

from gni.dashboard.data import DashboardFilters, resolve_filter_window, window_bounds


def test_window_bounds_rolling():
    start, end = window_bounds(30)
    assert end > start
    assert (end - start).days == 30


def test_window_bounds_explicit_historical():
    end = datetime(2026, 6, 1, tzinfo=timezone.utc)
    start = end - timedelta(days=7)
    s, e = window_bounds(30, window_start=start, window_end=end)
    assert s == start
    assert e == end


def test_window_bounds_rejects_inverted():
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    start = end + timedelta(days=1)
    with pytest.raises(ValueError):
        window_bounds(7, window_start=start, window_end=end)


def test_resolve_filter_window_uses_explicit():
    end = datetime(2026, 11, 1, tzinfo=timezone.utc)
    start = end - timedelta(days=90)
    f = DashboardFilters(days=30, window_start=start, window_end=end)
    s, e = resolve_filter_window(f)
    assert (e - s).days == 90

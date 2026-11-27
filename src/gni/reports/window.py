"""Unified Report Time Window Resolver (Task 3A).

Guarantees:
- Single source of truth for Daily, Weekly (rolling_7d), and Monthly (calendar_month / rolling_30d).
- Consistent half-open [start, end) boundaries in report timezone (default Asia/Shanghai).
- Fair mid-month comparison: when a calendar month is still in progress (now < end),
  marks is_partial_period=True and aligns the previous comparison window to equal-length
  month-to-date (MTD) days in the prior month (properly handling month-end and leap years).
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from gni.core.config import get_settings


def report_tz(tz_name: str | None = None) -> ZoneInfo:
    name = tz_name or get_settings().report_timezone or "Asia/Shanghai"
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001
        return ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class ReportWindowSpec:
    report_type: str
    period: str
    window_mode: str  # calendar_day | rolling_7d | calendar_month | rolling_30d
    timezone: str
    start: datetime
    end: datetime
    prev_start: datetime
    prev_end: datetime
    is_partial_period: bool = False
    elapsed_days: int = 0
    total_days: int = 0
    comparable_prev_start: datetime | None = None
    comparable_prev_end: datetime | None = None
    comparison_note: str = ""

    @property
    def effective_prev_start(self) -> datetime:
        return self.comparable_prev_start or self.prev_start

    @property
    def effective_prev_end(self) -> datetime:
        return self.comparable_prev_end or self.prev_end

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": self.report_type,
            "period": self.period,
            "window_mode": self.window_mode,
            "timezone": self.timezone,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "boundary_rule": "[start, end)",
            "prev_start": self.effective_prev_start.isoformat(),
            "prev_end": self.effective_prev_end.isoformat(),
            "full_prev_start": self.prev_start.isoformat(),
            "full_prev_end": self.prev_end.isoformat(),
            "is_partial_period": self.is_partial_period,
            "elapsed_days": self.elapsed_days,
            "total_days": self.total_days,
            "comparison_note": self.comparison_note,
        }


def resolve_daily_window(
    day: str | date | None = None,
    *,
    tz_name: str | None = None,
    now: datetime | None = None,
) -> ReportWindowSpec:
    tz = report_tz(tz_name)
    now_local = (now.astimezone(tz) if now else datetime.now(tz))
    if isinstance(day, date):
        d = day
    elif isinstance(day, str) and day.strip():
        d = date.fromisoformat(day.strip()[:10])
    else:
        d = now_local.date()
    start = datetime(d.year, d.month, d.day, tzinfo=tz)
    end = start + timedelta(days=1)
    prev_start = start - timedelta(days=1)
    prev_end = start
    is_partial = now_local < end and now_local >= start
    return ReportWindowSpec(
        report_type="daily",
        period=d.isoformat(),
        window_mode="calendar_day",
        timezone=str(tz),
        start=start,
        end=end,
        prev_start=prev_start,
        prev_end=prev_end,
        is_partial_period=is_partial,
        elapsed_days=1,
        total_days=1,
        comparison_note="自然日 [00:00, 次日 00:00) 环比前一日",
    )


def resolve_weekly_window(
    end_day: str | date | None = None,
    *,
    tz_name: str | None = None,
    now: datetime | None = None,
) -> ReportWindowSpec:
    tz = report_tz(tz_name)
    now_local = (now.astimezone(tz) if now else datetime.now(tz))
    if isinstance(end_day, date):
        ed = end_day
    elif isinstance(end_day, str) and end_day.strip():
        ed = date.fromisoformat(end_day.strip()[:10])
    else:
        ed = now_local.date()
    start_date = ed - timedelta(days=6)
    start = datetime(start_date.year, start_date.month, start_date.day, tzinfo=tz)
    end = datetime(ed.year, ed.month, ed.day, tzinfo=tz) + timedelta(days=1)
    prev_end = start
    prev_start = prev_end - timedelta(days=7)
    is_partial = now_local < end and now_local >= start
    return ReportWindowSpec(
        report_type="weekly",
        period=f"{start_date.isoformat()}_{ed.isoformat()}",
        window_mode="rolling_7d",
        timezone=str(tz),
        start=start,
        end=end,
        prev_start=prev_start,
        prev_end=prev_end,
        is_partial_period=is_partial,
        elapsed_days=7,
        total_days=7,
        comparison_note="滚动 7 个自然日（等长环比前 7 日）",
    )


def resolve_monthly_window(
    month: str | date | None = None,
    *,
    end_day: str | date | None = None,
    tz_name: str | None = None,
    now: datetime | None = None,
) -> ReportWindowSpec:
    tz = report_tz(tz_name)
    now_local = (now.astimezone(tz) if now else datetime.now(tz))
    if end_day is not None:
        ed = end_day if isinstance(end_day, date) else date.fromisoformat(str(end_day).strip()[:10])
        end = datetime(ed.year, ed.month, ed.day, tzinfo=tz) + timedelta(days=1)
        start = end - timedelta(days=30)
        prev_end = start
        prev_start = prev_end - timedelta(days=30)
        period = f"{(ed - timedelta(days=29)).isoformat()}_{ed.isoformat()}"
        is_partial = now_local < end and now_local >= start
        return ReportWindowSpec(
            report_type="monthly",
            period=period,
            window_mode="rolling_30d",
            timezone=str(tz),
            start=start,
            end=end,
            prev_start=prev_start,
            prev_end=prev_end,
            is_partial_period=is_partial,
            elapsed_days=30,
            total_days=30,
            comparison_note="滚动 30 个自然日（等长环比前 30 日）",
        )

    if isinstance(month, date):
        y, m = month.year, month.month
    elif isinstance(month, str) and month.strip():
        y, m = (int(x) for x in month.strip().split("-")[:2])
    else:
        today = now_local.date()
        y, m = today.year, today.month

    total_days = monthrange(y, m)[1]
    start = datetime(y, m, 1, tzinfo=tz)
    end = datetime(y, m, total_days, tzinfo=tz) + timedelta(days=1)
    py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
    prev_total_days = monthrange(py, pm)[1]
    prev_start = datetime(py, pm, 1, tzinfo=tz)
    prev_end = datetime(py, pm, prev_total_days, tzinfo=tz) + timedelta(days=1)

    is_partial = start <= now_local < end
    if is_partial:
        elapsed_days = max(1, min(total_days, (now_local.date() - date(y, m, 1)).days + 1))
        comp_days = min(elapsed_days, prev_total_days)
        comp_prev_start = prev_start
        comp_prev_end = prev_start + timedelta(days=comp_days)
        note = (
            f"暂定月报（MTD 截至 {now_local.date().isoformat()}，已过 {elapsed_days}/{total_days} 天）；"
            f"环比采用上月同期前 {comp_days} 天公平对比"
        )
    else:
        elapsed_days = total_days
        comp_prev_start = prev_start
        comp_prev_end = prev_end
        note = f"完整自然月（{total_days} 天）环比上个完整自然月（{prev_total_days} 天）"

    return ReportWindowSpec(
        report_type="monthly",
        period=f"{y:04d}-{m:02d}",
        window_mode="calendar_month",
        timezone=str(tz),
        start=start,
        end=end,
        prev_start=prev_start,
        prev_end=prev_end,
        is_partial_period=is_partial,
        elapsed_days=elapsed_days,
        total_days=total_days,
        comparable_prev_start=comp_prev_start,
        comparable_prev_end=comp_prev_end,
        comparison_note=note,
    )


def in_half_open_window(ts: datetime | None, start: datetime, end: datetime) -> bool:
    """True iff ts falls in [start, end) after normalizing naive timestamps as UTC."""
    if ts is None:
        return False
    aware = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return start <= aware.astimezone(start.tzinfo) < end


def resolve_display_event_time(
    actual: datetime | None,
    published_times: list[datetime | None],
) -> tuple[datetime | None, str | None]:
    """Display time for report events: actual event time first, else earliest publish time (Proxy Event Time).

    Returns (display_time, basis) where basis is "actual", "proxy_published_at", or None when unknown.
    """
    if actual is not None:
        aware_actual = actual if actual.tzinfo is not None else actual.replace(tzinfo=timezone.utc)
        return aware_actual, "actual"
    pubs = [
        p if p.tzinfo is not None else p.replace(tzinfo=timezone.utc)
        for p in published_times
        if p is not None
    ]
    if pubs:
        return min(pubs), "proxy_published_at"
    return None, None

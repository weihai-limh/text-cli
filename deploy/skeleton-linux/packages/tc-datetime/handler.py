"""
tc-datetime handler — Date/time calculator for path pipelines.

Zero external dependencies. Pure stdlib datetime + calendar.
Solves date arithmetic that AI models are brittle at (leap years, month boundaries).

Directives:
    tc-datetime;now[,<format>]             — current time
    tc-datetime;offset,<date>,<JSON>       — add/subtract time
    tc-datetime;between,<a>,<b>,<unit>     — duration between dates
    tc-datetime;weekday,<date>             — day of week
    tc-datetime;range,<start>,<JSON>       — date sequence
    tc-datetime;format,<date>,<to_fmt>     — format conversion
"""
import calendar
import json
import logging
from datetime import datetime, timezone, timedelta

from core.registry import directive

logger = logging.getLogger(__name__)

_WEEKDAYS_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
_WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def init_tc_datetime_handler():
    logger.info("tc-datetime initialised")

def _now() -> datetime:
    return datetime.now().astimezone()

def _parse_date(s: str) -> datetime:
    s = s.strip()
    if s.lstrip("-").isdigit():
        try:
            return datetime.fromtimestamp(float(s)).astimezone()
        except (ValueError, OSError):
            pass
    for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_now().tzinfo)
            return dt
        except ValueError:
            continue
    raise ValueError(f"cannot parse date: {s}")

def _parse_json_params(params: list[str], start_idx: int = 1) -> dict:
    if len(params) <= start_idx:
        raise ValueError("missing JSON parameter")
    direct = params[start_idx]
    try:
        return json.loads(direct)
    except json.JSONDecodeError:
        pass
    joined = ",".join(params[start_idx:])
    return json.loads(joined)

def _add_months(d: datetime, months: int) -> datetime:
    total_months = d.year * 12 + d.month - 1 + months
    year, month = divmod(total_months, 12)
    month += 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(d.day, max_day)
    return d.replace(year=year, month=month, day=day)

def _format_human(d: datetime) -> str:
    return f"{d.year}年{d.month}月{d.day}日 {_WEEKDAYS_CN[d.weekday()]} {d.strftime('%H:%M')}"

def _format_human_en(d: datetime) -> str:
    return f"{_WEEKDAYS_EN[d.weekday()]}, {d.strftime('%B')} {d.day}, {d.year}"

@directive("tc-datetime", "now", domain_alias="日期时间", action_aliases={"now": "现在"})
def tc_datetime_now(params: list[str]) -> dict:
    fmt = params[0].strip().lower() if params else "iso"
    now = _now()
    ts = int(now.timestamp())
    tz_str = now.strftime("%z")

    if fmt == "timestamp":
        result = str(ts)
    elif fmt == "date":
        result = now.strftime("%Y-%m-%d")
    elif fmt == "human":
        result = _format_human(now)
    else:
        result = now.isoformat(timespec="seconds")

    return {
        "status": "ok",
        "result": result,
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": ts,
        "timezone": f"{tz_str[:3]}:{tz_str[3:]}" if len(tz_str) >= 5 else tz_str,
    }

@directive("tc-datetime", "offset", domain_alias="日期时间", action_aliases={"offset": "偏移"})
def tc_datetime_offset(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-datetime;offset,<date>,<JSON>"}

    try:
        dt = _parse_date(params[0])
        offset = _parse_json_params(params)
    except (ValueError, json.JSONDecodeError) as e:
        return {"status": "error", "reason": str(e)}

    days = offset.get("days", 0) or 0
    weeks = offset.get("weeks", 0) or 0
    months = offset.get("months", 0) or 0
    years = offset.get("years", 0) or 0
    hours = offset.get("hours", 0) or 0
    minutes = offset.get("minutes", 0) or 0

    total_days = days + weeks * 7
    if months:
        dt = _add_months(dt, months)
    if years:
        dt = _add_months(dt, years * 12)
    if total_days or hours or minutes:
        dt = dt + timedelta(days=total_days, hours=hours, minutes=minutes)

    result_date = dt.strftime("%Y-%m-%d")
    return {
        "status": "ok",
        "input": params[0],
        "offset": {k: v for k, v in offset.items() if v},
        "result": result_date,
        "weekday": _WEEKDAYS_CN[dt.weekday()],
    }

_UNITS = {
    "days": 86400,
    "hours": 3600,
    "minutes": 60,
    "seconds": 1,
}

@directive("tc-datetime", "between", domain_alias="日期时间", action_aliases={"between": "间距"})
def tc_datetime_between(params: list[str]) -> dict:
    if len(params) < 3:
        return {"status": "error", "reason": "Usage: tc-datetime;between,<a>,<b>,<unit>"}

    try:
        a = _parse_date(params[0])
        b = _parse_date(params[1])
    except ValueError as e:
        return {"status": "error", "reason": str(e)}

    unit = params[2].strip().lower()
    delta = b - a
    total_seconds = delta.total_seconds()

    if unit == "human":
        abs_sec = abs(total_seconds)
        total_days = int(abs_sec // 86400)
        months = total_days // 30
        remain_days = total_days % 30
        if months > 0:
            result = f"{months}个月{remain_days}天" if remain_days else f"{months}个月"
        else:
            result = f"{total_days}天"
        if total_seconds < 0:
            result = f"-{result}"
    elif unit in _UNITS:
        result = round(total_seconds / _UNITS[unit], 2)
        if unit in ("days", "hours", "minutes") and result == int(result):
            result = int(result)
    else:
        return {"status": "error", "reason": f"unknown unit: {unit}. Use days/hours/minutes/seconds/human"}

    return {
        "status": "ok",
        "from": params[0],
        "to": params[1],
        "unit": unit,
        "result": result,
    }

@directive("tc-datetime", "weekday", domain_alias="日期时间", action_aliases={"weekday": "星期几"})
def tc_datetime_weekday(params: list[str]) -> dict:
    if not params:
        return {"status": "error", "reason": "Usage: tc-datetime;weekday,<date>"}

    try:
        dt = _parse_date(params[0])
    except ValueError as e:
        return {"status": "error", "reason": str(e)}

    wd = dt.weekday()
    return {
        "status": "ok",
        "date": dt.strftime("%Y-%m-%d"),
        "weekday": _WEEKDAYS_CN[wd],
        "weekday_en": _WEEKDAYS_EN[wd],
        "weekday_num": wd,
        "is_weekend": wd >= 5,
    }

@directive("tc-datetime", "range", domain_alias="日期时间", action_aliases={"range": "序列"})
def tc_datetime_range(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-datetime;range,<start_date>,<JSON>"}

    try:
        start = _parse_date(params[0])
        query = _parse_json_params(params)
    except (ValueError, json.JSONDecodeError) as e:
        return {"status": "error", "reason": str(e)}

    step = int(query.get("step", 1))
    out_fmt = query.get("format", "date")

    dates = []

    if "until" in query:
        try:
            end = _parse_date(query["until"])
        except ValueError as e:
            return {"status": "error", "reason": str(e)}
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=step)
        end_val = end
    else:
        days = query.get("days", 0) or 0
        weeks = query.get("weeks", 0) or 0
        total = days + weeks * 7
        if total <= 0:
            return {"status": "error", "reason": "specify days/weeks/until"}
        end_val = start + timedelta(days=total)
        for i in range(total + 1):
            if i % step == 0:
                dates.append(start + timedelta(days=i))

    formatted = []
    for d in dates:
        if out_fmt == "iso":
            formatted.append(d.isoformat(timespec="seconds"))
        elif out_fmt == "human":
            formatted.append(_format_human(d))
        else:
            formatted.append(d.strftime("%Y-%m-%d"))

    return {
        "status": "ok",
        "start": start.strftime("%Y-%m-%d"),
        "end": dates[-1].strftime("%Y-%m-%d") if dates else "",
        "dates": formatted,
        "count": len(formatted),
    }

@directive("tc-datetime", "format", domain_alias="日期时间", action_aliases={"format": "格式化"})
def tc_datetime_format(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-datetime;format,<date_or_ts>,<to_format>"}

    try:
        dt = _parse_date(params[0])
    except ValueError as e:
        return {"status": "error", "reason": str(e)}

    to_fmt = params[1].strip()
    if to_fmt == "iso":
        result = dt.isoformat(timespec="seconds")
    elif to_fmt == "date":
        result = dt.strftime("%Y-%m-%d")
    elif to_fmt == "timestamp":
        result = int(dt.timestamp())
    elif to_fmt == "human":
        result = _format_human(dt)
    elif to_fmt == "human_en":
        result = _format_human_en(dt)
    else:
        return {"status": "error", "reason": f"unknown format: {to_fmt}. Use iso/date/timestamp/human/human_en"}

    return {
        "status": "ok",
        "input": params[0],
        "format": to_fmt,
        "result": result,
    }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""不依赖任何网络接口的日期类信息计算，作为 60s 摸鱼日报接口的兜底。

输出结构与 60s `/v2/moyu` 的 data 字段保持一致，便于无缝替换。
"""
import calendar
import datetime

from lunar import solar_to_lunar

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 公历固定节假日
FIXED_HOLIDAYS = [(1, 1, "元旦"), (5, 1, "劳动节"), (10, 1, "国庆节")]


def _pct(passed, total):
    return int(round(passed / total * 100)) if total else 0


def _prog(passed, total):
    return {
        "passed": passed,
        "total": total,
        "remaining": total - passed,
        "percentage": _pct(passed, total),
    }


def _nth_weekday(year, month, nth):
    """该月第 nth 个星期一（nth 从 1 开始）。"""
    c = calendar.Calendar()
    mondays = [d for d in c.itermonthdates(year, month)
               if d.month == month and d.weekday() == 0]
    return mondays[nth - 1]


def _lunar_date_of(year, month, lunar_month, lunar_day):
    """反查某农历月日对应的公历日期（只在目标年前后一年内搜索）。"""
    d = datetime.date(year, 1, 1)
    end = datetime.date(year + 1, 1, 31)
    while d <= end:
        info = solar_to_lunar(d)
        if (info["year"] == year and info["month"] == lunar_month
                and info["day"] == lunar_day and not info["is_leap"]):
            return d
        d += datetime.timedelta(days=1)
    return None


def holidays_of(year):
    """返回该年的主要法定节假日 [(date, name)]，按日期排序。"""
    out = []
    for m, d, name in FIXED_HOLIDAYS:
        out.append((datetime.date(year, m, d), name))

    for lm, ld, name in [(1, 1, "春节"), (5, 5, "端午节"), (8, 15, "中秋节")]:
        dt = _lunar_date_of(year, year, lm, ld)
        if dt:
            out.append((dt, name))

    # 清明 = 清明节气当天
    d = datetime.date(year, 4, 1)
    while d.month == 4:
        if solar_to_lunar(d)["solar_term"] == "清明":
            out.append((d, "清明节"))
            break
        d += datetime.timedelta(days=1)

    out.sort(key=lambda x: x[0])
    return out


def _weekend_of(date):
    """本周周末（周六）及其后最近的一个周末。"""
    sat = date + datetime.timedelta(days=(5 - date.weekday()) % 7)
    if sat < date:
        sat += datetime.timedelta(days=7)
    return sat


def build(date=None, city="潍坊"):
    """生成与 60s moyu.data 同构的本地数据。"""
    if date is None:
        date = datetime.date.today()

    lun = solar_to_lunar(date)
    year = date.year

    week_passed = date.weekday() + 1
    days_in_month = calendar.monthrange(year, date.month)[1]
    days_in_year = 366 if calendar.isleap(year) else 365
    day_of_year = date.timetuple().tm_yday

    today_term = lun["solar_term"]

    # 今日是否为节假日（法定假日当天）
    hol = {d: n for d, n in holidays_of(year)}
    is_holiday = date in hol
    holiday_name = hol.get(date)

    # 下一个节假日
    upcoming = [(d, n) for d, n in holidays_of(year) if d > date]
    if not upcoming:
        upcoming = [(d, n) for d, n in holidays_of(year + 1) if d > date]
    next_holiday = None
    if upcoming:
        d, n = upcoming[0]
        next_holiday = {
            "name": n,
            "date": d.isoformat(),
            "until": (d - date).days,
            "duration": 1,
        }

    sat = _weekend_of(date)

    return {
        "date": {
            "gregorian": date.isoformat(),
            "weekday": WEEKDAYS[date.weekday()],
            "dayOfWeek": date.weekday() + 1,
            "lunar": {
                "year": lun["year"],
                "month": lun["month"],
                "day": lun["day"],
                "yearCN": "".join("零一二三四五六七八九"[int(c)] for c in str(lun["year"])),
                "monthCN": lun["month_name"],
                "dayCN": lun["day_name"],
                "isLeapMonth": lun["is_leap"],
                "yearGanZhi": lun["ganzhi_year"],
                "zodiac": lun["animal"],
            },
        },
        "today": {
            "isWeekend": date.weekday() >= 5,
            "isHoliday": is_holiday,
            "isWorkday": not (date.weekday() >= 5 or is_holiday),
            "holidayName": holiday_name,
            "solarTerm": today_term,
            "lunarFestivals": [],
        },
        "progress": {
            "week": _prog(week_passed, 7),
            "month": _prog(date.day, days_in_month),
            "year": _prog(day_of_year, days_in_year),
        },
        "currentHoliday": holiday_name if is_holiday else None,
        "nextHoliday": next_holiday,
        "nextWeekend": {
            "date": sat.isoformat(),
            "weekday": WEEKDAYS[sat.weekday()],
            "daysUntil": (sat - date).days,
        },
        "countdown": {
            "toWeekEnd": (sat - date).days,
            "toFriday": (4 - date.weekday()) % 7,
            "toMonthEnd": days_in_month - date.day,
            "toYearEnd": days_in_year - day_of_year,
        },
        "moyuQuote": None,
        "_source": "local",
        "_city": city,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build(), ensure_ascii=False, indent=2))

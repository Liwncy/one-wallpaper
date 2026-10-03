#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""农历换算（1900-2100）本地兜底实现，用于 60s 农历接口不可用时。

数据表 lunarInfo 为业界通用压缩表，每年一个整数：
  低 4 位  = 闰月月份（0 表示无闰月）
  5-16 位  = 1-12 月的大小月（1 = 大月 30 天，0 = 小月 29 天）
  17-20 位 = 闰月天数（1 = 30 天，0 = 29 天）
"""

lunar_info = [
    0x04bd8, 0x04ae0, 0x0a570, 0x054d5, 0x0d260, 0x0d950, 0x16554, 0x056a0, 0x09ad0, 0x055d2,
    0x04ae0, 0x0a5b6, 0x0a4d0, 0x0d250, 0x1d255, 0x0b540, 0x0d6a0, 0x0ada2, 0x095b0, 0x14977,
    0x04970, 0x0a4b0, 0x0b4b5, 0x06a50, 0x06d40, 0x1ab54, 0x02b60, 0x09570, 0x052f2, 0x04970,
    0x06566, 0x0d4a0, 0x0ea50, 0x06e95, 0x05ad0, 0x02b60, 0x186e3, 0x092e0, 0x1c8d7, 0x0c950,
    0x0d4a0, 0x1d8a6, 0x0b550, 0x056a0, 0x1a5b4, 0x025d0, 0x092d0, 0x0d2b2, 0x0a950, 0x0b557,
    0x06ca0, 0x0b550, 0x15355, 0x04da0, 0x0a5b0, 0x14573, 0x052b0, 0x0a9a8, 0x0e950, 0x06aa0,
    0x0aea6, 0x0ab50, 0x04b60, 0x0aae4, 0x0a570, 0x05260, 0x0f263, 0x0d950, 0x05b57, 0x056a0,
    0x096d0, 0x04dd5, 0x04ad0, 0x0a4d0, 0x0d4d4, 0x0d250, 0x0d558, 0x0b540, 0x0b6a0, 0x195a6,
    0x095b0, 0x049b0, 0x0a974, 0x0a4b0, 0x0b27a, 0x06a50, 0x06d40, 0x0af46, 0x0ab60, 0x09570,
    0x04af5, 0x04970, 0x064b0, 0x074a3, 0x0ea50, 0x06b58, 0x055c0, 0x0ab60, 0x096d5, 0x092e0,
    0x0c960, 0x0d954, 0x0d4a0, 0x0da50, 0x07552, 0x056a0, 0x0abb7, 0x025d0, 0x092d0, 0x0cab5,
    0x0a950, 0x0b4a0, 0x0baa4, 0x0ad50, 0x055d9, 0x04ba0, 0x0a5b0, 0x15176, 0x052b0, 0x0a930,
    0x07954, 0x06aa0, 0x0ad50, 0x05b52, 0x04b60, 0x0a6e6, 0x0a4e0, 0x0d260, 0x0ea65, 0x0d530,
    0x05aa0, 0x076a3, 0x096d0, 0x04afb, 0x04ad0, 0x0a4d0, 0x1d0b6, 0x0d250, 0x0d520, 0x0dd45,
    0x0b5a0, 0x056d0, 0x055b2, 0x049b0, 0x0a577, 0x0a4b0, 0x0aa50, 0x1b255, 0x06d20, 0x0ada0,
    0x14b63, 0x09370, 0x049f8, 0x04970, 0x064b0, 0x168a6, 0x0ea50, 0x06b20, 0x1a6c4, 0x0aae0,
    0x0a2e0, 0x0d2e3, 0x0c960, 0x0d557, 0x0d4a0, 0x0da50, 0x05d55, 0x056a0, 0x0a6d0, 0x055d4,
    0x052d0, 0x0a9b8, 0x0a950, 0x0b4a0, 0x0b6a6, 0x0ad50, 0x055a0, 0x0aba4, 0x0a5b0, 0x052b0,
    0x0b273, 0x06930, 0x07337, 0x06aa0, 0x0ad50, 0x14b55, 0x04b60, 0x0a570, 0x054e4, 0x0d160,
    0x0e968, 0x0d520, 0x0daa0, 0x16aa6, 0x056d0, 0x04ae0, 0x0a9d4, 0x0a2d0, 0x0d150, 0x0f252,
    0x0d520,
]

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
ANIMALS = "鼠牛虎兔龙蛇马羊猴鸡狗猪"
MONTHS = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]
DAY_TENS = ["初", "十", "廿", "卅"]
DAY_UNITS = "一二三四五六七八九十"
SOLAR_TERMS = [
    "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满",
    "芒种", "夏至", "小暑", "大暑", "立秋", "处暑", "白露", "秋分", "寒露", "霜降",
    "立冬", "小雪", "大雪", "冬至",
]

_BASE = None  # 1900-01-31 为农历 1900 年正月初一


def _base_date():
    import datetime
    return datetime.date(1900, 1, 31)


def leap_month(year):
    """返回该农历年的闰月月份，0 表示无闰月。"""
    return lunar_info[year - 1900] & 0xF


def leap_days(year):
    """返回该农历年闰月的天数，无闰月返回 0。"""
    if leap_month(year):
        return 30 if (lunar_info[year - 1900] & 0x10000) else 29
    return 0


def month_days(year, month):
    """返回该农历年第 month 个月（非闰月）的天数。"""
    return 30 if (lunar_info[year - 1900] & (0x10000 >> month)) else 29


def year_days(year):
    total = 348
    mask = 0x8000
    for _ in range(12):
        if lunar_info[year - 1900] & mask:
            total += 1
        mask >>= 1
    return total + leap_days(year)


def _gz(offset):
    return GAN[offset % 10] + ZHI[offset % 12]


def solar_to_lunar(date):
    """公历 date → 农历 dict。"""
    import datetime
    offset = (date - _base_date()).days
    if offset < 0:
        raise ValueError("仅支持 1900-01-31 之后的日期")

    year = 1900
    while year <= 2100:
        d = year_days(year)
        if offset < d:
            break
        offset -= d
        year += 1
    else:
        raise ValueError("超出 1900-2100 范围")

    is_leap = False
    month = 1
    while True:
        d = leap_days(year) if is_leap else month_days(year, month)
        if offset < d:
            break
        offset -= d
        if is_leap:
            is_leap = False
            month += 1
        elif leap_month(year) == month:
            is_leap = True
        else:
            month += 1

    day = offset + 1
    month_name = ("闰" if is_leap else "") + MONTHS[month - 1] + "月"

    if day <= 10:
        day_name = DAY_TENS[0] + (DAY_UNITS[day - 1] if day != 10 else "十")
    elif day < 20:
        day_name = DAY_TENS[1] + DAY_UNITS[day - 11]
    elif day == 20:
        day_name = DAY_TENS[2] + "十"
    elif day < 30:
        day_name = DAY_TENS[2] + DAY_UNITS[day - 21]
    else:
        day_name = DAY_TENS[3] + "十"

    term = _solar_term(date)
    return {
        "year": year,
        "month": month,
        "month_name": month_name,
        "day": day,
        "day_name": day_name,
        "text": f"{month_name}{day_name}",
        "long": f"{_gz(year - 1900 + 36)}年 {month_name}{day_name}",
        "ganzhi_year": _gz(year - 1900 + 36),
        "animal": ANIMALS[(year - 1900 + 36) % 12],
        "is_leap": is_leap,
        "solar_term": term,
    }


def _solar_term(date):
    """寿星通用公式近似节气，误差 ±1 天；仅用于壁纸展示。"""
    y = date.year % 100
    century = date.year // 100
    if century == 20:
        # 2000-2099 年（21 世纪）系数
        coef = [5.4055, 20.12, 3.87, 18.73, 5.63, 20.646, 4.81, 20.1,
                5.52, 21.04, 5.678, 21.37, 7.108, 22.83, 7.5, 23.13, 7.646,
                23.042, 8.318, 23.438, 7.438, 22.36, 7.18, 21.94]
    else:
        # 1900-1999 年（20 世纪）系数
        coef = [6.11, 20.84, 4.6295, 19.4599, 6.3826, 21.4155, 5.59, 20.888,
                6.318, 21.86, 6.5, 22.2, 7.928, 23.65, 8.35, 23.95, 9.098,
                24.218, 8.218, 23.08, 7.9, 22.6, 8.1, 23.2]
    for k in (0, 1):
        idx = (date.month - 1) * 2 + k
        if date.month in (1, 2):
            day = int(y * 0.2422 + coef[idx]) - int((y - 1) / 4)
        else:
            day = int(y * 0.2422 + coef[idx]) - int(y / 4)
        if date.day == day:
            return SOLAR_TERMS[idx]
    return None


if __name__ == "__main__":
    import datetime
    for s in [
        datetime.date(2026, 2, 17),
        datetime.date(2026, 9, 25),
        datetime.date(2026, 9, 29),
        datetime.date(2026, 10, 1),
    ]:
        r = solar_to_lunar(s)
        print(s.isoformat(), "→", r["long"], "| 节气:", r["solar_term"])

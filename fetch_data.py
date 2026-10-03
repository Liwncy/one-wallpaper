#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚合每日壁纸所需的全部数据源。

设计要点
--------
* 只用标准库 urllib，不依赖 requests，减少环境依赖。
* pearapi 四个接口直接调用；60s 接口在主域名 + 8 个公共实例间自动故障转移。
* 任何一路失败都不会中断流程：优先用缓存，再退到本地计算（localinfo.py）。
* 结构化输出到 cache/daily.json，供 render.py 与 Lively 页面共用。
"""
import datetime
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import localinfo

# pythonw.exe 下 stdout/stderr 为 None，print() 会抛异常导致任务静默失败
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# stdout 被重定向到管道/文件时，Windows 中文环境会退回 GBK 编码，
# 日志里的 ✓ / ✗ 等符号会抛 UnicodeEncodeError 而中断抓取。统一强制 UTF-8。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ROOT = pathlib.Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
CACHE_DIR = ROOT / CFG["output"]["cache_dir"]
RAW_DIR = CACHE_DIR / "raw"
IMG_DIR = CACHE_DIR / "img"
LOG_DIR = ROOT / CFG["output"]["log_dir"]
for d in (CACHE_DIR, RAW_DIR, IMG_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

REQ = CFG["request"]
UA = REQ["user_agent"]

_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", UA), ("Accept", "*/*")]

STATUS = {}
_last_60s_call = [0.0]


def log(msg):
    line = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_DIR / "fetch.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _fetch_bytes(url, timeout=None, retries=None, accept_json=False):
    """带重试的原始请求，返回 bytes；失败抛异常。"""
    timeout = timeout or REQ["timeout"]
    retries = retries if retries is not None else REQ["retries"]
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            if accept_json:
                req.add_header("Accept", "application/json")
            with _opener.open(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 网络异常种类繁多，统一重试
            last = e
            if attempt < retries:
                wait = REQ["retry_delay"] * attempt
                log(f"    ↻ 第 {attempt} 次失败 ({type(e).__name__})，{wait}s 后重试: {url[:70]}")
                time.sleep(wait)
    raise last


def fetch_json(url, cache_name, timeout=None, retries=None, accept_json=True):
    """请求 JSON。成功写缓存；失败读缓存；都不可用返回 None。"""
    try:
        raw = _fetch_bytes(url, timeout, retries, accept_json)
        data = json.loads(raw.decode("utf-8", errors="replace"))
        (RAW_DIR / f"{cache_name}.json").write_bytes(raw)
        return data, "ok"
    except Exception as e:  # noqa: BLE001
        log(f"    ✗ 请求失败 {cache_name}: {type(e).__name__} {str(e)[:80]}")
        cached = RAW_DIR / f"{cache_name}.json"
        if cached.exists():
            age = (time.time() - cached.stat().st_mtime) / 3600
            log(f"    ↺ 使用缓存 {cache_name}（{age:.1f} 小时前）")
            return json.loads(cached.read_text(encoding="utf-8")), "cache"
        return None, "fail"


def fetch_text(url, cache_name):
    try:
        raw = _fetch_bytes(url)
        text = raw.decode("utf-8", errors="replace").strip()
        if text.startswith("{"):
            # 有些端点会返回 {"code":..,"data":..}，取出真正的文本
            try:
                obj = json.loads(text)
                for k in ("data", "text", "result", "content"):
                    if isinstance(obj.get(k), str):
                        text = obj[k]
                        break
            except json.JSONDecodeError:
                pass
        (RAW_DIR / f"{cache_name}.json").write_text(
            json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")
        return text, "ok"
    except Exception as e:  # noqa: BLE001
        log(f"    ✗ 请求失败 {cache_name}: {type(e).__name__}")
        cached = RAW_DIR / f"{cache_name}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))["text"], "cache"
        return None, "fail"


def download_image(url, dest, referer=None):
    """下载图片到 dest，已存在且非空则跳过。返回相对路径或 None。"""
    if dest.exists() and dest.stat().st_size > 1024:
        return str(dest.relative_to(ROOT)).replace("\\", "/")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        if referer:
            req.add_header("Referer", referer)
        with _opener.open(req, timeout=REQ["timeout"]) as r:
            blob = r.read()
        if len(blob) < 512:
            raise ValueError(f"图片过小 {len(blob)}B")
        dest.write_bytes(blob)
        log(f"    ⬇ 图片已保存 {dest.name} ({len(blob) // 1024}KB)")
        return str(dest.relative_to(ROOT)).replace("\\", "/")
    except Exception as e:  # noqa: BLE001
        log(f"    ✗ 图片下载失败 {url[:60]}: {type(e).__name__}")
        return None


# ---------------------------------------------------------------- 60s 实例

def _60s_throttle():
    gap = CFG["sixty_s"]["min_interval"] - (time.time() - _last_60s_call[0])
    if gap > 0:
        time.sleep(gap)
    _last_60s_call[0] = time.time()


def pick_60s_instance():
    """探测可用实例，结果缓存到 cache/raw/_60s_host.json。"""
    probe = CACHE_DIR / "raw" / "_60s_host.json"
    if probe.exists():
        info = json.loads(probe.read_text(encoding="utf-8"))
        if time.time() - info.get("at", 0) < 6 * 3600:
            return info["host"]
    for host in CFG["sixty_s"]["instances"]:
        try:
            _60s_throttle()
            raw = _fetch_bytes(host + CFG["sixty_s"]["paths"]["moyu"], timeout=12, retries=1)
            if b'"code":200' in raw or b'"code": 200' in raw:
                log(f"  ✓ 60s 可用实例: {host}")
                probe.write_text(json.dumps({"host": host, "at": time.time()}),
                                 encoding="utf-8")
                return host
            log(f"  ✗ {host} 返回异常")
        except Exception as e:  # noqa: BLE001
            log(f"  ✗ {host} 不可用 ({type(e).__name__})")
    log("  ✗ 所有 60s 实例均不可用，将使用本地计算")
    return None


def fetch_60s(host, path, params=None, cache_name=None):
    if not host:
        return None, "fail"
    url = host + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    _60s_throttle()
    return fetch_json(url, cache_name or path.strip("/").replace("/", "_"),
                      timeout=15, retries=2, accept_json=True)


# ---------------------------------------------------------------- 各数据源

def get_calendar(host):
    """摸鱼日报：含农历、进度、倒计时、假期，一个接口全给。"""
    log("→ 摸鱼日报 / 农历")
    data, st = fetch_60s(host, CFG["sixty_s"]["paths"]["moyu"], cache_name="moyu")
    if data and data.get("code") == 200 and "data" in data:
        d = dict(data["data"])
        d["_source"] = st
        return d, st
    log("  ↺ 回退到本地农历计算")
    local = localinfo.build(city=CFG["city"])
    local["_source"] = "local"
    return local, ("local" if st == "fail" else st)


def get_weather(host):
    """60s 天气预报（腾讯天气源，中文描述 + AQI + 日出日落）。"""
    log("→ 潍坊天气")
    params = {"query": CFG["city"], "days": str(CFG["weather_forecast_days"])}
    data, st = fetch_60s(host, CFG["sixty_s"]["paths"]["weather"],
                         params=params, cache_name="weather")
    if data and data.get("code") == 200 and data.get("data"):
        return data["data"], st

    log("  ↺ 尝试 open-meteo 兜底")
    fb = CFG["fallback_weather"]
    q = urllib.parse.urlencode({
        "latitude": fb["latitude"], "longitude": fb["longitude"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,sunrise,sunset",
        "timezone": "Asia/Shanghai",
        "forecast_days": CFG["weather_forecast_days"],
    })
    om, st2 = fetch_json(f"{fb['url']}?{q}", "weather_openmeteo")
    if om:
        code_cn = {0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "雾", 48: "雾凇",
                   51: "毛毛雨", 53: "小雨", 55: "中雨", 61: "小雨", 63: "中雨",
                   65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨",
                   95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷暴"}
        cur = om.get("current", {})
        return {
            "location": {"name": CFG["city"], "city": CFG["city"], "province": ""},
            "daily_forecast": [{
                "date": t, "day_condition": code_cn.get(om["daily"]["weather_code"][i], "—"),
                "min_temperature": round(om["daily"]["temperature_2m_min"][i]),
                "max_temperature": round(om["daily"]["temperature_2m_max"][i]),
            } for i, t in enumerate(om["daily"]["time"])],
            "hourly_forecast": [],
            "sunrise_sunset": [{
                "sunrise_desc": om["daily"]["sunrise"][i][-5:],
                "sunset_desc": om["daily"]["sunset"][i][-5:],
            } for i in range(len(om["daily"]["time"]))],
            "_current": {
                "temperature": round(cur.get("temperature_2m", 0)),
                "condition": code_cn.get(cur.get("weather_code", -1), "—"),
                "humidity": cur.get("relative_humidity_2m"),
                "wind_speed": cur.get("wind_speed_10m"),
            },
            "_source": "open-meteo",
        }, "ok"
    return None, "fail"


def norm_weather(w):
    """把天气数据整理成渲染层直接可用的结构。"""
    if not w:
        return None
    now = datetime.datetime.now()
    hourly = w.get("hourly_forecast") or []
    cur = w.get("_current")

    if not cur and hourly:
        best, best_gap = None, None
        for h in hourly:
            try:
                dt = datetime.datetime.strptime(h["datetime"], "%Y-%m-%d %H:%M")
            except (ValueError, KeyError):
                continue
            gap = abs((dt - now).total_seconds())
            if best_gap is None or gap < best_gap:
                best, best_gap = h, gap
        if best:
            cur = {
                "temperature": best.get("temperature"),
                "condition": best.get("condition"),
                "wind_direction": best.get("wind_direction"),
                "wind_power": best.get("wind_power"),
                "icon": best.get("weather_icon"),
            }
    if not cur and w.get("daily_forecast"):
        d0 = w["daily_forecast"][0]
        cur = {"temperature": d0.get("max_temperature"),
               "condition": d0.get("day_condition")}

    today = now.date().isoformat()
    daily = [d for d in (w.get("daily_forecast") or [])]
    today_daily = next((d for d in daily if d.get("date") == today),
                       daily[1] if len(daily) > 1 and daily[0].get("date", "") < today else
                       (daily[0] if daily else None))
    ss = w.get("sunrise_sunset") or []
    today_ss = next((s for s in ss if s.get("sunrise", "").startswith(today)),
                    ss[1] if len(ss) > 1 and ss[0].get("sunrise", "") < today else
                    (ss[0] if ss else None))

    return {
        "location": (w.get("location") or {}).get("name") or CFG["city"],
        "current": cur,
        "today": today_daily,
        "forecast": [d for d in daily if d.get("date") and d["date"] >= today][:CFG["weather_forecast_days"]],
        "sunrise": (today_ss or {}).get("sunrise_desc"),
        "sunset": (today_ss or {}).get("sunset_desc"),
        "aqi": (today_daily or {}).get("aqi"),
        "air_quality": (today_daily or {}).get("air_quality"),
        "_source": w.get("_source", "60s"),
    }


# ---------------------------------------------------------------- 主流程

def build_daily():
    today = datetime.date.today()
    stamp = today.strftime("%Y%m%d")
    log(f"===== 开始生成 {today} 壁纸数据 =====")

    out = {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "date": today.isoformat(), "stamp": stamp, "status": {}}

    # 1. 60s 相关（先探测实例，避免多接口重复探测）
    host = pick_60s_instance()

    calendar, st = get_calendar(host)
    out["calendar"] = calendar
    out["status"]["calendar"] = st

    weather, st = get_weather(host)
    weather = norm_weather(weather)
    out["weather"] = weather
    out["status"]["weather"] = st if weather else "fail"

    # 2. AI 资讯
    log("→ AI 全网最新资讯")
    ai, st = fetch_json(CFG["apis"]["ai_news"], "ai_news")
    out["status"]["ai_news"] = st
    if ai and ai.get("data"):
        d = ai["data"]
        items = (d.get("models_and_releases") or [])[:CFG["ai_news_count"]]
        for it in items:
            it["summary"] = (it.get("summary") or "").replace("\n", " ")
        out["ai_news"] = {
            "items": items,
            "image": download_image(d["image_url"], IMG_DIR / f"ai_{stamp}.jpg")
            if d.get("image_url") else None,
            "_source": st,
        }
        log(f"    ✓ {len(items)} 条资讯")
    else:
        out["ai_news"] = {"items": [], "image": None, "_source": st}

    # 3. 今日老婆
    log("→ 今日老婆")
    wife_url = f"{CFG['apis']['today_wife']}?id={stamp}"
    wife, st = fetch_json(wife_url, "wife")
    out["status"]["wife"] = st
    if wife and wife.get("data"):
        d = wife["data"]
        out["wife"] = {
            "role_name": d.get("role_name"),
            "width": d.get("width"), "height": d.get("height"),
            "image": download_image(d["image_url"], IMG_DIR / f"wife_{stamp}.jpg"),
            "_source": st,
        }
        log(f"    ✓ {d.get('role_name')} ({d.get('width')}x{d.get('height')})")
    else:
        out["wife"] = {"role_name": None, "image": None, "_source": st}

    # 4. 毒鸡汤
    log("→ 毒鸡汤")
    txt, st = fetch_text(CFG["apis"]["dujitang"], "dujitang")
    out["dujitang"] = txt
    out["status"]["dujitang"] = st
    log(f"    ✓ {txt}")

    # 5. 星座运势
    log(f"→ {CFG['zodiac']}座运势")
    xz_url = CFG["apis"]["xzys"] + "?" + urllib.parse.urlencode({"xz": CFG["zodiac"]})
    xz, st = fetch_json(xz_url, "xzys")
    out["status"]["xzys"] = st
    if xz and xz.get("data"):
        d = xz["data"]
        out["zodiac"] = {"sign": xz.get("xz", CFG["zodiac"]), "_source": st, **d}
        log(f"    ✓ {d.get('title')} · {d.get('shortcomment')}")
    else:
        out["zodiac"] = {"sign": CFG["zodiac"], "_source": st}

    out["moyu_quote"] = (calendar or {}).get("moyuQuote")

    (CACHE_DIR / "daily.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"===== 完成，状态: {out['status']} =====")
    return out


if __name__ == "__main__":
    result = build_daily()
    failed = [k for k, v in result["status"].items() if v == "fail"]
    if failed:
        log(f"⚠ 以下数据源完全不可用: {failed}")
    sys.exit(0)

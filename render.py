#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 cache/daily.json 渲染成 2560×1440 的每日壁纸 PNG。

版式（从左到右）
----------------
  0..780        今日老婆立绘（contain 完整显示，不裁切；模糊衬底铺满整列）
  852..2496     内容区
      72..250     日期/农历  |  天气
      282..846    AI 资讯 TOP N
      878..1330   毒鸡汤+摸鱼+进度  |  星座运势
      1354       数据源健康状态

两条硬约束
----------
1. **任务栏安全区**：Windows 壁纸永远被任务栏盖住屏幕底部，本机任务栏 48px，
   所以所有内容必须落在 y < 1392 之内。SAFE_BOTTOM 就是这个上限。
2. **立绘不裁切**：今日老婆返回的是 849×1200 竖图，用 cover 填 780×1440 的窄条
   会横向切掉约 40%。改用 contain 完整显示 + 底部对齐，空缺用同一张图的
   高斯模糊衬底填满，人物手脚不会被切在框外。
"""
import datetime
import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
T = CFG["theme"]
W, H = CFG["resolution"]

# ---- 版式常量 ----------------------------------------------------------
TASKBAR = 48                      # 本机任务栏高度，实测
SAFE_BOTTOM = H - TASKBAR         # 内容不得越过这条线
MARGIN = 64

# 立绘列：按图片比例贴合高度铺满，不做任何裁切、不做渐隐。
# today_wife 是 849×1200（比例 0.7075），贴合 1392 高即 985×1392。
PORTRAIT_W = 985
PORTRAIT_GAP = 52
COL_X0 = PORTRAIT_W + PORTRAIT_GAP   # 内容区左边界
COL_X1 = W - MARGIN                  # 内容区右边界

HDR_Y0, HDR_Y1 = 72, 250
NEWS_Y0, NEWS_Y1 = 282, 846
BOT_Y0, BOT_Y1 = 878, 1330

GAP = 40
COL_MID = COL_X0 + 709             # 左右分栏的中缝
RIGHT_X0 = COL_MID + GAP

def _find_font(candidates):
    """按顺序挑第一个存在的字体文件，跨平台兜底。"""
    for p in candidates:
        if pathlib.Path(p).exists():
            return p
    return candidates[0]


# 中文字体：Windows 优先微软雅黑，其次黑体；Linux/macOS 走 Noto / 文泉驿 / 苹方
FONT_R = _find_font([
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
])
FONT_B = _find_font([
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
])
_cache = {}


def F(size, bold=False):
    key = (size, bold)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(FONT_B if bold else FONT_R, size)
    return _cache[key]


def hex2rgba(c, a=255):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a)


def white(a, tint=None):
    """轻玻璃用的白色叠加层；tint 给一个 RGB 微调色相。"""
    return (tint or (255, 255, 255)) + (a,)


def cover(img, tw, th, bias_x=0.5, bias_y=0.5):
    """等比缩放并居中裁剪到目标尺寸。bias 控制裁剪偏向（0=靠左/上，1=靠右/下）。"""
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    nw, nh = max(tw, int(round(sw * scale))), max(th, int(round(sh * scale)))
    img = img.resize((nw, nh), Image.LANCZOS)
    left = int((nw - tw) * bias_x)
    top = int((nh - th) * bias_y)
    return img.crop((left, top, left + tw, top + th))


def wrap(draw, text, font, max_w, max_lines=None, ellipsize=False):
    """按像素宽度贪心折行，支持中英文混排；超出 max_lines 时可补省略号。"""
    text = (text or "").strip()
    if not text:
        return []
    lines, cur, i, n = [], "", 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            lines.append(cur)
            cur = ""
            i += 1
        elif draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
            i += 1
        elif not cur:                      # 单字就超宽，强制放行避免死循环
            cur = ch
            i += 1
        else:
            lines.append(cur)
            cur = ""
        if max_lines and len(lines) >= max_lines:
            break
    if cur and (not max_lines or len(lines) < max_lines):
        lines.append(cur)
        cur = ""
    truncated = bool(cur) or i < n
    if truncated and ellipsize and lines:
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_w:
            last = last[:-1]
        lines[-1] = (last + "…") if last else "…"
    return lines


def fit_font(draw, text, sizes, max_w, max_lines, bold=True):
    """从大到小挑一个能让文字落在 max_lines 行内的字号。"""
    for s in sizes:
        f = F(s, bold)
        if len(wrap(draw, text, f, max_w, None)) <= max_lines:
            return f, wrap(draw, text, f, max_w, None)
    f = F(sizes[-1], bold)
    return f, wrap(draw, text, f, max_w, max_lines, ellipsize=True)


def ellipsis(draw, text, font, max_w):
    text = (text or "").strip()
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def text_ls(draw, xy, text, font, fill, ls=0, anchor="lm"):
    """带字间距的文本。锚点只支持 lm / rm / mm。"""
    if not ls:
        draw.text(xy, text, font=font, fill=fill, anchor=anchor)
        return draw.textlength(text, font=font)
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + ls * max(0, len(text) - 1)
    x, y = xy
    x0 = x if anchor == "lm" else (x - total if anchor == "rm" else x - total / 2)
    for ch, w in zip(text, widths):
        draw.text((x0, y), ch, font=font, fill=fill, anchor="lm")
        x0 += w + ls
    return total


def panel(base, box, radius=24, fill_a=None, border_a=None):
    """轻玻璃面板：极淡的白色叠加 + 一道很细的亮边，不要实色块。"""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(
        (0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=radius,
        fill=white(T.get("panel_alpha", 12) if fill_a is None else fill_a),
        outline=white(T.get("panel_border_alpha", 30) if border_a is None else border_a),
        width=1,
    )
    base.alpha_composite(layer, (x0, y0))


def rule(base, x0, x1, y, a=26):
    """极细分隔线。"""
    ImageDraw.Draw(base).line((x0, y, x1, y), fill=white(a), width=1)


def bar(base, x, y, w, h, pct, color, track_a=34):
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=white(track_a))
    fill_w = max(h, int(w * max(0, min(100, pct)) / 100))
    d.rounded_rectangle((x, y, x + fill_w, y + h), radius=h // 2, fill=hex2rgba(color))


def label(base, xy, text, anchor="lm", a=None):
    """小标题：小字号 + 大字距 + 低对比，是"轻盈"的主要手段。"""
    dr = ImageDraw.Draw(base)
    return text_ls(dr, xy, text, F(21), white(T.get("label_alpha", 120)),
                   ls=4, anchor=anchor)


def load_img(rel):
    if not rel:
        return None
    p = ROOT / rel
    if not p.exists():
        p = ROOT / CFG["output"]["cache_dir"] / "img" / pathlib.Path(rel).name
    try:
        return Image.open(p).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- 各区块

def draw_background(data):
    base = Image.new("RGBA", (W, H), hex2rgba(T["bg"]))
    bg = load_img((data.get("ai_news") or {}).get("image"))
    if bg:
        bg = cover(bg, W, H)
        bg = bg.filter(ImageFilter.GaussianBlur(T.get("bg_blur", 34)))
        base.paste(bg, (0, 0))
        base.alpha_composite(Image.new("RGBA", (W, H), hex2rgba(T["bg"], T["bg_dim"])))

    # 下方 40% 再压一层，保证底部卡片的文字对比度够
    veil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(veil)
    for i in range(int(H * 0.45)):
        y = H - 1 - i
        a = int(64 * (i / (H * 0.45)) ** 1.4)
        d.line((0, y, W, y), fill=(8, 10, 14, a))
    base.alpha_composite(veil)
    return base


def draw_portrait(base, data):
    """立绘按高度贴合、完整铺满整列；不裁切、不渐隐、不压暗。

    原则：这是壁纸的主角图，不是背景装饰，所以不给它叠任何遮罩。
    列宽由图片比例推导（849×1200 → 985×1392），内容区几何已经据此排好。
    万一某天的图比例不同、贴不满整列，才在缺口处补一段模糊衬底并做渐显，
    避免出现生硬的截断；填满的情况下这段逻辑不会触发。
    """
    wife = load_img((data.get("wife") or {}).get("image"))
    if not wife:
        return

    sw, sh = wife.size
    scale = SAFE_BOTTOM / sh                  # 贴合高度，宽度按比例走
    fw = max(1, int(round(sw * scale)))
    fh = SAFE_BOTTOM
    fg = wife.resize((fw, fh), Image.LANCZOS)

    # 列宽兜底：图比列宽就等比缩到列宽，图比列窄就居中
    if fw > PORTRAIT_W:
        k = PORTRAIT_W / fw
        fw, fh = PORTRAIT_W, max(1, int(round(fh * k)))
        fg = fg.resize((fw, fh), Image.LANCZOS)
    fg_x = (PORTRAIT_W - fw) // 2
    fg_y = SAFE_BOTTOM - fh

    layer = Image.new("RGBA", (PORTRAIT_W, H), (0, 0, 0, 0))

    if fg_x == 0 and fg_y == 0 and fw >= PORTRAIT_W - 2:
        # 正好铺满 —— 直接用原图，没有任何遮罩
        layer.paste(fg.convert("RGBA"), (0, 0))
    else:
        # 有缺口：用前景边缘向上/向两侧延伸（edge clamp）做同源衬底，再做渐显
        stage = Image.new("RGB", (PORTRAIT_W, H), (12, 14, 20))
        stage.paste(fg, (fg_x, fg_y))
        band_h = max(2, fh // 40)
        if fg_y > 0:
            band = fg.crop((0, 0, fw, band_h)).resize((fw, fg_y), Image.LANCZOS)
            stage.paste(band, (fg_x, 0))
        tail = H - (fg_y + fh)
        if tail > 0:
            band = fg.crop((0, fh - band_h, fw, fh)).resize((fw, tail), Image.LANCZOS)
            stage.paste(band, (fg_x, fg_y + fh))
        if fg_x > 0:
            band = fg.crop((0, 0, band_h, fh)).resize((fg_x, fh), Image.LANCZOS)
            stage.paste(band, (0, fg_y))
            band = fg.crop((fw - band_h, 0, fw, fh)).resize((fg_x, fh), Image.LANCZOS)
            stage.paste(band, (PORTRAIT_W - fg_x, fg_y))
        back = ImageEnhance.Brightness(
            stage.filter(ImageFilter.GaussianBlur(72))
        ).enhance(0.58)
        layer.paste(back, (0, 0))

        fg_layer = Image.new("RGBA", (PORTRAIT_W, H), (0, 0, 0, 0))
        ramp = min(200, fh // 3)
        fm = Image.new("L", (fw, fh), 255)
        gr = Image.new("L", (1, ramp))
        for y in range(ramp):
            gr.putpixel((0, y), int(255 * (y / ramp) ** 1.15))
        fm.paste(gr.resize((fw, ramp)), (0, 0))
        fg_layer.paste(fg.convert("RGBA"), (fg_x, fg_y), fm)
        layer.alpha_composite(fg_layer)

    base.alpha_composite(layer)


def draw_header(base, d):
    cal = d.get("calendar") or {}
    cdate = cal.get("date") or {}
    lun = cdate.get("lunar") or {}
    greg = d.get("date", "")
    try:
        dt = datetime.date.fromisoformat(greg)
        md = f"{dt.month}月{dt.day}日"
    except ValueError:
        md = greg

    dr = ImageDraw.Draw(base)

    # ---- 左：日期 / 农历
    box = (COL_X0, HDR_Y0, COL_MID, HDR_Y1)
    panel(base, box)
    x = COL_X0 + 44
    label(base, (x, HDR_Y0 + 44), "TODAY")

    dr.text((x - 4, HDR_Y0 + 104), md, font=F(56, True),
            fill=hex2rgba(T["text"]), anchor="lm")
    off = dr.textlength(md, font=F(56, True))
    dr.text((x + off + 16, HDR_Y0 + 112), cdate.get("weekday", ""), font=F(30),
            fill=hex2rgba(T["text_dim"]), anchor="lm")

    lunar_txt = f"农历{lun.get('monthCN','')}{lun.get('dayCN','')}"
    if lun.get("yearGanZhi"):
        lunar_txt += f" · {lun['yearGanZhi']}年"
    if lun.get("zodiac"):
        lunar_txt += f" {lun['zodiac']}"
    term = (cal.get("today") or {}).get("solarTerm")
    if term:
        lunar_txt += f" · {term}"
    dr.text((x, HDR_Y0 + 152), lunar_txt, font=F(26),
            fill=hex2rgba(T["text_dim"]), anchor="lm")

    nh = cal.get("nextHoliday")
    if nh and nh.get("until") is not None:
        text_ls(dr, (COL_MID - 44, HDR_Y0 + 44), f"距{nh['name']} {nh['until']} 天",
                F(24, True), hex2rgba(T["warn"]), ls=1, anchor="rm")

    # ---- 右：天气
    box = (RIGHT_X0, HDR_Y0, COL_X1, HDR_Y1)
    panel(base, box)
    wx = d.get("weather") or {}
    cur = wx.get("current") or {}
    today = wx.get("today") or {}
    x = RIGHT_X0 + 44

    label(base, (x, HDR_Y0 + 44), "WEATHER")
    dr.text((COL_X1 - 44, HDR_Y0 + 44), wx.get("location") or CFG["city"],
            font=F(24), fill=hex2rgba(T["text_dim"]), anchor="rm")

    tx = x - 4
    t = cur.get("temperature")
    if t is not None:
        dr.text((tx, HDR_Y0 + 106), f"{t}", font=F(56, True),
                fill=hex2rgba(T["accent"]), anchor="lm")
        tx += dr.textlength(f"{t}", font=F(56, True))
        dr.text((tx, HDR_Y0 + 96), "°", font=F(34, True),
                fill=hex2rgba(T["accent"]), anchor="lm")
        tx += dr.textlength("°", font=F(34, True)) + 20

    cond = cur.get("condition") or today.get("day_condition") or ""
    if cond:
        dr.text((tx, HDR_Y0 + 110), cond, font=F(32),
                fill=hex2rgba(T["text"]), anchor="lm")
        tx += dr.textlength(cond, font=F(32)) + 26

    lo, hi = today.get("min_temperature"), today.get("max_temperature")
    if lo is not None and hi is not None:
        dr.text((tx, HDR_Y0 + 112), f"{lo}° ~ {hi}°", font=F(27),
                fill=hex2rgba(T["text_dim"]), anchor="lm")

    aqi, aqitxt = today.get("aqi"), today.get("air_quality")
    if aqi is not None:
        col = T["ok"] if aqi <= 50 else (T["warn"] if aqi <= 100 else T["danger"])
        dr.text((COL_X1 - 44, HDR_Y0 + 106), f"AQI {aqi}", font=F(26, True),
                fill=hex2rgba(col), anchor="rm")
        if aqitxt:
            dr.text((COL_X1 - 44, HDR_Y0 + 138), aqitxt, font=F(21),
                    fill=hex2rgba(col), anchor="rm")

    bits = []
    if cur.get("wind_direction"):
        bits.append(f"{cur['wind_direction']}{cur.get('wind_power','')}级")
    elif today.get("day_wind_direction"):
        bits.append(f"{today['day_wind_direction']}{today.get('day_wind_power','')}级")
    if wx.get("sunrise"):
        bits.append(f"日出 {wx['sunrise']}")
    if wx.get("sunset"):
        bits.append(f"日落 {wx['sunset']}")
    if bits:
        dr.text((x, HDR_Y0 + 152), "  ·  ".join(bits), font=F(22),
                fill=hex2rgba(T["text_hint"]), anchor="lm")


def draw_news(base, d):
    news = (d.get("ai_news") or {}).get("items") or []
    box = (COL_X0, NEWS_Y0, COL_X1, NEWS_Y1)
    panel(base, box)
    dr = ImageDraw.Draw(base)
    x = COL_X0 + 44

    label(base, (x, NEWS_Y0 + 46), "AI 资讯")
    if news:
        text_ls(dr, (x + 108, NEWS_Y0 + 46), f"{len(news):02d}", F(20),
                hex2rgba(T["accent"]), ls=1, anchor="lm")

    src = (news[0].get("source") if news else "") or ""
    stamp = (d.get("generated_at") or "")[:16].replace("T", " ")
    right = " · ".join([v for v in (src, stamp) if v])
    if right:
        dr.text((COL_X1 - 44, NEWS_Y0 + 46), right, font=F(21),
                fill=hex2rgba(T["text_hint"]), anchor="rm")

    if not news:
        dr.text((x, NEWS_Y0 + 220), "今日暂无 AI 资讯数据", font=F(30),
                fill=hex2rgba(T["text_hint"]), anchor="lm")
        return

    rule(base, x, COL_X1 - 44, NEWS_Y0 + 84)

    inner_w = COL_X1 - 44 - (x + 62)
    avail = NEWS_Y1 - (NEWS_Y0 + 104) - 30
    step = min(64, avail // len(news))
    y = NEWS_Y0 + 136
    for i, it in enumerate(news, 1):
        dr.text((x, y), f"{i:02d}", font=F(23, True),
                fill=white(70), anchor="lm")
        title = ellipsis(dr, it.get("title", ""), F(30), inner_w)
        dr.text((x + 62, y), title, font=F(30),
                fill=hex2rgba(T["text"]), anchor="lm")
        y += step


def draw_quote_card(base, d):
    box = (COL_X0, BOT_Y0, COL_MID, BOT_Y1)
    panel(base, box)
    dr = ImageDraw.Draw(base)
    x = COL_X0 + 44
    inner_w = COL_MID - x - 44

    label(base, (x, BOT_Y0 + 46), "毒鸡汤")
    font, lines = fit_font(dr, d.get("dujitang") or "", [34, 31, 28], inner_w, 2)
    step = int(font.size * 1.46)
    y = BOT_Y0 + 104
    for ln in lines:
        dr.text((x, y), ln, font=font, fill=hex2rgba(T["text"]), anchor="lm")
        y += step

    dy = BOT_Y0 + 226
    rule(base, x, COL_MID - 44, dy)

    label(base, (x, dy + 40), "摸鱼语录")
    ql = wrap(dr, d.get("moyu_quote") or "", F(25), inner_w, 2, ellipsize=True)
    qy = dy + 78
    for ln in ql:
        dr.text((x, qy), ln, font=F(25), fill=hex2rgba(T["text_dim"]), anchor="lm")
        qy += 34

    # 进度条锚定卡片底部
    cal = d.get("calendar") or {}
    prog = cal.get("progress") or {}
    specs = [("本周", (prog.get("week") or {}).get("percentage"), T["accent"]),
             ("本月", (prog.get("month") or {}).get("percentage"), T["ok"]),
             ("今年", (prog.get("year") or {}).get("percentage"), T["warn"])]
    which = [s for s in specs if s[1] is not None]
    if not which:
        return
    bw = (inner_w - 60) // 3
    by = BOT_Y1 - 62
    for i, (name, pct, col) in enumerate(which):
        bx = x + i * (bw + 30)
        dr.text((bx, by), name, font=F(21), fill=hex2rgba(T["text_hint"]), anchor="lm")
        dr.text((bx + bw, by), f"{pct}%", font=F(21, True),
                fill=hex2rgba(col), anchor="rm")
        bar(base, bx, by + 20, bw, 7, pct, col)


def draw_zodiac_card(base, d):
    box = (RIGHT_X0, BOT_Y0, COL_X1, BOT_Y1)
    panel(base, box)
    dr = ImageDraw.Draw(base)
    x = RIGHT_X0 + 44
    inner_w = COL_X1 - x - 44

    z = d.get("zodiac") or {}
    label(base, (x, BOT_Y0 + 46), "星座运势")
    if z.get("time"):
        dr.text((COL_X1 - 44, BOT_Y0 + 46), z["time"], font=F(21),
                fill=hex2rgba(T["text_hint"]), anchor="rm")

    dr.text((x, BOT_Y0 + 96), f"{z.get('sign','')}座", font=F(34, True),
            fill=hex2rgba(T["text"]), anchor="lm")
    off = dr.textlength(f"{z.get('sign','')}座", font=F(34, True))
    if z.get("shortcomment"):
        dr.text((x + off + 20, BOT_Y0 + 100), z["shortcomment"], font=F(30, True),
                fill=hex2rgba(T["accent"]), anchor="lm")

    lines = wrap(dr, z.get("alltext") or "", F(24), inner_w, 3, ellipsize=True)
    y = BOT_Y0 + 156
    for ln in lines:
        dr.text((x, y), ln, font=F(24), fill=hex2rgba(T["text_dim"]), anchor="lm")
        y += 33

    def pct_of(v):
        try:
            return int(str(v).replace("%", ""))
        except ValueError:
            return None

    idx = [("健康", pct_of(z.get("health")), T["ok"]),
           ("讨论", pct_of(z.get("discuss")), T["accent"])]
    idx = [i for i in idx if i[1] is not None]
    if idx:
        bw = (inner_w - 40) // 2
        iy = BOT_Y1 - 122
        for i, (name, pct, col) in enumerate(idx):
            bx = x + i * (bw + 40)
            dr.text((bx, iy), name, font=F(21), fill=hex2rgba(T["text_hint"]), anchor="lm")
            dr.text((bx + bw, iy), f"{pct}%", font=F(21, True),
                    fill=hex2rgba(col), anchor="rm")
            bar(base, bx, iy + 20, bw, 7, pct, col)

    lucky = []
    if z.get("luckycolor"):
        lucky.append(f"幸运色 {z['luckycolor']}")
    if z.get("luckynumber"):
        lucky.append(f"幸运数字 {z['luckynumber']}")
    if z.get("luckyconstellation"):
        lucky.append(f"幸运星座 {z['luckyconstellation']}")
    if lucky:
        dr.text((x, BOT_Y1 - 56), "   ·   ".join(lucky), font=F(22),
                fill=hex2rgba(T["text_dim"]), anchor="lm")


def draw_footer(base, d):
    """数据源健康状态。注意必须落在 SAFE_BOTTOM 之上，否则会被任务栏吃掉。"""
    st = d.get("status") or {}
    mark = {"ok": "●", "cache": "◐", "local": "◑", "fail": "○"}
    col = {"ok": T["ok"], "cache": T["warn"], "local": T["warn"], "fail": T["danger"]}
    dr = ImageDraw.Draw(base)
    x = COL_X1
    y = SAFE_BOTTOM - 30
    for name, key in [("资讯", "ai_news"), ("老婆", "wife"), ("鸡汤", "dujitang"),
                      ("星座", "xzys"), ("日历", "calendar"), ("天气", "weather")]:
        s = st.get(key, "fail")
        txt = mark.get(s, "○") + " " + name
        w = dr.textlength(txt, font=F(20))
        dr.text((x - w, y), txt, font=F(20),
                fill=hex2rgba(col.get(s, T["danger"]), 190), anchor="lm")
        x -= w + 24
    dr.text((COL_X0, y), "数据源", font=F(20), fill=white(70), anchor="lm")


# ---------------------------------------------------------------- 入口

def render(data=None):
    if data is None:
        data = json.loads((ROOT / CFG["output"]["cache_dir"] / "daily.json")
                          .read_text(encoding="utf-8"))

    img = draw_background(data)
    draw_portrait(img, data)
    draw_header(img, data)
    draw_news(img, data)
    draw_quote_card(img, data)
    draw_zodiac_card(img, data)
    draw_footer(img, data)

    out_dir = ROOT / CFG["output"]["static_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"wallpaper_{data.get('date','today')}.png"
    path = out_dir / name
    img.convert("RGB").save(path, "PNG", optimize=True)
    latest = out_dir / "today.png"
    img.convert("RGB").save(latest, "PNG", optimize=True)
    print(f"✓ 已生成 {path}")
    print(f"✓ 已更新 {latest}")
    return path


if __name__ == "__main__":
    render()
    sys.exit(0)

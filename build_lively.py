#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 cache/daily.json 烘进 Lively Web 壁纸，使其断网也能显示最近一次的数据。

生成/更新
    lively/data.js        最近一次数据快照（离线兜底）
    lively/wife.jpg       今日老婆立绘
    lively/bg.jpg         AI 资讯配图（背景）
"""
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
LIVELY = ROOT / "lively"
CACHE = ROOT / CFG["output"]["cache_dir"]
LIVELY.mkdir(exist_ok=True)


def copy_asset(rel, dest_name):
    if not rel:
        return None
    src = ROOT / rel
    if not src.exists():
        src = CACHE / "img" / pathlib.Path(rel).name
    if not src.exists():
        return None
    shutil.copyfile(src, LIVELY / dest_name)
    return dest_name


def build():
    daily_path = CACHE / "daily.json"
    if not daily_path.exists():
        raise SystemExit("cache/daily.json 不存在，请先运行 fetch_data.py")

    d = json.loads(daily_path.read_text(encoding="utf-8"))

    # 图片改成本地相对路径，避免 file:// 页面依赖网络
    wife_img = copy_asset((d.get("wife") or {}).get("image"), "wife.jpg")
    bg_img = copy_asset((d.get("ai_news") or {}).get("image"), "bg.jpg")
    if d.get("wife") is not None:
        d["wife"]["image"] = wife_img
        d["wife"]["_local"] = True
    if d.get("ai_news") is not None:
        d["ai_news"]["image"] = bg_img
        d["ai_news"]["_local"] = True

    payload = {
        "zodiac": CFG["zodiac"],
        "city": CFG["city"],
        "instances": CFG["sixty_s"]["instances"],
        "apis": CFG["apis"],
    }

    js = (
        "// 由 build_lively.py 自动生成，请勿手工修改\n"
        "window.WALLPAPER_CONFIG = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n"
        "window.WALLPAPER_DATA = " + json.dumps(d, ensure_ascii=False, indent=1) + ";\n"
    )
    (LIVELY / "data.js").write_text(js, encoding="utf-8")

    # Lively 的远程图片改为在线地址（页面联网时优先用实时图，本地图作兜底）
    print(f"✓ lively/data.js 已更新（{len(js) // 1024}KB）")
    if wife_img:
        print(f"✓ lively/{wife_img}")
    if bg_img:
        print(f"✓ lively/{bg_img}")

    make_thumbnail()


def make_thumbnail(width=640):
    """用当日渲染图生成 Lively 列表缩略图。"""
    src = ROOT / CFG["output"]["static_dir"] / "today.png"
    if not src.exists():
        return
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(src).convert("RGB")
    h = int(im.height * width / im.width)
    im.resize((width, h), Image.LANCZOS).save(LIVELY / "thumbnail.jpg", "JPEG", quality=88)
    print(f"✓ lively/thumbnail.jpg（{width}x{h}）")


if __name__ == "__main__":
    build()

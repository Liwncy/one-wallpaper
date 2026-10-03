#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日壁纸流水线入口：抓数据 → 渲染静态图 → 烘焙 Lively 动态壁纸 → 清理旧文件。

用法
----
    python main.py                 # 完整跑一遍（抓取 + 出图 + 烘焙 Lively + 下发壁纸）
    python main.py --no-wallpaper  # 不修改当前桌面壁纸
    python main.py --no-lively     # 不烘焙 Lively 数据
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time
import traceback

# pythonw.exe 下 sys.stdout/stderr 为 None，print() 会抛异常导致任务静默失败
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

# 命令行开关：--no-lively / --no-wallpaper
FLAGS = {a[2:] for a in sys.argv[1:] if a.startswith("--")}


def prune():
    """按 keep_days 清理历史 PNG 与缓存图片。"""
    keep = CFG["output"]["keep_days"]
    cutoff = time.time() - keep * 86400
    out = ROOT / CFG["output"]["static_dir"]
    removed = 0
    for f in out.glob("wallpaper_*.png"):
        if f.name == "today.png":
            continue
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    img = ROOT / CFG["output"]["cache_dir"] / "img"
    for f in img.glob("*"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    if removed:
        print(f"· 清理了 {removed} 个超过 {keep} 天的旧文件")


def apply_wallpaper():
    """调用 set_wallpaper.ps1 把 today.png 下发为桌面壁纸。

    用 -ExecutionPolicy Bypass 绕过默认的 Restricted 策略；
    pythonw 下必须带 CREATE_NO_WINDOW，否则会闪出控制台窗口。
    """
    cfg = CFG["output"]
    if not cfg.get("set_wallpaper"):
        return "跳过（set_wallpaper=false）"

    png = ROOT / cfg["static_dir"] / "today.png"
    if not png.exists():
        return "失败（today.png 不存在）"

    ps1 = ROOT / "set_wallpaper.ps1"
    if not ps1.exists():
        return "失败（缺少 set_wallpaper.ps1）"

    cmd = [
        "powershell.exe", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(ps1),
        "-Path", str(png), "-Style", cfg.get("wallpaper_style", "Fill"),
    ]
    try:
        r = subprocess.run(
            cmd, capture_output=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:  # noqa: BLE001
        return f"失败（{type(exc).__name__}: {exc}）"

    if r.returncode == 0:
        return "ok"
    err = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()
    return f"失败（{r.returncode}: {err[-1] if err else '无输出'}）"


def main():
    started = time.time()
    print(f"\n{'=' * 60}")
    print(f"每日壁纸  {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 60)

    steps = []
    try:
        import fetch_data
        data = fetch_data.build_daily()
        failed = [k for k, v in data["status"].items() if v == "fail"]
        steps.append(("抓取数据", "ok" if not failed else f"部分失败 {failed}"))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        steps.append(("抓取数据", "失败"))
        print("\n数据抓取整体失败，保留上一次的壁纸。")
        return 1

    try:
        import render
        render.render(data)
        steps.append(("渲染静态图", "ok"))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        steps.append(("渲染静态图", "失败"))

    if "no-lively" not in FLAGS:
        try:
            import build_lively
            build_lively.build()
            steps.append(("烘焙 Lively", "ok"))
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            steps.append(("烘焙 Lively", "失败"))

    prune()

    if "no-wallpaper" not in FLAGS:
        steps.append(("下发壁纸", apply_wallpaper()))

    print("-" * 60)
    for name, result in steps:
        print(f"  {name:<12} {result}")
    print(f"  耗时         {time.time() - started:.1f}s")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""env_check.py —— v1.2 开工配置检测（任务书④：开始就发现配置缺失，明确可用能力与后备）
用法: py tools/env_check.py
输出: 必需/可选/缺失 三档 + 能力结论。退出码 0（必需齐）1（必需缺）"""
import io
import os
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LINES = []
optional_missing = []


def need(name, fn):
    try:
        detail = fn()
        LINES.append("[必需][OK] %s%s" % (name, (" — " + detail) if detail else ""))
        return True
    except Exception as exc:
        LINES.append("[必需][缺] %s — %s（阻断，先解决）" % (name, exc))
        return False


def opt(name, fn, fallback):
    try:
        detail = fn()
        LINES.append("[可选][OK] %s%s" % (name, (" — " + detail) if detail else ""))
        return True
    except Exception as exc:
        optional_missing.append(name)
        LINES.append("[可选][缺] %s — %s；后备: %s" % (name, exc, fallback))
        return False


py_ok = sys.version_info >= (3, 8)
LINES.append("[必需][%s] Python ≥3.8 — 当前 %s" % ("OK" if py_ok else "缺", sys.version.split()[0]))

def _check_std_chain():
    missing = [f for f in ("validate_trip_data.py", "gen_roadbook.py", "pricing.py",
                           "gen_route_svg.py", "apply_routes.py")
               if not os.path.exists(os.path.join(HERE, f))]
    if missing:
        raise OSError("缺 " + "、".join(missing))
    if not os.path.exists(os.path.join(HERE, "..", "schema.md")):
        raise OSError("schema.md 缺失")
    return "五件核心工具+schema 在位"


std_ok = need("标准库工具链（validate/gen/pricing/route/apply）", _check_std_chain)

def _check_pil():
    import PIL  # noqa
    return "真解码模式"


def _check_playwright():
    import playwright  # noqa
    return "--visual 可用"


def _check_pexels():
    p = os.path.join(HERE, ".env")
    if not os.path.exists(p):
        raise OSError("tools/.env 不存在——官方已暂停发放新 API key，已有 key 才可配置")
    if "PEXELS_API_KEY=" not in io.open(p, encoding="utf-8").read():
        raise OSError(".env 缺 PEXELS_API_KEY=")
    return "已配置"


opt("Pillow（深度验图）", _check_pil,
    "imgcheck 自动降级结构校验（chunk CRC+IDAT），返回消息带「PIL 不可用」标注")
opt("Playwright+Edge（视觉验收）", _check_playwright,
    "checklist --visual 的视觉项自动 SKIP 声明（fail-closed），不阻塞其余验收")
opt("Pexels API key（配图通路）", _check_pexels,
    "无 key 时脚本会报错（不自动切图源）；用 Wikimedia Commons 图源或 AI 示意图（标「示意」）")
opt("高德地图 key（底图）", lambda: (_ for _ in ()).throw(
    OSError("见 README「地图能力」——Web 服务类型 key 需在 lbs.amap.com 创建")),
    "无 key 使用节点示意图（非等比例标注），不阻塞制作")

essential = py_ok and std_ok
LINES.append("---")
LINES.append("能力结论: " + ("必需齐备——可跑「校验→生成→检查」全链" if essential
                          else "必需项缺失——先解决 [必需][缺] 各项"))
if optional_missing:
    LINES.append("可选未装: %s（各自有降级行为，见上）" % "、".join(optional_missing))
LINES.append("提示: 外部 API key 一律本地配置（tools/.env），不随路书/发布包分发")

print("\n".join(LINES))
sys.exit(0 if essential else 1)

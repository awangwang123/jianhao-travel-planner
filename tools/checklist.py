# -*- coding: utf-8 -*-
"""路书交付前机械检查清单（通用版，任意城市路书可跑）
用法: python checklist.py <路书.html> [--visual]
  --visual: 额外跑 Playwright 双视口/JS错/图渲染（需本机 playwright+Edge；跑不了会声明 SKIP）

输出: 每项 PASS/FAIL/WARN/SKIP + 总结。exit 0=全过可交稿；exit 1=有 FAIL 不许交稿。
2026-10-05 v1.0：源起=东京/国际三册/山东三城三次同类翻车（区块空壳/author 越权/JS 双拼/占位符残留），
条款靠人记不可靠，机械检查才可靠。
"""
import sys, re, os, hashlib
sys.stdout.reconfigure(encoding="utf-8")

# ---------- 参数 ----------
if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(2)
PATH = sys.argv[1]
VISUAL = "--visual" in sys.argv
if not os.path.exists(PATH):
    print(f"❌ 文件不存在: {PATH}")
    sys.exit(2)

t = open(PATH, encoding="utf-8").read()
results = []

def add(ok, name, detail=""):
    mark = {True: "PASS", False: "FAIL", None: "WARN"}.get(ok if ok is not None else None, "PASS")
    results.append((mark, name, detail))
    m = {"PASS": "✅", "FAIL": "❌", "WARN": "🟡", "SKIP": "⏭"}
    print(f"{m.get(mark,'·')} [{mark}] {name}" + (f" | {detail}" if detail else ""))

def addf(name, detail):
    results.append(("FAIL", name, detail))
    print(f"❌ [FAIL] {name} | {detail}")

def addw(name, detail):
    results.append(("WARN", name, detail))
    print(f"🟡 [WARN] {name} | {detail}")

def addp(name, detail=""):
    results.append(("PASS", name, detail))
    print(f"✅ [PASS] {name}" + (f" | {detail}" if detail else ""))

# ---------- 1. 区块完备与空壳 ----------
CORE = ["overview", "drive", "boost", "ticket", "tips", "stay", "cost", "sos", "eat", "gift"]
secs = re.findall(r'<section id="([a-z0-9]+)"', t)
days = sorted([s for s in secs if re.fullmatch(r"day\d+", s)], key=lambda x: int(x[3:]))
missing_core = [c for c in CORE if c not in secs]
if missing_core:
    addf("区块完备", f"缺核心区块: {','.join(missing_core)}")
else:
    addp("区块完备", f"10 核心区块 + {len(days)} 个每日区块")

empty_blocks = []
for sid in secs:
    m = re.search(r'<section id="' + sid + r'".*?</section>', t, re.S)
    if not m:
        continue
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0))).strip()
    floor = 30 if sid in ("author", "intel") else 80
    if len(txt) < floor:
        empty_blocks.append(f"#{sid}仅{len(txt)}字")
if empty_blocks:
    addf("区块空壳", "、".join(empty_blocks) + " —— 空壳区块不许交稿（东京/国际三册/山东三案实证）")
else:
    addp("区块空壳", f"{len(secs)} 个区块全部非空")

# ---------- 2. 餐行 ----------
bad_meals = []
for d in days:
    m = re.search(r'<section id="' + d + r'".*?</section>', t, re.S)
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0)))
    lack = [x for x in ("早餐", "午餐", "晚餐") if x not in txt]
    if lack:
        bad_meals.append(f"{d}缺{'+'.join(lack)}")
if bad_meals:
    addf("每日餐行", "、".join(bad_meals) + "（v3.29 机械钩）")
else:
    addp("每日餐行", f"{len(days)} 天早/午/晚全齐")

# ---------- 3. author 资格 ----------
if '<section id="author"' in t:
    addw("author 选装件", "author 区块存在——资格制（v3.37）：仅当作者对该目的地有真实推荐资历才保留，否则删区块+删导航项（山东案：非武汉却带 author=越权）")
else:
    addp("author 选装件", "未装（默认正确）")

# ---------- 4. JS 拼接与 ID 唯一 ----------
n_script = len(re.findall(r"<script", t))
if n_script > 3:
    addf("JS 拼接", f"script 块 {n_script} 个（标准 3 个）——双拼嫌疑，主逻辑会重复执行（东京/国际三册/山东实证）")
else:
    addp("JS 拼接", f"{n_script} 个 script 块")
ids = re.findall(r'id="([A-Za-z_-][\w-]*)"', t)
dup = sorted({x for x in ids if ids.count(x) > 1})
if dup:
    addf("ID 唯一", f"重复 id: {','.join(dup)}（backtop 双拼案）")
else:
    addp("ID 唯一", "无重复 id")

# ---------- 5. 占位符 ----------
ph_hits = {}
for ph in ["__CITY__", "【目的地】", "TODO", "Lorem"]:
    n = t.count(ph)
    if n:
        ph_hits[ph] = n
if ph_hits:
    addf("占位符", str(ph_hits) + " —— 模板残留（__CITY__ 三连案）")
else:
    addp("占位符", "归零")

# ---------- 6. 骨架指纹 ----------
style = re.search(r"<style[^>]*>(.*?)</style>", t, re.S)
if style:
    fp = hashlib.md5(style.group(1).encode()).hexdigest()[:10]
    if fp == "9c3c6249a4":
        addp("骨架指纹", fp)
    else:
        addw("骨架指纹", f"{fp} ≠ 基准 9c3c6249a4——若是刻意改样式需在交付说明注明，否则=派生自旧骨架")
else:
    addw("骨架指纹", "未找到 style 块")

# ---------- 7. 价格切碎模式（大岛 Ken's 案） ----------
broken = re.findall(r"¥\d+）\s*\.\d", t)
if broken:
    addf("价格切碎", f"{len(broken)} 处「¥XX）.XX」模式——双币种转换脚本把小数价切裂（Ken's $16（¥108）.50 案）")
else:
    addp("价格切碎", "无")

# ---------- 8. 视觉项（可选） ----------
if VISUAL:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            url = "file:///" + os.path.abspath(PATH).replace("\\", "/")
            for w, h, tag in [(1280, 900, "桌面"), (390, 844, "手机")]:
                pg = browser.new_page(viewport={"width": w, "height": h})
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(1200)
                ov = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
                if errs or ov > 0:
                    addf(f"{tag}视口", f"JS错{len(errs)} 溢出{ov}px")
                else:
                    addp(f"{tag}视口", "0 错 0 溢出")
                pg.close()
            browser.close()
    except Exception as e:
        results.append(("SKIP", "视觉项", str(e)[:80]))
        print(f"⏭ [SKIP] 视觉项 | Playwright 不可用: {str(e)[:60]} —— 该检查未执行，不视为通过（fail-closed）")
else:
    results.append(("SKIP", "视觉项", "未加 --visual 参数"))
    print("⏭ [SKIP] 视觉项 | 未加 --visual（建议：python checklist.py 文件 --visual）")

# ---------- 总结 ----------
n_fail = sum(1 for m, _, _ in results if m == "FAIL")
n_warn = sum(1 for m, _, _ in results if m == "WARN")
n_skip = sum(1 for m, _, _ in results if m == "SKIP")
print("\n" + "=" * 46)
print(f"结果: {len(results)} 项 | FAIL {n_fail} | WARN {n_warn} | SKIP {n_skip}")
if n_fail:
    print("🔴 有 FAIL —— 不许交稿，修复后重跑。")
    sys.exit(1)
if n_skip:
    print("🟡 有 SKIP（未执行的检查）——交稿时必须向用户声明哪些检查未跑。")
if n_warn:
    print("🟡 有 WARN —— 人工确认后可交稿，说明放行理由。")
if not n_fail and not n_skip:
    print("🟢 全部通过，可交稿。")

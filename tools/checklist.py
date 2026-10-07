# -*- coding: utf-8 -*-
"""路书交付前机械检查清单（通用版，任意城市路书可跑）
用法: python checklist.py <路书.html> [--visual]
  --visual: 额外跑 Playwright 双视口/JS错/图渲染（需本机 playwright+Edge；跑不了会声明 SKIP）

输出: 每项 PASS/FAIL/WARN/SKIP + 总结。exit 0=全过可交稿；exit 1=有 FAIL 不许交稿。
2026-10-05 v1.0：源起=东京/国际三册/山东三城三次同类翻车（区块空壳/author 越权/JS 双拼/占位符残留），
条款靠人记不可靠，机械检查才可靠。
2026-10-07 v1.2（skill v3.56——注：v3.56 曾被两会话双占，10/8 收口归并时山东「升级体验必答化」保留 v3.56、苏州「冷知识卡」让号 v3.58，本工具 v1.2 内容对应「升级体验必答化+必答抽查」即现 v3.56）
必答清单关键词抽查（7g）：作者定稿「不希望再出现老问题」——
住宿店名/升级体验/雨天方案/隐藏成本/应急医疗/⚠️必办 各区块机器兜底。
2026-10-07 v1.1（skill v3.54）：新增四项——①图渲染（视觉项内：滚动触发懒加载后逐张查，
不滚动=假 FAIL 教训）②badge 在位（v3.27 连坐 bug，被 TRIP 空掩盖）③存储键跨成品污染
（山东版 tky_font=东京键名案：从别的成品抄 script 未改键）④长【】指引残留（页脚
「配图：【逐张写明…】」骨架填稿指引未删案；短标注【估算】不受影响）。
源起=山东三城 WB 版终审：机械 13 项全过但四项问题全漏——检查项必须跟上翻车形态。
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
optional_absent = []
for sid in secs:
    m = re.search(r'<section id="' + sid + r'".*?</section>', t, re.S)
    if not m:
        continue
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0))).strip()
    floor = 30 if sid in ("author", "intel") else 80
    if len(txt) < floor:
        if sid == "intel":
            # intel=情报卡区块仅自用版装（v3.16），朋友/通用版不装=正常（东京终审先例 2026-09-27）
            optional_absent.append(sid)
        else:
            empty_blocks.append(f"#{sid}仅{len(txt)}字")
if empty_blocks:
    addf("区块空壳", "、".join(empty_blocks) + " —— 空壳区块不许交稿（东京/国际三册/山东三案实证）")
elif optional_absent:
    addp("区块空壳", f"{len(secs)} 个区块非空（intel 空壳=未装选装区块，正常）")
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


# ---------- 2b. slot 时间线有序 + 餐行不重复（山东 day2 链式替换污染案：14:00 排在 12:30 前+晚餐双份） ----------
tl_bad = []
for d in days:
    m = re.search(r'<section id="' + d + r'">(.*?)</section>', t, re.S)
    if not m:
        continue
    slots = re.findall(r'<div class="slot"><b>([^<]+)</b>', m.group(1))
    times = []
    for s in slots:
        tm = re.match(r'(\d{1,2}):(\d{2})', s)
        if tm:
            times.append(int(tm.group(1)) * 60 + int(tm.group(2)))
    if times != sorted(times):
        tl_bad.append(f"{d}时间乱序{times[:6]}")
    meals = [s for s in slots if any(x in s for x in ("早餐", "午餐", "晚餐"))]
    dup = sorted({x for x in meals if meals.count(x) > 1})
    if dup:
        tl_bad.append(f"{d}重复餐行{dup}")
if tl_bad:
    addf("slot 时间线", "；".join(tl_bad) + " —— 每日 slot 必须按时间升序、餐行不重复（链式替换污染案）")
else:
    addp("slot 时间线", f"{len(days)} 天时间戳升序+餐行无重复")

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

# ---------- 7b. 每日配图对称律（v3.38：每日 2 或 4 张，禁 3） ----------
fig_bad = []
for d in days:
    m = re.search(r'<section id="' + d + r'".*?</section>', t, re.S)
    n = m.group(0).count("<figure") if m else 0
    if n not in (2, 4):
        fig_bad.append(f"{d}={n}张")
if fig_bad:
    addf("配图对称律", "、".join(fig_bad) + "（v3.38：每日 2 或 4 张，.photos 为 2 列网格，3 张=不对称）")
else:
    addp("配图对称律", f"{len(days)} 天全部 2/4 张")

# ---------- 7c. navLock 特征（导航双通道，9/27 根治） ----------
if "navLock" in t:
    addp("navLock", "导航双通道在位")
else:
    addf("navLock", "无 navLock 特征 = 旧导航 JS（滚动高亮乱跳/点击不同步老毛病）——从基准骨架原样带走 script 块，勿自写")

# ---------- 7d. today-badge 元素在位（v3.27 四补；山东四天全缺案） ----------
badge_bad = []
for d in days:
    m = re.search(r'<section id="' + d + r'".*?</section>', t, re.S)
    if m and "today-badge" not in m.group(0):
        badge_bad.append(d)
if badge_bad:
    addf("badge 在位", f"{','.join(badge_bad)} 每日卡缺 today-badge 元素（v3.27：每日卡头部必含，显隐由 JS 决定；TRIP 空时不显示=缺陷被掩盖）")
else:
    addp("badge 在位", f"{len(days)} 天全在位")

# ---------- 7e. 存储键跨成品污染（山东版 tky_font=东京键名案） ----------
lkeys = sorted(set(m.group(2) for m in re.finditer(r"localStorage\.\w+\((['\"])([\w-]+)\1", t)))
KNOWN_CITY = {"tky": "东京", "hl": "檀香山", "mnl": "马尼拉", "chongqing": "重庆",
              "wuhan": "武汉", "cs": "长沙", "wh": "威海", "qd": "青岛", "yt": "烟台", "sd": "山东"}
title_m = re.search(r"<title>(.*?)</title>", t)
title_txt = (title_m.group(1) if title_m else "") + " " + os.path.basename(PATH)
if not lkeys:
    addw("存储键", "未发现 localStorage 键（字号记忆功能缺失？人工确认）")
elif "__CITY___font" in lkeys:
    addw("存储键", f"{lkeys} —— 基准占位符未替换（派生时应改为本趟前缀，派生首检漏项）")
else:
    bad = []
    for pf in {k.split("_")[0] for k in lkeys if "_" in k}:
        city = KNOWN_CITY.get(pf)
        if city and city not in title_txt:
            bad.append(f"{pf}_→{city}（本稿非{city}）")
    if bad:
        addf("存储键", f"{lkeys} —— 跨成品键名污染: {'; '.join(bad)}（从别的成品抄 script 未改键，同一浏览器会与他册互踩字号记忆）")
    else:
        addp("存储键", f"{lkeys}")

# ---------- 7f. 长【】指引残留（山东页脚「配图：【逐张写明…】」案） ----------
long_bracket = re.findall(r"【[^】]{15,}】", t)
if long_bracket:
    addf("【】指引残留", f"{len(long_bracket)} 处长【】=骨架填稿指引未删: {long_bracket[0][:34]}…（短标注如【估算】【未核实】不受影响）")
else:
    addp("【】指引残留", "无")

# ---------- 7g. 必答清单关键词抽查（v1.2，作者：不希望再出现老问题） ----------
def _sec_txt(sid):
    m = re.search(r'<section id="' + sid + r'".*?</section>', t, re.S)
    if not m:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"data:image/[^\"]+", "", m.group(0))))

brand_words = ["全季", "亚朵", "汉庭", "如家", "维也纳", "希尔顿", "万豪", "凯悦", "香格里拉", "民宿", "客栈", "青旅", "搜「", "连锁"]
checks_7g = []
st = _sec_txt("stay")
if st is not None:
    has_brand = any(w in st for w in brand_words)
    has_price = ("元" in st or "¥" in st)
    if not (has_brand and has_price):
        checks_7g.append(("住宿无具体落脚点", "缺品牌店名/搜索关键词或价格区间——只给片区=老毛病（v3.45 必答①店名）"))
et = _sec_txt("eat")
if et is not None:
    if "升级体验" not in et:
        checks_7g.append(("美食缺升级体验子表", "v3.55 必答：丰俭由人+体现细节（1-3 家，四项标准 ≥3 才收，无合格如实写无）"))
    # v3.57 自用版脱敏制后，成稿不再带博主名——信源痕迹查 md 事实源，此处降为 WARN 提醒
    if not any(w in et for w in ["探店实锤", "单搜记录", "博主"]):
        results.append(("WARN", "美食信源", "成稿无信源痕迹=脱敏正常；人工确认 md 事实源有单搜记录"))
        print("🟡 [WARN] 美食信源 | 成稿无信源痕迹=脱敏正常；人工确认 md 事实源有单搜记录")
tt = _sec_txt("tips")
if tt is not None and "雨天" not in tt:
    checks_7g.append(("提示无雨天方案", "v3.29⑥：「雨天方案」是正选之一不是备用"))
ct = _sec_txt("cost")
if ct is not None and "隐藏成本" not in ct:
    checks_7g.append(("预算缺隐藏成本行", "核心铁律 7：过路/停车/服务费/小费必须留行"))
so = _sec_txt("sos")
if so is not None and not any(w in so for w in ["医院", "120", "急诊", "医疗"]):
    checks_7g.append(("应急无医疗落点", "sos 必须有医院/急诊/120 兜底"))
ov = _sec_txt("overview")
if ov is not None:
    if not any(w in ov for w in ["℃", "°C"]):
        checks_7g.append(("总览无天气格", "天气定节奏铁律：℃ 数据必须显性"))
    if not any(w in ov for w in ["必办", "提前办", "出发前"]):
        checks_7g.append(("总览无⚠️必办清单", "出发前动作必须显性（倒计时口径）"))
if checks_7g:
    addf("必答抽查", "；".join(f"{n}（{d.split('——')[0]}）" for n, d in checks_7g) + " —— 对照 v3.43-45 必答清单逐块修")
else:
    addp("必答抽查", "住宿店名/升级体验/雨天/隐藏成本/医疗/必办 六件全在位")


# ---------- 7h. nav 顺序 == DOM 顺序（山东 eat/sos 倒挂案：nav 按标准写、DOM 旧病未修 → 高亮回跳「乱跳」） ----------
nav_hrefs = re.findall(r'<a href="#([a-z0-9]+)"', t)
dom_order = [s for s in secs if s in nav_hrefs]
nav_seq = [h for h in nav_hrefs if h in dom_order]
if nav_seq != dom_order:
    badpairs = [(nav_seq[i], dom_order[i]) for i in range(min(len(nav_seq), len(dom_order))) if nav_seq[i] != dom_order[i]]
    addf("nav==DOM 顺序", f"nav 顺序与页面区块顺序不一致（前 2 处错位: {badpairs[:2]}）——滚动高亮会回跳（用户感知=乱跳）。修法=调整 DOM 区块顺序对齐 nav，或改 nav。")
else:
    addp("nav==DOM 顺序", f"{len(nav_seq)} 项顺序一致")


# ---------- 7i. nav 分组隔断（v3.16「侧栏两组导航」；山东案：重写 nav 压丢分组实锤） ----------
n_labels = len(re.findall(r'class="nav-label"', t))
if n_labels >= 2:
    addp("nav 分组", f"{n_labels} 组（行程/备忘隔断）")
else:
    addf("nav 分组", f"nav-label 仅 {n_labels} 个——基准骨架=两组隔断（行程组：总览/路程/每日/备选；备忘组 chips：门票/提示/住宿/预算/应急/美食/特产），单列长导航=执行偏差")

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
            # 图渲染（先滚动触发懒加载再查——不滚动=假 FAIL 教训 2026-10-07）
            pg = browser.new_page(viewport={"width": 1280, "height": 900})
            pg.goto(url, wait_until="domcontentloaded", timeout=30000)
            n_fig = pg.evaluate("() => document.querySelectorAll('figure img').length")
            for _ in range(15):
                pg.evaluate("() => window.scrollBy(0, 1000)")
                pg.wait_for_timeout(300)
            pg.wait_for_timeout(800)
            dead = pg.evaluate("""() => Array.from(document.querySelectorAll('figure img')).filter(
                im => !(im.naturalWidth > 0 && im.getBoundingClientRect().width > 50)).length""")
            if n_fig == 0:
                addw("图渲染", "页面 0 张 figure img（若配图对称律 PASS 则图在结构外，人工确认）")
            elif dead:
                addf("图渲染", f"{dead}/{n_fig} 张未真渲染（naturalWidth=0 或显示宽≤50）——base64 损坏或引用失效")
            else:
                addp("图渲染", f"{n_fig}/{n_fig} 张真渲染")
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

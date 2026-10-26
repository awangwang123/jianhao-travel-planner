# -*- coding: utf-8 -*-
"""
2026-10-26 v1.11：2c 动线图出界断言重构——①兼容 route-svg 程序化导览图（旧版只认 zoomable+属性顺序固定，
pipeline 注入 3 图实际数出 0 张报 PASS 的零样本假绿案）②元素覆盖 polyline/circle/line/rect/path
③零样本不再 PASS，报 WARN 声明覆盖缺口（fail-closed）④逻辑抽出 tools/svg_bounds.py 可单测，
越界必失败用例入 test_route_semantics.py。
2026-10-19 公用版同步：功能与作者版 v1.9 一致，叙事注释已中性化（实战案例去地名/去署名）。
2026-10-24 公用版同步：功能与作者版 v1.10 一致——slot 正则兼容 data-slot-id 属性、0 样本 fail-closed（0 时刻 slot=FAIL 非假 PASS）、餐段判定窗口 40→18 字。
路书交付前机械检查清单（通用版，任意城市路书可跑）
用法: python checklist.py <路书.html> [--visual]
  --visual: 额外跑 Playwright 双视口/JS错/图渲染（需本机 playwright+Edge；跑不了会声明 SKIP）

输出: 每项 PASS/FAIL/WARN/SKIP + 总结。exit 0=全过可交稿；exit 1=有 FAIL 不许交稿。
2026-10-17 v1.9（外部评审三漏检复现+北疆长线出界案，双源反哺）：①天数前置校验——0 个 day 区块时后续循环
空跑出「0 天全齐」假 PASS，现在 0 天=FAIL+编号跳号=FAIL（修「删全部每日区块仍 PASS」）②2b 重写：slot 时间
线双形态兼容（<b> 旧形态+slot-time div canonical——旧版只读 <b>，骨架 canonical 整个读不到=时间线检查空转
假 PASS）+餐段键值去重（每 slot 归入首个餐段词，同段 ≥2 slot=FAIL——旧版比完整标题，不同店名两顿晚餐不判重）
③新增 2c 动线图出界断言——解析 zoomable SVG 的 polyline/circle 坐标 vs viewBox，出界点>0=FAIL（北疆长线
G216 绕行 11 点出界 10px 目测漏案：端点在框内≠路径在框内，数学断言替代目测）④--visual 视口 2→4 档
（+768/320，对齐自查⑱四档要求）⑤回归测试：tools/_reg_v19/ 四坏样本必 FAIL（改闸必跑）。
2026-10-12 v1.6（南方某册夜四连打回反哺）：「形态检查组」八项——实战拷问「写到规范还犯」的终结手段：
翻车全在「条款有、检查器没有」的形态层（导航格式 D1 代号案/eyebrow 自创案/冷知识卡缺案/机位三条全时有时无案/
示意双写案/工具条遮挡案/每餐无备选案/参数速查卡缺案）——检查项跟上翻车形态（v3.54 原则）本轮补齐：
①eyebrow 措辞白名单（自创=FAIL，v3.57 正本集）②冷知识卡逐日（v3.58 固定件）③机位三条全覆盖（每日「📷 位置：」≥1）
④拍摄参数速查卡在 tips（v3.59③）⑤nav 日链接「第 N 天 · 」格式（v3.27 导航族）⑥eat 表头含「备选」（每餐 2 家）
⑦figcaption「（示意）」双写 ⑧尾部工具条占位（tailpad，镇江 9/10 老坑）。
⚠️ 老成品跑 v1.6 会在②③④⑥⑧上报 FAIL——按「老成品不动」人工放行，不回改。
2026-10-05 v1.0：源起=东京/国际三册/山东三城三次同类翻车（区块空壳/author 越权/JS 双拼/占位符残留），
条款靠人记不可靠，机械检查才可靠。
2026-10-16 v1.8：占位符检查先剥离内嵌图片 base64 数据再计数（data:image/*;base64,...）——base64 是随机字节编码，大文件天然可能碰巧含 TODO 等序列造成假 FAIL（东京 480 案/宏村 TODO 案两撞；宏村案当时靠底图转 JPEG 碰运气绕过）；剥离只可能减误报不漏真报（模板残留只存在于可见文本层）。
2026-10-10 v1.5：存储键检查补抓「前缀拼接形态」（引号常量形如 tky_chk_/sd_font 的城市码前缀键）——此前只抓 localStorage 直调，
tky_chk_ 残留漏检（山东版双窗合并仲裁案：另一副本修过 chk 键、基线 font 键修了 chk 没修，checklist 全程报 PASS）。
2026-10-10 v1.4：①图渲染滚动改「滚到页底为止」（固定 15 步=15000px，长页后半图懒加载没触发误报死图——
山东版 4/10 误报实锤，手动全量实测 10/10 正常）②新增「导航今天标记」检查（navA.innerHTML 注入已废止，
实战定性——今日标识归正文 today-badge 一处承担）。
2026-10-10 v1.3：①基准指纹 9c3c6249a4→9f1fd4856f（移动端表格修复：媒体查询 .tb 加
table-layout:fixed+桌面 col 抵消规则，双骨架同款；成品层按列型配 colgroup——山东版手机竖排案）
②新增检查「移动端表格布局」（WARN 级）：媒体查询无 fixed=WARN 列宽失衡风险，老成品人工放行待升级。
2026-10-07 v1.2（skill v3.56——注：v3.56 曾被两会话双占，10/8 收口归并时山东「升级体验必答化」保留 v3.56、苏州「冷知识卡」让号 v3.58，本工具 v1.2 内容对应「升级体验必答化+必答抽查」即现 v3.56）
必答清单关键词抽查（7g）：实战定规「不希望再出现老问题」——
住宿店名/升级体验/雨天方案/隐藏成本/应急医疗/⚠️必办 各区块机器兜底。
2026-10-07 v1.1（skill v3.54）：新增四项——①图渲染（视觉项内：滚动触发懒加载后逐张查，
不滚动=假 FAIL 教训）②badge 在位（v3.27 连坐 bug，被 TRIP 空掩盖）③存储键跨成品污染
（山东版 tky_font=东京键名案：从别的成品抄 script 未改键）④长【】指引残留（页脚
「配图：【逐张写明…】」骨架填稿指引未删案；短标注【估算】不受影响）。
源起=山东三城协作版终审：机械 13 项全过但四项问题全漏——检查项必须跟上翻车形态。
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

# ---------- 2a. 天数前置校验（v1.9，GPT 报告三漏检之三：删除全部每日区块后「0 天全齐」空跑 PASS 案） ----------
if not days:
    addf("天数前置校验", "每日区块 0 个——无 day 区块时后续循环全部空跑，禁止以「0 天全齐」放行")
else:
    nums = [int(x[3:]) for x in days]
    gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in nums]
    if gaps:
        addf("天数前置校验", f"day 编号跳号: 缺 day{','.join(map(str, gaps))}")
    else:
        addp("天数前置校验", f"{len(days)} 天（day{nums[0]}-day{nums[-1]}）编号连续")

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


# ---------- 2b. slot 时间线有序 + 餐行不重复（v1.9 重写：GPT 报告三漏检之一/之二——旧版只匹配 <b> 形态，骨架 canonical 的 slot-time 结构整个读不到=时间线检查空转假 PASS；餐行去重比完整标题，不同店名的两顿晚餐不判重） ----------
tl_bad = []
tl_total = 0
for d in days:
    m = re.search(r'<section id="' + d + r'">(.*?)</section>', t, re.S)
    if not m:
        continue
    seg = m.group(1)
    # 双形态兼容：旧=<div class="slot"><b>HH:MM…文本；新(canonical/武汉v8+)=slot-time div+slot-body div
    # v1.9a 修：餐段词在 slot-body——按 slot 块抓（起点到下一 slot），时间取 slot-time，餐段词在整块文本找
    slot_starts = list(re.finditer(r'<div class="slot"[^>]*><b>([^<]+)</b>|<div class="slot"[^>]*><div class="slot-time">([^<]+)</div>', seg))
    times = []
    meal_seq = []
    for i, sm in enumerate(slot_starts):
        tlabel = sm.group(1) or sm.group(2) or ""
        end = slot_starts[i + 1].start() if i + 1 < len(slot_starts) else len(seg)
        chunk = seg[sm.start():end]
        tm = re.match(r'\s*(\d{1,2}):(\d{2})(\+1)?', tlabel)
        if tm:
            times.append(int(tm.group(1)) * 60 + int(tm.group(2)) + (1440 if tm.group(3) else 0))
        body_txt = re.sub(r"<[^>]+>", " ", chunk)
        head = re.sub(r"\s+", " ", body_txt)[:18]  # v1.16 同步作者版 v1.10：窗口 40→18 字——餐段特征=紧跟时刻；40 字窗口把顺带提及（如「明后两天早餐时间」）误判成第二顿早餐（实战回归实证）。收紧代价：餐词靠后的合法餐行可能漏判（漏判比误伤温和）
        for kw in ("早餐", "午餐", "晚餐"):
            if kw in head:
                meal_seq.append(kw)
                break
    tl_total += len(times)
    if times != sorted(times):
        tl_bad.append(f"{d}时间乱序{times[:6]}")
    dup = sorted({x for x in meal_seq if meal_seq.count(x) > 1})
    if dup:
        tl_bad.append(f"{d}重复餐段{dup}")
if not days:
    pass  # 天数前置校验已 FAIL，此处不再叠加
elif tl_total == 0:
    # v1.16 同步作者版 v1.10 fail-closed：天数区块存在却读到 0 个带时刻 slot = 检查器无法解析当前结构，禁止假 PASS（data-slot-id 属性不匹配案）
    addf("slot 时间线", f"读到 0 个带时刻 slot（{len(days)} 天区块存在）——检查器无法解析当前 slot 结构，时间线未检查；请更新匹配规则或核对页面结构")
elif tl_bad:
    addf("slot 时间线", "；".join(tl_bad) + " —— 每日 slot 必须按时间升序、同餐段不重复（链式替换污染案+GPT 三漏检回归）")
else:
    addp("slot 时间线", f"{len(days)} 天时间戳升序（读到 {tl_total} 个带时刻 slot）+同餐段无重复")

# ---------- 2c. 动线图出界点断言（v1.9 立；v1.11 重构：兼容 route-svg+line/rect/path，零样本 WARN 不 PASS，逻辑在 svg_bounds.py） ----------
from svg_bounds import check_svg_bounds
svg_n, svg_skip, svg_bad = check_svg_bounds(t)
if svg_bad:
    addf("动线图出界", "、".join(svg_bad) + " —— polyline/circle/line/rect/path 坐标越出 viewBox（bbox 必须覆盖路径全程，数学断言替代目测）")
elif svg_n == 0:
    addw("动线图出界", "0 张可检导览图（zoomable/route-svg）——若本册应有路线图即覆盖缺口，须排查生成/注入环节；确认无图才可放行")
else:
    extra = f"；另有 {svg_skip} 张类名匹配但 viewBox 非 0 0 起点，未检" if svg_skip else ""
    addp("动线图出界", f"{svg_n} 张导览图坐标全在框内（容差 2px）{extra}")

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
# v1.8：先剥离内嵌图片的 base64 数据再计数——base64 是随机字节编码，大文件天然可能
# 碰巧含 "TODO" 等序列造成假 FAIL（东京 480 案/宏村 TODO 案两撞）；模板残留只可能出现在
# 可见文本层，剥离只会减误报不会漏真报。
t_visible = re.sub(r'data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+', '', t)
ph_hits = {}
for ph in ["__CITY__", "【目的地】", "TODO", "Lorem"]:
    n = t_visible.count(ph)
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
    if fp == "9f1fd4856f":
        addp("骨架指纹", fp)
    else:
        addw("骨架指纹", f"{fp} ≠ 基准 9f1fd4856f——若是刻意改样式需在交付说明注明，否则=派生自旧骨架")
else:
    addw("骨架指纹", "未找到 style 块")

# ---------- 6.5 移动端表格列宽（v1.3，2026-10-10 山东版手机竖排案） ----------
# 注意：成品可能有多个 max-width:900px 块（如 photos 单行块），必须全部遍历，search 会提前截止误报
mqs = re.findall(r"@media\s*\(max-width:900px\)\{(.*?)\n\}", t, re.S)
if mqs and ".tb" in t:
    if any("table-layout:fixed" in b for b in mqs):
        addp("移动端表格布局", "fixed 已配（colgroup 按列型在成品层）")
    else:
        addw("移动端表格布局", "媒体查询无 table-layout:fixed——手机窄屏表格列宽失衡竖排风险（山东 10/10 案）；老成品可人工放行待升级")

# ---------- 6.6 导航「今天」重复标记（v1.4，2026-10-10 实战定性——正文徽章已承担今日标识，导航禁再挂） ----------
if "navA.innerHTML" in t:
    addw("导航今天标记", "script 含 navA.innerHTML 当日文字/圆点注入——导航重复标识已废止（v3.64）应删；今日标识由正文 today-badge 承担")
else:
    addp("导航今天标记", "无（信息归位正文徽章）")

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
lkeys = sorted(
    set(m.group(2) for m in re.finditer(r"localStorage\.\w+\((['\"])([\w-]+)\1", t))
    # v1.5：补抓「前缀拼接形态」键——tky_chk_ 曾以字符串常量藏在 script 里漏检（山东版 10/10 双窗合并仲裁案：font 键修了 chk 键没修=双键盲区）
    | set(m.group(1) for m in re.finditer(r"['\"](\w{2,5}_(?:chk|font)[\w-]*)['\"]", t))
)
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

# ---------- 7g. 必答清单关键词抽查（v1.2，实战反馈：不希望再出现老问题） ----------
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

# ---------- v1.6 形态检查组（2026-10-12 桂林册夜四连打回反哺） ----------
mor = []
# ① eyebrow 措辞白名单（v3.57 正本集 ∪ 老成品历史口径——新口径优先，老口径放行老成品）
EB_WHITELIST = {"总览", "路程", "备选 · 想多玩这样加", "门票 · 预约", "真实场景 · 提前知道", "住宿", "预算", "应急",
                "照着吃就行", "回来带点啥", "特产 · 带一份回家", "提示", "总览 · 行程速览", "路程 · 交通串联",
                "每段开多久", "进门花多少", "心里有数", "可选 · 更从容", "温馨提示"}
for eb in re.findall(r'class="eyebrow">([^<]*)<', t):
    eb = eb.strip()
    if eb and eb not in EB_WHITELIST:
        mor.append((f"eyebrow 自创「{eb[:20]}」", "v3.57 正本=武汉式主题词·补充语（正本集见 checklist 源码 EB_WHITELIST），自创措辞=执行偏差"))
# ② 冷知识卡逐日（v3.58 固定件：实战定规「以后的路书都要保留」）
day_secs = re.findall(r'<section id="day\d+">.*?</section>', t, re.S)
no_kn = [i + 1 for i, d in enumerate(day_secs) if "你知道吗" not in d]
if day_secs and no_kn:
    mor.append((f"冷知识卡缺 {no_kn}", "v3.58 固定件：每日「💡你知道吗：」一条（放 Plan B 后），真·冷知识禁编造"))
# ③ 机位三条全覆盖（v3.59：位置+时段+拍法）
no_jw = [i + 1 for i, d in enumerate(day_secs) if "📷 位置：" not in d]
if day_secs and no_jw:
    mor.append((f"机位信息缺 {no_jw}", "v3.59 机位标准：每日至少 1 处「📷 位置：…｜时段：…｜拍法：…」三条全灰字"))
# ④ 参数速查卡（v3.59③：机位日汇总废止后并入 tips）
if tt is not None and "拍摄参数速查卡" not in tt:
    mor.append(("tips 缺拍摄参数速查卡", "v3.59③：特殊场景参数（夜景/日落/一人行自拍分 iPhone 安卓）归 tips 速查卡"))
# ⑤ nav 日链接格式（v3.27 导航族：第 N 天 · 主题）
bad_nav = [h for h in re.findall(r'<a href="#day\d+"[^>]*>([^<]*)</a>', t) if not re.match(r"第 \d+ 天 · ", h.strip())]
if bad_nav:
    mor.append((f"nav 格式违规 {len(bad_nav)} 处", f"v3.27 导航族=「第 N 天 · 主题」两字短名式；实测样本: {bad_nav[:2]}（D1 代号=偷懒替换骨架占位符案）"))
# ⑥ eat 表头备选列（每餐 2 家，09-25 打回「只给 1 家=偏少」）
if et is not None and "备选" not in et:
    mor.append(("美食表无备选列", "每餐主推+备选 ≥2 家（09-25 打回单店案）"))
# ⑦ figcaption（示意）双写
if re.search(r"（示意）[^<]*（示意）", t):
    mor.append(("figcaption「（示意）」双写", "嵌入脚本 mark+cap 双带示意标记案——渲染出「（示意）xxx（示意）」"))
# ⑧ 尾部占位（移动端工具条遮挡，镇江 9/10 老坑）
if VISUAL and "tailpad" not in t:
    mor.append(("缺尾部工具条占位", "移动端底部工具条遮挡正文最后一行（镇江 9/10 老坑）——内容尾部加 height:96px 占位"))
if mor:
    addf("形态检查", "；".join(n for n, _ in mor) + " —— 对照 skill 形态条款逐项修（老成品跑 v1.6 报 ②③④⑥⑧ 按惯例人工放行）")
else:
    addp("形态检查", "eyebrow 正本/冷知识逐日/机位三条全/参数速查卡/nav 格式/备选列/示意单写/尾部占位 八项全在位")


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
            for w, h, tag in [(1280, 900, "桌面1280"), (768, 1024, "平板768"), (390, 844, "手机390"), (320, 568, "小屏320")]:
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
            for _ in range(80):
                # v1.4：滚到页底为止——固定 15 步=15000px，长页后半图没滚到=懒加载没触发误报死图（山东版 4/10 实锤 2026-10-10）
                pg.evaluate("() => window.scrollBy(0, 1000)")
                pg.wait_for_timeout(200)
                if pg.evaluate("() => Math.ceil(window.scrollY + window.innerHeight) >= document.documentElement.scrollHeight - 5"):
                    break
            pg.wait_for_timeout(800)
            dead = pg.evaluate("""() => Array.from(document.querySelectorAll('figure img')).filter(
                im => !(im.naturalWidth > 0 && im.getBoundingClientRect().width > 50)).length""")
            if n_fig == 0:
                addw("图渲染", "页面 0 张 figure img（若配图对称律 PASS 则图在结构外，人工确认）")
            elif dead:
                # v1.4 二次确认：死图可能是懒加载时序（IO 触发晚/解码慢）而非真坏——回顶再滚底重查一次，仍死才 FAIL
                pg.evaluate("() => window.scrollTo(0, 0)")
                pg.wait_for_timeout(400)
                for _ in range(80):
                    pg.evaluate("() => window.scrollBy(0, 1000)")
                    pg.wait_for_timeout(150)
                    if pg.evaluate("() => Math.ceil(window.scrollY + window.innerHeight) >= document.documentElement.scrollHeight - 5"):
                        break
                pg.wait_for_timeout(1200)
                dead2 = pg.evaluate("""() => Array.from(document.querySelectorAll('figure img')).filter(
                    im => !(im.naturalWidth > 0 && im.getBoundingClientRect().width > 50)).length""")
                if dead2:
                    addf("图渲染", f"{dead2}/{n_fig} 张未真渲染（二次确认仍死）——base64 损坏或引用失效")
                else:
                    addp("图渲染", f"{n_fig}/{n_fig} 张真渲染（首轮 {dead} 张为懒加载时序，二次确认放行）")
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
    # ---------- 修复指引（v1.9a，Gemini 方案增量②：局部修补替代推倒重来——每 FAIL 项给「修哪」提示） ----------
    FIX_HINTS = {
        "区块完备": "缺哪个区块补哪个 section；只补缺件，禁全文重写",
        "天数前置校验": "核对行程天数与 day 区块数量；跳号=补缺失 day 或改编号",
        "每日餐行": "在缺失餐段词的 slot 标题/正文补「早餐/午餐/晚餐」字面词——只改对应 slot",
        "slot 时间线": "乱序=调换 slot 顺序；重复餐段=改其中一行的餐段词或合并——只动涉及行",
        "动线图出界": "扩 bbox 重拼底图（覆盖路径全程）或裁剪出界点——禁手调坐标数字",
        "每日配图对称律": "缺图日补到 2 或 4 张（禁 3）；只补缺图日",
        "必答抽查": "按提示缺失件逐块补——只补缺失项，已过项不动",
        "形态检查": "按列出的形态项逐项修——只修列出的",
        "nav==DOM 顺序": "调整 nav 链接顺序与 DOM 一致——只动 nav",
        "占位符": "grep 残留【】替换为实际内容——逐处替换",
    }
    hinted = []
    for mark, name, detail in results:
        if mark == "FAIL":
            for k, v in FIX_HINTS.items():
                if k in name:
                    hinted.append(f"  🛠 {name} → {v}")
                    break
            else:
                hinted.append(f"  🛠 {name} → 定位到具体区块/字段局部修正，禁推倒重写全篇")
    print("🛠 修复指引（局部修补，禁推倒重来——同 FAIL 连续 3 轮未消→按熔断条款停手降级声明）:")
    print("\n".join(hinted))
    sys.exit(1)
if n_skip:
    print("🟡 有 SKIP（未执行的检查）——交稿时必须向用户声明哪些检查未跑。")
if n_warn:
    print("🟡 有 WARN —— 人工确认后可交稿，说明放行理由。")
if not n_fail and not n_skip:
    print("🟢 全部通过，可交稿。")

# ---------- 交付证据卡（v1.7，2026-10-15）：机械闸只证明机械项，判断项必须逐项填证据——空项=不交稿 ----------
print()
print("🧾 交付证据卡（执行者逐项填写，随产物交付；任一空项 = 未达交付标准，返工修复，不得交稿）")
print("─" * 46)
ev = [
    ("1.家族对齐 diff", "与家族中最接近成品逐段 diff（数指标不算对比）；差异 N 处、修几处、不修的理由？"),
    ("2.信息归位抽查", "抽 2-3 个高频信息（门票/防晒/预约类）grep 全文落区数——同一信息 ≥2 个叙事区整句重复=违规"),
    ("3.配图逐张亲验", "配图 N 张导出验 N/N？图注落位对 ≠ 图内容对，两层分开验"),
    ("4.双视口截图亲验", "桌面+手机各 ≥1 张真机视口截图；手机端工具条/遮挡/溢出重点看"),
    ("5.通读去AI味", "标题+各板块通读一遍；grep 高频词（进行/值得注意/仿佛/为您/标志着…）N 处"),
    ("6.脱敏逐词", "内部词 grep：博主名/平台内部ID/内部路径/称谓 = 0？朋友版与发布口径一致？"),
]
for k, q in ev:
    print(f"□ {k}：{q}")
print("─" * 46)
print("填写格式：每项一行「✅/❌ + 证据（命令输出/计数/文件路径）」；❌ 或空 = 返工修复后重跑本闸。")

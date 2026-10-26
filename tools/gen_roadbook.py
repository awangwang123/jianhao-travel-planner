# -*- coding: utf-8 -*-
"""
gen_roadbook.py —— P3 M2 渲染引擎 v0.1
输入: pilot_italy/trip_data.json + 基准骨架（style 指纹不动）
输出: pilot_italy/render_v01.html
范围: overview/day1-3/cost/sos 全渲染（带 data-ref 溯源）；day4-5/intel 删除；
      drive/boost/ticket/tips/stay/eat/gift = v0.1 占位（后续里程碑补）
验收: 骨架指纹断言 + checklist v1.9 + 人工对比
"""
import io, json, re, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pricing import expense_mult  # 计费口径唯一正本（Codex 五轮复核）
from fact import fact_display, resolve_slot_t, fill_slot_text  # 事实展示派生唯一正本（R6 fact 接通；R8 引用派生；R9 文案占位符）

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "pilot_italy", "trip_data.json")
OUT = os.path.join(ROOT, "pilot_italy", "render_v02.html")
SKELETON = os.path.join(ROOT, "assets", "路书_基准骨架.html")  # 发布包版：骨架随包分发（包内 assets/），不依赖本机 skill 安装
FINGERPRINT = "9f1fd4856f"  # 骨架 CSS 指纹（v2 设计: style 禁碰）


def load():
    d = json.load(io.open(DATA, encoding="utf-8"))
    h = io.open(SKELETON, encoding="utf-8").read()
    assert FINGERPRINT in h, "骨架指纹缺失"
    return d, h


# ---------- 组件（带 data-ref 溯源=3.2 责任层判定的基础设施） ----------
def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slot(t, body, ref=None, sid=None):
    dr = ' data-ref="%s"' % ref if ref else ""
    si = ' data-slot-id="%s"' % sid if sid else ""  # v1.1：稳定 id 上 DOM，归属可追溯（Codex 四轮复核）
    return ('<div class="slot"%s%s><div class="slot-time">%s</div>'
            '<div class="slot-body">%s</div></div>' % (dr, si, esc(t), body))


def day_head(no, date, city, theme):
    return ('<div class="day-head"><span class="day-idx">DAY %d · %s</span>'
            '<h3>%s · %s</h3><span class="today-badge">· 今天</span></div>'
            % (no, esc(date), esc(city), esc(theme)))


def cam_row(c):
    return ('<div style="font-size:.78rem;color:var(--ink3);margin-top:6px">'
            "📷 位置：%s｜时段：%s｜拍法：%s</div>"
            % (esc(c.get("spot")), esc(c.get("time")), esc(c.get("how"))))


def noterow(ic, label, text):
    if not text:
        return ""
    return ('<div class="note-row"><span class="ic">%s</span>'
            "<span><b>%s：</b>%s</span></div>" % (ic, esc(label), esc(text)))


def replace_section(html, sec_id, new_content):
    pat = re.compile(r'<section id="' + sec_id + r'">.*?</section>', re.S)
    assert pat.search(html), "section %s 不存在" % sec_id
    return pat.sub(lambda m: '<section id="' + sec_id + '">\n' + new_content + "\n</section>",
                   html, count=1)


def drop_section(html, sec_id):
    pat = re.compile(r'\s*<section id="' + sec_id + r'">.*?</section>', re.S)
    assert pat.search(html), "待删 section %s 不存在" % sec_id
    return pat.sub("", html, count=1)


# ---------- 渲染 ----------
def idx(data):
    m = {}
    for t in ("tickets", "stays", "meals", "flights", "transports", "misc"):
        for r in data.get(t) or []:
            m[r["id"]] = r
    return m


def r_day(d, I):
    """v0.4 数据驱动渲染：day 块=骨架注释官方结构（作者 17:xx 打回修正版）
    顺序：day-head → 🧭今日速览 → 动线图 → photos → .slot×N（机位灰字小字紧随对应 slot=v3.56③）
    → Plan B → 你知道吗。作者拍板：删「今日交通/住」卡片（内容少时显空）；引用名不进正文"""
    parts = []
    label = d.get("label") or d.get("date", "")
    h3 = d.get("h3") or ("%s · %s" % (d.get("city", ""), d.get("theme", "")))
    parts.append('<div class="day-head"><span class="day-idx">DAY %d · %s</span>'
                 '<h3>%s</h3><span class="today-badge">· 今天</span></div>'
                 % (d["day"], esc(label), esc(h3)))
    if d.get("brief"):
        parts.append(noterow("🧭", "今日速览", d["brief"]))
    if d.get("svg_html"):
        parts.append(d["svg_html"])  # 每日动线图（真底图 SVG，家族基准件）
    if d.get("photos_html"):
        # B17（Codex 十/十一轮）：列布局全部交给 CSS 类（行内 flex 会压过媒体查询——手机单列失效根因）。
        # 数据只供 figure；单图 :only-child 全宽、双图各半、≤768px 单列，全部在统一 style 块定义
        ph = '<div class="pp">' + d["photos_html"] + "</div>"
        parts.append(ph)
    slot_text = " ".join((s.get("text") or "")[:40] for s in (d.get("slots") or []))
    slot_refs = {s.get("ref") for s in (d.get("slots") or []) if s.get("ref")}
    for s in d.get("slots") or []:
        body = s.get("text", "")  # 受信数据：家族形态文本内嵌 <b> 加粗（esc 会把加粗变字面文本）
        ref = s.get("ref")
        if ref:  # R9：班次时刻文案占位符 {dep}/{arr} 由正本填充（同一班次时刻不手写两处）
            body = fill_slot_text(body, I.get(ref), "days[%s] slot %s" % (d.get("day"), s.get("id")))
        # v3.56③ 机位=slot-body 内部子 div（宏村 DOM 真身：<div class="slot-body">…<div style="灰字">📷…</div></div>）
        # 独立平级 div 会视觉"顶出来"——作者 10-21 点破的排版问题
        # v1.1 机位挂 slot_ref（稳定 id）——slot_t 时间字符串匹配已废弃
        #（Codex 变更实验 2026-10-21：改时段文字即静默丢机位）
        cam_html = "".join(cam_row(c) for c in (d.get("cam") or [])
                           if c.get("slot_ref") == s.get("id"))
        # R6 正文 fact 接通 + R8 引用派生：slot.t 支持 fact 结构与 {tr_ref, field} 引用形态——
        # 引用形态查业务记录正本派生（改正本一处，正文/表格/导览图自动同步，核实状态不丢）
        t_disp = s.get("t", "")
        if isinstance(t_disp, dict):
            t_disp = resolve_slot_t(t_disp, I, "days[%s] slot %s" % (d.get("day"), s.get("id")))
        if isinstance(t_disp, dict):
            t_disp = fact_display(t_disp, "days[%s] slot %s" % (d.get("day"), s.get("id")))
        parts.append(slot(t_disp, body + cam_html, ref, s.get("id")))
    # 餐段=融进 slots 文本（家族形态：「早餐·XX：<b>」时段块）；尾部不再补餐行
    # （旧版 meals 尾部补渲=早餐错排到当天末尾；数据 meals 仅作关联备查）
    for c in (d.get("cam") or []):  # 无 slot_ref 的机位兜底（不绑时段的全天型机位，排当日尾部）
        if not c.get("slot_ref"):
            parts.append(cam_row(c))
    if d.get("planb"):
        parts.append('<div class="note-row" style="background:var(--warn-soft)">'
                     '<span class="ic">🛟</span><span><b>当日 Plan B：</b>%s</span></div>'
                     % esc(d["planb"]))
    if d.get("knowhow"):
        parts.append(noterow("💡", "你知道吗", d["knowhow"]))
    return "\n".join(p for p in parts if p)


def r_overview(data):
    m = data["meta"]
    fx = m["fx"][0]
    lead1 = ("%s｜%s → %s｜%s｜%s" % (
        m["destination"], m["home_city"],
        m["date_window"]["start"] + "~" + m["date_window"]["end"],
        "%d 成人" % m["pax"]["adults"] if not m["pax"].get("children") else "%d 大 %d 小" % (
            m["pax"]["adults"], m["pax"]["children"]),
        {"fast": "快速档", "standard": "标准档", "premium": "精装档"}.get(m.get("tier"), m.get("tier"))))
    lead2 = ("时差 %s（%s）｜汇率 %s→%s %.3f（%s 查）" % (
        m["timezones"][0]["utc_offset"], m["timezones"][0]["area"],
        fx["base"], fx["quote"], fx["rate"], fx["checked_at"]))
    return "\n".join([
        '<p class="eyebrow">总览</p>',
        '<h1 style="font-size:2rem;margin:.2em 0 .3em">%s</h1>' % esc(m["title"]),
        '<p class="lead">%s</p>' % esc(lead1),
        '<p class="lead">%s</p>' % esc(lead2),
        '<div class="warn-line">⚠️ 本页由 P3 渲染引擎 v0.1 从 trip_data.json 生成——'
        '「改一处数据、全页更新」试点（M2 里程碑 1）。</div>',
    ])


def r_cost(data):
    """v0.4/M4 新册预算=程序按费用明细账细算（回填册走基线原版直渲，本函数不接）
    形态对齐家族基准（宏村/意册）：人话标题+口径 lead+三卡+明细表+尾注（含隐藏成本行）"""
    m = data["meta"]
    fx = m["fx"]
    target = fx[0]["quote"]
    rates = {(f["base"], f["quote"]): f["rate"] for f in fx}
    total_lo = total_hi = 0.0
    paid_lo = paid_hi = 0.0
    pend = est = 0
    lines = []
    cat_sum = {}  # 大头项统计（B13：三数字卡=总计/人均/大头项）
    pend_items = []  # 待核逐项披露（替代旧计数卡）
    pax_all = m["pax"]["adults"] + m["pax"].get("children", 0)
    for e in data.get("expenses") or []:
        if e.get("tier") != "主选" or (e.get("inclusion") or {}).get("included_in"):
            continue
        vs = e.get("verify_status")
        if vs == "pending":
            pend += 1
            pend_items.append(e)
            continue
        if vs == "estimated":
            est += 1
        cur = e["currency"]
        rate = 1.0 if cur == target else rates.get((cur, target))
        lo = e.get("amount", e.get("amount_min"))
        hi = e.get("amount", e.get("amount_max"))
        if lo is None or rate is None:
            continue
        mult = e.get("qty", 1) * expense_mult(e, pax_all)  # 口径按 unit 分派（每间夜禁乘人头）
        if e.get("price_mode") == "净价+税":
            mult *= 1 + (e.get("tax_rate") or 0)
        lo_c, hi_c = lo * mult * rate, hi * mult * rate
        total_lo += lo_c
        total_hi += hi_c
        cat_sum[e.get("category", "杂项")] = cat_sum.get(e.get("category", "杂项"), 0) + lo_c
        if e.get("pay_status") == "已付":
            paid_lo += lo_c
            paid_hi += hi_c
        # B14（Codex 六轮）：乘数系数>1 时在金额格里展示推导链，读者可复算
        unit = e.get("unit", "")
        qty = e.get("qty", 1)
        coef = qty * expense_mult(e, pax_all)
        if e.get("amount") is not None:
            amt_s = "%.0f" % e["amount"]
        else:
            amt_s = "%s~%s" % (lo, hi)
        if coef > 1:
            unit_cn = {"每人": "/人", "每间夜": "/晚", "每晚": "/晚", "每天": "/天"}.get(unit, "")
            base = e.get("amount", lo)
            amt_s += "（%s%s ×%s = %.0f）" % (base, unit_cn, qty, lo_c)
        lines.append((e.get("category", "杂项"), e.get("label", "?"), amt_s,
                      e.get("source", "")))
    th = '<tr><th>项</th><th>估算（%s）</th><th>说明/来源</th></tr>' % target
    trs = "".join("<tr><td>%s</td><td>%s</td><td style='font-size:.85rem'>%s</td></tr>" % (r[1], r[2], r[3]) for r in lines)
    big_cat = max(cat_sum, key=cat_sum.get) if cat_sum else "—"
    big_item = "%s %.0f 元" % (big_cat, cat_sum.get(big_cat, 0)) if cat_sum else "—"
    pend_lines = ""
    if pend_items:
        rows = "".join("<li>%s（%s %s）</li>" % (e.get("label", "?"), e.get("amount", e.get("amount_min", "?")), e.get("currency", ""))
                       for e in pend_items)
        pend_lines = ('<div class="warn-line" style="margin-top:10px">⚠ 待核未计入合计：'
                      '<ul style="margin:6px 0 0 18px">%s</ul></div>' % rows)
    n_pax = m["pax"]["adults"] + m["pax"].get("children", 0)
    per = "（人均同额）" if n_pax == 1 else "（%d 人分摊）" % n_pax
    return "\n".join([
        '<div class="eyebrow">心里有数</div>',
        '<h2>预算（主案口径）</h2>',
        '<p class="lead">口径=主案全链花销（不含购物与替代差额，替代见尾注）；金额为实查/估算，'
        '估算项逐条标注；自选项单列不进合计；1 人出行合计即人均。</p>',
        '<div class="stats" style="display:flex;flex-wrap:wrap;gap:8px">',
        '  <div class="stat"><div class="n">%.0f~%.0f</div><div class="l">合计 %s%s</div></div>' % (total_lo, total_hi, target, per),
        '  <div class="stat"><div class="n">%.0f~%.0f</div><div class="l">人均 %s</div></div>' % (total_lo / max(pax_all, 1), total_hi / max(pax_all, 1), target),
        '  <div class="stat"><div class="n">%s</div><div class="l">大头项</div></div>' % big_item,
        "</div>",
        (pend_lines if pend_lines else ""),
        '<div style="overflow-x:auto"><table class="tb">'
        '<colgroup><col style="width:20%%"><col style="width:15%%"><col style="width:65%%"></colgroup>'
        '%s%s</table></div>' % (th, trs),
        '<p style="font-size:.86rem;color:var(--ink2);margin-top:12px">'
        '<b>自选另计</b>：%s——不进主线合计。%s</p>'
        % (data["meta"].get("optional_note", "无"),
           data["meta"].get("budget_tail_note", "")),
    ])


def r_eat(data):
    """v0.4 结构化渲染：eat=数据驱动（eyebrow/h2/lead 整段+按天分组表）
    行格式与基线逐字节对齐：tr 每行一个、表间空行、tail 段空行"""
    E = data.get("eat_structured")
    if not E:
        return None
    parts = ['<div class="eyebrow">%s</div>' % E["eyebrow"],
             "<h2>%s</h2>" % E["h2"],
             '<p class="lead">%s</p>' % E["lead"],
             '']
    for g in E["groups"]:
        parts.append('<p style="font-weight:700;margin:12px 0 4px">%s</p>' % g["title"])
        cg = "".join('<col style="width:%s">' % w for w in g["widths"])
        th = "".join("<th>%s</th>" % c for c in g["cols"])
        trs = "\n".join("<tr>" + "".join("<td>%s</td>" % c for c in row) + "</tr>"
                        for row in g["rows"])
        parts.append('<table class="tb"><colgroup>%s</colgroup>\n<tr>%s</tr>\n%s\n</table>'
                     % (cg, th, trs))
        parts.append('')
    if E.get("tail_title"):
        parts.append('<p style="font-weight:700;margin:12px 0 4px">%s</p>' % E["tail_title"])
        parts.append('<p style="font-size:.9rem;line-height:1.75">%s</p>' % E["tail_body"])
        parts.append('')
    for card in (E.get("tail_cards") or []):
        parts.append(card)
    if E.get("tail_footer"):
        parts.append(E["tail_footer"])
    return "\n".join(parts)


def _overflow_table(tb):
    """overflow-x 包裹表格（thead/tbody 结构，colgroup/thead/tbody 2 空格、tr 4 空格）
    ticket/stay 同族版式共用"""
    cg = "".join('<col style="width:%s">' % w for w in tb["widths"])
    th = "".join("<th>%s</th>" % c for c in tb["cols"])
    trs = "\n".join("    <tr>" + "".join("<td>%s</td>" % c for c in row) + "</tr>"
                    for row in tb["rows"])
    return ('<div style="overflow-x:auto"><table class="tb">\n'
            '  <colgroup>%s</colgroup>\n'
            '  <thead><tr>%s</tr></thead>\n'
            '  <tbody>\n%s\n  </tbody>\n'
            '</table></div>' % (cg, th, trs))


def _r_head_table_tail(S):
    """通用：eyebrow/h2/[lead 可选] + overflow-x 表格 + 尾部块列表
    ticket/stay/drive/gift 同构（gift 无 lead 由 lead=None 跳过）"""
    parts = ['<div class="eyebrow">%s</div>' % S["eyebrow"],
             "<h2>%s</h2>" % S["h2"]]
    if S.get("lead"):
        parts.append('<p class="lead">%s</p>' % S["lead"])
    parts.append(_overflow_table(S["table"]))
    parts.extend(S.get("tail_notes") or [])
    return "\n".join(parts)


def r_ticket(data):
    """v0.4 结构化渲染：ticket=数据驱动（头部三件套+overflow-x 表格+尾注）
    门票价格单源：行挂 _row_refs→tickets 业务表 price_display 覆盖价格列（改一处全联动）"""
    T = data.get("ticket_structured")
    if not T:
        return None
    parts = ['<div class="eyebrow">%s</div>' % T["eyebrow"],
             "<h2>%s</h2>" % T["h2"]]
    if T.get("lead"):
        parts.append('<p class="lead">%s</p>' % T["lead"])
    tb = T["table"]
    rows = [list(r) for r in tb["rows"]]
    refs = tb.get("_row_refs") or []
    idx = {t["id"]: t for t in data.get("tickets") or []}
    # 门票价格单源=expenses 费用明细账（schema 总纪律：金额唯一出现处=明细账）
    # 改一处（expenses.amount）→ 门票表+预算同时更新（Codex 五轮复核：拆两个测试绕开单源=假通过）
    exp_by_ref = {}
    for e in data.get("expenses") or []:
        if e.get("ref") and e.get("tier") == "主选":
            exp_by_ref.setdefault(e["ref"], e)
    legacy = 0
    dropped = []
    kept_rows, kept_refs = [], []
    # R10 修复（demo 样本暴露）：无 _row_refs 时必须原样渲染 rows——
    # 旧逻辑 refs 空时 kept 循环不执行、rows 被空列表顶替=整表被清空
    if refs:
        for i, ref in enumerate(refs):
            if ref not in idx:  # 失效引用：删行+WARN，禁继续显示旧行（Codex 六轮复核）
                dropped.append(ref)
                continue
            if i >= len(rows):
                continue
            kept_rows.append(rows[i])
            kept_refs.append(ref)
        rows, refs = kept_rows, kept_refs
    # refs 为空：保留原 rows 原样渲染（存量无引用数据兼容路径）
    if dropped:
        print("⚠ ticket 表删除 %d 行失效引用（业务记录已不存在）: %s" % (len(dropped), dropped))
    for i, ref in enumerate(refs):
        # 价格轨：优先费用明细（单源）；缺失才走 price_display 兼容回退
        # （Codex 九轮：上一版把说明列的 if 插进本 if/elif 链中间，回退被劫持——价格与说明必须独立双轨）
        e = exp_by_ref.get(ref)
        if e is not None and e.get("amount") is not None:
            cur = e.get("currency", "CNY")
            rows[i][1] = ("%.0f 元" % e["amount"]) if cur == "CNY" else ("%.0f %s" % (e["amount"], cur))
        elif idx[ref].get("price_display"):
            rows[i][1] = idx[ref]["price_display"]  # 兼容回退：expenses 无对应明细时用旧字段
            legacy += 1
        # 说明轨（B07 八/九轮）：优先业务正文；缺失显式未核实兜底，禁保留静态确定句
        if idx[ref].get("text"):
            rows[i][2] = idx[ref]["text"]
        else:
            rows[i][2] = "【未核实】跨日/预约规则以官方小程序为准"
    if legacy:
        print("⚠ ticket 表 %d 行价格来自 price_display 旧字段（expenses 无对应明细）——"
              "应补明细账实现单源" % legacy)
    cg = "".join('<col style="width:%s">' % w for w in tb["widths"])
    th = "".join("<th>%s</th>" % c for c in tb["cols"])
    trs = "\n".join("    <tr>" + "".join("<td>%s</td>" % c for c in row) + "</tr>"
                    for row in rows)
    parts.append('<div style="overflow-x:auto"><table class="tb">\n'
                 '  <colgroup>%s</colgroup>\n'
                 '  <thead><tr>%s</tr></thead>\n'
                 '  <tbody>\n%s\n  </tbody>\n'
                 '</table></div>' % (cg, th, trs))
    parts.extend(T.get("tail_notes") or [])
    return "\n".join(parts)


def r_stay(data):
    """v0.4 结构化渲染：stay=数据驱动（同 ticket 版式，尾部=订房问三样 <p>）"""
    S = data.get("stay_structured")
    return _r_head_table_tail(S) if S else None


def _hhmm_min(s):
    """从展示文字开头解析 HH:MM → 分钟数；解析失败返回 None（「08:30（未核实）」可解析；
    fact 多值长文案「来源 X 为…，待确认」不可解析→自然降级不派生时长）"""
    m = re.match(r"\s*(\d{1,2}):(\d{2})", str(s or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def r_drive(data):
    """v0.4 结构化渲染：drive=数据驱动（同 ticket 版式，尾部=时差 <p>+机场 note-row 两块）
    R6 时刻单源：行挂 _row_refs→transports 业务表 dep/arr 覆盖时刻列（改一处全联动，
    模式同门票价格单源先例）；dep/arr 支持 fact 结构（fact_display 派生，核实状态不丢）。
    时长自动派生仅限两端可解析 HH:MM（同日同时区；跨日加 24h 口径；时差直减属出境规则后续工程，
    候选冲突长文案不派生时长自然降级）。无 _row_refs 的行保持自由文本原样（存量兼容）。"""
    D = data.get("drive_structured")
    if not D:
        return None
    tb = D.get("table") or {}
    refs = tb.get("_row_refs") or []
    if refs:
        import copy as _copy
        D = _copy.deepcopy(D)  # 不改调用方数据
        tb = D["table"]
        rows = [list(r) for r in tb["rows"]]
        tr_idx = {t.get("id"): t for t in data.get("transports") or [] if t.get("id")}

        def _disp(x, where):
            if isinstance(x, dict) and "candidates" in x:
                return fact_display(x, where)
            return str(x) if x is not None else ""

        dropped, kept = [], []
        for i, ref in enumerate(refs):
            if i >= len(rows):
                continue
            tr = tr_idx.get(ref)
            if tr is None:  # 失效引用：删行+WARN，禁继续显示旧行（同门票单源纪律）
                dropped.append(ref)
                continue
            kept.append((rows[i], tr))
        if dropped:
            print("⚠ drive 表删除 %d 行失效引用（transports 记录已不存在）: %s" % (len(dropped), dropped))
        for row, tr in kept:
            ap = tr.get("applicability") or {}
            dep = _disp(ap.get("dep_time"), "drive ref %s dep_time" % tr.get("id"))
            arr = _disp(ap.get("arr_time"), "drive ref %s arr_time" % tr.get("id"))
            if dep and arr:
                cell = "%s→%s" % (dep, arr)
                m1, m2 = _hhmm_min(dep), _hhmm_min(arr)
                if m1 is not None and m2 is not None:
                    dur = (m2 - m1) if m2 >= m1 else (m2 - m1 + 24 * 60)
                    cell += "（%dh%02dm）" % (dur // 60, dur % 60)
                row[2] = cell
        tb["rows"] = rows
    return _r_head_table_tail(D)


def r_overview_body(data):
    """v0.4 结构化渲染：overview 主体=数据驱动（eyebrow/h1/lead×2/warn-line/weather 3 格/
    气温口径 p/figure 图行/note-row）。figure_html 暂整行存数据（图独立存=后续优化）。
    leads 支持 {date_range} 占位符=从 meta.date_window 派生（改窗口总览自动同步，Codex 六轮复核）。"""
    O = data.get("overview_structured")
    if not O:
        return None
    m = data["meta"]
    dw_s, dw_e = m["date_window"]["start"][5:], m["date_window"]["end"][5:]
    parts = ['<p class="eyebrow">%s</p>' % O["eyebrow"],
             '<h1 style="font-size:2rem;margin:.2em 0 .3em">%s</h1>' % O["h1"]]
    parts.extend('<p class="lead">%s</p>' % ld.replace("{date_range}", "%s~%s" % (dw_s, dw_e))
                 for ld in O["leads"])
    parts.append('<div class="warn-line">%s</div>' % O["warn_line"])
    wdays = "\n".join(
        '  <div class="wday"><div class="d">%s</div><div class="w">%s</div><div class="t">%s</div></div>'
        % (w["d"], w["w"], w["t"]) for w in O["weather"])
    parts.append('<div class="weather">\n%s\n</div>' % wdays)
    parts.append(O["weather_note"])
    # B17（Codex 十轮）：总览图同入 .pp 容器（img max-width 约束全局生效，裸 1280px 图=四视口溢出真凶）
    parts.append('<div class="pp" style="display:flex;flex-wrap:wrap;gap:8px">' + O["figure_html"] + "</div>")
    parts.append(O["tail_note"])
    # B16（Codex 六轮）：总览动线图=家族基准件（无则缺件，由数据提供 route_svg_html）
    if O.get("route_svg_html"):
        parts.append(O["route_svg_html"])
    parts.append(O["tail_note"])
    return "\n".join(parts)


def r_prep_gear(data):
    """v0.4 结构化渲染：prep_gear=数据驱动（勾选卡循环：倒计时卡+装备卡）
    li 版式：hot 标记+checkbox id+ct span；引导/尾部 <p> 可选。拼在 overview 主体后。"""
    P = data.get("prep_structured")
    if not P:
        return None
    out = []
    for c in P["cards"]:
        lines = ['<div class="card" %s>' % c["card_attr"],
                 '  <div class="eyebrow" style="margin-bottom:6px">%s</div>' % c["eyebrow"]]
        if c.get("lead_p"):
            lines.append('  <p style="font-size:.9rem">%s</p>' % c["lead_p"])
        lines.append('  <ul class="check">')
        for it in c["items"]:
            hot = ' class="hot"' if it.get("hot") else ""
            lines.append('    <li%s><input type="checkbox" id="%s"><span class="ct">%s</span></li>'
                         % (hot, it["id"], it["html"]))
        lines.append('  </ul>')
        if c.get("tail_p"):
            lines.append('  <p style="font-size:.9rem;margin-top:14px">%s</p>' % c["tail_p"])
        lines.append('</div>')
        out.append("\n".join(lines))
    return "\n".join(out)


def r_sos(data):
    """v0.4 结构化渲染：sos=数据驱动（eyebrow/h2/lead+sos-grid 卡片循环）
    卡片单行版式：2 空格缩进 <div class="sos"><h4>..</h4><p>..</p></div>"""
    S = data.get("sos_structured")
    if not S:
        return None
    parts = ['<div class="eyebrow">%s</div>' % S["eyebrow"],
             "<h2>%s</h2>" % S["h2"],
             '<p class="lead">%s</p>' % S["lead"]]
    cards = "\n".join('  <div class="sos"><h4>%s</h4><p>%s</p></div>' % (c["h4"], c["p"])
                      for c in S["cards"])
    parts.append('<div class="sos-grid">\n%s\n</div>' % cards)
    return "\n".join(parts)


def r_boost(data):
    """v0.4 结构化渲染：boost=数据驱动（头部三件套+单卡 p 列表
    首条裸 style、余 margin-top:10px 由 mt10 标记）"""
    S = data.get("boost_structured")
    if not S:
        return None
    parts = ['<div class="eyebrow">%s</div>' % S["eyebrow"],
             "<h2>%s</h2>" % S["h2"],
             '<p class="lead">%s</p>' % S["lead"]]
    ps = "\n".join('  <p style="font-size:.92rem%s">%s</p>'
                   % ((";margin-top:10px" if p.get("mt10") else ""), p["html"])
                   for p in S["items"])
    parts.append('<div class="card">\n%s\n</div>' % ps)
    return "\n".join(parts)


def r_gift(data):
    """v0.4 结构化渲染：gift=数据驱动（同 ticket 版式，头部无 lead）"""
    S = data.get("gift_structured")
    return _r_head_table_tail(S) if S else None


def r_tips(data):
    """v0.4 结构化渲染：tips=数据驱动（eyebrow/h2/lead+tip 卡片列表+尾部速查卡）"""
    T = data.get("tips_structured")
    if not T:
        return None
    parts = ['<div class="eyebrow">%s</div>' % T["eyebrow"],
             "<h2>%s</h2>" % T["h2"],
             '<p class="lead">%s</p>' % T["lead"]]
    tips = "\n".join('  <div class="tip"><p>%s</p></div>' % t for t in T["tips"])
    parts.append('<div class="tips">\n%s\n</div>' % tips)
    for card in (T.get("tail_cards") or []):
        parts.append(card)
    return "\n".join(parts)


SOS_BODY = """
<div class="eyebrow">应急</div>
<h2>应急 · 出状况有兜底</h2>
<div class="sos-grid">
  <div class="sos"><h4>🆘 紧急号码</h4><p>意大利报警 112｜救护 118｜外交部全球领保 +86-10-12308｜驻意使馆领保（出发前官网复核）。</p></div>
  <div class="sos"><h4>🚨 证件丢了</h4><p>辖区警察局开证明 → 使领馆补办旅行证；护照/签证页拍照存相册能加速。</p></div>
  <div class="sos"><h4>🤢 突发不适</h4><p>常用药先顶；旅行险开案例去私立医院（意私立英文服务好）。</p></div>
  <div class="sos"><h4>🚆 错过车/机</h4><p>意铁改签规则分档（D8 衔接日买 Economy 档即为此）；航班延误险+航司柜台改签。</p></div>
</div>"""

PLACEHOLDER = ('<p class="eyebrow">%s</p><p style="color:var(--ink3);font-size:.85rem">'
               "⏳ 渲染引擎 v0.1 暂未渲染本板块（M2 后续里程碑补全）。</p>")


def main():
    global DATA, OUT
    # M4：参数化数据/输出路径（回填册默认 pilot_italy；新册 gen_roadbook.py <data.json> <out.html>）
    if len(sys.argv) > 2:
        DATA, OUT = sys.argv[1], sys.argv[2]
    data, h = load()
    I = idx(data)
    m = data["meta"]
    need_days = len(data["days"])
    # 骨架扩天：克隆 day5 壳为 day6-N（插在 day5 后）
    if need_days > 5:
        m5 = re.search(r'<section id="day5">.*?</section>', h, re.S)
        assert m5, "骨架无 day5 区块可克隆"
        shell = re.sub(r'(?<=<section id="day5">).*?(?=</section>)', "", m5.group(0), flags=re.S)
        extra = "\n".join(shell.replace('id="day5"', 'id="day%d"' % i) for i in range(6, need_days + 1))
        h = h.replace(m5.group(0), m5.group(0) + "\n" + extra, 1)
    # M4：新册天数<骨架天数时删多余 section+nav 链接（day(N+1)~day5）
    if need_days < 5:
        for i in range(need_days + 1, 6):
            h = drop_section(h, "day%d" % i)
            h = re.sub(r'\s*<a href="#day%d">[^<]*</a>' % i, "", h, count=1)
    # 导航：补 day6-N 链接+全部天链接文案按数据主题重写
    nav5 = re.search(r'<a href="#day5">[^<]*</a>', h)
    if nav5 and need_days > 5:
        adds = "\n".join(
            '      <a href="#day%d">第 %d 天 · %s</a>' % (i, i, esc(data["days"][i - 1].get("nav_label") or data["days"][i - 1]["theme"])[:12])
            for i in range(6, need_days + 1))
        h = h.replace(nav5.group(0), nav5.group(0) + "\n" + adds, 1)
    for i in range(1, min(need_days, 5) + 1):
        pat = re.compile(r'(<a href="#day%d">第 %d 天 · )[^<]*(</a>)' % (i, i))
        h = pat.sub(lambda mm: mm.group(1) + esc(data["days"][i - 1].get("nav_label") or data["days"][i - 1]["theme"])[:12] + mm.group(2), h, count=1)
    # logo / logo-sub / title / 占位符与填稿指引清理
    h = h.replace('<div class="logo">【目的地】<span>.</span></div>',
                  '<div class="logo">%s<span>.</span></div>' % esc(m["destination"].split("（")[0]), 1)
    days_cn = "%d 天 %d 晚" % (need_days, max(0, need_days - 1))
    h = h.replace('<div class="logo-sub">【N 天 N 晚】 · 【人数结构】</div>',
                  '<div class="logo-sub">%s · %d 人</div>' % (days_cn, m["pax"]["adults"]), 1)
    h = h.replace("<title>【目的地】路书 · 基准骨架</title>",
                  "<title>%s · P3 渲染 v0.2</title>" % esc(m["title"]), 1)
    h = h.replace("<h2>【目的地】路书 · 【行程主题】</h2>",
                  "<h2>%s路书 · %s</h2>" % (esc(m["destination"].split("（")[0]), esc(m["title"])), 1)
    h = h.replace("__CITY__", "it")
    # v1.18: 页尾图源/动线行支持 meta 覆盖（photo_credit / photo_credit_source / route_credit）——
    # 缺省维持 Pexels/Commons+OSRM 口径不变；虚构示意册等非实拍成品必须如实覆盖，禁谎报图源
    h = h.replace("【逐张写明哪些是当地实景照、哪些是同题材示意（示意项须在 caption 标「（示意）」）】",
                  m.get("photo_credit", "Pexels+Wikimedia Commons 授权实拍（摄影师署名见各图注）"))
    h = h.replace("【自绘示意图说明：非等比例、仅供参考】",
                  m.get("route_credit", "动线为 OSRM 真实路径示意，非等比例"))
    h = h.replace("【图源】", m.get("photo_credit_source", "Pexels / Wikimedia Commons"))
    # 打印页眉+页脚占位符（先长后短，防子串先被吃；回填册靠基线切块覆盖，新册须自填）
    dw = m["date_window"]["start"].replace("2026-", "") + "~" + m["date_window"]["end"].replace("2026-", "")
    h = h.replace("【出发地】出发 · 【日期区间】 · 【人数结构】",
                  "%s出发 · %s · %d 人" % (esc(m["home_city"]), esc(dw), m["pax"]["adults"]))
    h = h.replace("【出发地】出发 · 【日期区间】",
                  "%s出发 · %s" % (esc(m["home_city"]), esc(dw)))
    h = h.replace("【实查日期】", m.get("checked_at_label", "2026-10-20"))
    h = h.replace("【人数结构】", "%d 人" % m["pax"]["adults"])
    # Codex 评审抓的两个漏网（review_v381）：①当日高亮 TRIP 日期映射（骨架写死示例日期）
    trip_js = ", ".join('"%s-%s":"day%d"' % (m["date_window"]["start"][:4], d["date"], d["day"])
                        for d in data["days"])
    h = re.sub(r'var TRIP = \{[^}]*\}', 'var TRIP = { %s }' % trip_js, h, count=1)
    h = h.replace('todayStr() < "2026-10-01"',
                  'todayStr() < "%s"' % m["date_window"]["start"])
    # ②存储键前缀（骨架默认 it=意大利残留；换本册城市码+册缩写）
    city_code = m.get("city_code", "wy")
    h = h.replace("'it_font'", "'%s_font'" % city_code)
    h = h.replace('"it_font"', '"%s_font"' % city_code)
    h = h.replace("itv_chk_", "%s_chk_" % city_code)
    # 渲染（v0.3=基线整块直渲，字节级对齐 作者 8 条反馈一次全消；v0.4=M4 新册数据驱动回退路径）
    B = data.get("blocks") or {}
    assert B.get("overview_body") or data.get("overview_structured"), \
        "缺 overview 数据源（回填册先跑 retarget_v03.py；新册填 overview_structured）"
    # v0.4 结构化渲染：overview 主体+prep_gear 拼接（无结构化时回退 blocks 直渲）
    ov_body = r_overview_body(data) or B.get("overview_body", "")
    prep = r_prep_gear(data) or B.get("prep_gear", "")
    h = replace_section(h, "overview", ov_body + "\n" + prep)
    for i in range(1, need_days + 1):
        day_html = B.get("day%d" % i) or r_day(data["days"][i - 1], I)
        h = replace_section(h, "day%d" % i, day_html)
    # cost=基线原版直渲（回填册 作者拍板）；新册无 blocks=程序细算 r_cost（明细账→预算=schema 设计）
    cost_html = B.get("cost") or r_cost(data)
    h = replace_section(h, "cost", cost_html)
    # v0.4 结构化渲染：sos（字节等价验收过则此路径替代 blocks 直渲）
    sos_html = r_sos(data)
    if sos_html:
        h = replace_section(h, "sos", sos_html)
    else:
        h = replace_section(h, "sos", B["sos"])
    # v0.4 结构化渲染：boost/gift（字节等价验收过则此路径替代 blocks 直渲）
    boost_html = r_boost(data)
    h = replace_section(h, "boost", boost_html if boost_html else B["boost"])
    gift_html = r_gift(data)
    h = replace_section(h, "gift", gift_html if gift_html else B["gift"])
    # v0.4 结构化渲染：drive（字节等价验收过则此路径替代 blocks 直渲）
    drive_html = r_drive(data)
    if drive_html:
        h = replace_section(h, "drive", drive_html)
    else:
        h = replace_section(h, "drive", B["drive"])
    # v0.4 结构化渲染：stay（字节等价验收过则此路径替代 blocks 直渲）
    stay_html = r_stay(data)
    if stay_html:
        h = replace_section(h, "stay", stay_html)
    else:
        h = replace_section(h, "stay", B["stay"])
    # v0.4 结构化渲染：ticket（字节等价验收过则此路径替代 blocks 直渲）
    ticket_html = r_ticket(data)
    if ticket_html:
        h = replace_section(h, "ticket", ticket_html)
    else:
        h = replace_section(h, "ticket", B["ticket"])
    # v0.4 结构化渲染：tips（字节等价验收过则此路径替代 blocks 直渲）
    tips_html = r_tips(data)
    if tips_html:
        h = replace_section(h, "tips", tips_html)
    else:
        h = replace_section(h, "tips", B["tips"])
    # v0.4 样板：eat 结构化渲染（字节等价验收过则此路径替代 blocks 直渲）
    eat_html = r_eat(data)
    if eat_html:
        h = replace_section(h, "eat", eat_html)
    # 底部尾部 + 附加样式（背景色等 build 阶段覆盖）
    if B.get("page_tail"):
        tail_pat = re.compile(r'</section>\s*(<footer.*?</body>)', re.S)
        gm = re.search(r'<section id="gift">.*?</section>', h, re.S)
        if gm:
            h = h[:gm.end()] + "\n" + B["page_tail"] + "\n</body></html>"
    else:
        # 新册：回填册 tailpad 在基线 page_tail 切块里；新册无 page_tail 须自补（checklist ⑧ 移动端工具条占位）
        if "tailpad" not in h:
            h = h.replace("</body>", '<div class="tailpad" style="height:96px"></div>\n</body>', 1)
    # 侧边栏+title=基线原文直渲（nav 短主题/底部署注对齐）
    if B.get("aside"):
        h = re.sub(r'<aside class="side">.*?</aside>', lambda m: B["aside"], h, count=1, flags=re.S)
    if B.get("base_title"):
        h = re.sub(r'<title>.*?</title>', lambda m: B["base_title"], h, count=1, flags=re.S)
    if B.get("extra_styles"):
        h = h.replace("</head>", "<style>\n" + B["extra_styles"] + "\n</style>\n</head>", 1)
    # 指纹终验：style 禁碰
    assert FINGERPRINT in h, "渲染后骨架指纹丢失（style 被改动=违规）"
    # B17（Codex 十/十一轮）：.pp 组件样式统一在 CSS（新增独立 style 块，不触碰骨架原 style 段）——
    # 断点切换只依赖样式表，无行内布局样式可覆盖
    h = h.replace("</head>",
                  "<style>"
                  ".pp{display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start}"
                  ".pp figure{flex:1 1 calc(50% - 4px);min-width:0;margin:0}"
                  ".pp figure:only-child{flex:1 1 100%}"
                  ".pp img{max-width:100%;height:auto;display:block}"
                  "@media(max-width:768px){.pp figure{flex-basis:100%}}"
                  "</style>\n</head>", 1)
    io.open(OUT, "w", encoding="utf-8").write(h)
    print("✅ 写出 %s（%d 字符）" % (OUT, len(h)))
    print("指纹在位：%s ✓" % FINGERPRINT)


if __name__ == "__main__":
    main()

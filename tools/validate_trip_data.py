# -*- coding: utf-8 -*-
"""
trip_data.json 校验器 v1.1 —— P3 M1（schema.md 的可执行形态）
用法: py validate_trip_data.py <trip_data.json> [--budget-out out.json]
退出码: 0=全 PASS, 1=有 FAIL, 2=用法错误
规则清单 V01~V14 见 schema.md §6（V15+ 为 v1.2 增量，同文件 §6 同步）——改规则必同步 schema.md（两处一体）
v1.1（2026-10-21）：新增 V11 组件关联稳定（slot.id / cam.slot_ref，Codex 变更实验立规）
发布包注（2026-10-22）：V12/V13（WARN 级）与 V14（FAIL 级）为 M4/M5 迭代增量，原头注释停于 V11 系笔误，本包修正
v1.2 增量：V15 路线语义闸 / V16 事实候选闸 / V18 费用三态闸 / V17 游玩开始闸（R5 终版口径：默认 09:30 起游玩，起床/吃饭/交通不入闸，bool early_ok 与 day.wake 均废弃）/ V20 时刻单源一致性闸（R6：slot.t ↔ transports dep/arr 对账，fact 派生配套）/ V19 跨日排天 + V21 时长自洽（时差直减拦）+ V22 门票日期绑定（R7：出境语义规则三条，各配好样本与必败反例）
"""
import json, sys, io, os, re
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pricing import expense_mult  # 计费口径唯一正本（Codex 五轮复核）

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------- 枚举（与 schema.md 同步） ----------
ENUMS = {
    "tier": {"主选", "备选", "可选"},
    "unit": {"每人", "每间夜", "每晚", "每次", "每天", "每单"},
    "price_mode": {"含税", "净价+税"},
    "pay_status": {"已付", "待付"},
    "verify_status": {"verified", "estimated", "pending"},
    "category": {"机票", "签证", "住宿", "城际交通", "市内交通", "门票", "餐饮", "杂项"},
    "slot_type": {"flight", "transport", "spot", "meal", "checkin", "note"},
    "meal_key": {"早餐", "午餐", "晚餐"},
    "reservation": {"必须", "建议", "免预约"},
    "meal_type": {"早餐", "午餐", "晚餐"},
    "meta_tier": {"fast", "standard", "premium"},
}
TABLE_PREFIX = {"tickets": "t", "stays": "s", "meals": "m", "flights": "f",
                "transports": "tr", "misc": "x"}
BIZ_TABLES = list(TABLE_PREFIX.keys())
TOP_REQUIRED = ["schema_version", "meta", "tickets", "stays", "meals",
                "flights", "transports", "misc", "expenses", "days"]
SLOT_REF_TABLE = {"flight": "flights", "transport": "transports",
                  "meal": "meals", "checkin": "stays"}

FIX_HINTS = {
    "V01": "检查 JSON 语法（多余逗号/引号）与顶层必备键（对照 schema.md §0）",
    "V02": "重号/前缀错：改为该表前缀的下一个可用编号，并同步更新所有引用处",
    "V03": "悬空 ref：补建对应记录，或把引用改为已存在的 id（禁删引用了事）",
    "V04": "引用类型错：ref 改指向匹配表（餐段→m、航班→f、住宿→s），或改正 slot type",
    "V05": "包含关系成环或指向不存在的明细：理顺包含链（谁含谁），被含项最终挂主选明细",
    "V06": "枚举值非法：对照 schema.md §6 枚举表改正，禁自创取值",
    "V07": "日期 YYYY-MM-DD、时差 ±HH:MM、汇率>0 且 fx.quote 全表一致、days.date=MM-DD",
    "V08": "净价+税必须带 tax_rate（小数）；区间价保证 min≤max；amount 与 min/max 至少其一",
    "V09": "days.day 必须从 1 连续编号：补齐缺失日或重排",
    "V10": "预算无法折算：为缺失币种补 meta.fx（带 checked_at+source），或改正 currency 拼写",
    "V11": "组件关联断：slots[].id 按 d{day}s{n} 补齐（day 内不重号，day 数字=所在天）；cam 补 scope 字段（绑定时段=slot+slot_ref，全天型显式 scope=day 且不带 ref），禁漏填 slot_ref 隐式代表全天",
    "V12": "机位归属启发式：spot 名应在所绑 slot 文案中出现（合法引用≠业务绑对）；WARN 提示人工确认，误报由交付通读兜底",
    "V13": "门票价格两源不一致：tickets.price_display 与对应 expenses.amount 数字不符（单源=expenses，显示字段应派生）",
    "V14": "日期不对齐：days[].date 必须 = date_window.start 推算（start+day-1 天）；总天数须与窗口闭合",
    "V17": "游玩开始口径（R5）：默认 09:30—10:00 开始游玩；早餐/交通按需安排可在此前、起床不入册——首个游玩项早于 09:30 时给该 slot 加 user_ok:{reason 写明用户选择}或移 planb 可选",
    "V20": "时刻单源不一致：班次时刻正本=transports 业务表（dep_time/arr_time），slot.t 改成与正本一致的值（或对齐 fact 候选）",
    "V19": "跨日航班排天：到达日复现同 ref 且为紧邻次日凌晨到达；到达前不排活动、起飞后不排活动、出发当夜不订房；crosses_days=true 必须排到达 slot",
    "V21": "时长自洽：duration_min=官方飞行时长（实查）；arr=dep+duration+时差（vs_home_hours）——漏加时差即「时差直减」错误",
    "V22": "门票日期绑定：applicability.date 须在行程窗口内且与实际使用日一致（绑错日=当天进不了园）",
}


class V:
    """校验上下文：收集 FAIL，输出带规则号+JSON 路径+修哪提示（M2 字段级溯源打样）"""

    def __init__(self):
        self.fails = []

    def fail(self, rule, where, msg):
        self.fails.append(rule)
        print("[FAIL] %s %s: %s" % (rule, where, msg))
        print("       🛠 修哪: %s" % FIX_HINTS.get(rule, "对照 schema.md"))

    def ok(self, rule, msg):
        print("[PASS] %s %s" % (rule, msg))


def is_list(x):
    return isinstance(x, list)


def chk_date(s):
    if not isinstance(s, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return False
    try:
        y, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
        return 1 <= m <= 12 and 1 <= d <= 31
    except Exception:
        return False


def build_id_index(data, v):
    """V02: ID 全局唯一+前缀正确。返回 id→表名 映射。"""
    idx = {}
    dup = {}
    for table in BIZ_TABLES + ["expenses", "assets"]:
        for i, rec in enumerate(data.get(table) or []):
            rid = rec.get("id")
            where = "%s[%d].id" % (table, i)
            if not rid:
                v.fail("V02", where, "缺少 id")
                continue
            prefix = {"expenses": "e", "assets": "a"}.get(table) or TABLE_PREFIX[table]
            if not str(rid).startswith(prefix):
                v.fail("V02", where, "id=%s 前缀不符（该表应为 %s*）" % (rid, prefix))
            if rid in idx:
                v.fail("V02", where, "id=%s 与 %s 重号" % (rid, dup[rid]))
            else:
                idx[rid] = table
                dup[rid] = where
    if not [f for f in v.fails if f == "V02"]:
        v.ok("V02", "ID 全局唯一+%d 个" % len(idx))
    return idx


def iter_refs(data):
    """产出 (where, ref, expected_table or None)——V03/V04 引用检查用"""
    for i, d in enumerate(data.get("days") or []):
        for j, s in enumerate(d.get("slots") or []):
            ref = s.get("ref")
            if ref:
                yield ("days[%d].slots[%d].ref" % (i, j), ref,
                       SLOT_REF_TABLE.get(s.get("type")))
        meals = d.get("meals")
        if isinstance(meals, dict):
            for mk, mv in meals.items():
                if isinstance(mv, dict) and mv.get("ref"):
                    yield ("days[%d].meals.%s.ref" % (i, mk), mv["ref"], "meals")
        st = d.get("stay")
        if isinstance(st, dict) and st.get("ref"):
            yield ("days[%d].stay.ref" % i, st["ref"], "stays")
    for k, e in enumerate(data.get("expenses") or []):
        if e.get("ref"):
            yield ("expenses[%d].ref" % k, e["ref"], BIZ_TABLES)
    # structured 板块的行级引用（ticket 表 _row_refs 等）：悬空=删天残留（Codex 六轮复核）
    ts = (data.get("ticket_structured") or {}).get("table") or {}
    for j, ref in enumerate(ts.get("_row_refs") or []):
        if ref:
            yield ("ticket_structured.table._row_refs[%d]" % j, ref, "tickets")


def check_refs(data, idx, v):
    """V03 引用存在 + V04 引用类型正确"""
    n = 0
    for where, ref, exp in iter_refs(data):
        n += 1
        if ref not in idx:
            v.fail("V03", where, "悬空引用 -> %s" % ref)
        elif exp is not None:
            tabs = set(exp) if isinstance(exp, list) else {exp}
            if idx[ref] not in tabs:
                v.fail("V04", where, "%s 在表 %s，期望类型 %s" % (ref, idx[ref], sorted(tabs)))
    if not [f for f in v.fails if f in ("V03", "V04")]:
        v.ok("V03", "引用存在（%d 处 ref 全可解析）" % n)
        v.ok("V04", "引用类型正确")


def check_inclusion(data, v):
    """V05: included_in 存在性 + 无循环（DFS 找环）"""
    expenses = data.get("expenses") or []
    exp_ids = {e.get("id") for e in expenses}
    edges = {}
    bad = False
    for k, e in enumerate(expenses):
        inc = (e.get("inclusion") or {}).get("included_in")
        if inc:
            if inc not in exp_ids:
                v.fail("V05", "expenses[%d].inclusion" % k,
                       "included_in 指向不存在的明细 %s" % inc)
                bad = True
            elif inc == e.get("id"):
                v.fail("V05", "expenses[%d].inclusion" % k, "included_in 指向自身")
                bad = True
            else:
                edges.setdefault(e.get("id"), set()).add(inc)
    # 环检测
    state = {}  # 0=未访 1=在栈 2=完成

    def dfs(node, stack):
        nonlocal bad
        state[node] = 1
        stack.append(node)
        for nxt in edges.get(node, ()):
            if state.get(nxt) == 1:
                cyc = stack[stack.index(nxt):] + [nxt]
                v.fail("V05", "expenses.inclusion", "包含关系成环: %s" % " -> ".join(cyc))
                bad = True
            elif state.get(nxt, 0) == 0:
                dfs(nxt, stack)
        stack.pop()
        state[node] = 2

    for eid in edges:
        if state.get(eid, 0) == 0:
            dfs(eid, [])
    if not bad:
        v.ok("V05", "包含关系无循环（%d 条 inclusion 边）" % len(edges))


def check_enums(data, v):
    """V06: 全部枚举字段"""
    bad = False

    def enumchk(where, val, key):
        nonlocal bad
        if val is not None and val not in ENUMS[key]:
            v.fail("V06", where, "%r 不在枚举 %s" % (val, sorted(ENUMS[key])))
            bad = True

    mt = data.get("meta") or {}
    enumchk("meta.tier", mt.get("tier"), "meta_tier")
    for i, t in enumerate(data.get("tickets") or []):
        ap = t.get("applicability") or {}
        enumchk("tickets[%d].applicability.reservation" % i, ap.get("reservation"), "reservation")
    for i, m in enumerate(data.get("meals") or []):
        ap = m.get("applicability") or {}
        enumchk("meals[%d].applicability.meal_type" % i, ap.get("meal_type"), "meal_type")
    for i, e in enumerate(data.get("expenses") or []):
        w = "expenses[%d]" % i
        enumchk(w + ".tier", e.get("tier"), "tier")
        enumchk(w + ".unit", e.get("unit"), "unit")
        enumchk(w + ".price_mode", e.get("price_mode"), "price_mode")
        enumchk(w + ".pay_status", e.get("pay_status"), "pay_status")
        enumchk(w + ".verify_status", e.get("verify_status"), "verify_status")
        enumchk(w + ".category", e.get("category"), "category")
    for i, d in enumerate(data.get("days") or []):
        for j, s in enumerate(d.get("slots") or []):
            enumchk("days[%d].slots[%d].type" % (i, j), s.get("type"), "slot_type")
        meals = d.get("meals")
        if isinstance(meals, dict):
            for mk in meals:
                if mk not in ENUMS["meal_key"]:
                    v.fail("V06", "days[%d].meals 键 %r" % (i, mk),
                           "不在枚举 %s" % sorted(ENUMS["meal_key"]))
                    bad = True
    if not bad:
        v.ok("V06", "枚举全部合法")


def check_formats(data, v):
    """V07: 日期/时区/汇率格式"""
    bad = False
    mt = data.get("meta") or {}
    dw = mt.get("date_window") or {}
    for k in ("start", "end"):
        if not chk_date(dw.get(k)):
            v.fail("V07", "meta.date_window.%s" % k, "%r 不是 YYYY-MM-DD" % dw.get(k))
            bad = True
    for i, tz in enumerate(mt.get("timezones") or []):
        off = tz.get("utc_offset")
        if not isinstance(off, str) or not re.match(r"^[+-]\d{2}:\d{2}$", off):
            v.fail("V07", "meta.timezones[%d].utc_offset" % i, "%r 不是 ±HH:MM" % off)
            bad = True
    quotes = {f.get("quote") for f in (mt.get("fx") or [])}
    if len(quotes) > 1:
        v.fail("V07", "meta.fx", "quote 不一致: %s（全表须同一目标币种）" % sorted(quotes))
        bad = True
    for i, f in enumerate(mt.get("fx") or []):
        if not isinstance(f.get("rate"), (int, float)) or f.get("rate", 0) <= 0:
            v.fail("V07", "meta.fx[%d].rate" % i, "汇率必须>0")
            bad = True
        if not chk_date(f.get("checked_at")):
            v.fail("V07", "meta.fx[%d].checked_at" % i, "不是 YYYY-MM-DD")
            bad = True
    for i, d in enumerate(data.get("days") or []):
        dt = d.get("date")
        if not isinstance(dt, str) or not re.match(r"^\d{2}-\d{2}$", dt):
            v.fail("V07", "days[%d].date" % i, "%r 不是 MM-DD" % dt)
            bad = True
    if not bad:
        v.ok("V07", "日期/时区/汇率格式合法")


def check_amounts(data, v):
    """V08: 净价税率/区间价/金额在场"""
    bad = False
    for i, e in enumerate(data.get("expenses") or []):
        w = "expenses[%d]" % i
        has_point = isinstance(e.get("amount"), (int, float))
        has_range = isinstance(e.get("amount_min"), (int, float)) and \
            isinstance(e.get("amount_max"), (int, float))
        if not has_point and not has_range:
            v.fail("V08", w, "amount 与 amount_min/max 至少其一（数字）")
            bad = True
        if has_range and e["amount_min"] > e["amount_max"]:
            v.fail("V08", w, "amount_min(%s)>amount_max(%s)" % (e["amount_min"], e["amount_max"]))
            bad = True
        if e.get("price_mode") == "净价+税":
            r = e.get("tax_rate")
            if not isinstance(r, (int, float)) or r <= 0:
                v.fail("V08", w + ".tax_rate", "净价+税模式必须带正数 tax_rate")
                bad = True
    if not bad:
        v.ok("V08", "金额/税率口径合法")


def check_days_seq(data, v):
    """V09: day 从 1 连续编号"""
    days = data.get("days") or []
    seq = [d.get("day") for d in days]
    if seq != list(range(1, len(days) + 1)):
        v.fail("V09", "days[].day", "编号非 1..N 连续: %s" % seq)
    else:
        v.ok("V09", "day 编号 1..%d 连续" % len(days))


def check_day_components(data, v):
    """V11（v1.1 细化）: 组件关联稳定——slot.id 存在、day 内唯一、day 数字=所在天；
    cam.scope 枚举 slot/day：scope=slot（默认）必须给合法 slot_ref（漏填=FAIL，禁隐式全天），
    scope=day 不得带 slot_ref。背景：Codex 变更实验（2026-10-21）实证按时间字符串关联时
    改时段即静默丢机位；二轮复核抓漏填隐式全天与 id 天序不一致。"""
    bad = False
    legacy_t = 0
    for i, d in enumerate(data.get("days") or []):
        day_no = d.get("day")
        ids, seen = [], set()
        for j, s in enumerate(d.get("slots") or []):
            where = "days[%d].slots[%d].id" % (i, j)
            sid = s.get("id")
            if not sid:
                v.fail("V11", where, "slot 缺稳定 id（应 d%ds%d 式）" % (day_no, j + 1))
                bad = True
                continue
            m = re.match(r"^d(\d+)s(\d+)$", str(sid))
            if not m:
                v.fail("V11", where, "id=%r 不符合 d{day}s{n} 格式" % sid)
                bad = True
            elif int(m.group(1)) != day_no:
                v.fail("V11", where, "id=%r 天序号 %s ≠ 所在 day %s（id 一次分配后不随排序重编，但数字必须归属正确）"
                       % (sid, m.group(1), day_no))
                bad = True
            if sid in seen:
                v.fail("V11", where, "id=%r 与本 day 内重号" % sid)
                bad = True
            seen.add(sid)
            ids.append(sid)
        slot_ids = set(ids)
        for k, c in enumerate(d.get("cam") or []):
            where = "days[%d].cam[%d]" % (i, k)
            if "slot_t" in c:
                legacy_t += 1
            scope = c.get("scope", "slot")
            if scope not in ("slot", "day"):
                v.fail("V11", where + ".scope", "%r 不在枚举 slot|day" % scope)
                bad = True
            elif scope == "slot":
                sr = c.get("slot_ref")
                if sr is None:
                    v.fail("V11", where, "scope=slot（默认）缺 slot_ref——全天型机位必须显式 scope=day，禁漏填隐式代表全天")
                    bad = True
                elif sr not in slot_ids:
                    v.fail("V11", where + ".slot_ref",
                           "指向 %r 不在本 day slots（悬空或跨日引用）" % sr)
                    bad = True
            else:  # scope == "day"
                if c.get("slot_ref") is not None:
                    v.fail("V11", where, "scope=day 不得带 slot_ref（要么绑时段要么全天，二选一）")
                    bad = True
    if legacy_t:
        print("[WARN] V11 检测到 %d 处 cam[].slot_t 旧字段（v1.0 时间匹配已废弃，"
              "渲染不读取——跑 tools/migrate_slot_ids.py 迁移后删除）" % legacy_t)
    if not bad:
        v.ok("V11", "组件关联稳定（slot.id 全在位且天序归属正确，cam scope 合法）"
             + ("；%d 处 slot_t 待迁移" % legacy_t if legacy_t else ""))


def cam_affinity_ok(cam, slot):
    """机位归属启发式（v1.1 V12）：spot 名应能在所绑 slot 文案中找到（全名或前 3 字）。
    合法引用≠业务绑对（Codex 三轮复核 2026-10-21 抓"挂错位检测器不拒绝"）——
    同一函数供校验器（生产 WARN）与测试（样张可控，断言失败）两处使用。"""
    spot = (cam.get("spot") or "").strip()
    text = slot.get("text") or ""
    if not spot:
        return True
    return spot in text or (len(spot) >= 3 and spot[:3] in text)


def check_cam_affinity(data, v):
    """V12（WARN 级）: 机位与绑定时段的归属启发式。误报可能（文案措辞差异）故不 FAIL，
    逐处点名交人工确认；测试侧对措辞可控的样张用 cam_affinity_ok 做硬断言。"""
    warn = 0
    for i, d in enumerate(data.get("days") or []):
        smap = {s.get("id"): s for s in (d.get("slots") or [])}
        for k, c in enumerate(d.get("cam") or []):
            if c.get("scope", "slot") != "slot":
                continue
            s = smap.get(c.get("slot_ref"))
            if s and not cam_affinity_ok(c, s):
                warn += 1
                print("[WARN] V12 days[%d].cam[%d]「%s」绑到 %s 但该时段文案未提及此地点（绑错时段？人工确认）"
                      % (i, k, c.get("spot"), c.get("slot_ref")))
    v.ok("V12", "机位归属启发式完成" + ("；%d 处待人工确认" % warn if warn else "，全部匹配"))


def check_price_display(data, v):
    """V13（WARN 级）: tickets.price_display 与对应 expenses.amount 数字一致性。
    单源=expenses（schema 总纪律）；显示字段不一致=数据债务，提示迁移。"""
    warn = 0
    exp_by_ref = {}
    for e in data.get("expenses") or []:
        if e.get("ref"):
            exp_by_ref.setdefault(e["ref"], e)
    for t in data.get("tickets") or []:
        pd = t.get("price_display")
        e = exp_by_ref.get(t.get("id"))
        if not pd or e is None:
            continue
        amt = e.get("amount", e.get("amount_min"))
        m = re.search(r"[\d.]+", str(pd))
        if m and amt is not None and abs(float(m.group(0)) - float(amt)) > 0.005:
            warn += 1
            print("[WARN] V13 ticket %s（%s）price_display=%s 与 expenses.amount=%s 不一致"
                  "（单源=expenses，门票表已按明细渲染）" % (t.get("id"), t.get("name"), pd, amt))
    v.ok("V13", "门票价格两源一致性检查完成" + ("；%d 处不一致待迁移" % warn if warn else "，全一致"))


def check_date_alignment(data, v):
    """V14（FAIL 级）: days[].date 必须 = date_window.start 推算（start+day-1），
    总天数与窗口闭合。改窗口不同步每日日期=页面日期互相冲突（Codex 五轮复核）。"""
    bad = False
    dw = (data.get("meta") or {}).get("date_window") or {}
    try:
        start = date.fromisoformat(dw["start"])
        end = date.fromisoformat(dw["end"])
    except Exception:
        v.fail("V14", "meta.date_window", "start/end 无法解析（%r/%r）" % (dw.get("start"), dw.get("end")))
        return
    days = data.get("days") or []
    for d in days:
        expect = (start + timedelta(days=d.get("day", 1) - 1)).strftime("%m-%d")
        if d.get("date") != expect:
            v.fail("V14", "days[day=%s].date" % d.get("day"),
                   "%r ≠ 窗口推算 %r（窗口 %s~%s）" % (d.get("date"), expect, dw["start"], dw["end"]))
            bad = True
    if len(days) and len(days) != (end - start).days + 1:
        v.fail("V14", "days", "总天数 %d 与窗口 %s~%s（%d 天）不闭合"
               % (len(days), dw["start"], dw["end"], (end - start).days + 1))
        bad = True
    if not bad:
        v.ok("V14", "每日日期与窗口推算一致（%d 天闭合）" % len(days))


def route_check(data, v):
    """V15（v1.2 新增，FAIL 级）: routes 导览图路线数据毒化闸——
    结构非法（<2 节点/mode 非法/遗留 edge_from/day 重复/label 空）必须拒绝，
    由 gen_route_svg.validate_routes 同一函数把关（生成器与校验器同一闸门）。
    routes 未提供 = ok 声明（v1.1 数据兼容，导览图未由路线数据生成）。"""
    routes = data.get("routes")
    if not routes:
        v.ok("V15", "routes 未提供（v1.1 兼容）——导览图未由路线数据生成，建议 v1.2 数据补 routes")
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gen_route_svg import validate_routes
    tr_idx = {r.get("id"): r for r in list(data.get("transports", [])) + list(data.get("flights", [])) if r.get("id")}  # 班次+航段正本同权（R9）
    try:
        validate_routes(routes, data.get("days"), tr_idx)
    except ValueError as exc:
        v.fail("V15", "routes", str(exc))
        return
    n_nodes = sum(len(r.get("nodes", [])) for r in routes)
    v.ok("V15", "路线数据结构合法（%d 天 / %d 节点，顺序即拓扑）" % (len(routes), n_nodes))


def _t2min(s):
    """HH:MM → 分钟数；解析失败返回 None。
    fact 候选结构（dict 带 candidates）→ 取最早可解析候选（保守口径：任一候选早于闸线即算违规）"""
    if isinstance(s, dict):
        mins = [_t2min(c) for c in (s.get("candidates") or [])]
        mins = [m for m in mins if m is not None]
        return min(mins) if mins else None
    m = re.match(r"(\d{1,2}):(\d{2})", str(s or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _user_ok_ok(obj):
    """V17 结构化例外：user_ok:{reason 非空}——对应用户实际选择/客观取舍，复核可对质
    （R3 的 bool early_ok 被制作侧自行添加绕闸，作者复核否决，废弃）"""
    uo = obj.get("user_ok") if isinstance(obj, dict) else None
    return isinstance(uo, dict) and bool(str(uo.get("reason", "")).strip())


def schedule_check(data, v):
    """V17（v1.2 R5 终版，FAIL 级）: 游玩开始闸（2026-10-23 终版口径，作者偏好正本 已同步）——
    用户要的是**轻松的旅行节奏，不是生活作息表**：
      - 默认 09:30—10:00 开始当天游玩/主要活动（meta.customize.play_start 可配，默认 09:30）；
      - 路书**不写起床/洗漱等生活细节，不要求填写或校验起床时刻**（R4 的 day.wake 强制字段作废）；
      - 早餐、交通按实际行程需要列出，**可安排在此前**——不机械要求 09:30 后才能吃饭/乘车
        （R4「吃饭/交通都算首项安排」的扩大化管制作废；接驳合理不赶场属制作判断，不设机械闸）；
      - 唯一实质闸：当日首个 type=spot（游玩开始）早于 play_start → 须该 slot.user_ok:{reason}
        （=用户明确选择的早间玩法；制作侧不得自行补例外放行；未选择的早起玩法列 planb 可选）。
    废弃残留仅 WARN 不拦：R3 bool early_ok、R4 day.wake、customize.wake_earliest。"""
    cust = (data.get("meta") or {}).get("customize") or {}
    play_key = cust.get("play_start", "09:30")
    play_line = _t2min(play_key)
    if play_line is None:
        v.fail("V17", "meta.customize.play_start", "%r 不是 HH:MM" % play_key)
        return
    if "wake_earliest" in cust:
        print("[WARN] V17 meta.customize.wake_earliest 已废弃（R5：不校验起床时刻）——请删除该键")
    bad, n_days, n_spot, n_ok, legacy = 0, 0, 0, 0, 0
    tr_idx = {r0.get("id"): r0 for r0 in list(data.get("transports", [])) + list(data.get("flights", [])) if r0.get("id")}  # 班次+航段正本同权（R9）
    for d in data.get("days", []):
        dayno = d.get("day")
        slots = [s for s in d.get("slots", []) if _slot_t_min(s, tr_idx) is not None]
        if not slots:
            continue
        n_days += 1
        if d.get("wake") is not None:
            legacy += 1
            print("[WARN] V17 days[day=%s].wake 已废弃（R5：路书不写起床细节、不校验起床时刻）——请删除该字段" % dayno)
        for s in slots:
            if s.get("early_ok") and not _user_ok_ok(s):
                legacy += 1
                print("[WARN] V17 days[day=%s] slot %s 的 early_ok 为废弃 bool——不作为放行依据，请迁移为 user_ok:{reason}"
                      % (dayno, s.get("id")))
        spot = min((s for s in slots if s.get("type") == "spot"),
                   key=lambda s: _slot_t_min(s, tr_idx), default=None)
        if spot is not None:
            n_spot += 1
            if _slot_t_min(spot, tr_idx) < play_line:
                if _user_ok_ok(spot):
                    n_ok += 1
                else:
                    bad += 1
                    v.fail("V17", "days[day=%s].slots %s" % (dayno, spot.get("id")),
                           "开始游玩 %s（%s）早于默认游玩线 %s——明显早于默认节奏的玩法（日出/晨雾等）"
                           "属可选建议：未选择请移 planb；用户已明确选择的须该 slot.user_ok:{reason} 写明选择出处"
                           % (spot.get("t"), str(spot.get("text", ""))[:16] or "游玩", play_key))
    if n_days:
        if not bad:
            v.ok("V17", "游玩开始闸完成（R5：默认 %s 起游玩；早餐/交通按需安排不校验、起床不入册；"
                 "%d 天核对，%d 天有游玩项，%d 天带用户选择的早间玩法%s）"
                 % (play_key, n_days, n_spot, n_ok,
                    "，%d 处废弃残留待迁移" % legacy if legacy else ""))
    else:
        v.ok("V17", "无可核对的当日安排")


def biz_cost_check(data, v):
    """V18（v1.2 R3 重做，FAIL 级）: 费用关联**结构化**闸——废词表判定
    （R2 反例：「不含接驳车费，须另付50元」因含"含"字被误判已包含——子串匹配不可靠）。
    业务记录（flights/transports/tickets/stays/meals/misc 全类型）三态，用结构化字段表达：
      a) 已计费：id 被 expenses[].ref 引用（默认形态，无需字段）；
      b) 打包："billing": {"included_in": "<expense id>"} → 该 expense 必须真实存在
         （作者 第 3 条：住宿餐饮打包必须有费用落点，删除落点=漏账必拦）；
      c) 排除/可选："billing": {"optional": true, "reason": "…"} → reason 必填（未实查/备选等显式理由）。
    无 ref 且无 billing → FAIL（漏账）。"""
    exp_ids = {e.get("id") for e in data.get("expenses", [])}
    exp_refs = {e.get("ref") for e in data.get("expenses", []) if e.get("ref")}
    known_biz = {}
    for tbl0 in ("flights", "transports", "tickets", "stays", "meals", "misc"):
        for it0 in data.get(tbl0, []):
            if it0.get("id"):
                known_biz[it0["id"]] = tbl0[:-1]
    checked, bad = 0, 0
    for tbl in ("flights", "transports", "tickets", "stays", "meals", "misc"):
        for item in data.get(tbl, []):
            iid = item.get("id")
            if not iid:
                continue
            checked += 1
            if iid in exp_refs:
                continue  # a) 已计费
            billing = item.get("billing")
            if isinstance(billing, dict):
                inc = billing.get("included_in")
                if inc:
                    # R3：落点=expense 或**已计费的业务记录**（如「通票内含」指向已计费的通票 ticket）
                    if inc in exp_ids:
                        continue  # 指向 expense：真实费用落点
                    if inc in exp_refs:  # 指向的业务记录自身已被计费（如通票内含→已计费通票）
                        continue  # 指向已计费的业务（通票内含→通票已计费）：包含链闭合
                    bad += 1
                    v.fail("V18", "%s/%s" % (tbl[:-1], iid),
                           "billing.included_in=%r 无真实费用落点（expense 不存在或目标自身未计费）——打包必须落到已计费项" % inc)
                    continue
                if billing.get("optional"):
                    if not str(billing.get("reason", "")).strip():
                        bad += 1
                        v.fail("V18", "%s/%s" % (tbl[:-1], iid),
                               "billing.optional 缺 reason——排除/可选必须写明理由（未实查/备选等）")
                    continue
                bad += 1
                v.fail("V18", "%s/%s" % (tbl[:-1], iid),
                       "billing 结构不识别（需 included_in 或 optional+reason）")
                continue
            bad += 1
            v.fail("V18", "%s/%s" % (tbl[:-1], iid),
                   "%s 未被 expenses 计费且无 billing 字段——结构化声明单独计费/包含于/可选（M6 巴士 60 元漏项案）"
                   % item.get("name", iid)[:24])
    if checked:
        if not bad:
            v.ok("V18", "费用关联三态对账完成（%d 条业务记录：计费/打包落点/排除均有结构化着落）" % checked)
    else:
        v.ok("V18", "无业务记录")


def fact_check(data, v):
    """V16（v1.2 新增，FAIL 级）: 事实候选结构毒化闸——
    全树扫描带 candidates+status 的 fact dict：候选≥2 却标 confirmed / sources 不等长 /
    状态非法 / 缺 checked_at 必须拒绝（M6 教训：G505 到汉两源冲突曾被写死单值 20:34）。
    无 fact 结构 = ok 声明（纯文本数据兼容）。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fact import validate_fact
    found, bad = 0, 0

    def walk(obj, path):
        nonlocal found, bad
        if isinstance(obj, dict):
            if "candidates" in obj and "status" in obj:
                found += 1
                try:
                    validate_fact(obj, path)
                except ValueError as exc:
                    bad += 1
                    v.fail("V16", path, str(exc))
            for k, val in obj.items():
                walk(val, path + "." + str(k))
        elif isinstance(obj, list):
            for i, val in enumerate(obj):
                walk(val, path + "[%d]" % i)

    walk(data, "data")
    if found:
        if not bad:
            v.ok("V16", "事实候选结构合法（%d 处：候选/来源/状态/展示分离）" % found)
    else:
        v.ok("V16", "无 fact 候选结构（纯文本数据兼容）")


def time_consistency_check(data, v):
    """V20（v1.2 R8 重写，FAIL 级）: 时刻单源引用闸——
    独立复核：值复制+一致性比对=两份存储，且比对有漏检面（fact 正本被写死单值绕过、
    dep/arr 值混集合误配）。「改正本一处、三视图自动更新」必须由**引用派生**达成。
    slot.ref 指向 transports 且被引记录 applicability 有 dep_time/arr_time 时：
      slot.t 必须为引用形态 {"tr_ref": <slot.ref>, "field": "dep_time"|"arr_time"}——
      正文/表格/导览图由正本派生（fact 核实状态随之保留），复制值（字符串/fact 直填）=FAIL 引导迁移。
    引用形态自身校验：tr_ref 必须等于 slot.ref（时刻来自本 slot 绑定的班次）、
    field 必须存在且为 str/fact（悬空/错字段/引用链=FAIL）。
    正本无时刻字段的引用（门票/餐饮等）与无 ref 的自由 slot 不受此闸。"""
    tr_idx = {r.get("id"): r for r in list(data.get("transports", [])) + list(data.get("flights", [])) if r.get("id")}  # 班次+航段正本同权（R9）
    bad = checked = 0
    for i, d in enumerate(data.get("days", [])):
        for s in d.get("slots", []):
            ref = s.get("ref")
            t = s.get("t")
            if not ref or ref not in tr_idx or t is None:
                continue
            ap = tr_idx[ref].get("applicability") or {}
            if "dep_time" not in ap and "arr_time" not in ap:
                continue
            checked += 1
            where = "days[%d].slots %s" % (i, s.get("id"))
            if not (isinstance(t, dict) and "tr_ref" in t):
                bad += 1
                v.fail("V20", where,
                       "slot.t=%r 为复制值——应改引用形态 {{\"tr_ref\": \"%s\", \"field\": \"dep_time\" 或 \"arr_time\"}} "
                       "由正本派生（改正本一处三视图自动同步，核实状态不丢）" % (t, ref))
                continue
            if t.get("tr_ref") != ref:
                bad += 1
                v.fail("V20", where, "tr_ref=%r 与 slot.ref=%r 不符——时刻必须引用本 slot 绑定的班次"
                       % (t.get("tr_ref"), ref))
                continue
            fld = t.get("field")
            if fld not in ("dep_time", "arr_time"):
                bad += 1
                v.fail("V20", where, "field=%r 非法（仅 dep_time/arr_time）" % (fld,))
                continue
            if fld not in ap:
                bad += 1
                v.fail("V20", where, "正本 %s 无字段 %r——引用了不存在的时刻" % (ref, fld))
                continue
            pv = ap[fld]
            if isinstance(pv, dict) and "candidates" not in pv:
                bad += 1
                v.fail("V20", where, "正本 %s.%s 结构非法（须字符串或 fact）" % (ref, fld))
            # R9（作者 缺口①）：同一班次发车时刻不得手写在 slot.text/地图标题——
            #   a) 手写正本当前值 → 拦（脆弱副本，改正本必漂移）：应改 {dep}/{arr} 占位符由正本填充
            #   b) 班次号邻近时刻无一等于正本值 → 拦（矛盾残留——改正本漏改文案）
            # 普通时段（无班次号邻近，如「17:30 停运」）不受影响，不做全局替换。
            text = str(s.get("text") or "")
            if text:
                pvals = set()
                for fld in ("dep_time", "arr_time"):
                    fv = ap.get(fld)
                    if isinstance(fv, dict) and "candidates" in fv:
                        pvals.update(str(x) for x in fv["candidates"])
                    elif isinstance(fv, str) and fv.strip():
                        pvals.add(fv.strip())
                hit = [p for p in pvals if re.search(r"(?<!\d)%s(?!\d)" % re.escape(p), text)]
                if hit:
                    bad += 1
                    v.fail("V20", where,
                           "班次时刻 %s 手写在正文（含于 slot.text）——须改 {dep}/{arr} 占位符由正本派生"
                           "（手写副本改正本必漂移，地图标题亦从正文派生）" % "、".join(hit))
                else:
                    tr_rec = tr_idx[ref]
                    m_no = re.search(r"([A-Z]{1,2}\d{1,5})", "%s %s" % (tr_rec.get("name", ""),
                                                                        (tr_rec.get("applicability") or {}).get("flight_no", "")))
                    if m_no and m_no.group(1) in text:
                        S = set(re.findall(r"(?<!\d)(\d{1,2}:\d{2})(?!\d)", text))
                        if S and not (S & pvals):
                            bad += 1
                            v.fail("V20", where,
                                   "班次 %s 邻近时刻 %s 与正本 %s 无一相符——改正本后文案残留矛盾"
                                   % (m_no.group(1), "、".join(sorted(S)), "、".join(sorted(pvals))))
    if checked:
        if not bad:
            v.ok("V20", "时刻单源引用闸完成（%d 处班次 slot 全部引用正本派生）" % checked)
    else:
        v.ok("V20", "无 slot↔transport 时刻对账点")


def _slot_t_min(s, tr_idx):
    """slot.t 三形态 → 分钟数（R8）：引用形态查正本（解析失败 None——V20 负责拦非法引用）、
    fact 取最早候选、字符串直解析；解析失败返回 None"""
    try:
        from fact import resolve_slot_t
        resolved = resolve_slot_t(s.get("t"), tr_idx, "slots")
    except ValueError:
        return None
    return _t2min(resolved)


def flight_crossday_check(data, v):
    """V19（v1.2 R7 新增，FAIL 级）: 跨日航班排天闸（出境语义规则①）——
    写法约定：红眼/跨日航班在到达日的 slots 中复现同一 flight ref（出发日 slot + 到达日 slot，
    见 fixtures/synth_abroad_sample.json 示范）。同一 flight ref 出现在多个 day 时断言：
      a) 恰好两个相邻日（arr_day == dep_day + 1——次日到达排错天=出境五类风险之首）
      b) 到达日该 slot 为当日最早的有时刻安排（落地前不得已开始游玩/用餐）
      c) 出发日该 slot 之后不得再有非 note 安排（起飞后人在空中）
      d) 出发日 stay 必须为空（当夜在空中，订房=错排）
    另两个分支：applicability.crosses_days=true 但 ref 只出现在一天 → FAIL（声明跨日未排到达）；
    flight slot 时刻 ≥22:00、ref 未复现次日、又未声明 crosses_days → WARN 提示人工确认（红眼漏排嫌疑）。"""
    fl_idx = {f.get("id"): f for f in data.get("flights", []) if f.get("id")}
    tr_idx = {r.get("id"): r for r in list(data.get("transports", [])) + list(data.get("flights", [])) if r.get("id")}
    days = data.get("days", [])
    day_by_no = {}
    for d in days:
        day_by_no[d.get("day")] = d
    flight_days = {}
    flight_slot = {}
    for d in days:
        for s in d.get("slots", []):
            ref = s.get("ref")
            if ref in fl_idx and s.get("type") == "flight":
                flight_days.setdefault(ref, []).append(d.get("day"))
                flight_slot[(ref, d.get("day"))] = s
    bad = checked = 0
    warn = 0
    for fid, dlist in flight_days.items():
        uniq = sorted({x for x in dlist if x is not None})
        if len(uniq) != len(dlist):
            bad += 1
            v.fail("V19", "flights/%s" % fid, "同一航班在同一 day 重复出现 %d 次（结构异常）" % (len(dlist) - len(uniq) + 1))
            continue
        ap = (fl_idx[fid].get("applicability") or {})
        if len(uniq) == 1:
            checked += 1
            if ap.get("crosses_days"):
                bad += 1
                v.fail("V19", "flights/%s" % fid,
                       "声明 crosses_days（跨日到达）但该航班只在 day %s 排了 slot——次日到达未排天"
                       "（应在到达日复现同 ref 的到达 slot）" % uniq[0])
            else:
                s = flight_slot.get((fid, uniq[0]))
                m = _slot_t_min(s, tr_idx) if s else None
                if m is not None and m >= 22 * 60 and (uniq[0] + 1) in day_by_no:
                    warn += 1
                    print("[WARN] V19 flights/%s 于 day %s %02d:%02d 起飞、次日未复现到达 slot 且未声明 "
                          "crosses_days——红眼跨日漏排嫌疑，请人工确认（当日到达可忽略）" % (fid, uniq[0], m // 60, m % 60))
            continue
        checked += 1
        if len(uniq) > 2:
            bad += 1
            v.fail("V19", "flights/%s" % fid, "跨 %d 天复现（%s）——跨日航班应为出发/到达两天"
                   % (len(uniq), uniq))
            continue
        dep_day, arr_day = uniq
        if arr_day != dep_day + 1:
            bad += 1
            v.fail("V19", "flights/%s" % fid,
                   "出发 day %s 到达 day %s——到达日必须为紧邻次日（次日到达排错天）" % (dep_day, arr_day))
            continue
        dep_s = flight_slot.get((fid, dep_day))
        arr_s = flight_slot.get((fid, arr_day))
        dep_d, arr_d = day_by_no.get(dep_day, {}), day_by_no.get(arr_day, {})
        # b) 到达日最早（非 note 的有时刻安排不得早于到达 slot）
        if arr_s is not None:
            arr_t = _slot_t_min(arr_s, tr_idx)
            for s in arr_d.get("slots", []):
                if s is arr_s or s.get("type") == "note" or _slot_t_min(s, tr_idx) is None:
                    continue
                if _slot_t_min(s, tr_idx) < arr_t:
                    bad += 1
                    v.fail("V19", "days[day=%s].slots %s" % (arr_day, s.get("id")),
                           "安排 %s 早于航班到达 %s——落地前不得已开始安排（次日到达时序错位）"
                           % (s.get("t"), arr_s.get("t")))
        # c) 出发日起飞后无非 note 安排
        if dep_s is not None:
            seen = False
            for s in dep_d.get("slots", []):
                if s is dep_s:
                    seen = True
                    continue
                if seen and s.get("type") != "note" and _slot_t_min(s, tr_idx) is not None:
                    bad += 1
                    v.fail("V19", "days[day=%s].slots %s" % (dep_day, s.get("id")),
                           "安排 %s 晚于起飞 %s——起飞后人在空中，不得再排当日活动" % (s.get("t"), dep_s.get("t")))
        # d) 出发日当夜无房
        if dep_d.get("stay"):
            bad += 1
            v.fail("V19", "days[day=%s].stay" % dep_day,
                   "红眼航班出发当夜仍订住宿（%s）——当夜人在空中，住宿应从到达日起排"
                   % (dep_d["stay"] or {}).get("ref"))
    if checked:
        if not bad:
            v.ok("V19", "跨日航班排天闸完成（%d 个航班核对，%d 处红眼嫌疑待人工确认）" % (checked, warn))
    else:
        v.ok("V19", "无跨日航班对账点")


def flight_duration_check(data, v):
    """V21（v1.2 R9 重写，FAIL 级）: 跨时区时长自洽闸（R8 复核两缺口修复）——
    **完整当地日期时间核对**（缺口②：仅钟面取模会放过时长多填一天——1840=400+24h 曾 PASS）：
      expected_arr = datetime(dep_date, dep_time) + duration_min + (arr_off − dep_off)
      与 datetime(arr_date, arr_time) 相差 ≤10 分钟——400 合法、1840 与原日期不符必拦。
    **输入完备强制**（缺口③：有航班缺检查输入=「未检」必须 FAIL 阻断，不适用仅限无航班）：
      flights 表非空时每条记录缺 dep_time/arr_time/duration_min/dep_date/arr_date/航段时区
      任一项 → FAIL 逐项列名；flights 表为空 → 「不适用」PASS。"""
    flights = data.get("flights", [])
    tz_off = {}
    for t in (data.get("meta") or {}).get("timezones") or []:
        if t.get("area") and _tz_min(t.get("utc_offset")) is not None:
            tz_off[t["area"]] = _tz_min(t["utc_offset"])
    if not flights:
        v.ok("V21", "不适用（无航班记录）")
        return
    bad = checked = 0
    for f in flights:
        fid = f.get("id")
        ap = f.get("applicability") or {}
        missing = [k for k in ("dep_time", "arr_time", "duration_min", "dep_date", "arr_date")
                   if not ap.get(k)]
        # R10：UTC+00:00 解析出合法 0——仅在 None（缺失）时回退查表，禁 or 链（0 被当空值的误判）
        dep_off = _tz_min(ap.get("dep_utc_offset"))
        if dep_off is None:
            dep_off = tz_off.get(ap.get("dep_tz_area"))
        arr_off = _tz_min(ap.get("arr_utc_offset"))
        if arr_off is None:
            arr_off = tz_off.get(ap.get("arr_tz_area"))
        if dep_off is None:
            missing.append("航段时区 dep（dep_tz_area 或 dep_utc_offset）")
        if arr_off is None:
            missing.append("航段时区 arr（arr_tz_area 或 arr_utc_offset）")
        if missing:
            bad += 1
            v.fail("V21", "flights/%s" % fid,
                   "未检：缺 %s——有航班缺检查输入不能宣称时长已核（补齐或删除该航班记录）"
                   % "、".join(missing))
            continue
        try:
            dep_m = _t2min(ap["dep_time"])
            arr_m = _t2min(ap["arr_time"])
            dep_dt = datetime.combine(date.fromisoformat(ap["dep_date"]),
                                      time(dep_m // 60, dep_m % 60))
            arr_dt = datetime.combine(date.fromisoformat(ap["arr_date"]),
                                      time(arr_m // 60, arr_m % 60))
        except Exception as exc:
            bad += 1
            v.fail("V21", "flights/%s" % fid, "日期/时刻解析失败：%s（V07 亦会拦，此处不重复展开）" % exc)
            continue
        checked += 1
        expect_arr = dep_dt + timedelta(minutes=ap["duration_min"] + (arr_off - dep_off))
        diff = abs((arr_dt - expect_arr).total_seconds() / 60.0)
        if diff > 10:
            bad += 1
            v.fail("V21", "flights/%s" % fid,
                   "%s %02d:%02d(UTC%+.1f) + 官方时长 %dm + 时差 %+.1fh 应于 %s %02d:%02d 前后到达，"
                   "实际 %s %02d:%02d 相差 %.0f 分钟——检查 duration_min 是否误填钟面表差（时差直减）、"
                   "多填/少填整天，或去/返程时差方向弄反"
                   % (ap.get("dep_date"), dep_m // 60, dep_m % 60, dep_off / 60.0,
                      ap["duration_min"], (arr_off - dep_off) / 60.0,
                      expect_arr.strftime("%m-%d"), expect_arr.hour, expect_arr.minute,
                      arr_dt.strftime("%m-%d"), arr_dt.hour, arr_dt.minute, diff))
    # R10：有 FAIL（未检/不自洽）时不追加 PASS 行——FAIL 已逐项列名，避免日志自相矛盾
    if bad:
        pass
    elif checked:
        v.ok("V21", "跨时区时长自洽完成（%d 个航段按完整日期时间核对，±10 分钟官方舍入内）" % checked)
    else:
        v.ok("V21", "不适用（无可用航段）")



def _tz_min(v):
    """时区偏移 → 分钟数：接受数字小时（-1 / 8.5）或 ±HH:MM 字符串；解析失败 None"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(round(v * 60))
    m = re.match(r"^([+-])(\d{1,2}):(\d{2})$", str(v or "").replace(" ", ""))
    if m:
        sign = 1 if m.group(1) == "+" else -1
        return sign * (int(m.group(2)) * 60 + int(m.group(3)))
    return None


def _resolve_date(s, w_start, w_end):
    """日期解析（V22 R8，作者复核：统一换年份会破坏跨年顺序）：
    YYYY-MM-DD 直接用；MM-DD 结合行程窗口定年——依次尝试窗口 end 与 start 两个年份，
    取能落入 [w_start, w_end] 的候选（跨年窗口 12-31~01-02 中 01-01 正确解析到末年）；
    两候选都落不进窗口 → None（=窗口外，交判定层拦）。"""
    s = str(s or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None
    m = re.match(r"^(\d{2})-(\d{2})$", s)
    if not m:
        return None
    mm, dd = int(m.group(1)), int(m.group(2))
    for y in (w_end.year, w_start.year):
        try:
            cand = date(y, mm, dd)
        except ValueError:
            continue
        if w_start <= cand <= w_end:
            return cand
    return None


def ticket_date_binding_check(data, v):
    """V22（v1.2 R8 重写，FAIL 级）: 门票日期绑定闸（出境语义规则③）——
    tickets[].applicability.date / date_range 绑定适用日时：
      a) 绑定日必须能落入 meta.date_window（支持跨年窗口：MM-DD 结合窗口定年，保留完整年月日比较）；
      b) 该 ticket 被某天 slot 引用时，使用日必须落在绑定范围内——
         票绑 A 日行程排 B 日=当天进不了园（日期绑定错位）。
    无 date/date_range → 跳过（未绑定=预约规则人工确认，不妄拦）。"""
    mt = data.get("meta") or {}
    dw = mt.get("date_window") or {}
    try:
        w_start = date.fromisoformat(dw["start"])
        w_end = date.fromisoformat(dw["end"])
    except Exception:
        v.ok("V22", "date_window 无法解析（V14 已报）——绑定检查跳过")
        return
    tick_idx = {t.get("id"): t for t in data.get("tickets", []) if t.get("id")}
    used_at = {}
    for d in data.get("days", []):
        for s in d.get("slots", []):
            ref = s.get("ref")
            if ref in tick_idx and d.get("date"):
                used_at.setdefault(ref, set()).add(d["date"])
    bad = checked = 0

    def _bind_range(t):
        ap = t.get("applicability") or {}
        if ap.get("date"):
            return ap["date"], ap["date"]
        dr = ap.get("date_range") or {}
        if isinstance(dr, dict) and dr.get("start") and dr.get("end"):
            return dr["start"], dr["end"]
        return None

    for tid, t in tick_idx.items():
        rng = _bind_range(t)
        if not rng:
            continue
        checked += 1
        b0 = _resolve_date(rng[0], w_start, w_end)
        b1 = _resolve_date(rng[1], w_start, w_end)
        if b0 is None or b1 is None:
            bad += 1
            v.fail("V22", "tickets/%s" % tid,
                   "绑定日 %s~%s 无法落入行程窗口 %s~%s——票绑到了行程之外"
                   % (rng[0], rng[1], dw["start"], dw["end"]))
            continue
        for u_raw in used_at.get(tid, ()):
            u = _resolve_date(u_raw, w_start, w_end)
            if u is None:
                continue  # 使用日格式异常交 V07/V14，不重复拦
            if not (b0 <= u <= b1):
                bad += 1
                v.fail("V22", "tickets/%s" % tid,
                       "绑定日 %s~%s 但行程在 %s 使用该票——日期绑定错位（绑错日=当天进不了园）"
                       % (b0.isoformat(), b1.isoformat(), u.isoformat()))
    if checked:
        if not bad:
            v.ok("V22", "门票日期绑定完成（%d 张绑定票核对：窗口内+引用日一致，支持跨年窗口）" % checked)
    else:
        v.ok("V22", "无日期绑定票（未绑定的预约规则请人工确认）")



def budget_calc(data, v):
    """V10 + 预算试算。返回 summary dict（V10 FAIL 时仍返回尽力而为的部分结果）。"""
    mt = data.get("meta") or {}
    fx = mt.get("fx") or []
    target = fx[0].get("quote") if fx else None
    rates = {(f.get("base"), f.get("quote")): f.get("rate") for f in fx}
    pax_all = (mt.get("pax") or {}).get("adults", 0) + (mt.get("pax") or {}).get("children", 0)

    total_lo = total_hi = paid_lo = paid_hi = 0.0
    pending_items, excluded_tier, excluded_incl = [], [], []
    est_cnt = ver_cnt = 0
    v10_bad = False

    for i, e in enumerate(data.get("expenses") or []):
        w = "expenses[%d](%s)" % (i, e.get("label", "?"))
        vs = e.get("verify_status")
        tier = e.get("tier")
        inc = (e.get("inclusion") or {}).get("included_in")

        if vs == "pending":
            pending_items.append({"label": e.get("label"),
                                  "amount": e.get("amount", e.get("amount_min")),
                                  "currency": e.get("currency")})
        if vs == "estimated":
            est_cnt += 1
        if vs == "verified":
            ver_cnt += 1
        if tier and tier != "主选":
            excluded_tier.append(e.get("label"))
            continue
        if inc:
            excluded_incl.append({"label": e.get("label"), "included_in": inc})
            continue
        if vs == "pending":
            continue  # 未核实不计入合计（已在上面披露）

        if e.get("currency") == target:
            rate = 1.0  # 明细币种=目标币种，免折算
        else:
            rate = rates.get((e.get("currency"), target))
        if rate is None:
            v.fail("V10", w, "币种 %s 无法折算到 %s（fx 缺通路）" % (e.get("currency"), target))
            v10_bad = True
            continue
        lo = e.get("amount", e.get("amount_min"))
        hi = e.get("amount", e.get("amount_max"))
        if lo is None:
            continue  # V08 已报
        mult = e.get("qty", 1) * expense_mult(e, pax_all)  # 口径按 unit 分派（每间夜禁乘人头）
        if e.get("price_mode") == "净价+税":
            mult *= (1 + (e.get("tax_rate") or 0))
        lo_c = lo * mult * rate
        hi_c = hi * mult * rate
        total_lo += lo_c
        total_hi += hi_c
        if e.get("pay_status") == "已付":
            paid_lo += lo_c
            paid_hi += hi_c
        else:
            # 待付不单独累计区间（=总计-已付，区间各自相减）
            pass
    due_lo, due_hi = total_lo - paid_lo, total_hi - paid_hi

    summary = {
        "quote": target,
        "paid": [round(paid_lo, 2), round(paid_hi, 2)],
        "due": [round(due_lo, 2), round(due_hi, 2)],
        "total": [round(total_lo, 2), round(total_hi, 2)],
        "pending_items": pending_items,
        "estimated_count": est_cnt,
        "verified_count": ver_cnt,
        "excluded_by_inclusion": excluded_incl,
        "excluded_by_tier": excluded_tier,
    }
    if not v10_bad:
        v.ok("V10", "预算试算可执行（%d 项计入，%d 项待核已披露，%d 项估算，%d 项被包含剔除，%d 项备选不计入）"
             % (ver_cnt + est_cnt - len(pending_items), len(pending_items), est_cnt,
                len(excluded_incl), len(excluded_tier)))
    return summary


def print_budget(s):
    print("")
    print("=== 预算试算（唯一计算源=expenses 费用明细账，折 %s）===" % s["quote"])
    print("已付: %s ~ %s" % tuple(s["paid"]))
    print("待付: %s ~ %s" % tuple(s["due"]))
    print("合计（主选+已核/估算）: %s ~ %s" % tuple(s["total"]))
    if s["pending_items"]:
        print("⚠ 预算完整度——以下待核项未计入合计:")
        for p in s["pending_items"]:
            print("   - %s（%s %s）" % (p["label"], p["amount"], p["currency"]))
    if s["excluded_by_inclusion"]:
        print("包含关系剔除: " + "；".join(
            "%s（含于 %s）" % (x["label"], x["included_in"]) for x in s["excluded_by_inclusion"]))
    if s["excluded_by_tier"]:
        print("备选/可选不计入: " + "、".join(s["excluded_by_tier"]))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    path = args[0]
    budget_out = None
    if "--budget-out" in args:
        budget_out = args[args.index("--budget-out") + 1]

    print("=== trip_data 校验: %s ===" % os.path.basename(path))
    v = V()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        v.fail("V01", path, "JSON 无法解析或文件缺失: %s" % exc)
        print("")
        print("RESULT: FAIL(1)")
        sys.exit(1)

    # V01 顶层必备键
    missing = [k for k in TOP_REQUIRED if k not in data]
    if missing:
        v.fail("V01", "顶层", "缺必备键: %s" % missing)
    else:
        v.ok("V01", "顶层必备键齐全")

    idx = build_id_index(data, v)
    check_refs(data, idx, v)
    check_inclusion(data, v)
    check_enums(data, v)
    check_formats(data, v)
    check_amounts(data, v)
    check_days_seq(data, v)
    check_day_components(data, v)
    check_cam_affinity(data, v)
    check_price_display(data, v)
    check_date_alignment(data, v)
    route_check(data, v)
    fact_check(data, v)
    schedule_check(data, v)
    biz_cost_check(data, v)
    time_consistency_check(data, v)
    flight_crossday_check(data, v)
    flight_duration_check(data, v)
    ticket_date_binding_check(data, v)
    summary = budget_calc(data, v)

    if summary and not [f for f in v.fails if f == "V10"]:
        print_budget(summary)
        if budget_out:
            with open(budget_out, "w", encoding="utf-8") as fh:
                json.dump(summary, fh, ensure_ascii=False, indent=1)
            print("（预算明细已写 %s）" % budget_out)

    print("")
    print("RESULT: %s" % ("PASS" if not v.fails else "FAIL(%d)" % len(v.fails)))
    sys.exit(0 if not v.fails else 1)


if __name__ == "__main__":
    main()

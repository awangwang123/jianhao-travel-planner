# -*- coding: utf-8 -*-
"""gen_route_svg.py —— v1.2 导览图程序化生成器（任务书②：地图按节点与路线生成）
设计：routes[].nodes 数组顺序即游览顺序即连线顺序——拓扑由数据结构保证（结构上无断线/误连/死端）；
线型颜色由 MODE_STYLE 定义表派生（图例同源，杜绝图例与线型不符）；布局=纵向单列（无交叉无遮挡）。
用法: py gen_route_svg.py <trip_data.json> <out.svg片段或html>   （独立测试：py gen_route_svg.py --selftest）
校验: 节点<2 / mode 非法 / label 空 → ValueError 拒绝生成（毒化数据进不来）
print 只 ASCII（GBK 纪律）"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # 同目录 fact 模块（-I 隔离模式也可跑）
from fact import fact_display, resolve_slot_t, fill_slot_text  # R8 引用派生 + R9 文案占位符（与正文同正本）

# 注意：stdout 的 UTF-8 包装只在主模块运行时做——被 validate_trip_data 等 import 时
# 不动 sys.stdout（双重包装会导致宿主打印时 I/O on closed file，M6 test_day_components 同款先例）

# 线型定义表（单一来源：连线与图例都从这里派生——M6 教训 D5：图例与线型不符/两图互斥）
MODE_STYLE = {
    "walk":  {"stroke": "#5C594E", "dash": "",      "label": "步行/接驳"},
    "rail":  {"stroke": "#2F5D43", "dash": "",      "label": "高铁"},
    "bus":   {"stroke": "#B08D2E", "dash": "6 4",   "label": "站点巴士"},
    "cable": {"stroke": "#8A3B2E", "dash": "",      "label": "园区索道/步道"},
}
MODE_DEFAULT = "walk"
NOTE_W = 480          # 注释盒宽
NODE_W = 320          # 节点框宽（高度随文字行数动态）
GAP = 46              # 竖直箭头段高
SVG_W = 720
DISCLAIMER = "行程示意图，非等比例；实际导航请使用地图软件。"


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


NO_HEAD_PUNCT = "，。、；：！？）】」』〉》”’…·~-—％%"  # 中文排版避头点：这些字符不落行首


def _wrap_text(s, max_units):
    """按显示宽度贪心断行（CJK 全角=1、半角=0.5）——R4（作者复核）：文字**完整保留**，
    禁止「截断防出框」（截断=丢限制信息，R2 方案被判未完成）。
    断点避头点：下一字符为标点时并入当前行（行尾悬挂，SVG 不裁剪略超可接受）。
    返回行列表，空串返回 [""]。"""
    s = str(s or "")
    if not s:
        return [""]
    lines, cur, w = [], "", 0.0
    for ch in s:
        cw = 0.5 if ord(ch) < 0x2E80 else 1.0
        if cur and w + cw > max_units and ch not in NO_HEAD_PUNCT:
            lines.append(cur)
            cur, w = ch, cw
        else:
            cur += ch
            w += cw
    if cur:
        lines.append(cur)
    return lines


def validate_routes(routes, days=None, tr_idx=None):
    """毒化数据闸（R2 语义化升级）：
    结构层：day 非法/重复、节点<2、label 空、mode 非法、遗留 edge_from；
    语义层（days 提供时，作者复核 R2 要求）：
      - routes[].day 必须存在于 days[].day（「第 99 天」案）
      - slot_ref 必须解析到该天的 slot（跨天/悬空引用拒绝）——引用形态由事件派生地点与时间
      - 相邻可解析时刻禁止倒退（酒店 09:00→车站 08:00 案）
    覆盖声明（不 FAIL）：routes 覆盖天数与 days 总数在 ok 文案中如实报告。"""
    if not isinstance(routes, list) or not routes:
        raise ValueError("routes 缺失或为空——v1.2 起导览图必须由路线数据生成")
    seen_days = set()
    for r in routes:
        day = r.get("day")
        if not isinstance(day, int) or day < 1:
            raise ValueError("routes[].day 非法: %r" % day)
        if day in seen_days:
            raise ValueError("routes day 重复: %d" % day)
        seen_days.add(day)
        nodes = r.get("nodes")
        if not isinstance(nodes, list) or len(nodes) < 2:
            raise ValueError("routes[day %d].nodes 少于 2 个——单节点无路线可言" % day)
        for i, n in enumerate(nodes):
            if not (n.get("label") or "").strip() and not n.get("slot_ref"):
                raise ValueError("routes[day %d] node[%d] label 为空（且无 slot_ref）" % (day, i))
            if i > 0:
                mode = n.get("arrive_mode", MODE_DEFAULT)
                if mode not in MODE_STYLE:
                    raise ValueError(
                        "routes[day %d] node[%d] arrive_mode %r 不在定义表 %s"
                        % (day, i, mode, sorted(MODE_STYLE)))
            if n.get("edge_from"):  # v1.1 遗留字段：顺序即拓扑，edge_from 不再使用——出现即数据未迁移
                raise ValueError(
                    "routes[day %d] node[%d] 含遗留 edge_from——v1.2 顺序即拓扑，请删除该字段" % (day, i))
    if days is None:
        return
    # ---- 语义层（需要 days 上下文）----
    day_map = {}
    for d in days:
        day_map[d.get("day")] = d
    for r in routes:
        day = r["day"]
        if day not in day_map:
            raise ValueError(
                "routes day=%d 不存在于 days（%s）——路线不能挂在不存在的上（作者 第 99 天案）"
                % (day, sorted(k for k in day_map if k is not None)))
        slots_by_id = {}
        for s in day_map[day].get("slots", []):
            if s.get("id"):
                slots_by_id[s["id"]] = s
        prev_min = None
        for i, n in enumerate(r["nodes"]):
            ref = n.get("slot_ref")
            n_time = n.get("time")
            if isinstance(n_time, dict):
                cands = [str(v) for v in n_time.get("candidates", [])]
                n_time = cands[0] if cands else ""
            if ref:
                if ref not in slots_by_id:
                    raise ValueError(
                        "routes[day %d] node[%d] slot_ref %r 在该天的 slots 中不存在（悬空/跨天引用）"
                        % (day, i, ref))
                raw = slots_by_id[ref].get("t", "")
                if isinstance(raw, dict):  # R8：引用/fact 形态先解析到可比较字符串
                    raw = resolve_slot_t(raw, tr_idx, "routes[day %d] slot %s" % (day, ref))
                t = str(raw.get("candidates", [""])[0]) if isinstance(raw, dict) else str(raw)
                if n_time and n_time != t:
                    raise ValueError(
                        "routes[day %d] node[%d] 自带 time %r 与所引 slot %r 的时刻 %r 不一致——引用形态下时刻由事件派生"
                        % (day, i, n_time, ref, t))
                n_time = t
            # 时间倒退检查（可解析 HH:MM 的相邻节点）
            m = re.match(r"\s*(\d{1,2}):(\d{2})", str(n_time or ""))
            cur = int(m.group(1)) * 60 + int(m.group(2)) if m else None
            if cur is not None:
                if prev_min is not None and cur < prev_min:
                    raise ValueError(
                        "routes[day %d] node[%d] 时刻 %02d:%02d 早于前一节点 %02d:%02d——时间倒退（作者 酒店 09:00→车站 08:00 案）"
                        % (day, i, cur // 60, cur % 60, prev_min // 60, prev_min % 60))
                prev_min = cur


def gen_day_svg(r, day=None, tr_idx=None):
    """单日路线 → SVG 片段（纵向单列，节点框+mode 箭头+注释盒+图例）
    R4（作者复核）：标题/节点 label/时刻（含 fact 区间文案）/notes 全部换行**完整保留**，
    节点框与注释盒随行数动态增高——两遍法排版（先算高再出图），禁止截断。
    R8：slot.t 引用形态 {tr_ref, field} 经 resolve_slot_t 查正本派生（与正文同源）。"""
    tr_idx = tr_idx or {}
    LABEL_FS, LABEL_LH, LABEL_UNITS = 15, 21, 19   # 节点标题行（框内宽 292/15）
    TIME_FS, TIME_LH, TIME_UNITS = 12.5, 17, 23    # 节点时刻/fact 区间行
    NOTE_FS, NOTE_LH, NOTE_UNITS = 12.5, 19, 36    # 注释行（盒内宽 452/12.5）
    TITLE_FS, TITLE_LH, TITLE_UNITS = 17, 22, 40   # 图标题（全宽 680/17）

    nodes = []
    for n in r["nodes"]:
        n = dict(n)  # 不改原数据
        ref = n.get("slot_ref")
        if ref and day:
            for s in day.get("slots", []):
                if s.get("id") == ref:
                    if not n.get("time"):
                        n["time"] = s.get("t", "")
                    if not n.get("label"):
                        txt = re.sub(r"<[^>]+>", " ", str(s.get("text", "")))
                        txt = re.sub(r"\s+", " ", txt).strip()
                        txt = fill_slot_text(txt, tr_idx.get(s.get("ref")),
                                             "routes[day %s] label" % r.get("day", "?"))  # R9：地图标题同样由正本填充
                        n["label"] = txt  # R4：不再截 24 字——换行完整保留
                    break
        nodes.append(n)

    title_lines = _wrap_text("DAY %s · %s（按时间顺序）" % (r.get("day", "?"), r.get("title", "")), TITLE_UNITS)
    # 预排版（两遍法第一遍：算每个节点框高与注释盒高，得总高）
    laid = []
    for i, n in enumerate(nodes):
        n_time = n.get("time", "")
        if isinstance(n_time, dict):
            n_time = resolve_slot_t(n_time, tr_idx, "routes[day %s] node[%d].time" % (r.get("day", "?"), i))
        if isinstance(n_time, dict):
            n_time = fact_display(n_time, "routes[day %s] node[%d].time" % (r.get("day", "?"), i))
        n_time = str(n_time)
        laid.append((n, _wrap_text(n.get("label", ""), LABEL_UNITS), _wrap_text(n_time, TIME_UNITS)))
    boxes = []
    y = 30 + len(title_lines) * TITLE_LH + 8
    for n, ll, tl in laid:
        bh = 12 + len(ll) * LABEL_LH + 6 + len(tl) * TIME_LH + 12
        boxes.append((y, bh))
        y += bh + GAP
    notes_wrap = [_wrap_text(ln, NOTE_UNITS) for ln in (r.get("notes") or [])]
    total_note_lines = sum(len(x) for x in notes_wrap)
    nh = 12 + total_note_lines * NOTE_LH + 10
    ny = y - GAP + 10
    H = (ny + nh if r.get("notes") else y) + 52  # 尾部图例+声明区

    cx = SVG_W // 2
    box_l = cx - NODE_W // 2
    parts = []
    parts.append(
        '<svg class="route-svg" viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
        'role="img" aria-label="%s">' % (SVG_W, H, _esc(r.get("title", "行程示意图"))))
    parts.append('<title>%s</title>' % _esc("DAY %s · %s" % (r.get("day", "?"), r.get("title", ""))))
    # 箭头 marker 定义（每种 mode 一个，线端三角）——v1.2 初版漏 defs 致箭头不渲染，已修
    day_key = 'd%s' % r.get('day', 'x')  # R2：marker id 带 day 前缀——多图注入同一 HTML 时 id 全局唯一（checklist ID 唯一闸实证）
    parts.append('<defs>')
    for m, st in MODE_STYLE.items():
        parts.append(
            '<marker id="arr-%s-%s" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="%s"/></marker>' % (day_key, m, st["stroke"]))
    parts.append('</defs>')
    for ti, tln in enumerate(title_lines):
        parts.append(
            '<text x="%d" y="%d" text-anchor="middle" font-size="%s" font-weight="bold" fill="#2C2A26">%s</text>'
            % (SVG_W // 2, 30 + ti * TITLE_LH, TITLE_FS, _esc(tln)))

    prev_bottom = None  # R2：箭头从上一节点框底边中轴直连本节点框顶边（M6/作者复核：悬空线不连边界=不合格）
    for i, (n, ll, tl) in enumerate(laid):
        by, bh = boxes[i]
        # 连线（来自上一节点）：上一框底边中轴 → 本框顶边中轴（箭头贴边界）
        if i > 0 and prev_bottom is not None:
            mode = n.get("arrive_mode", MODE_DEFAULT)
            st = MODE_STYLE[mode]
            dash = ' stroke-dasharray="%s"' % st["dash"] if st["dash"] else ""
            parts.append(
                '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2.5"%s marker-end="url(#arr-%s-%s)"/>'
                % (cx, prev_bottom + 2, cx, by - 3, st["stroke"], dash, day_key, mode))
            parts.append(
                '<text x="%d" y="%d" font-size="12" fill="%s" text-anchor="start">%s</text>'
                % (cx + 10, (prev_bottom + by) // 2 + 4, st["stroke"], _esc(st["label"])))
        # 节点框（高度=标题行+时刻行动态）
        fill = "#F7F5EF" if i % 2 == 0 else "#FFFFFF"
        parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="#8A8677" stroke-width="1.4"/>'
            % (box_l, by, NODE_W, bh, fill))
        for li, tln in enumerate(ll):
            parts.append(
                '<text x="%d" y="%d" text-anchor="middle" font-size="%s" font-weight="bold" fill="#2C2A26">%s</text>'
                % (cx, by + 24 + li * LABEL_LH, LABEL_FS, _esc(tln)))
        base_t = by + 12 + len(ll) * LABEL_LH + 6 + 10
        for tj, tln in enumerate(tl):
            parts.append(
                '<text x="%d" y="%d" text-anchor="middle" font-size="%s" fill="#5C594E">%s</text>'
                % (cx, base_t + tj * TIME_LH, TIME_FS, _esc(tln)))
        prev_bottom = by + bh
    # 注释盒（独立区域，不压节点——M6 教训 D3/D5；行数动态增高）
    if r.get("notes"):
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="#EFF2EC" stroke="#B9C2B2"/>'
                     % ((SVG_W - NOTE_W) // 2, ny, NOTE_W, nh))
        k = 0
        for lines_j in notes_wrap:
            for tln in lines_j:
                parts.append('<text x="%d" y="%d" font-size="%s" fill="#4A4A42">%s</text>'
                             % ((SVG_W - NOTE_W) // 2 + 14, ny + 22 + k * NOTE_LH, NOTE_FS, _esc(tln)))
                k += 1
    # 图例：只列本图实际用到的 mode（同源派生）+ 固定示意声明
    used, seen = [], set()
    for n in nodes[1:]:
        m = n.get("arrive_mode", MODE_DEFAULT)
        if m not in seen:
            seen.add(m)
            used.append(m)
    lx = 30
    ly = H - 34
    for m in used:
        st = MODE_STYLE[m]
        dash = ' stroke-dasharray="%s"' % st["dash"] if st["dash"] else ""
        parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2.5"%s/>'
                     % (lx, ly, lx + 34, ly, st["stroke"], dash))
        parts.append('<text x="%d" y="%d" font-size="12" fill="#4A4A42">%s</text>' % (lx + 40, ly + 4, _esc(st["label"])))
        lx += 40 + len(st["label"]) * 12 + 26
    parts.append('<text x="%d" y="%d" font-size="11.5" fill="#8A8677" text-anchor="end">%s</text>' % (SVG_W - 24, ly + 20, _esc(DISCLAIMER)))
    parts.append("</svg>")
    return "\n".join(parts)


def gen_all(data):
    """trip_data 含 routes 时 → [(day, svg_str)]；校验先行（毒化数据拒绝，含语义层）
    R8：建 transports 索引传入——slot.t 引用形态由正本派生"""
    routes = data.get("routes")
    days = data.get("days")
    tr_idx = {r.get("id"): r for r in list(data.get("transports") or []) + list(data.get("flights") or []) if r.get("id")}  # 班次+航段正本同权（R9）
    validate_routes(routes, days, tr_idx)
    day_map = {d.get("day"): d for d in (days or [])}
    return [(r["day"], gen_day_svg(r, day_map.get(r["day"]), tr_idx)) for r in routes]


def _selftest():
    """内置最小自测：合法数据出图 + 长文本换行完整保留（R4） + 三类毒化数据拒绝"""
    good = [{"day": 1, "title": "测试", "nodes": [
        {"label": "甲", "time": "09:00"},
        {"label": "乙", "time": "10:00", "arrive_mode": "rail"},
        {"label": "丙", "time": "11:00", "arrive_mode": "bus"}]}]
    validate_routes(good)
    svg = gen_day_svg(good[0])
    assert svg.count("<rect") >= 3 and "marker-end" in svg and DISCLAIMER in svg
    # R4：长 label/长 fact 区间/长注释换行完整保留，动态增高生效，无截断省略号
    LONG = "这是一个特别长的景点名称用来验证换行后文字完整保留不截断共三十余字必须全部出现在成图之中"
    long_note = "注释也很长必须完整保留不允许任何截断省略，" * 4
    long_r = {"day": 1, "title": "长文本换行完整保留测试", "notes": [long_note], "nodes": [
        {"label": LONG, "time": "09:00"},
        {"label": "乙", "time": "20:34~20:39 聚合源不一，待 12306 确认后更新为确定时刻再行展示",
         "arrive_mode": "rail"}]}
    svg_l = gen_day_svg(long_r)
    assert "…" not in svg_l, "出现截断省略号（R4 禁止截断）"
    for x in _wrap_text(LONG, 19):
        assert _esc(x) in svg_l, "长 label 行缺失: " + x
    for x in _wrap_text(long_note, 36):
        assert _esc(x) in svg_l, "长注释行缺失: " + x
    assert "20:34~20:39" in svg_l and "12306" in svg_l, "fact 区间长时刻被截断"
    vh = lambda s: int(re.search(r'viewBox="0 0 720 (\d+)"', s).group(1))
    svg_s = gen_day_svg({"day": 1, "title": "短", "nodes": [
        {"label": "甲", "time": "09:00"}, {"label": "乙", "time": "10:00"}]})
    assert vh(svg_l) > vh(svg_s), "长文本未使图动态增高"
    for bad, desc in [
        ([{"day": 1, "nodes": [{"label": "只有一个"}]}], "单节点"),
        ([{"day": 1, "nodes": [{"label": "甲"}, {"label": "乙", "arrive_mode": "飞机"}]}], "非法mode"),
        ([{"day": 1, "nodes": [{"label": "甲", "edge_from": "x"}, {"label": "乙"}]}], "遗留edge_from"),
    ]:
        try:
            validate_routes(bad)
            raise AssertionError("毒数据未被拒绝: " + desc)
        except ValueError:
            pass
    print("SELFTEST OK: legal gen + long-text wrap kept + dynamic height + 3 poison rejected")


if __name__ == "__main__":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--selftest" in sys.argv:
        _selftest()
    else:
        if len(sys.argv) < 3:
            print("usage: py gen_route_svg.py <trip_data.json> <out.html或.svg> | --selftest")
            sys.exit(2)
        data = json.load(io.open(sys.argv[1], encoding="utf-8"))
        pieces = gen_all(data)
        body = "\n".join(s for _, s in pieces)
        io.open(sys.argv[2], "w", encoding="utf-8").write(body)
        print("wrote %d route svg(s) -> %s" % (len(pieces), sys.argv[2]))

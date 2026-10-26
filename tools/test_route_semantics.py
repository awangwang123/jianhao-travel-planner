# -*- coding: utf-8 -*-
"""test_route_semantics.py —— V15 语义层毒化测试（实战反例固化：第99天/时间倒退/slot_ref悬空）
用法: py test_route_semantics.py（结果落盘 test_route_semantics_result.txt）"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_route_svg import validate_routes  # noqa: E402

RESULT = os.path.join(HERE, "test_route_semantics_result.txt")
OUT = io.open(RESULT, "w", encoding="utf-8")
fails = []


def expect_reject(name, routes, days, frag=""):
    try:
        validate_routes(routes, days)
        OUT.write("FAIL %s | 未被拒绝\n" % name)
        fails.append(name)
    except ValueError as e:
        if frag and frag not in str(e):
            OUT.write("FAIL %s | 拒绝但文案不含 %r： %s\n" % (name, frag, e))
            fails.append(name)
        else:
            OUT.write("PASS %s | %s\n" % (name, e))


def expect_ok(name, routes, days):
    try:
        validate_routes(routes, days)
        OUT.write("PASS %s | 合法通过\n" % name)
    except ValueError as e:
        OUT.write("FAIL %s | 合法数据被拒: %s\n" % (name, e))
        fails.append(name)


days = [
    {"day": 1, "slots": [{"id": "d1s1", "t": "09:00", "text": "酒店早餐后出发"},
                          {"id": "d1s2", "t": "10:30", "text": "篁岭套票入园"}]},
    {"day": 2, "slots": [{"id": "d2s1", "t": "08:00", "text": "石城晨雾"}]},
]

# 实战反例 1：第 99 天（days 不存在）
expect_reject("第 99 天被拒",
              [{"day": 99, "nodes": [{"label": "酒店", "time": "09:00"}, {"label": "车站", "time": "08:00"}]}],
              days, "不存在于 days")

# 实战反例 2：时间倒退（酒店 09:00 → 车站 08:00）
expect_reject("同日时间倒退被拒",
              [{"day": 1, "nodes": [{"label": "酒店", "time": "09:00"}, {"label": "车站", "time": "08:00"}]}],
              days, "时间倒退")

# 实战反例 3：slot_ref 悬空（指向不存在的 slot）
expect_reject("slot_ref 悬空被拒",
              [{"day": 1, "nodes": [{"label": "酒店", "time": "09:00"},
                                     {"slot_ref": "d1s99", "arrive_mode": "walk"}]}],
              days, "不存在")

# 反例 4：slot_ref 跨天引用（d2s1 引在 day1 路线里）
expect_reject("slot_ref 跨天被拒",
              [{"day": 1, "nodes": [{"label": "酒店", "time": "09:00"},
                                     {"slot_ref": "d2s1", "arrive_mode": "walk"}]}],
              days, "不存在")

# 反例 5：引用形态下自带 time 与 slot 时刻不一致
expect_reject("引用时刻不一致被拒",
              [{"day": 1, "nodes": [{"label": "酒店", "time": "09:00"},
                                     {"slot_ref": "d1s2", "arrive_mode": "walk", "time": "11:00"}]}],
              days, "不一致")

# 合法：slot_ref 引用形态（label/time 由事件派生）
expect_ok("slot_ref 引用形态合法",
          [{"day": 1, "nodes": [{"slot_ref": "d1s1"},
                                 {"slot_ref": "d1s2", "arrive_mode": "walk"}]}],
          days)

# 合法：自由文本形态且时间递增
expect_ok("自由文本形态合法",
          [{"day": 1, "nodes": [{"label": "酒店", "time": "09:00"},
                                 {"label": "篁岭", "time": "10:30", "arrive_mode": "bus"}]}],
          days)

# 覆盖声明：只覆盖 1 天（2 天日程）→ 不 FAIL（覆盖数在 ok 文案如实报告）

# ---- v1.18 越界必失败用例（checklist 2c 抽出的 svg_bounds 单元毒抓）----
# 背景：旧 2c 只认 zoomable+polyline/circle，对 route-svg（line/rect/path）数出 0 张报 PASS。
# 已知阳性对照（越界必判）+已知阴性对照（合法必过）+零样本声明，三面都断言。
from svg_bounds import check_svg_bounds  # noqa: E402


def bounds_case(name, html, expect_n, expect_bad):
    n, skip, bad = check_svg_bounds(html)
    if n == expect_n and bool(bad) == expect_bad:
        OUT.write("PASS %s | n=%d bad=%s\n" % (name, n, bad))
    else:
        OUT.write("FAIL %s | n=%d(期望%d) bad=%s(期望有出界=%s)\n" % (name, n, expect_n, bad, expect_bad))
        fails.append(name)


G_SVG = '<svg class="route-svg" viewBox="0 0 720 300"><line x1="50" y1="50" x2="650" y2="250"/><rect x="100" y="60" width="200" height="60"/></svg>'
bounds_case("route-svg 合法（line+rect 在框内）", G_SVG, 1, False)
bounds_case("route-svg line 出界必判",
            '<svg class="route-svg" viewBox="0 0 720 300"><line x1="50" y1="50" x2="900" y2="250"/></svg>', 1, True)
bounds_case("route-svg rect 越右界必判",
            '<svg class="route-svg" viewBox="0 0 720 300"><rect x="600" y="250" width="300" height="80"/></svg>', 1, True)
bounds_case("route-svg path 出界必判",
            '<svg class="route-svg" viewBox="0 0 720 300"><path d="M50,50 L1000,600"/></svg>', 1, True)
bounds_case("zoomable polyline 出界必判（旧形态回归保护）",
            '<svg class="zoomable" viewBox="0 0 300 120"><polyline points="10,10 400,50"/></svg>', 1, True)
bounds_case("marker 小三角（局部坐标）不误报",
            '<svg class="route-svg" viewBox="0 0 720 300"><defs><marker id="a"><path d="M0,0 L10,5 L0,10 z"/></marker></defs></svg>', 1, False)
bounds_case("类名不匹配的 svg 不检查",
            '<svg viewBox="0 0 100 100"><line x1="0" y1="0" x2="500" y2="500"/></svg>', 0, False)
bounds_case("零样本如实报 0", "<p>no svg</p>", 0, False)

OUT.write("RESULT: %s (%d fails)\n" % ("ALL PASS" if not fails else "HAS FAIL", len(fails)))
try:
    print("RESULT: %s (%d fails)" % ("ALL PASS" if not fails else "HAS FAIL", len(fails)))
except Exception:
    pass
sys.exit(0 if not fails else 1)

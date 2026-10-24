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
OUT.write("RESULT: %s (%d fails)\n" % ("ALL PASS" if not fails else "HAS FAIL", len(fails)))
try:
    print("RESULT: %s (%d fails)" % ("ALL PASS" if not fails else "HAS FAIL", len(fails)))
except Exception:
    pass
sys.exit(0 if not fails else 1)

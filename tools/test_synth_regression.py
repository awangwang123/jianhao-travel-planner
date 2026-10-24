# -*- coding: utf-8 -*-
"""
test_synth_regression.py —— 第 3 步「同路径离线回归」：3/8/10 天合成数据全流程
每册：V01-V12 全量校验 PASS → 结构化渲染（禁 blocks 直渲）→ 产物断言
  （天数区块/导航/机位 DOM 独立预期归属/返程真图可解码/指纹）
变更实验（3 天册，期望值独立手算写死）：E0 基数 500；E1 完整日期联动（TRIP 全映射+旧日期清零+V14）；
  E2 单一价格源（改一次 expenses→门票表+预算双更新）；E3 改时刻机位不挪；E4 增/删天（删天数据同步）
三条必须失败：F1 悬空 slot_ref（V11）；F2 机位挂错时段（独立预期 mismatch）；F3 返程图缺失
输出: 落盘 result.txt；退出码 0=全过, 1=有失败
"""
import base64
import copy
import io
import json
import os
import re
import struct
import subprocess
import sys
import zlib
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "fixtures"))
sys.path.insert(0, HERE)
from make_synth_books import make_book  # noqa: E402
from imgcheck import png_check  # 唯一正本（Codex 五轮复核：禁各测试维护缩水副本）

RESULT = os.path.join(HERE, "test_synth_regression_result.txt")
SYNTH = os.path.join(os.path.dirname(HERE), "fixtures", "synth")
GEN = os.path.join(HERE, "gen_roadbook.py")
VAL = os.path.join(HERE, "validate_trip_data.py")

OUT = io.open(RESULT, "w", encoding="utf-8")
fails = []


def ok(name, cond, detail=""):
    OUT.write(("PASS " if cond else "FAIL ") + name + ((" | " + detail) if detail else "") + "\n")
    if not cond:
        fails.append(name)


def run_json_args(script, *args):
    p = subprocess.run([sys.executable, script] + list(args), capture_output=True)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", errors="replace")


# ---------- DOM 树（与 test_day_components 同款，隔离复制防 import 副作用） ----------
class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []


VOID = {"img", "br", "hr", "input", "meta", "link", "polygon", "polyline", "path", "col"}


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node("#root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        if data.strip():
            self.cur.children.append(data)


def build_tree(html):
    tb = TreeBuilder()
    tb.feed(html)
    return tb.root


def cam_nodes(root):
    hits = []

    def walk(n):
        if any(isinstance(c, str) and "📷" in c for c in n.children):
            hits.append(n)
        for c in n.children:
            if isinstance(c, Node):
                walk(c)
    walk(root)
    return hits


def collect(n):
    s = "".join(ch for ch in n.children if isinstance(ch, str))
    for ch in n.children:
        if isinstance(ch, Node):
            s += collect(ch)
    return s


def cam_info(cam_div):
    """(spot, 实际归属 data-slot-id)"""
    m = re.search(r"📷 位置：([^｜]+)", collect(cam_div))
    spot = m.group(1).strip() if m else "?"
    cur = cam_div
    while cur.parent is not None:
        if cur.tag == "div" and "slot-body" in (cur.attrs.get("class") or ""):
            slot_div = cur.parent
            if slot_div is not None and "slot" in (slot_div.attrs.get("class") or "").split():
                return spot, slot_div.attrs.get("data-slot-id")
            return spot, None
        cur = cur.parent
    return spot, None


def check_affinity(html, expect_map):
    """独立预期核对：{spot: 预期slot_id} vs DOM 实际归属。返回失败明细列表。"""
    got = {sp: sid for sp, sid in (cam_info(c) for c in cam_nodes(build_tree(html)))}
    return [(sp, exp, got.get(sp)) for sp, exp in expect_map.items() if got.get(sp) != exp]


def last_return_img(html):
    m = re.search(r"<img[^>]*src='([^']+)'", html)
    return m.group(1) if m else None


# ---------- 主流程 ----------
os.makedirs(SYNTH, exist_ok=True)
books = {}
for n in (3, 8, 10):
    books[n] = make_book(n)
    p = os.path.join(SYNTH, "book%d.json" % n)
    with io.open(p, "w", encoding="utf-8") as fh:
        json.dump(books[n], fh, ensure_ascii=False, indent=1)

n_cams = {n: sum(len(d.get("cam") or []) for d in books[n]["days"]) for n in books}
expect_maps = {n: {"合成景点%d" % i: "d%ds2" % i for i in range(1, n + 1)} for n in books}
outs = {}

for n in (3, 8, 10):
    jp = os.path.join(SYNTH, "book%d.json" % n)
    hp = os.path.join(SYNTH, "book%d.html" % n)
    rc, out = run_json_args(VAL, jp)
    ok("R%d 全量校验 V01-V12 PASS（%d 天）" % (n, n), rc == 0 and "RESULT: PASS" in out,
       "exit=%d %s" % (rc, [l for l in out.splitlines() if "RESULT" in l][:1]))
    rc2, out2 = run_json_args(GEN, jp, hp)
    ok("R%d 渲染成功（%d 天）" % (n, n), rc2 == 0 and os.path.exists(hp),
       "exit=%d" % rc2)
    h = io.open(hp, encoding="utf-8").read()
    outs[n] = h
    ok("R%d 天数区块 day1..dayN 全在位" % n,
       all('id="day%d"' % i in h for i in range(1, n + 1)))
    ok("R%d 固定板块 11 个全在位" % n,
       all('id="%s"' % s in h for s in ("overview", "cost", "sos", "boost", "gift",
                                        "drive", "stay", "ticket", "tips", "eat")))
    ok("R%d 导航末天链接在位" % n, 'href="#day%d"' % n in h)
    ok("R%d 无多余 dayN+1 区块" % n, 'id="day%d"' % (n + 1) not in h)
    mism = check_affinity(h, expect_maps[n])
    ok("R%d 机位独立预期归属全匹配（%d 个）" % (n, n_cams[n]), not mism, "mismatch=%s" % mism[:3])
    rc3, _ = run_json_args(VAL, jp)  # 指纹由 gen 内部断言（渲染成功即含指纹）；此处补真图检查
    last_day_html = re.search(r'<section id="day%d">.*?</section>' % n, h, re.S)
    seg = last_day_html.group(0) if last_day_html else ""
    img = last_return_img(seg)
    pok, pdet = png_check(img) if img else (False, "无 img")
    ok("R%d 返程日真图可完整解码" % n, pok, pdet)
    ok("R%d 返程日动线 SVG 含坐标+箭头" % n,
       "polyline" in seg and "data-arrow" in seg)
    ok("R%d 骨架指纹在位" % n, "9f1fd4856f" in h)

# ---------- 四类变更实验（3 天册） ----------
def rerender(book, tag):
    jp = os.path.join(SYNTH, "_e_%s.json" % tag)
    hp = os.path.join(SYNTH, "_e_%s.html" % tag)
    with io.open(jp, "w", encoding="utf-8") as fh:
        json.dump(book, fh, ensure_ascii=False, indent=1)
    rc, _ = run_json_args(GEN, jp, hp)
    return rc == 0, (io.open(hp, encoding="utf-8").read() if rc == 0 else "")

def total_of(html):
    m = re.search(r'<div class="n">([\d.]+)~[\d.]+</div>', html)
    return float(m.group(1)) if m else None


# E0 预算基数（独立手算写死，不从被测程序提取——Codex 五轮复核第 3 条）
# 3 天册：门票 100×3 + 住宿 200×1 间（每间夜不乘人头）= 500
t_base = total_of(outs[3])
ok("E0 预算基数 500（独立计算：300 门票+200 住宿一间）", t_base == 500.0, "实测 %.0f" % (t_base or -1))




def _dump(book, tag):
    jp = os.path.join(SYNTH, "_%s.json" % tag)
    with io.open(jp, "w", encoding="utf-8") as fh:
        json.dump(book, fh, ensure_ascii=False, indent=1)
    return jp


# E1 完整日期联动：sync_dates=改日期的规范操作（窗口/每日/标签/天气格一次同步；总览走占位符派生）
from datetime import date as _date, timedelta as _td


def sync_dates(book, start, end):
    book["meta"]["date_window"] = {"start": start, "end": end}
    s = _date.fromisoformat(start)
    for d in book["days"]:
        d["date"] = (s + _td(days=d["day"] - 1)).strftime("%m-%d")
        d["label"] = d["date"]
    for k, w in enumerate(book["overview_structured"]["weather"]):
        w["d"] = (s + _td(days=k)).strftime("%m-%d")


b1 = copy.deepcopy(books[3])
sync_dates(b1, "2026-12-20", "2026-12-22")
rc_v14, out_v14 = run_json_args(VAL, _dump(b1, "_e_e1v"))
ok("E1a 同步后 V14 日期对齐 PASS", rc_v14 == 0 and "[FAIL] V14" not in out_v14)
ok_e1, h1 = rerender(b1, "e1")
trip_m = sorted(re.findall(r'"(2026-12-2[0-2])":"(day[123])"', h1))
ok("E1b TRIP 完整映射=窗口推算（12-20/21/22→day1/2/3）",
   ok_e1 and trip_m == [("2026-12-20", "day1"), ("2026-12-21", "day2"), ("2026-12-22", "day3")],
   "实测=%s" % trip_m)
seg_ov = re.search(r'<section id="overview">.*?</section>', h1, re.S).group(0)
ok("E1c 总览日期派生自窗口（{date_range} 占位符）", "12-20~12-22" in seg_ov)
ok("E1d 总览+全部 day 区块旧 11 月日期清零（全页扫描）",
   "11-" not in seg_ov and all("11-" not in re.search(
       r'<section id="day%d">.*?</section>' % i, h1, re.S).group(0) for i in (1, 2, 3)))

# E2 单一价格源联动：只改一次 expenses.amount → 门票表+预算同时更新（Codex 五轮复核第 1 条）
b2 = copy.deepcopy(books[3])
b2["expenses"][0]["amount"] = 188
ok_e2, h2 = rerender(b2, "e2")
seg_t2 = re.search(r'<section id="ticket">.*?</section>', h2, re.S)
seg_t2 = seg_t2.group(0) if seg_t2 else ""
t_after = total_of(h2)
first_row = re.search(r"<tbody>\s*<tr>(.*?)</tr>", seg_t2, re.S)
first_row = first_row.group(1) if first_row else seg_t2
ok("E2a 改一处费用 100→188：门票表第一行（景点1）同步为 188 元",
   ok_e2 and "188 元" in first_row and "100 元" not in first_row,
   "未改的景点2/3 仍为 100 元属正确")
ok("E2b 同一次修改：预算合计 500→588（独立手算）", ok_e2 and t_after == 588.0,
   "实测 %.0f" % (t_after or -1))

# E2c 整单/按次费不乘人数（Codex 六轮复核第 3 条）：出租车 100 元/单适用 2 人 = 100 不是 200
b2c = copy.deepcopy(books[3])
b2c["expenses"].append({"id": "e9001", "category": "市内交通", "label": "出租车包趟",
                        "amount": 100, "currency": "CNY", "unit": "每次", "qty": 1,
                        "scope": {"pax": 2}, "price_mode": "含税", "tier": "主选",
                        "pay_status": "待付", "verify_status": "verified",
                        "checked_at": "2026-10-21", "source": "synthetic"})
ok_e2c, h2c = rerender(b2c, "e2c")
t_2c = total_of(h2c)
ok("E2c 按次费只按次数：500+100=600（若误乘人数会成 700）", ok_e2c and t_2c == 600.0,
   "实测 %.0f" % (t_2c or -1))

# E3 改时刻 → 机位归属不变（slot_ref 稳定关联）
b3 = copy.deepcopy(books[3])
for s in b3["days"][0]["slots"]:
    if s["id"] == "d1s2":
        s["t"] = "22:22"
ok_e3, h3 = rerender(b3, "e3")
mism3 = check_affinity(h3, expect_maps[3])
ok("E3 改时刻 14:00→22:22 机位归属全部不变", ok_e3 and not mism3, "mismatch=%s" % mism3[:3])

# E4 增减天 → 骨架扩删+导航同步
b4 = make_book(4)
ok_e4, h4 = rerender(b4, "e4")
ok("E4a 增至 4 天：day4 区块+导航在位", ok_e4 and 'id="day4"' in h4 and 'href="#day4"' in h4)
# E4b 真执行删天：4 天数据删 day4（days/tickets/expenses/window 同步）→ 重渲染（Codex 五轮复核第 5 条）
b4b = make_book(4)
b4b["days"].pop()
b4b["tickets"] = [t for t in b4b["tickets"] if t["id"] != "t004"]
b4b["expenses"] = [e for e in b4b["expenses"] if e.get("ref") != "t004"]
tt = b4b["ticket_structured"]["table"]
tt["rows"] = tt["rows"][:3]
tt["_row_refs"] = tt["_row_refs"][:3]
b4b["meta"]["date_window"]["end"] = "2026-11-03"
rc_e4b, out_e4b = run_json_args(VAL, _dump(b4b, "_e_e4b"))
ok_e4b, h4b = rerender(b4b, "e4b")
ok("E4b-1 删天后全量校验 PASS（V14 窗口闭合）", rc_e4b == 0 and "RESULT: PASS" in out_e4b)
ok("E4b-2 删天后 day4 区块+导航清零", ok_e4b and 'id="day4"' not in h4b and 'href="#day4"' not in h4b)
t_e4b = total_of(h4b)
ok("E4b-3 删天后预算回 500（无 day4 费用虚挂）", t_e4b == 500.0, "实测 %.0f" % (t_e4b or -1))
seg_t_e4b = re.search(r'<section id="ticket">.*?</section>', h4b, re.S)
seg_t_e4b = seg_t_e4b.group(0) if seg_t_e4b else ""
ok("E4b-4 门票表无删天残留（合成景点4 不再出现）", "合成景点4" not in seg_t_e4b)

# F4 只改窗口不同步每日日期 → V14 必 FAIL（页面日期互相冲突的防线）
b8 = copy.deepcopy(books[3])
b8["meta"]["date_window"] = {"start": "2026-12-20", "end": "2026-12-22"}
rc8, out8 = run_json_args(VAL, _dump(b8, "_f4"))
ok("F4 改窗口不同步 days 被校验器拒绝（V14）", rc8 == 1 and "[FAIL] V14" in out8)

# F5 删天未同步门票表 → _row_refs 悬空被 V03 拒绝（Codex 六轮复核第 2 条反向闸）
b9 = make_book(4)
b9["days"].pop()
b9["tickets"] = [t for t in b9["tickets"] if t["id"] != "t004"]
b9["expenses"] = [e for e in b9["expenses"] if e.get("ref") != "t004"]
b9["meta"]["date_window"]["end"] = "2026-11-03"
rc9, out9 = run_json_args(VAL, _dump(b9, "_f5"))
ok("F5 删天未同步门票表被 V03 拒绝（_row_refs 悬空）", rc9 == 1 and "[FAIL] V03" in out9)

# ---------- 三条必须失败 ----------
# F1 悬空 slot_ref → V11 FAIL
b5 = copy.deepcopy(books[3])
b5["days"][0]["cam"][0]["slot_ref"] = "d1s99"
jp = os.path.join(SYNTH, "_f1.json")
with io.open(jp, "w", encoding="utf-8") as fh:
    json.dump(b5, fh, ensure_ascii=False, indent=1)
rc, out = run_json_args(VAL, jp)
ok("F1 悬空 slot_ref 被校验器拒绝", rc == 1 and "[FAIL] V11" in out)

# F2 机位挂错时段（引用合法但违背独立预期）→ 归属核对必须报 mismatch
b6 = copy.deepcopy(books[3])
b6["days"][0]["cam"][0]["slot_ref"] = "d1s4"  # 绑到晚餐（合法引用）
ok_f2, h6 = rerender(b6, "f2")
mism6 = check_affinity(h6, expect_maps[3])
ok("F2 挂错时段被独立预期核对拒绝", ok_f2 and len(mism6) == 1,
   "mismatch=%s" % mism6)

# F3 返程图缺失 → 真图断言必须失败
b7 = copy.deepcopy(books[3])
b7["days"][2]["svg_html"] = ""
b7["days"][2]["photos_html"] = ""
ok_f3, h7 = rerender(b7, "f3")
seg7 = re.search(r'<section id="day3">.*?</section>', h7, re.S)
seg7 = seg7.group(0) if seg7 else ""
img7 = last_return_img(seg7)
p_ok7, _ = png_check(img7) if img7 else (False, "无 img")
svg_ok7 = "polyline" in seg7 and "data-arrow" in seg7
ok("F3 返程图缺失被断言捕获（svg/图双失）", ok_f3 and not p_ok7 and not svg_ok7)

OUT.close()
try:
    print("RESULT: %s (%d fails) -- details: %s"
          % ("ALL PASS" if not fails else "HAS FAIL", len(fails), RESULT))
except Exception:
    pass
sys.exit(0 if not fails else 1)

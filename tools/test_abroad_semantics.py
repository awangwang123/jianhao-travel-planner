# -*- coding: utf-8 -*-
"""test_abroad_semantics.py —— v1.2 R7 出境语义规则专项（任务书②：跨日/时差/日期绑定）
每条规则：好样本必须 PASS + 必须失败的反例（毒化）。基于 fixtures/synth_abroad_sample.json 注入。
  V19 跨日航班排天闸：到达日复现同 ref/紧邻次日/到达前不排/起飞后不排/出发夜不订房/crosses_days 声明兑现
  V21 跨时区时长自洽闸：arr=dep+官方时长+时差——时差直减（漏加时差）必拦
  V22 门票日期绑定闸：绑定日在窗口内+与实际使用日一致
用法: py test_abroad_semantics.py（结果落盘 test_abroad_semantics_result.txt）"""
import copy
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "fixtures", "synth_abroad_sample.json")
RESULT = os.path.join(HERE, "test_abroad_semantics_result.txt")
OUT = io.open(RESULT, "w", encoding="utf-8")
fails = []

base = json.load(io.open(SAMPLE, encoding="utf-8"))


def ok(name, cond, detail=""):
    OUT.write(("PASS " if cond else "FAIL ") + name + ((" | " + detail) if detail else "") + "\n")
    if not cond:
        fails.append(name)


def run_val(doc):
    p = os.path.join(HERE, "_as_run.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False))
    r = subprocess.run([sys.executable, os.path.join(HERE, "validate_trip_data.py"), p],
                       capture_output=True)
    txt = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", errors="replace")
    os.remove(p)
    return r.returncode, txt


def expect_fail(name, doc, vrule, frag=""):
    rc, txt = run_val(doc)
    ok_ = rc == 1 and f"[FAIL] {vrule}" in txt and (frag in txt if frag else True)
    OUT.write(("PASS " if ok_ else "FAIL ") + name + ((" | " + frag) if frag else "") + "\n")
    if not ok_:
        fails.append(name)


def day_of(doc, n):
    for d in doc["days"]:
        if d.get("day") == n:
            return d
    raise AssertionError("no day %s" % n)


def flight(doc):
    return doc["flights"][0]


def ticket(doc):
    return doc["tickets"][0]


# ---- 好样本：三条闸在合法出境样本上全部通过 ----
rc, txt = run_val(copy.deepcopy(base))
ok("好样本：V19 跨日排天 PASS（D1 23:50 起/D2 05:30 复现，紧邻次日+时序+无当夜房）",
   rc == 0 and "[PASS] V19" in txt, txt[-100:] if rc else "")
ok("好样本：V21 时长自洽 PASS（400min+时差-1h=05:30 自洽）",
   rc == 0 and "[PASS] V21" in txt, "")
ok("好样本：V22 日期绑定 PASS（t001 绑 12-11 且 D2 使用）",
   rc == 0 and "[PASS] V22" in txt, "")

# ---- V19 反例 ----
# a) 到达日排错天（移到 day3，非紧邻次日）
p = copy.deepcopy(base)
arr = None
for s in day_of(p, 2)["slots"]:
    if s.get("id") == "d2s1":
        arr = s
day_of(p, 2)["slots"].remove(arr)
p["meta"]["date_window"]["end"] = "2026-12-12"
p["days"].append({"day": 3, "date": "12-12", "weekday": "六", "city": "曼谷", "theme": "落地",
                  "slots": [arr], "meals": {"早餐": None, "午餐": None, "晚餐": None},
                  "stay": {"ref": "s001"}, "cam": [], "knowhow": "", "planb": ""})
expect_fail("V19 反例：到达日非紧邻次日被拦", p, "V19", "紧邻次日")

# b) 到达日前已排活动（04:30 交通早于 05:30 落地）
p = copy.deepcopy(base)
day_of(p, 2)["slots"].insert(0, {"id": "d2s0", "t": "04:30", "type": "transport", "text": "提前安排（毒化）"})
expect_fail("V19 反例：落地前已排活动被拦", p, "V19", "落地前不得已开始安排")

# c) 起飞后仍有当日安排（23:55 交通晚于 23:50 起飞）
p = copy.deepcopy(base)
day_of(p, 1)["slots"].append({"id": "d1s3", "t": "23:55", "type": "transport", "text": "起飞后活动（毒化）"})
expect_fail("V19 反例：起飞后仍排活动被拦", p, "V19", "起飞后人在空中")

# d) 出发当夜订房
p = copy.deepcopy(base)
day_of(p, 1)["stay"] = {"ref": "s001"}
expect_fail("V19 反例：出发当夜订住宿被拦", p, "V19", "当夜人在空中")

# e) 声明 crosses_days 却未排到达 slot
p = copy.deepcopy(base)
flight(p)["applicability"]["crosses_days"] = True
day_of(p, 2)["slots"] = [s for s in day_of(p, 2)["slots"] if s.get("id") != "d2s1"]
expect_fail("V19 反例：声明跨日但次日未排到达被拦", p, "V19", "次日到达未排天")

# ---- V21 反例 ----
# 时差直减（去程）：duration_min 误填钟面表差 5h40m（漏加 1h 时差）
p = copy.deepcopy(base)
flight(p)["applicability"]["duration_min"] = 340
expect_fail("V21 反例：去程时差直减（漏加时差的表差时长）被拦", p, "V21", "时差直减")

# ---- V21 返程（实战反例：全局 vs_home_hours 会把去程方向套到返程——R8 已改逐航段） ----
def add_return(p, duration):
    """注入返程航班 f002：曼谷(泰国+7) 10:00 起飞，飞 duration 分钟，武汉(+8) 到达。
    自洽条件：10:00 + duration + (+1h) = 13:00 → duration=120。费用以结构化 optional 挂账。"""
    p["flights"].append({
        "id": "f002", "name": "9C8762 曼谷→武汉（返程合成）",
        "text": "D3 返程（合成）",
        "applicability": {"flight_no": "9C8762", "dep_time": "10:00", "arr_time": "13:00",
                          "duration_min": duration, "dep_date": "2026-12-12", "arr_date": "2026-12-12",
                          "dep_tz_area": "泰国", "arr_tz_area": "武汉"},
        "billing": {"optional": True, "reason": "返程正反例注入（费用合成省略）"}})
    return p

# 返程好样本：10:00(+7) + 120min + 时差(+1h) = 13:00(+8) 自洽 → 必 PASS
p = add_return(copy.deepcopy(base), 120)
rc, txt = run_val(p)
ok("V21 返程好样本 PASS（逐航段时区：+7→+8 方向正确）", rc == 0 and "[PASS] V21" in txt, txt[-90:] if rc else "")

# 返程反例：时差直减（duration 误填 180=钟面差 3h，漏加时差方向）→ 必拦
p = add_return(copy.deepcopy(base), 180)
expect_fail("V21 返程反例：时差直减/方向弄反被拦（R6 缺口②修复实证）", p, "V21", "时差直减")

# ---- V21 R10（作者 缺口：合法 UTC+00:00 被当成缺时区——or 链把 0 当空值）----
# UTC0 好样本：出发 UTC+01:00 23:50、到达 UTC+00:00 次日 05:30、飞行 400min——自洽必 PASS
p = copy.deepcopy(base)
f0 = flight(p)
f0["applicability"]["dep_utc_offset"] = "+01:00"
f0["applicability"]["arr_utc_offset"] = "+00:00"
rc, txt = run_val(p)
ok("V21 UTC0 好样本 PASS（+01:00→+00:00 时差 -1h，0 不再被当空值）",
   rc == 0 and "[PASS] V21" in txt, txt[-90:] if rc else "")

# 缺时区反例（保留）+ 日志自洽断言：FAIL 后不得追加「[PASS] V21」行
p = copy.deepcopy(base)
ap0 = flight(p)["applicability"]
ap0.pop("dep_tz_area")
ap0.pop("arr_tz_area")
rc, txt = run_val(p)
c_mz = rc == 1 and "[FAIL] V21" in txt and "[PASS] V21" not in txt
OUT.write(("PASS " if c_mz else "FAIL ") + "V21 缺时区必拦且日志自洽（无自相矛盾 PASS 行）"
          + ((" | " + txt[-90:].replace(chr(10), " ")) if not c_mz else "") + "\n")
if not c_mz:
    fails.append("V21 缺时区必拦且日志自洽")

# ---- V21 R9（作者 缺口②③）：完整日期核对 + 输入完备强制 ----
# 时长多填一天（400→1840）：完整日期时间核对必拦（钟面取模旧法曾放过）
p = copy.deepcopy(base)
flight(p)["applicability"]["duration_min"] = 1840
expect_fail("V21 反例：时长多填一天（1840=400+24h）被拦（R8 缺口②修复实证）", p, "V21", "相差")

# 缺航段时区：有航班缺检查输入=未检 → 必拦（旧版曾标 PASS「跳过」）
p = copy.deepcopy(base)
ap0 = flight(p)["applicability"]
ap0.pop("dep_tz_area")
ap0.pop("arr_tz_area")
expect_fail("V21 反例：缺航段时区=未检被拦（R8 缺口③修复实证）", p, "V21", "未检")

# 缺日期：无 dep_date/arr_date 不能宣称跨日时长已核 → 必拦
p = copy.deepcopy(base)
ap0 = flight(p)["applicability"]
ap0.pop("dep_date")
ap0.pop("arr_date")
expect_fail("V21 反例：缺日期=未检被拦（不能宣称跨日时长已检查）", p, "V21", "未检")

# ---- V22 反例 ----
# a) 绑错日：票绑 12-10 但行程 D2（12-11）使用
p = copy.deepcopy(base)
ticket(p)["applicability"]["date"] = "12-10"
expect_fail("V22 反例：绑定日与使用日错位被拦", p, "V22", "日期绑定错位")

# b) 绑定日超出行程窗口
p = copy.deepcopy(base)
ticket(p)["applicability"]["date"] = "12-15"
expect_fail("V22 反例：绑定日超出行程窗口被拦", p, "V22", "行程之外")

# ---- V22 跨年窗口（实战反例：统一换年份破坏跨年顺序——R8 已改窗口内定年） ----
def make_cross_year(p):
    """窗口 2026-12-31~2027-01-02（3 天），票绑 01-01 且 D2(01-01) 使用——合法自洽"""
    p["meta"]["date_window"] = {"start": "2026-12-31", "end": "2027-01-02"}
    p["days"][0]["date"] = "12-31"
    p["days"][1]["date"] = "01-01"
    p["days"].append({"day": 3, "date": "01-02", "weekday": "六", "city": "曼谷", "theme": "返程",
                      "slots": [], "meals": {"早餐": None, "午餐": None, "晚餐": None},
                      "stay": None, "cam": [], "knowhow": "", "planb": ""})
    ticket(p)["applicability"]["date"] = "01-01"  # 绑定日随窗口同步（01-01 应解析到 2027）
    return p

# 跨年好样本：01-01 解析到 2027 年（窗口末年）→ 必 PASS
p = make_cross_year(copy.deepcopy(base))
rc, txt = run_val(p)
ok("V22 跨年好样本 PASS（窗口 12-31~01-02、票绑 01-01 且当日使用）",
   rc == 0 and "[PASS] V22" in txt, txt[-90:] if rc else "")

# 跨年错日反例：票绑 01-02 但行程 D2(01-01) 使用 → 必拦
p = make_cross_year(copy.deepcopy(base))
ticket(p)["applicability"]["date"] = "01-02"
expect_fail("V22 跨年反例：绑定日与使用日错位仍拦（跨年窗口不误放）", p, "V22", "日期绑定错位")

OUT.write("RESULT: %s (%d fails)\n" % ("ALL PASS" if not fails else "HAS FAIL", len(fails)))
try:
    print("RESULT: %s (%d fails)" % ("ALL PASS" if not fails else "HAS FAIL", len(fails)))
except Exception:
    pass
sys.exit(0 if not fails else 1)

# -*- coding: utf-8 -*-
"""test_abroad.py —— v1.2 出境合成测试（任务书④：跨日/时区/多币种确定性测试）
样本: fixtures/synth_abroad_sample.json（曼谷 2 天：红眼跨日航班/时区 +07:00/THB 双币）
断言:
  1. 合法出境样本 → validate 全 PASS（格式层兼容出境实证）
  2. fx 毒化（rate=0） → V07 拦截（既有能力回归）
  3. fx 缺 THB 通路 → V10 拦截（既有能力回归）
盲区声明（如实，非工具缺陷登记）: 时差直减时长/门票绑日期错位的**语义级**校验
  属出境规则配置工程（后续），本测试只证明格式层与既有闸门行为。"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "fixtures", "synth_abroad_sample.json")
RESULT = os.path.join(HERE, "test_abroad_result.txt")
OUT = io.open(RESULT, "w", encoding="utf-8")
fails = []


def ok(name, cond, detail=""):
    OUT.write(("PASS " if cond else "FAIL ") + name + ((" | " + detail) if detail else "") + "\n")
    if not cond:
        fails.append(name)


def run_val(doc, tag):
    p = os.path.join(HERE, f"_abroad_{tag}.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False))
    r = subprocess.run([sys.executable, os.path.join(HERE, "validate_trip_data.py"), p],
                       capture_output=True)
    txt = (r.stdout or b"").decode("utf-8", errors="replace") + (r.stderr or b"").decode("utf-8", errors="replace")
    os.remove(p)
    return r.returncode, txt


base = json.load(io.open(SAMPLE, encoding="utf-8"))

# 1. 合法出境样本
rc, txt = run_val(base, "legal")
ok("合法出境样本全 PASS（含跨日红眼/时区/THB）", rc == 0 and "RESULT: PASS" in txt)

# 2. fx rate=0 毒化 → V07 拦
import copy
poison = copy.deepcopy(base)
poison["meta"]["fx"][0]["rate"] = 0
rc, txt = run_val(poison, "fx0")
ok("fx rate=0 被 V07 拦", rc == 1 and "[FAIL] V07" in txt and "汇率必须>0" in txt)

# 3. fx 缺 THB 通路毒化 → V10 拦
poison = copy.deepcopy(base)
poison["meta"]["fx"] = []
rc, txt = run_val(poison, "nofx")
ok("fx 缺 THB 通路被 V10 拦", rc == 1 and "V10" in txt and ("无法折算" in txt or "fx 缺通路" in txt))

# 4. utc_offset 格式毒化 → V07 拦
poison = copy.deepcopy(base)
poison["meta"]["timezones"][0]["utc_offset"] = "7"
rc, txt = run_val(poison, "tz")
ok("utc_offset 非 ±HH:MM 被 V07 拦", rc == 1 and "不是 ±HH:MM" in txt)

OUT.write("盲区声明: 时差直减时长/门票绑日期错位的语义级校验属出境规则配置工程（后续），本套只测格式层与既有闸门。\n")
OUT.write("RESULT: %s (%d fails)\n" % ("ALL PASS" if not fails else "HAS FAIL", len(fails)))
try:
    print("RESULT: %s (%d fails) -- %s" % ("ALL PASS" if not fails else "HAS FAIL", len(fails), RESULT))
except Exception:
    pass
sys.exit(0 if not fails else 1)

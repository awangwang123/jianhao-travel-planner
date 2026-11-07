# -*- coding: utf-8 -*-
"""pipeline.py —— v1.2 统一制作入口（任务书④：整合制作入口+自动计时，替代每册临时写脚本）
用法:
  py tools/pipeline.py full <trip_data.json> <输出.html> [标题]
      全链: validate → gen → apply_routes(有 routes 时) → consistency（不过就停，并删掉输出）→ checklist
      自动计时（timer start/end 落 timer_records.jsonl），各环节失败即停并报环节名
  py tools/pipeline.py check <成品.html>            # 只跑 checklist
  py tools/pipeline.py validate <trip_data.json>    # 只跑数据闸
各环节输出原文直通（失败原文可直接贴给用户）。"""
import io
import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(step, cmd, must_fail_keywords=(), delete_on_fail=None):
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True)
    dur = time.time() - t0
    out = (r.stdout or b"").decode("utf-8", errors="replace") + (r.stderr or b"").decode("utf-8", errors="replace")
    tail = "\n".join(out.strip().splitlines()[-12:]) if out.strip() else "(无输出)"
    print("── [%s] %s （%.0fs）" % ("OK" if r.returncode == 0 else "FAIL", step, dur))
    print(tail)
    if r.returncode != 0:
        if delete_on_fail and os.path.exists(delete_on_fail):
            os.remove(delete_on_fail)
            print("已删除未过闸的输出: %s（避免漂掉的 HTML 留在盘上）" % delete_on_fail)
        print("⛔ 环节失败: %s（exit %d）——全链停止" % (step, r.returncode))
        sys.exit(1)
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    mode = sys.argv[1]
    if mode == "validate":
        run("数据闸 V01-V16", [PY, os.path.join(HERE, "validate_trip_data.py"), sys.argv[2]])
        return
    if mode == "check":
        args = [PY, os.path.join(HERE, "checklist.py"), sys.argv[2]] + (["--visual"] if "--visual" in sys.argv else [])
        run("成品闸 checklist", args)
        return
    if mode != "full" or len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    data, out_html = sys.argv[2], sys.argv[3]
    tag = os.path.basename(out_html).rsplit(".", 1)[0]
    rec_tag = "full:" + tag
    import timer as timer_mod
    timer_mod.start_timer(rec_tag)  # R2：入口自动计时——不再依赖人工预挂 start
    print("▶ 全链开工: %s → %s" % (os.path.basename(data), out_html))
    outcome = "OK"
    try:
        run("① 数据闸", [PY, os.path.join(HERE, "validate_trip_data.py"), data])
        run("② 渲染 gen", [PY, os.path.join(HERE, "gen_roadbook.py"), data, out_html])
        routes_info = run("③ 导览图注入", [PY, os.path.join(HERE, "apply_routes.py"), data, out_html])
        applied = "applied" in routes_info
        base = os.path.join(HERE, "..", "assets", "路书_基准骨架.html")
        run("④ 版式闸 consistency",
            [PY, os.path.join(HERE, "consistency.py"), out_html, "--base", base],
            delete_on_fail=out_html)
        vis = ["--visual"] if "--visual" in sys.argv else []
        run("⑤ 成品闸", [PY, os.path.join(HERE, "checklist.py"), out_html] + vis)
    except SystemExit:
        outcome = "FAILED"
        timer_mod.end_timer(rec_tag, outcome=outcome)
        raise
    human = timer_mod.end_timer(rec_tag, outcome=outcome)
    path_report = ("导览图新路径已执行并注入" if applied
                   else "旧数据兼容路径（routes 缺失，导览图未生成）——与执行成功分开报告")
    print("⏱ 本链耗时: %s（自动计时落 timer_records.jsonl）｜路径: %s" % (human, path_report))


def cmd_new(args):
    """v1.19: 从 template_trip_data.json 实例化骨架——普通制作只填值，不读源码"""
    import json as _json
    import datetime
    tpl = os.path.join(HERE, "..", "template_trip_data.json")
    data = _json.load(io.open(tpl, encoding="utf-8"))
    start = datetime.date.fromisoformat(args.start)
    days = data["days"][:args.days]
    need = args.days - len(days)
    for i in range(max(0, need)):
        last = data["days"][-1]
        days.append(dict(last, day=len(days) + 1))
    data["days"] = days
    wd = "一二三四五六日"
    for i, day in enumerate(data["days"]):
        dt = start + datetime.timedelta(days=i)
        day["date"] = dt.strftime("%m-%d")
        day["weekday"] = wd[dt.weekday()]
    data["meta"]["title"] = "%s %d 天 · 朋友版" % (args.dest, args.days)
    data["meta"]["destination"] = args.dest
    data["meta"]["date_window"] = {"start": start.isoformat(),
                                   "end": (start + datetime.timedelta(days=args.days - 1)).isoformat()}
    out = os.path.join(args.dir, "trip_data.json")
    os.makedirs(args.dir, exist_ok=True)
    io.open(out, "w", encoding="utf-8").write(_json.dumps(data, ensure_ascii=False, indent=1))
    print("skeleton written:", out)
    print("next: edit it (fields -> schema.md speed table), then: pipeline.py outline %s" % out)


def cmd_outline(args):
    """v1.19: 简表前置检查点——30 秒出时刻轴+费用速算+预警，过了再配图扩写"""
    import re
    import json as _json
    data = _json.load(io.open(args.data, encoding="utf-8"))
    warns = []
    print("========== 行程简表 ==========")
    for day in data["days"]:
        print("D%s %s %s · %s" % (day["day"], day.get("date", ""), day.get("weekday", ""), day.get("theme", "")))
        prev = None
        for s in day["slots"]:
            if isinstance(s["t"], str):
                t = s["t"]
            else:
                tr = s["t"].get("tr_ref")
                t = "?"
                for trr in data.get("transports", []):
                    if trr["id"] == tr:
                        t = trr["applicability"].get(s["t"].get("field"), "?")
            if prev and t < prev:
                warns.append("D%s 时刻倒退: %s 在 %s 之后" % (day["day"], t, prev))
            prev = t
            txt = re.sub(r"<[^>]+>", "", s.get("text", ""))[:38]
            print("  %s %-9s %s" % (t, s.get("type", ""), txt))
    print("========== 费用速算（主选，不含自选） ==========")
    lo = hi = 0.0
    for e in data.get("expenses", []):
        if (e.get("billing") or {}).get("optional"):
            continue
        unit = e.get("unit", "")
        mult = 2 if unit == "每人" else (e.get("scope", {}).get("rooms", 1) if unit == "每间夜" else 1)
        a = e.get("amount")
        mn, mx = e.get("amount_min"), e.get("amount_max")
        if a is not None:
            l = hh = a * mult
        elif mn is not None and mx is not None:
            l, hh = mn * mult, mx * mult
        else:
            warns.append("费用 %s(%s) 无金额字段" % (e.get("id"), e.get("label", "")[:12]))
            continue
        lo += l
        hi += hh
    print("合计: %.0f ~ %.0f CNY（2 人）｜人均 %.0f ~ %.0f" % (lo, hi, lo / 2, hi / 2))
    n_meal = {}
    for e in data.get("expenses", []):
        if e.get("category") == "餐饮" and not (e.get("billing") or {}).get("optional"):
            n_meal[e.get("ref", "?")] = 1
    print("========== 预警 ==========")
    if not warns:
        print("（无）")
    else:
        for w in warns:
            print("⚠ " + w)
    print("提醒: 过了这关再配图扩写；配图后跑 full --visual")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "new":
        ap = __import__("argparse")
        p = ap.ArgumentParser()
        p.add_argument("dest")
        p.add_argument("--days", type=int, default=3)
        p.add_argument("--start", required=True, help="首日日期 YYYY-MM-DD")
        p.add_argument("--dir", default="pkg_work")
        a = p.parse_args(sys.argv[2:])
        cmd_new(a)
    elif len(sys.argv) >= 2 and sys.argv[1] == "outline":
        cmd_outline(type("A", (), {"data": sys.argv[2]})())
    else:
        main()

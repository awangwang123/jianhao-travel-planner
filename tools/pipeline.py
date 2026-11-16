# -*- coding: utf-8 -*-
"""pipeline.py —— v1.2 统一制作入口（任务书④：整合制作入口+自动计时，替代每册临时写脚本）
用法:
  py tools/pipeline.py full <trip_data.json> <输出.html> [标题]
      全链: validate → route_map(有 map_spec 时出图回写数据) → gen → apply_routes(旧 routes 兼容) → checklist
      自动计时（timer start/end 落 timer_records.jsonl），各环节失败即停并报环节名
      v1.20 三批（11-05 复核）：地图工具接入正式入口——改行程后同一入口重跑，地图随数据同步，
      不再允许「手动跑 route_map 把结果算作入口完成」；审计失败(孤儿时刻/出界)即停链。
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


def run(step, cmd, must_fail_keywords=()):
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True)
    dur = time.time() - t0
    out = (r.stdout or b"").decode("utf-8", errors="replace") + (r.stderr or b"").decode("utf-8", errors="replace")
    tail = "\n".join(out.strip().splitlines()[-3:]) if out.strip() else "(无输出)"
    print("── [%s] %s （%.0fs）" % ("OK" if r.returncode == 0 else "FAIL", step, dur))
    print(tail)
    if r.returncode != 0:
        print("⛔ 环节失败: %s（exit %d）——全链停止" % (step, r.returncode))
        sys.exit(1)
    return out, dur


def gate_check():
    """v128（M9C R5 实证）：入口自检——基准骨架可读是渲染/成品闸的共同依赖。
    解包没走正门（Windows 自带解压/unzip）会损坏 assets 中文文件名 → 到渲染环节才 FileNotFoundError
    白烧一轮。开跑即拦并指回 setup_pack.py 正门。"""
    base = os.path.join(HERE, "..", "assets", "路书_基准骨架.html")
    if not os.path.exists(base):
        print("⛔ 基准骨架缺失: assets/路书_基准骨架.html")
        print("   常见原因 = 解包没用正门（Windows 自带解压/unzip 损坏中文文件名）。")
        print("   修法: py tools/setup_pack.py <包.zip> --sha256 <发布页值>（勿用其他解压方式）")
        sys.exit(1)


def write_summary(out_html, data, steps, checklist_out):
    """v128（交付文档自动汇总）：full 成功后自动写交付摘要——环节耗时/成品闸结果/产物清单/今日计时。
    制作侧 TESTLOG 引用它+只补解释，不再手写长篇战果报告。"""
    lines = ["# 交付摘要（pipeline 自动生成 %s）" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
    lines.append("## 一、全链环节耗时（自动计时）")
    lines.append("| 环节 | 耗时 |")
    lines.append("|---|---|")
    total = 0.0
    for name, dur in steps:
        if isinstance(dur, str):
            # v1.20 图像选项跳过步（配置声明）——无耗时，不计入合计
            lines.append("| %s | %s |" % (name, dur))
            continue
        lines.append("| %s | %.0fs |" % (name, dur))
        total += dur
    lines.append("| **全链合计** | **%.0fs（%.1f 分钟）** |" % (total, total / 60))
    lines.append("")
    lines.append("## 二、成品闸结果（checklist 尾部原文）")
    for ln in checklist_out.strip().splitlines():
        if ("结果" in ln) or ("FAIL" in ln and "WARN" in ln):
            lines.append("    " + ln.strip())
    lines.append("")
    lines.append("## 三、产物清单")
    lines.append("| 文件 | 字节 |")
    lines.append("|---|---|")
    for p in [data, out_html]:
        if os.path.exists(p):
            lines.append("| %s | %d |" % (os.path.basename(p), os.path.getsize(p)))
    ddir = os.path.dirname(os.path.abspath(data))
    for sub in ("maps", "images"):
        sd = os.path.join(ddir, sub)
        if os.path.isdir(sd):
            for f in sorted(os.listdir(sd)):
                fp = os.path.join(sd, f)
                if os.path.isfile(fp) and not f.endswith(".json"):
                    lines.append("| %s/%s | %d |" % (sub, f, os.path.getsize(fp)))
    lines.append("")
    lines.append("## 四、今日 timer 记录（timer_records.jsonl 当日）")
    rec_file = os.path.join(HERE, "timer_records.jsonl")
    today = time.strftime("%Y-%m-%d")
    if os.path.exists(rec_file):
        for line in io.open(rec_file, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("start", r.get("end", "")).startswith(today):
                if r.get("type") == "stage":
                    lines.append("- stage %s：%s（止于 %s）" % (r.get("stage"), r.get("human"), r.get("end")))
                else:
                    lines.append("- %s：%s（%s → %s，%s）" % (r.get("tag"), r.get("human"),
                                 r.get("start"), r.get("end"), r.get("outcome", "")))
    lines.append("")
    lines.append("> 本摘要由 pipeline.py 自动汇总（交付文档自动汇总口径：机器数据机器出，"
                 "人只补解释）——TESTLOG 引用本文件+补人工解释（人工复核四项结论/绕行记录/口径声明），不重复上表数据。")
    sp = out_html + ".交付摘要.md"
    io.open(sp, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("📄 交付摘要已写: %s" % sp)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    mode = sys.argv[1]
    gate_check()  # v128：入口自检——解包损坏开跑即拦
    if mode == "validate":
        run("数据闸 V01-V26", [PY, os.path.join(HERE, "validate_trip_data.py"), sys.argv[2]])
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
    steps = []
    try:
        _, d1 = run("① 数据闸", [PY, os.path.join(HERE, "validate_trip_data.py"), data])
        steps.append(("数据闸", d1))
        # v1.20 图像选项（schema §5d）：map:false 跳过地图生成步（配置声明，非偷跑——
        # 数据闸 V27 已拦「声明关图却带 map_spec」矛盾），渲染出的成品无导览图，
        # 成品闸按 gen 注入的 image-options 标记记「不适用」。
        import json as _j
        _io = _j.load(open(data, encoding="utf-8")).get("image_options") or {}
        if _io.get("map", True):
            _, d2 = run("② 地图生成 route_map", [PY, os.path.join(HERE, "route_map.py"), data])
            steps.append(("地图 route_map", d2))
        else:
            steps.append(("地图 route_map", "跳过（配置声明 map:false）"))
            print("⏭ ② 地图生成跳过——image_options.map=false（配置声明）")
        _, d3 = run("③ 渲染 gen", [PY, os.path.join(HERE, "gen_roadbook.py"), data, out_html])
        steps.append(("渲染 gen", d3))
        routes_info, d4 = run("④ 旧路线注入(兼容)", [PY, os.path.join(HERE, "apply_routes.py"), data, out_html])
        steps.append(("路线注入", d4))
        applied = "applied" in routes_info
        vis = ["--visual"] if "--visual" in sys.argv else []
        ck_out, d5 = run("⑤ 成品闸", [PY, os.path.join(HERE, "checklist.py"), out_html] + vis)
        steps.append(("成品闸", d5))
    except SystemExit:
        outcome = "FAILED"
        timer_mod.end_timer(rec_tag, outcome=outcome)
        raise
    human = timer_mod.end_timer(rec_tag, outcome=outcome)
    write_summary(out_html, data, steps, ck_out)
    path_report = ("地图由入口生成(route_map)＋旧路线注入" if applied
                   else "地图由入口生成(route_map)；routes 缺失走旧数据兼容(无旧路线注入)")
    print("⏱ 本链耗时: %s（自动计时落 timer_records.jsonl）｜路径: %s" % (human, path_report))


def cmd_new(args):
    """v1.19: 从 template_trip_data.json 实例化骨架——普通制作只填值，不读源码"""
    import json as _json
    import datetime
    gate_check()  # v128：骨架/渲染依赖基准骨架，解包损坏第一入口即拦
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
    # v128（洁净室验收抓的 new 缺口）：窗口平移后示例票的绑定日同步——否则新骨架开跑即 V22 FAIL
    # （模板示例票默认 D2 使用：applicability.date=窗口第 2 天；单日窗口兜底=D1）
    last_day = start + datetime.timedelta(days=args.days - 1)
    use_day = start + datetime.timedelta(days=1)
    if use_day > last_day:
        use_day = start
    for tk in data.get("tickets", []):
        ap = tk.get("applicability")
        if isinstance(ap, dict) and ap.get("date"):
            ap["date"] = use_day.strftime("%m-%d")
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

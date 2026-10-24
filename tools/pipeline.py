# -*- coding: utf-8 -*-
"""pipeline.py —— v1.2 统一制作入口（任务书④：整合制作入口+自动计时，替代每册临时写脚本）
用法:
  py tools/pipeline.py full <trip_data.json> <输出.html> [标题]
      全链: validate → gen → apply_routes(有 routes 时) → checklist
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
        vis = ["--visual"] if "--visual" in sys.argv else []
        run("④ 成品闸", [PY, os.path.join(HERE, "checklist.py"), out_html] + vis)
    except SystemExit:
        outcome = "FAILED"
        timer_mod.end_timer(rec_tag, outcome=outcome)
        raise
    human = timer_mod.end_timer(rec_tag, outcome=outcome)
    path_report = ("导览图新路径已执行并注入" if applied
                   else "旧数据兼容路径（routes 缺失，导览图未生成）——与执行成功分开报告")
    print("⏱ 本链耗时: %s（自动计时落 timer_records.jsonl）｜路径: %s" % (human, path_report))


if __name__ == "__main__":
    main()

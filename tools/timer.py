# -*- coding: utf-8 -*-
"""timer.py —— v1.2 自动计时（任务书②④：不再让模型事后估算耗时；M6 两轮虚账教训）
用法:
  py timer.py start <标签>    # 记录开工时间戳
  py timer.py end <标签>      # 记录收尾并结算差值 → timer_records.jsonl（追加）
  py timer.py list            # 查看全部记录
时间源=time.now()（date 等价），估算禁入。"""
import io
import json
import os
import sys
import time

# v1.2：stdout 不在此包装（print 全 ASCII）——模块级包装会在被 pipeline import 时
# 重新包装宿主 stdout，旧 wrapper GC 关闭底层 buffer 致宿主 print 崩（I/O on closed file 实证）

HERE = os.path.dirname(os.path.abspath(__file__))
TS_FILE = os.path.join(HERE, ".timer_state.json")
LOG_FILE = os.path.join(HERE, "timer_records.jsonl")


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S"), time.time()


def start_timer(tag):
    """函数 API（pipeline 自动计时用）：等价 CLI start。返回 start_epoch。"""
    ts, epoch = _now()
    state = {}
    if os.path.exists(TS_FILE):
        state = json.load(io.open(TS_FILE, encoding="utf-8"))
    state[tag] = {"start_str": ts, "start_epoch": epoch}
    io.open(TS_FILE, "w", encoding="utf-8").write(json.dumps(state, ensure_ascii=False, indent=1))
    return epoch


def end_timer(tag, outcome="OK"):
    """函数 API：结算并落盘（outcome 记成功/失败——R2：失败也是计时记录）。返回 human 时长。"""
    ts, epoch = _now()
    state = {}
    if os.path.exists(TS_FILE):
        state = json.load(io.open(TS_FILE, encoding="utf-8"))
    st = state.pop(tag, None)
    if st is None:
        # R2：无预挂 start 时由入口自动补——起点未知则记「入口启动时刻起算」并在记录中声明
        st = {"start_str": ts, "start_epoch": epoch, "auto_start": True}
    dur = max(0.0, epoch - st["start_epoch"])
    rec = {"tag": tag, "start": st["start_str"], "end": ts, "seconds": round(dur, 1),
           "human": "%dm%02ds" % (int(dur // 60), int(dur % 60)),
           "outcome": outcome}
    if st.get("auto_start"):
        rec["note"] = "入口自动起算（不含入口前的准备时间）"
    with io.open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    io.open(TS_FILE, "w", encoding="utf-8").write(json.dumps(state, ensure_ascii=False, indent=1))
    return rec["human"]


def main():
    if len(sys.argv) < 2:
        print("usage: py timer.py start|end <标签> | list")
        sys.exit(2)
    cmd = sys.argv[1]
    tag = sys.argv[2] if len(sys.argv) > 2 else ""
    state = {}
    if os.path.exists(TS_FILE):
        state = json.load(io.open(TS_FILE, encoding="utf-8"))
    if cmd == "start":
        ts, epoch = _now()
        state[tag] = {"start_str": ts, "start_epoch": epoch}
        io.open(TS_FILE, "w", encoding="utf-8").write(json.dumps(state, ensure_ascii=False, indent=1))
        print("TIMER start [%s] %s" % (tag, ts))
    elif cmd == "end":
        if not tag:
            print("TIMER ERROR: end 需要标签")
            sys.exit(2)
        ts, epoch = _now()
        if tag not in state:
            print("TIMER ERROR: [%s] 没有 start 记录——禁止无起点结算（估算禁入）" % tag)
            sys.exit(1)
        st = state.pop(tag)
        dur = epoch - st["start_epoch"]
        rec = {"tag": tag, "start": st["start_str"], "end": ts, "seconds": round(dur, 1),
               "human": "%dm%02ds" % (int(dur // 60), int(dur % 60))}
        with io.open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        io.open(TS_FILE, "w", encoding="utf-8").write(json.dumps(state, ensure_ascii=False, indent=1))
        print("TIMER end [%s] %s -> %s -> %s" % (tag, st["start_str"], ts, rec["human"]))
    elif cmd == "list" or cmd == "listall":
        if os.path.exists(LOG_FILE):
            for line in io.open(LOG_FILE, encoding="utf-8"):
                r = json.loads(line)
                print("%s  %s ~ %s  %s" % (r["tag"], r["start"], r["end"], r["human"]))
        else:
            print("(no records)")
    else:
        print("unknown cmd:", cmd)
        sys.exit(2)


if __name__ == "__main__":
    main()

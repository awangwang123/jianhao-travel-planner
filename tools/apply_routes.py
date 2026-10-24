# -*- coding: utf-8 -*-
"""apply_routes.py —— v1.2 导览图注入（gen 之后的后处理，不动核心渲染器）
用法: py apply_routes.py <trip_data.json> <成品.html>
行为: trip_data.routes 存在 → gen_route_svg 生成 → 替换成品中各 day section 的第一个 <svg>…</svg>
     routes 缺失 → 原样退出（兼容既有数据）；毒化数据 → ValueError 拒绝（不写文件）
print 只 ASCII"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_route_svg import gen_all, validate_routes  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    if len(sys.argv) < 3:
        print("usage: py apply_routes.py <trip_data.json> <成品.html>")
        sys.exit(2)
    data_path, html_path = sys.argv[1], sys.argv[2]
    import json
    data = json.load(io.open(data_path, encoding="utf-8"))
    if not data.get("routes"):
        print("no routes in data -- skip (v1.1 compatible)")
        return
    validate_routes(data["routes"])          # 毒化闸：非法数据不写文件
    pieces = gen_all(data)                    # [(day, svg)]
    h = io.open(html_path, encoding="utf-8").read()
    replaced = 0
    for day, svg in pieces:
        sec = re.search(r'<section id="day%d">(.*?)</section>' % day, h, re.S)
        if not sec:
            print("WARN: day%d section not found -- skipped" % day)
            continue
        seg = sec.group(1)
        new_seg, n = re.subn(r"<svg\b.*?</svg>", lambda _: svg, seg, count=1, flags=re.S)
        if n == 0:
            # 区块内无既有 SVG → 注入到 section 开头（h3 之后）
            new_seg = re.sub(r"(</h3>)", r"\1\n" + svg, seg, count=1)
            if new_seg == seg:
                new_seg = svg + seg
        h = h[:sec.start(1)] + new_seg + h[sec.end(1):]
        replaced += 1
    io.open(html_path, "w", encoding="utf-8").write(h)
    print("applied %d route svg(s) -> %s" % (replaced, os.path.basename(html_path)))


if __name__ == "__main__":
    main()

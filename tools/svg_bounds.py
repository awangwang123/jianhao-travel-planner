# -*- coding: utf-8 -*-
"""
svg_bounds.py —— 导览图出界点断言的可测实现（v1.18 从 checklist 2c 抽出）
背景: 旧 2c 只认 `viewBox 在前 + class="zoomable" 在后` 且只解析 polyline/circle——
      gen_route_svg 程序化注入的导览图是 `class="route-svg"`（class 在前）、动线用
      line/rect、path 仅 marker 小三角——形态完全不匹配，数出 0 张还报 PASS（零样本假绿）。
本模块: ①类名兼容 zoomable（skill 手工导览图）与 route-svg（程序化注入），属性顺序无关
        ②元素覆盖 polyline/circle/line/rect/path(d 数字对)
        ③零匹配不算通过——调用方须对 svg_n==0 报 WARN/FAIL（fail-closed）
取舍: path d 提取全部坐标对（含贝塞尔控制点）——保守方向宁可误报不漏报；
      marker 局部小坐标（0~10）天然在界内不会误报。
"""
import re

# 认这些类名的 svg 才是导览图（其余 svg 不检查）
CLASS_KEYS = ("zoomable", "route-svg")


def _attr(tag, name):
    m = re.search(r'\b%s="(-?[\d.]+)"' % name, tag)
    return float(m.group(1)) if m else None


def check_svg_bounds(t):
    """扫描 HTML 文本，返回 (svg_n, skipped, bad_list)。
    svg_n=已检查的导览图张数；skipped=类名匹配但 viewBox 非 "0 0" 起点无法检查的张数；
    bad_list 元素形如 "SVG#1出界3点"。"""
    svg_n = skipped = 0
    bad = []

    for sm in re.finditer(r'<svg\b([^>]*)>(.*?)</svg>', t, re.S):
        attrs, body = sm.group(1), sm.group(2)
        cls = re.search(r'class="([^"]*)"', attrs)
        if not cls or not any(k in cls.group(1) for k in CLASS_KEYS):
            continue
        vm = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', attrs)
        if not vm:
            skipped += 1
            continue
        vw, vh = float(vm.group(1)), float(vm.group(2))
        svg_n += 1
        oob = 0

        def hit(x, y):
            nonlocal oob
            if x < -2 or y < -2 or x > vw + 2 or y > vh + 2:
                oob += 1

        # polyline：points="x,y x,y ..."
        for pm in re.finditer(r'<polyline\b[^>]*\bpoints="([^"]+)"', body):
            for pt in pm.group(1).split():
                xy = pt.split(",")
                if len(xy) == 2:
                    hit(float(xy[0]), float(xy[1]))
        # circle / line / rect：抓标签后逐属性抽（属性顺序无关）
        for cm in re.finditer(r'<circle\b[^>]*>', body):
            cx, cy = _attr(cm.group(0), "cx"), _attr(cm.group(0), "cy")
            if cx is not None and cy is not None:
                hit(cx, cy)
        for lm in re.finditer(r'<line\b[^>]*>', body):
            tag = lm.group(0)
            x1, y1 = _attr(tag, "x1"), _attr(tag, "y1")
            x2, y2 = _attr(tag, "x2"), _attr(tag, "y2")
            if None not in (x1, y1, x2, y2):
                hit(x1, y1)
                hit(x2, y2)
        for rm in re.finditer(r'<rect\b[^>]*>', body):
            tag = rm.group(0)
            x, y = _attr(tag, "x"), _attr(tag, "y")
            w, h = _attr(tag, "width"), _attr(tag, "height")
            if None not in (x, y, w, h):
                hit(x, y)
                hit(x + w, y)
                hit(x, y + h)
                hit(x + w, y + h)
        # path：d 里全部数字对当坐标点查（marker 局部小坐标天然在界内）
        for pm in re.finditer(r'<path\b[^>]*\bd="([^"]+)"', body):
            for nm in re.finditer(r'(-?[\d.]+)[ ,]+(-?[\d.]+)', pm.group(1)):
                hit(float(nm.group(1)), float(nm.group(2)))

        if oob:
            bad.append("SVG#%d出界%d点" % (svg_n, oob))
    return svg_n, skipped, bad

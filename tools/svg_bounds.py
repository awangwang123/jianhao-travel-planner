# -*- coding: utf-8 -*-
"""
svg_bounds.py —— 导览图出界点断言的可测实现（v1.18 立，v1.18r2 按 WW 二次复核收紧）
设计原则: ①只声明「已检查」的才算检查过——任何无法完整解析的形态一律计入 partial 阻断，
          禁静默跳过；②只覆盖生成器实际使用的形态（绝对 M/L/Z path + line/rect/polyline
          + circle/ellipse 含半径），超出能力的写法（相对命令/H/V/贝塞尔/transform/
          非 0 0 viewBox）明确未检；③类名不识别的 svg 单独计数，调用方判定阻断。
返回: dict(checked, partial, unrecognized, bad, total)
      checked=完成坐标检查张数（含查出出界的）；partial=未能完成检查的张数明细；
      unrecognized=有 viewBox 但类名不是导览图的张数；bad=出界明细；total=带 viewBox 的 svg 总数。
"""
import re

CLASS_KEYS = ("zoomable", "route-svg")
# path d 允许的命令字母：M/L 绝对坐标对 + Z/z 闭合（生成器 marker 三角形态）。
# 相对命令(m l h v c q s t a)与贝塞尔/弧线(C Q S T H V A)一律阻断——数字配对不等于坐标语义
_PATH_OK = set("MLZz")
_NUM = r"-?[\d.]+"


def _attr(tag, name):
    m = re.search(r'\b%s="(%s)"' % (name, _NUM), tag)
    return float(m.group(1)) if m else None


def check_svg_bounds(t):
    total = checked = unrecognized = 0
    partial = []
    bad = []
    idx = 0  # 已识别导览图编号（bad/partial 明细用）

    for sm in re.finditer(r'<svg\b([^>]*)>(.*?)</svg>', t, re.S):
        attrs, body = sm.group(1), sm.group(2)
        if 'viewBox="' not in attrs:
            continue  # 无坐标系的 svg（装饰件）不在导览图判定范围
        total += 1
        cls = re.search(r'class="([^"]*)"', attrs)
        if not cls or not any(k in cls.group(1) for k in CLASS_KEYS):
            unrecognized += 1
            continue
        idx += 1
        tagname = "SVG#%d" % idx

        vm = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', attrs)
        if not vm:
            partial.append(tagname + " viewBox 非「0 0 宽 高」起点，坐标语义未定未检")
            continue
        if re.search(r'\btransform="', attrs) or re.search(r'\btransform="', body):
            partial.append(tagname + " 含 transform 变换，属性坐标≠渲染位置未检")
            continue
        vw, vh = float(vm.group(1)), float(vm.group(2))
        oob = 0
        hits = 0  # 实际完成坐标检查的点数——零点=未检查（v1.18r3：解析不完整/零坐标不得计入已检查）
        unsup = []

        def hit(x, y):
            nonlocal oob, hits
            hits += 1
            if x < -2 or y < -2 or x > vw + 2 or y > vh + 2:
                oob += 1

        def seg(tag, names):
            """四至点检查；属性缺失返回 False（调用方计阻断）"""
            vals = [_attr(tag, n) for n in names]
            if any(v is None for v in vals):
                return False
            xs, ys = vals[0::2], vals[1::2]
            hit(min(xs), min(ys))
            hit(max(xs), max(ys))
            return True

        # polyline：坐标序列数字提取后成对消费（逗号/空白/换行分隔等价）；奇数个或空=解析不完整计阻断
        for pm in re.finditer(r'<polyline\b[^>]*\bpoints="([^"]+)"', body):
            nums = re.findall(_NUM, pm.group(1))
            if len(nums) < 2 or len(nums) % 2 != 0:
                unsup.append("polyline 坐标无法成对解析")
                continue
            for i in range(0, len(nums), 2):
                hit(float(nums[i]), float(nums[i + 1]))

        for cm in re.finditer(r'<(circle|ellipse)\b[^>]*>', body):
            tag = cm.group(0)
            is_e = tag.startswith("<ellipse")
            cx, cy = _attr(tag, "cx"), _attr(tag, "cy")
            rx = _attr(tag, "rx") if is_e else _attr(tag, "r")
            ry = _attr(tag, "ry") if is_e else rx
            if cx is None or cy is None or rx is None or ry is None:
                unsup.append("circle/ellipse 属性不全")
                continue
            hit(cx - rx, cy - ry)
            hit(cx + rx, cy + ry)

        for lm in re.finditer(r'<line\b[^>]*>', body):
            if not seg(lm.group(0), ("x1", "y1", "x2", "y2")):
                unsup.append("line 属性不全")

        for rm in re.finditer(r'<rect\b[^>]*>', body):
            tag = rm.group(0)
            x, y = _attr(tag, "x"), _attr(tag, "y")
            w, h = _attr(tag, "width"), _attr(tag, "height")
            if None in (x, y, w, h):
                unsup.append("rect 属性不全")
                continue
            hit(x, y)
            hit(x + w, y + h)

        # path：命令白名单（绝对 M/L/Z）+ 数字提取后成对消费——分隔符不限空格/逗号（含换行）；
        # 无坐标可查（如仅闭合 z）=未检查
        for pm in re.finditer(r'<path\b[^>]*\bd="([^"]+)"', body):
            d = pm.group(1)
            letters = set(re.findall(r"[A-Za-z]", d))
            if not letters <= _PATH_OK:
                unsup.append("path 含未支持命令 %s（仅支持绝对 M/L/Z）"
                             % "".join(sorted(letters - _PATH_OK)))
                continue
            nums = re.findall(_NUM, d)
            if len(nums) < 2 or len(nums) % 2 != 0:
                unsup.append("path 坐标无法成对解析")
                continue
            for i in range(0, len(nums), 2):
                hit(float(nums[i]), float(nums[i + 1]))

        if unsup:
            partial.append(tagname + " " + "；".join(sorted(set(unsup))))
        elif hits == 0:
            partial.append(tagname + " 零个有效坐标被检查（无可检坐标元素），不算已完成检查")
        else:
            checked += 1
            if oob:
                bad.append(tagname + "出界%d点" % oob)
    return {"checked": checked, "partial": partial, "unrecognized": unrecognized,
            "bad": bad, "total": total}

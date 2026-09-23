#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
consistency.py — 路书 HTML「版式一致性」校验

为什么需要它：盘上 11 份路书 = 7 个 CSS 指纹 / 4 套 IA 命名 / 8 套导航集合。
根因是骨架从没固化，每趟「抄上一份」就漂一点。本脚本拿基准骨架当唯一真值，
把"看起来差不多"变成"机器数得出来的相等"。

用法：
    python consistency.py 新路书.html [更多.html ...] [--base 基准骨架.html] [--days 5]
默认基准 = jianhao-travel-planner（见好 · 旅行规划器）skill 的 assets/路书_基准骨架.html
退出码：0 = 全部一致；1 = 有不一致。

校验项（基准即真值，不硬编码指纹数字——指纹随基准改动而变）：
  ① <style> 块数（朋友版 1；带 #intel 的自用版 2）
  ② CSS 指纹 == 基准
  ③ IA：非 day 区块的集合与顺序 == 基准；day 区块必须是连续的 day1..dayN 且夹在 drive 与 boost 之间
  ④ 导航覆盖全部区块（含 #drive —— 原家族漏了这个入口）
  ⑤ 8 个版式 token 值与基准逐条相等
  ⑥ 字体栈 == 基准
  ⑦ js 门控 + 兜底脚本 + 六件事标记齐全
  ⑧ localStorage 命名规约 <城市码>_font / <城市码>_chk_
  ⑨ 无残留占位符（【】、__CITY__）
  ⑩ 每日配图 <figure> 数 >= 行程天数
"""
import io
import re
import sys
import argparse
import hashlib
import os

# 默认基准 = 随包自寻址（tools/ 的上一级 assets/），任何机器上拷包即跑；可用 --base 覆盖
DEFAULT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "路书_基准骨架.html")
TOKENS = ["--bg", "--surface", "--ink", "--ink2", "--ink3", "--line", "--accent", "--warn"]
DAY_RE = re.compile(r"^day(\d+)$")

# ---- 终端符号自适应（2026-09-21 朋友实战反馈）：中文 Windows 黑框(GBK)认不出 ✅❌✓→■ 时
# 自动退 ASCII 再打印，防 UnicodeEncodeError 崩框；UTF-8 终端保持原符号。
_SYM_FALLBACK = str.maketrans({
    '✅': '[OK]', '✓': '[OK]', '√': '[OK]',
    '❌': '[X]', '✗': '[X]', '×': '[X]',
    '→': '->', '■': '[*]', '●': '[*]', '·': '.',
})


def emit(line=''):
    try:
        print(line)
    except UnicodeEncodeError:
        try:
            print(line.translate(_SYM_FALLBACK))
        except UnicodeEncodeError:
            enc = sys.stdout.encoding or 'ascii'
            print(line.encode(enc, 'replace').decode(enc))


def read(p):
    if not os.path.exists(p):
        emit("FATAL 文件不存在: %s" % p)
        sys.exit(2)
    return io.open(p, encoding="utf-8", errors="replace").read()


def css_of(s):
    m = re.search(r"<style[^>]*>(.*?)</style>", s, re.S)
    return m.group(1) if m else ""


def style_count(s):
    # 剥掉 HTML 注释再数，否则注释里提到 <style> 会误报
    return re.sub(r"<!--.*?-->", "", s, flags=re.S).count("<style")


def secs_of(s):
    return re.findall(r'<section id="([^"]+)"', s)


def navs_of(s):
    return set(re.findall(r'href="#([^"]+)"', s))


def tokens_of(s):
    css = css_of(s)
    return dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;{}]+);", css))


def fonts_of(s):
    return sorted(set(f.strip().strip("\"'") for f in re.findall(r"font-family\s*:\s*([^;}]+)", css_of(s))))


def fp(s):
    return hashlib.md5(css_of(s).encode("utf-8")).hexdigest()[:10]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--days", type=int, default=None, help="行程天数，默认按文件里的 day 区块数判断")
    a = ap.parse_args()

    base = read(a.base)
    b_ids = secs_of(base)
    b_days = [i for i in b_ids if DAY_RE.match(i)]
    b_non = [i for i in b_ids if not DAY_RE.match(i)]
    b_tok = tokens_of(base)
    b_font = fonts_of(base)
    b_fp = fp(base)
    b_nav = navs_of(base)
    # 基准里出现的 【...】 就是"待填占位符"清单（与正文里的【估算】类合法标注区分开）
    BASE_PLACEHOLDERS = set(re.findall(r"【[^】]{1,24}】", base))

    emit("=" * 118)
    emit("路书版式一致性校验　基准 = %s" % os.path.basename(a.base))
    emit("  基准指纹 %s ｜ 基准 IA %d 区块（含 %d 天）｜ 占位符 %d 个"
          % (b_fp, len(b_ids), len(b_days), len(BASE_PLACEHOLDERS)))
    emit("=" * 118)

    allbad = []
    for f in a.files:
        s = read(f)
        bad = []
        n = os.path.basename(f)
        ids = secs_of(s)
        days = [i for i in ids if DAY_RE.match(i)]
        non = [i for i in ids if not DAY_RE.match(i)]
        has_intel = "intel" in ids
        navs = navs_of(s)
        tok = tokens_of(s)
        fonts = fonts_of(s)
        ndays = a.days or len(days)

        # ① <style> 块数
        want_style = 2 if has_intel else 1
        if style_count(s) != want_style:
            bad.append("<style> 块数 %d（应为 %d）" % (style_count(s), want_style))

        # ② 指纹
        if fp(s) != b_fp:
            bad.append("CSS 指纹 %s ≠ 基准 %s" % (fp(s), b_fp))

        # ③ IA
        exp_non = [i for i in b_non if i != "intel"]
        got_non = [i for i in non if i != "intel"]
        if got_non != exp_non:
            miss = [i for i in exp_non if i not in got_non]
            extra = [i for i in got_non if i not in exp_non]
            bad.append("IA 不符（缺 %s / 多 %s / 或顺序不同）" % (miss or "无", extra or "无"))
        exp_days = ["day%d" % (k + 1) for k in range(len(days))]
        if days != exp_days:
            bad.append("day 区块不连续：%s" % days)
        if len(days) != ndays:
            bad.append("天数 %d ≠ 期望 %d" % (len(days), ndays))
        if days:
            i0, i1 = ids.index(days[0]), ids.index(days[-1])
            if i0 == 0 or ids[i0 - 1] != "drive":
                bad.append("day1 前面不是 drive")
            if i1 + 1 >= len(ids) or ids[i1 + 1] != "boost":
                bad.append("最后一天后面不是 boost")
        if has_intel and ids[-1] != "intel":
            bad.append("#intel 不在末尾")

        # ④ 导航覆盖（含 drive）
        need = [i for i in ids if i != "intel"]
        missing = [i for i in need if i not in navs]
        if missing:
            bad.append("导航缺入口：%s" % missing)

        # ⑤ token
        for t in TOKENS:
            if t not in tok:
                bad.append("缺 token %s" % t)
            elif t in b_tok and tok[t].strip() != b_tok[t].strip():
                bad.append("token %s = %s ≠ 基准 %s" % (t, tok[t].strip(), b_tok[t].strip()))

        # ⑥ 字体
        if fonts != b_font:
            bad.append("字体栈不符: %s" % fonts)

        # ⑦ JS 门控 + 兜底 + 六件事
        if "documentElement.classList.add('js')" not in s.replace('"', "'"):
            bad.append("缺 html.js 门控脚本")
        if "setTimeout" not in s or "main section.in" not in s:
            bad.append("缺入场动效兜底脚本")
        for mark, desc in [("TRIP", "当日模式"), ("fontInc", "字号+"), ("fontDec", "字号−"),
                           ("printBtn", "打印"), ("backtop", "返回顶部"),
                           ("IntersectionObserver", "滚动入场/侧栏高亮"), ("_chk_", "勾选记忆")]:
            if mark not in s:
                bad.append("缺 JS 功能：%s(%s)" % (desc, mark))

        # ⑧ localStorage 命名规约
        lskeys = set(re.findall(r'localStorage\.(?:setItem|getItem)\("([^"]+)"', s))
        font_keys = [k for k in lskeys if k.endswith("_font")]
        chk_pref = set(re.findall(r'"([a-z]{2,8}_chk_)"', s))
        if len(font_keys) != 1 or not re.match(r"^[a-z]{2,8}_font$", font_keys[0] if font_keys else ""):
            bad.append("字号键不合规（应 <城市码>_font）: %s" % sorted(lskeys))
        if len(chk_pref) != 1:
            bad.append("勾选键前缀不合规（应单个 <城市码>_chk_）: %s" % sorted(chk_pref))
        else:
            fp_city = font_keys[0][:-5] if font_keys else ""
            if fp_city and list(chk_pref)[0][:-5] != fp_city:
                bad.append("字号键与勾选键城市码不一致：%s vs %s" % (fp_city, list(chk_pref)[0][:-5]))

        # ⑨ 残留占位符
        # ⚠️ 不能全局查「【」——路书正文里 `【具体店以现场为准】`『【估算】』『【未核实】』
        #    是**合法的内容标注**（家族写法本来就这么标），首版全局判据把 3 份正常路书误报成 ❌。
        #    → 只查"基准骨架里定义过的占位符"，基准加占位符即自动纳入。
        hits = sorted(p for p in BASE_PLACEHOLDERS if p in s)
        if hits:
            bad.append("残留基准占位符：%s" % hits)
        if "__CITY__" in s:
            bad.append("残留 __CITY__")

        # ⑩ 配图
        nfig = s.count("<figure")
        if nfig < ndays:
            bad.append("每日配图 %d 张 < 天数 %d" % (nfig, ndays))

        status = "✅" if not bad else "❌"
        emit("\n%s %s" % (status, n))
        emit("   指纹 %s ｜ style %d ｜ 区块 %d（%d 天%s）｜ 导航 %d ｜ figure %d ｜ 字号键 %s"
              % (fp(s), style_count(s), len(ids), len(days),
                 "·含intel" if has_intel else "", len(navs), nfig,
                 (font_keys[0] if font_keys else "—")))
        for x in bad:
            emit("     - " + x)
        allbad += [(n, x) for x in bad]

    emit("\n" + "=" * 118)
    if allbad:
        emit("❌ 不一致 %d 项：" % len(allbad))
        for n, x in allbad:
            emit("   [%s] %s" % (n, x))
        emit("\n常见修法：搬基准骨架的 <style> + 3 个 <script>；补 #drive 导航入口；"
              "\n          把城市码统一为 <城市码>_font / <城市码>_chk_；回收 【】占位符与残留城市名。")
        sys.exit(1)
    emit("✅ 全部与基准一致（%d 份）" % len(a.files))


if __name__ == "__main__":
    main()

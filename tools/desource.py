# -*- coding: utf-8 -*-
"""
路书双轨化主脚本（配置驱动）
用法： <python> desource.py rules.json

rules.json 结构：
{
  "stamp": "20260914-pm",
  "files": [
    {
      "city": "宁波",
      "friend": "C:/.../宁波中秋_朋友版路书.html",
      "self":   "C:/.../宁波中秋_自用版路书.html",
      "self_title": "宁波·中秋 自用版路书（含探店情报原档）",
      "comment_anchor": "<!-- 宁波中秋·朋友版路书 v1（2026-09-13）",
      "comment_new":    "<!-- 宁波中秋·自用版路书 v1（2026-09-14）｜含六博主实探原档，勿外发",
      "logo_anchor": "<div class=\"logo\">宁波·中秋</div>",
      "nav_link_re": "<a href=\"#eat\">[^<]*</a>",
      "insert_before": "<p style=\"text-align:center;margin:40px 0 20px",
      "md": "C:/.../探店情报卡_丽水宁波_六博主.md",
      "md_self_keep": "## 【宁波】",          // 自用版从中截到附录
      "md_appendix": "## 附一",
      "cut_icons": ["📌","🦀","🚗","🧺","📚"],
      "insert_after_icon": "🥟",
      "insert_row": "<div class=\"note-row\" ...>...</div>",
      "replacements": [
        {"tag":"Day1槽位","mode":"regex","old":"<br><b>📌 六博主.*?心里就有底了。","new":"<br>..."},
        {"tag":"表intro","mode":"exact","old":"<span class=\"intro\">...</span>","new":"<span class=\"intro\">...</span>"}
      ],
      "drop": ["六博主","唐仁杰","刘雨鑫","米雪","老谢","隋坡","庞师","实探","万赞"]
    }
  ]
}
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

LOG = []

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


def log(*a):
    line = " ".join(str(x) for x in a)
    LOG.append(line)
    emit(line)


# ----------------------------------------------------------------- helpers
def rep1(s, old, new, tag):
    n = s.count(old)
    assert n == 1, f"[{tag}] 期望精确命中 1 处，实际 {n} 处"
    log(f"  ✓ {tag}: 精确替换 1 处")
    return s.replace(old, new)


def resub1(s, pat, new, tag, flags=re.S):
    """new 可含 \\1 —— 用普通替换串走转义（lambda 不会转义，是踩过的坑）"""
    rx = re.compile(pat, flags)
    n = len(rx.findall(s))
    assert n == 1, f"[{tag}] 期望正则命中 1 处，实际 {n} 处"
    log(f"  ✓ {tag}: 正则替换 1 处")
    return rx.sub(new, s, count=1)


def cut_row(s, icon, tag):
    pat = re.compile(r'<div class="note-row"[^>]*>\s*<span class="ic">' + re.escape(icon) +
                     r'</span>.*?</div>[ \t]*\n?', re.S)
    n = len(pat.findall(s))
    assert n == 1, f"[{tag}] 情报块 {icon} 期望 1 块，实际 {n} 块"
    log(f"  ✓ {tag}: 删除情报块 {icon}")
    return pat.sub('', s, count=1)


def add_after_row(s, icon, extra, tag):
    pat = re.compile(r'<div class="note-row"[^>]*>\s*<span class="ic">' + re.escape(icon) +
                     r'</span>.*?</div>', re.S)
    n = len(pat.findall(s))
    assert n == 1, f"[{tag}] 锚定块 {icon} 期望 1 块，实际 {n} 块"
    log(f"  ✓ {tag}: 在 {icon} 块后插入 1 行")
    return pat.sub(lambda m: m.group(0) + "\n" + extra, s, count=1)


# ----------------------------------------------------------------- md -> html
def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def inl(t):
    t = esc(t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    return t


def mk_table(rows):
    cells = []
    for r in rows:
        c = [x.strip() for x in r.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-{2,}:?', x or '-') for x in c):
            continue
        cells.append(c)
    if not cells:
        return ''
    out = ['<table>', '<tr>' + ''.join(f'<th>{inl(x)}</th>' for x in cells[0]) + '</tr>']
    for c in cells[1:]:
        out.append('<tr>' + ''.join(f'<td>{inl(x)}</td>' for x in c) + '</tr>')
    out.append('</table>')
    return '\n'.join(out)


def md_to_html(md):
    out, i, open_card = [], 0, False
    L = md.split('\n')
    while i < len(L):
        st = L[i].strip()
        if not st:
            i += 1
            continue
        if st.startswith('# ') and not st.startswith('## '):
            i += 1
            continue
        if st.startswith('#### '):
            out.append(f'<h5>{inl(st[5:])}</h5>'); i += 1; continue
        if st.startswith('### '):
            out.append(f'<h4>{inl(st[4:])}</h4>'); i += 1; continue
        if st.startswith('## '):
            if open_card:
                out.append('</div>')
            out.append(f'<div class="ic-card"><h3 class="ic-h">{inl(st[3:])}</h3>')
            open_card = True; i += 1; continue
        if st.startswith('---'):
            out.append('<hr>'); i += 1; continue
        if st.startswith('|'):
            rows = []
            while i < len(L) and L[i].strip().startswith('|'):
                rows.append(L[i].strip()); i += 1
            out.append(mk_table(rows)); continue
        if st.startswith('> '):
            buf = []
            while i < len(L) and L[i].strip().startswith('> '):
                buf.append(L[i].strip()[2:]); i += 1
            out.append('<blockquote>' + '<br>'.join(inl(x) for x in buf) + '</blockquote>'); continue
        if st.startswith('- ') or st.startswith('* '):
            buf = []
            while i < len(L) and (L[i].strip().startswith('- ') or L[i].strip().startswith('* ')):
                buf.append(L[i].strip()[2:]); i += 1
            out.append('<ul>' + ''.join(f'<li>{inl(x)}</li>' for x in buf) + '</ul>'); continue
        if re.match(r'^\d+\.\s+', st):
            buf = []
            while i < len(L) and re.match(r'^\d+\.\s+', L[i].strip()):
                buf.append(re.sub(r'^\d+\.\s+', '', L[i].strip())); i += 1
            out.append('<ol>' + ''.join(f'<li>{inl(x)}</li>' for x in buf) + '</ol>'); continue
        if re.match(r'^\*\*[一二三四五六七八九十][、.]', st):
            out.append(f'<p class="ic-f">{inl(st)}</p>'); i += 1; continue
        out.append(f'<p>{inl(st)}</p>'); i += 1
    if open_card:
        out.append('</div>')
    return '\n'.join(out)


INTEL_CSS = """<style>
#intel .ic-card{border:1px solid var(--line);border-radius:12px;padding:16px 18px 14px;margin:14px 0;background:var(--surface)}
#intel .ic-h{font-size:1rem;line-height:1.5;color:var(--accent);border-left:3px solid var(--accent);padding-left:9px;margin-bottom:6px}
#intel h4{font-size:.9rem;margin:14px 0 5px}
#intel h5{font-size:.85rem;margin:12px 0 4px}
#intel .ic-f{font-size:.86rem;font-weight:700;margin:11px 0 3px;color:var(--ink)}
#intel p{font-size:.85rem;margin:4px 0}
#intel ul,#intel ol{margin:4px 0 4px 1.3em;font-size:.85rem}
#intel li{margin:3px 0}
#intel blockquote{border-left:3px solid var(--gold);background:rgba(200,164,92,.14);padding:9px 13px;margin:9px 0;font-size:.82rem;border-radius:0 8px 8px 0}
#intel table{width:100%;border-collapse:collapse;font-size:.79rem;margin:8px 0}
#intel th,#intel td{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
#intel th{background:var(--accent-soft);font-weight:700}
#intel hr{border:0;border-top:1px dashed var(--line);margin:18px 0}
#intel code{background:rgba(28,27,23,.06);padding:1px 4px;border-radius:4px}
</style>
"""

SELF_BADGE = ('<div style="font-size:.7rem;line-height:1.5;color:#b5493a;font-weight:800;'
              'text-align:left;margin:2px 0 10px;letter-spacing:0">'
              '🔒 自用版 · 勿外发<br><span style="color:#8a8578;font-weight:600">'
              '含博主实探原档</span></div>')


def intel_section(md_html, city, tag='博主逐条抓取', extra=''):
    return (INTEL_CSS +
            '<section id="intel">\n'
            '  <div class="eyebrow">自用存档 · 不要外发</div>\n'
            f'  <h2>探店情报原档<span class="tag">{tag}</span></h2>\n'
            '  <p class="lead" style="font-size:.85rem">这一节是<b>原始情报</b>：含博主来源、赞数、账单明细、情报边界说明'
            + extra +
            '。<b>只给自己看</b>；发给朋友请用「_朋友版路书.html」，那份已把来源全部去掉，只留店名 / 菜品 / 评价 / 位置 / 价格。</p>\n'
            + md_html + '\n</section>\n\n')


# ----------------------------------------------------------------- main
def run(rule, stamp):
    f = Path(rule['friend'])
    s0 = f.read_text(encoding='utf-8')
    base = len(s0)
    log("=" * 64)
    log(f"■ {rule['city']}　源文件 {f.name} {base} 字符")

    # ---- (1) 自用版（先出，含全部来源）
    self_s = s0
    self_s = rep1(self_s, rule['comment_anchor'], rule['comment_new'], '自用版·头部注释')
    self_s = resub1(self_s, r'<title>[^<]*</title>', f"<title>{rule['self_title']}</title>", '自用版·title')
    self_s = rep1(self_s, rule['logo_anchor'], rule['logo_anchor'] + '\n' + SELF_BADGE, '自用版·左上标识')
    self_s = resub1(self_s, '(' + rule['nav_link_re'] + ')',
                    r'\1\n      <a href="#intel">🔒 探店情报原档</a>', '自用版·导航项')
    md = Path(rule['md']).read_text(encoding='utf-8')
    # md 头部（# 标题 + 「结构/出卡依据/制作日期」引用块）默认保留
    h = md.find('\n## ')
    head = md[:h + 1] if h > 0 else ''
    a = md.find(rule['md_self_keep'])
    b = md.find(rule['md_appendix'])
    body = md[a:b]
    appendix = md[b:] if b >= 0 else ''
    if rule.get('md_is_this_city_only'):
        keep = body
    else:
        cut = body.find(rule.get('md_next_city_marker', '\x00'))
        keep = (body[:cut] + appendix) if cut >= 0 else (body + appendix)
    if not rule.get('md_include_head', True):
        head = ''
    self_s = rep1(self_s, rule['insert_before'],
                  intel_section(md_to_html(head + keep), rule['city'],
                                rule.get('intel_tag', '博主逐条抓取'),
                                rule.get('intel_extra', '')) + rule['insert_before'],
                  '自用版·情报原档章节')
    assert '\\n' not in self_s and '\\1' not in self_s, '自用版出现字面转义残留'
    out_self = Path(rule['self'])
    out_self.write_text(self_s, encoding='utf-8')
    log(f"  → 写出 {out_self.name}（{len(self_s)} 字符，+{len(self_s)-base}）")

    # ---- (2) 朋友版（剥离）
    log(f"【{rule['city']}·朋友版】去来源化")
    s = s0
    for r in rule.get('replacements', []):
        if r.get('mode') == 'exact':
            s = rep1(s, r['old'], r['new'], r['tag'])
        else:
            s = resub1(s, r['old'], r['new'], r['tag'])
    for ic in rule.get('cut_icons', []):
        s = cut_row(s, ic, f"{rule['city']}·情报块")
    if rule.get('insert_after_icon') and rule.get('insert_row'):
        s = add_after_row(s, rule['insert_after_icon'], rule['insert_row'], f"{rule['city']}·补核对行")

    drop = rule.get('drop', [])
    left = {k: s.count(k) for k in drop if s.count(k)}
    assert not left, f"{rule['city']} 朋友版仍残留来源词：{left}"
    log(f"  ✓ 来源词残留检查：全部为 0（{'/'.join(drop)}）")
    soft = {k: s.count(k) for k in ['博主', '情报', '来源', '口径', '边界', '赞'] if s.count(k)}
    log(f"  · 软性词残留（逐条看上下文，正常用语可留）：{soft or '无'}")
    for bad in ('\\n', '\\1'):
        assert bad not in s, f"朋友版出现字面转义残留：{bad!r}"

    bak = f.with_name(f.name + f'.bak-{stamp}')
    shutil.copy2(f, bak)
    log(f"  → 备份 {bak.name}")
    f.write_text(s, encoding='utf-8')
    log(f"  → 写出 {f.name}（{len(s)} 字符，-{base-len(s)}）")
    return dict(city=rule['city'], base=base, self_bytes=len(self_s), friend_bytes=len(s),
                removed=base - len(s))


def main():
    ap = argparse.ArgumentParser(
        prog='desource.py',
        description='路书双轨化：由朋友版路书+情报卡 md 生成「自用版（含情报原档）」，'
                    '并把朋友版原地脱敏（自动 .bak-<stamp>）。',
        usage='%(prog)s rules.json',
        epilog='rules.json 结构见脚本头部说明（stamp / files[] / log_out）。')
    ap.add_argument('rules', metavar='rules.json', nargs='?',
                    help='规则配置 JSON 的路径（缺省则打印本帮助）')
    args = ap.parse_args()
    if not args.rules:
        ap.print_help()
        sys.exit(2)
    rules = json.loads(Path(args.rules).read_text(encoding='utf-8'))
    stamp = rules.get('stamp', 'bak')
    rep = [run(r, stamp) for r in rules['files']]
    Path(rules.get('log_out', 'desource_report.txt')).write_text('\n'.join(LOG), encoding='utf-8')
    emit('\n' + json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

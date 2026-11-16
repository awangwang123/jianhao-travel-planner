# -*- coding: utf-8 -*-
"""fetch_images.py —— 配图一条龙：Commons 检索 → 下载验图 → 署名清单（无 API key）
用法:
  py fetch_images.py search "洛阳 龙门石窟" [--limit 5]        # 检索并列出 标题/作者/许可
  py fetch_images.py fetch "File:XXX.jpg" --note "图注文字" [--out images]
                                                 # 下载 + PIL 完整性校验 + 记入 manifest
  py fetch_images.py manifest [--out images/署名清单.md]       # 生成署名清单 md
说明:
  - Commons API 免 key；下载后逐张 PIL load 校验（截断/损坏即 FAIL，不静默）
  - manifest.json 累积元数据（文件/作者/许可/图注/SHA256），署名清单 md 由它生成
"""
import argparse
import base64
import copy
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "travel-roadbook-maker/1.0 (educational use)"}
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.join(HERE, "..", "images")
MANIFEST = "manifest.json"


def _api(params):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _load_manifest(d):
    p = os.path.join(d, MANIFEST)
    if os.path.exists(p):
        return json.load(io.open(p, encoding="utf-8"))
    return []


def _save_manifest(d, items):
    io.open(os.path.join(d, MANIFEST), "w", encoding="utf-8").write(
        json.dumps(items, ensure_ascii=False, indent=1))


def cmd_search(args):
    data = _api({"action": "query", "generator": "search",
                 "gsrsearch": args.query, "gsrnamespace": 6, "gsrlimit": args.limit,
                 "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size",
                 "iiurlwidth": 1200})
    pages = data.get("query", {}).get("pages", {})
    rows = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        em = ii.get("extmetadata", {}) or {}
        rows.append({
            "title": p.get("title", ""),
            "artist": _strip_html((em.get("Artist") or {}).get("value", ""))[:60],
            "license": _strip_html((em.get("LicenseShortName") or {}).get("value", "")),
            "mime": ii.get("mime", ""),
            "size_kb": round(ii.get("size", 0) / 1024),
        })
    rows.sort(key=lambda r: r["title"])
    for i, r in enumerate(rows):
        print("%d. %s | %s | %s | %sKB" % (i + 1, r["title"], r["artist"] or "?", r["license"] or "?", r["size_kb"]))
    print("TOTAL %d — fetch 用完整 title" % len(rows))


def cmd_fetch(args):
    d = os.path.abspath(args.out)
    os.makedirs(d, exist_ok=True)
    title = args.title if args.title.startswith("File:") else "File:" + args.title
    data = _api({"action": "query", "titles": title,
                 "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
                 "iiurlwidth": 1200})
    pages = data.get("query", {}).get("pages", {})
    ii = None
    for p in pages.values():
        if p.get("imageinfo"):
            ii = p["imageinfo"][0]
            title = p.get("title", title)
    if not ii:
        print("FAIL: no imageinfo for", title)
        sys.exit(1)
    em = ii.get("extmetadata", {}) or {}
    thumb = ii.get("thumburl") or ii.get("url")
    req = urllib.request.Request(thumb, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = r.read()
    ext = ".jpg" if "jpeg" in ii.get("mime", "jpg") else ".png"
    fn = os.path.join(d, re.sub(r"[^A-Za-z0-9_.-]", "_", title[5:])[:60] + ext)
    open(fn, "wb").write(blob)
    status = "OK"
    try:
        from PIL import Image
        im = Image.open(fn)
        im.load()
        status = "OK %dx%d" % im.size
    except Exception as e:
        status = "BROKEN: " + str(e)[:60]
        print("WARN image failed integrity check — do not use:", status)
    sha = hashlib.sha256(blob).hexdigest()[:16]
    items = _load_manifest(d)
    items = [x for x in items if x.get("file") != os.path.basename(fn)]
    items.append({"file": os.path.basename(fn), "title": title, "note": args.note or "",
                  "artist": _strip_html((em.get("Artist") or {}).get("value", "")),
                  "license": _strip_html((em.get("LicenseShortName") or {}).get("value", "")),
                  "sha256_16": sha, "bytes": len(blob)})
    _save_manifest(d, items)
    print("%s %s %dKB | %s" % (status, os.path.basename(fn), len(blob) // 1024, title))


def cmd_manifest(args):
    d = os.path.abspath(os.path.dirname(args.out)) if os.path.dirname(args.out) else DEFAULT_DIR
    src = os.path.join(d, MANIFEST)
    items = json.load(io.open(src, encoding="utf-8")) if os.path.exists(src) else _load_manifest(DEFAULT_DIR)
    lines = ["# 配图署名清单（Wikimedia Commons 实拍）", "",
             "| 图 | 图注 | 作者 | 许可 |", "|---|---|---|---|"]
    for x in items:
        lines.append("| %s | %s | %s | %s |" % (x.get("file", ""), x.get("note", ""),
                                                x.get("artist", "?"), x.get("license", "?")))
    out = args.out if args.out.endswith(".md") else os.path.join(d, "署名清单.md")
    io.open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("manifest md written:", out, "(%d images)" % len(items))


def cmd_embed(args):
    """v1.20 候选九批（v128，M9C 实证）：配图回填正式入口——只写 days[n].photos_html 一个字段。
    禁制作侧手写脚本整份覆盖 trip_data（M9C inject_photos 用旧数据覆盖已修数据=restore_fixes 全量重放案）。
    plan.json 形态: {"1": [{"file": "xxx.jpg", "cap": "图注（非实拍须含「（示意）」）}, ...], "2": [...]}
    artist/license 自动从 images/manifest.json 补齐（fetch 时已登记）；宽高 PIL 实读（禁手填）。
    保障: 写前留底 .bak-embed-时间戳；写后深比对断言——除目标 photos_html 外零变化。"""
    data_p = os.path.abspath(args.data)
    d = json.load(io.open(data_p, encoding="utf-8"))
    # v1.20 图像选项（schema §5d）：photo:false=配置声明本册无每日风景照片——embed 入口拦，
    # 防止照片被回填进关照片的册子（成品闸矛盾闸兜底，这里是源头拦）。
    if not (d.get("image_options") or {}).get("photo", True):
        print("FAIL: image_options.photo=false —— 本册配置声明无照片，embed 拒绝执行；如需照片改回 photo:true")
        sys.exit(1)
    plan = json.load(io.open(os.path.abspath(args.plan), encoding="utf-8"))
    imgdir = os.path.abspath(args.out)
    manifest = {x.get("file"): x for x in _load_manifest(imgdir)}
    try:
        from PIL import Image
    except ImportError:
        print("FAIL: PIL unavailable — py -m pip install pillow")
        sys.exit(1)
    per_day = {}
    for day_s, items in plan.items():
        try:
            n = int(day_s)
        except ValueError:
            print("FAIL: plan key %r 不是 day 数字" % day_s)
            sys.exit(1)
        if not (1 <= n <= len(d.get("days", []))):
            print("FAIL: plan day %s 超出范围 (1..%d)" % (day_s, len(d.get("days", []))))
            sys.exit(1)
        if len(items) not in (2, 4):
            print("FAIL: day %s 配 %d 张——配图对称律=每日 2 或 4 张，禁 3（.photos 两列网格）" % (n, len(items)))
            sys.exit(1)
        figs = []
        for it in items:
            fn = os.path.join(imgdir, it["file"])
            if not os.path.exists(fn):
                print("FAIL: 图片不存在: %s（先 fetch 再 embed）" % it["file"])
                sys.exit(1)
            try:
                im = Image.open(fn)
                im.load()
            except Exception as e:
                print("FAIL: 图片损坏（PIL 校验不过）: %s — %s" % (it["file"], str(e)[:60]))
                sys.exit(1)
            w, h = im.size
            meta = manifest.get(it["file"], {})
            cap = it.get("cap") or meta.get("note") or ""
            artist = meta.get("artist") or it.get("artist") or ""
            lic = meta.get("license") or it.get("license") or ""
            ext = "jpeg" if fn.lower().endswith((".jpg", ".jpeg")) else "png"
            b64 = base64.b64encode(open(fn, "rb").read()).decode("ascii")
            figs.append('<figure><img src="data:image/%s;base64,%s" alt="%s" width="%d" height="%d">'
                        '<figcaption>%s · 图：%s / Wikimedia Commons · %s</figcaption></figure>'
                        % (ext, b64, cap, w, h, cap, artist, lic))
        per_day[n] = "\n".join(figs)
    bak = data_p + ".bak-embed-" + time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(data_p, bak)
    before = json.load(io.open(data_p, encoding="utf-8"))
    for n, html in per_day.items():
        d["days"][n - 1]["photos_html"] = html
    # 深比对断言：预期态=写前数据仅替换目标 photos_html——任何其他字段变化=内部错误，拒绝落盘
    expected = copy.deepcopy(before)
    for i, dy in enumerate(expected.get("days", [])):
        if (i + 1) in per_day:
            dy["photos_html"] = per_day[i + 1]
    if expected != d:
        print("FAIL: 检测到 photos_html 之外的字段变化（内部错误）——未落盘，数据未动")
        sys.exit(1)
    io.open(data_p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    print("EMBED_OK: %d 天已更新 | 只写 photos_html（深比对断言过）| 留底 %s"
          % (len(per_day), os.path.basename(bak)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("search")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=5)
    sp.set_defaults(fn=cmd_search)
    fp = sub.add_parser("fetch")
    fp.add_argument("title")
    fp.add_argument("--note", default="")
    fp.add_argument("--out", default=str(DEFAULT_DIR))
    fp.set_defaults(fn=cmd_fetch)
    mp = sub.add_parser("manifest")
    mp.add_argument("--out", default="")
    mp.set_defaults(fn=cmd_manifest)
    ep = sub.add_parser("embed",
                        help="把已亲验图片回填 trip_data 的每日 photos_html（只动这一个字段）")
    ep.add_argument("data")
    ep.add_argument("--plan", required=True, help="plan.json: {day: [{file, cap}, ...]}")
    ep.add_argument("--out", default=str(DEFAULT_DIR))
    ep.set_defaults(fn=cmd_embed)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

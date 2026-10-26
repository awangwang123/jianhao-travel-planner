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
import hashlib
import io
import json
import os
import re
import sys
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
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

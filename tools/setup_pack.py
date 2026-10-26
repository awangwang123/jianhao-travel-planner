# -*- coding: utf-8 -*-
"""setup_pack.py —— 首次开工一条命令：校验 SHA256 → 中文名安全解压 → 清点 → 复制工作副本
用法:
  py tools/setup_pack.py <下载的zip路径> --sha256 <发布页标注值> [--work pkg_work]
说明:
  - Windows 自带解压会损坏 assets 下中文文件名（洛阳实测缺陷①）——本工具用 Python zipfile
    按 UTF-8 标志解压，杜绝该坑
  - 工作副本为全量复制（一切改动在副本内，原始解压目录保持只读参考）
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import zipfile

TOP = "jianhao-travel-planner"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_path")
    ap.add_argument("--sha256", default="", help="发布页标注的 SHA256（建议必填，防下载损坏）")
    ap.add_argument("--work", default="pkg_work", help="工作副本目录（默认 pkg_work）")
    args = ap.parse_args()

    zp = os.path.abspath(args.zip_path)
    if not os.path.exists(zp):
        print("FAIL: zip not found:", zp)
        sys.exit(1)
    got = sha256_file(zp)
    print("sha256:", got)
    if args.sha256:
        want = args.sha256.strip().lower()
        if got != want:
            print("FAIL: SHA256 mismatch (want %s) — 重新下载后再试" % want)
            sys.exit(1)
        print("SHA256 match OK")

    base = os.path.dirname(zp)
    unz = os.path.join(base, "_unzip_v118" if "v1.18" in zp else "_unzip")
    if os.path.exists(unz):
        shutil.rmtree(unz)
    os.makedirs(unz)
    with zipfile.ZipFile(zp) as z:
        z.extractall(unz)
    src = os.path.join(unz, TOP)
    if not os.path.isdir(src):
        print("FAIL: 解压后找不到", TOP)
        sys.exit(1)
    n = sum(len(fs) for _, _, fs in os.walk(src))
    print("unzipped: %d files" % n)

    work = os.path.abspath(args.work)
    if os.path.exists(work):
        shutil.rmtree(work)
    shutil.copytree(src, work)
    wn = sum(len(fs) for _, _, fs in os.walk(work))
    print("work copy:", work, "(%d files)" % wn)
    print("SETUP_OK — 下一步: py tools/pipeline.py new <目的地> --days 3 --start YYYY-MM-DD --dir", os.path.join(args.work, "out"))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
imgcheck.py —— PNG 完整性检查（唯一正本，禁止各测试复制缩水版，Codex 五轮复核立规）
主通道：PIL 真解码像素（打不开=坏）；结构层：chunk CRC32 逐块 + IDAT 解压长度 vs IHDR 声明。
返回 (ok: bool, detail: str)。
"""
import base64
import io
import struct
import zlib

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def png_check(src):
    """src=data:image/png;base64,... → (bool, detail)。任何一层不过即坏。"""
    if not src or not src.startswith("data:image/png;base64,"):
        return False, "非 png data URI"
    try:
        raw = base64.b64decode(src.split(",", 1)[1], validate=True)
    except Exception as exc:
        return False, "base64 解码失败: %s" % exc
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return False, "PNG 签名缺失（%d 字节）" % len(raw)
    # 结构层：chunk 逐块 CRC + 长度闭合
    pos, idat, n_chunk = 8, b"", 0
    while pos + 8 <= len(raw):
        (length,) = struct.unpack(">I", raw[pos:pos + 4])
        ctype = raw[pos + 4:pos + 8]
        if pos + 8 + length + 4 > len(raw):
            return False, "chunk %s 声明 %d 字节但文件截断" % (ctype.decode("latin1"), length)
        (crc,) = struct.unpack(">I", raw[pos + 8 + length:pos + 12 + length])
        if zlib.crc32(raw[pos + 4:pos + 8 + length]) & 0xFFFFFFFF != crc:
            return False, "chunk %s CRC 不符=内容损坏（总 %d 字节）" % (ctype.decode("latin1"), len(raw))
        if ctype == b"IDAT":
            idat += raw[pos + 8:pos + 8 + length]
        n_chunk += 1
        pos += 12 + length
        if ctype == b"IEND":
            break
    else:
        return False, "IEND 缺失=文件截断（%d 字节）" % len(raw)
    if pos != len(raw):
        return False, "IEND 后有 %d 字节多余数据" % (len(raw) - pos)
    # 像素层：IDAT 解压长度 vs IHDR 声明（"签名+IEND 空壳"在此暴露：无 IDAT/长度不符）
    ihdr = None
    pos2 = 8
    while pos2 + 8 <= len(raw):
        (length,) = struct.unpack(">I", raw[pos2:pos2 + 4])
        ctype = raw[pos2 + 4:pos2 + 8]
        if ctype == b"IHDR":
            ihdr = raw[pos2 + 8:pos2 + 8 + length]
            break
        pos2 += 12 + length
    if ihdr is None or len(ihdr) < 10:
        return False, "IHDR 缺失（%d 字节文件）" % len(raw)
    w, h = struct.unpack(">II", ihdr[:8])
    color_type = ihdr[9]
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if bpp is None:
        return False, "色型 %d 未支持" % color_type
    try:
        raw_px = zlib.decompress(idat)
    except Exception as exc:
        return False, "IDAT 解压失败: %s" % exc
    expect = h * (1 + w * bpp)
    if len(raw_px) != expect:
        return False, "像素数据 %d 字节 ≠ %dx%d 需 %d" % (len(raw_px), w, h, expect)
    # 主通道：PIL 真解码（能被图片库打开才算图）
    if HAS_PIL:
        try:
            img = Image.open(io.BytesIO(raw))
            img.load()
            return True, "%dx%d PIL 解码通过（%d 字节 PNG，%d chunk）" % (w, h, len(raw), n_chunk)
        except Exception as exc:
            return False, "PIL 打不开: %s（%d 字节）" % (exc, len(raw))
    return True, "%dx%d 结构+像素校验通过（PIL 不可用，%d 字节）" % (w, h, len(raw))

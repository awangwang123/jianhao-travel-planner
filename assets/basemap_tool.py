# -*- coding: utf-8 -*-
"""高德瓦片底图拼接+坐标映射工具（GCJ-02 与收藏点坐标系直接对齐）"""
import sys, math, io, time, urllib.request, os, json
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# 瓦片磁盘缓存（v3.74）：默认 ~/.amap_tile_cache 跨册复用，环境变量 BASEMAP_TILE_CACHE 可改
TILE_CACHE = os.environ.get("BASEMAP_TILE_CACHE") or os.path.join(os.path.expanduser("~"), ".amap_tile_cache")

def fetch_tile(tx, ty, z):
    """单瓦片获取：先查缓存（命中=零网络零睡眠），未命中下载并回写。返回 (data|None, hit)"""
    cp = os.path.join(TILE_CACHE, "style8", "z%d" % z, "%d_%d.png" % (tx, ty))
    if os.path.exists(cp):
        return open(cp, "rb").read(), True
    url = f"https://webrd0{1 + (tx + ty) % 4}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={tx}&y={ty}&z={z}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=15).read()
            os.makedirs(os.path.dirname(cp), exist_ok=True)
            open(cp, "wb").write(data)
            return data, False
        except Exception as e:
            if attempt == 2:
                print(f"  ⚠️ 瓦片 {tx},{ty} 三次失败: {e}")
            time.sleep(1.5)
    return None, False

def lonlat_to_tile_px(lon, lat, z):
    """web 墨卡托：经纬度→全局像素坐标"""
    n = 2 ** z * 256
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return x, y

def stitch(bbox, z, out_path, pad_px=60):
    """bbox=(lon_min, lat_min, lon_max, lat_max)，拼接瓦片裁剪到 bbox 外扩 pad_px"""
    lon_min, lat_min, lon_max, lat_max = bbox
    x0, y1 = lonlat_to_tile_px(lon_min, lat_min, z)   # 左下
    x1, y0 = lonlat_to_tile_px(lon_max, lat_max, z)   # 右上
    x0, y0, x1, y1 = x0 - pad_px, y0 - pad_px, x1 + pad_px, y1 + pad_px
    tx0, ty0, tx1, ty1 = int(x0 // 256), int(y0 // 256), int(x1 // 256), int(y1 // 256)
    W, H = (tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256
    canvas = [[None] * (tx1 - tx0 + 1) for _ in range(ty1 - ty0 + 1)]
    total = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    print(f"  拼接 {tx1-tx0+1}x{ty1-ty0+1} 瓦片（z={z}，输出 {W}x{H}）...")
    done = 0
    hits = 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            data, hit = fetch_tile(tx, ty, z)
            canvas[ty - ty0][tx - tx0] = data
            if data:
                done += 1
            if hit:
                hits += 1
                continue  # 缓存命中：不睡眠不重试
            time.sleep(0.4)
    print(f"  缓存命中 {hits}/{total}（{TILE_CACHE}）")
    # PNG 拼接（纯 py，无 PIL 依赖的最低方案：直接存单瓦片不可行——用 zopfli 不现实）
    # 检查 PIL
    try:
        from PIL import Image
    except ImportError:
        print("  ❌ 无 PIL，需 pip install pillow")
        return None
    img = Image.new("RGB", (W, H), "#F2EFE9")
    for i, row in enumerate(canvas):
        for j, tile in enumerate(row):
            if tile:
                img.paste(Image.open(io.BytesIO(tile)).convert("RGB"), (j * 256, i * 256))
    crop = img.crop((int(x0 - tx0 * 256), int(y0 - ty0 * 256),
                     int(x0 - tx0 * 256) + int(x1 - x0), int(y0 - ty0 * 256) + int(y1 - y0)))
    crop.save(out_path)
    print(f"  ✅ {out_path}（{crop.size[0]}x{crop.size[1]}）")
    # 返回映射函数：bbox 原点（裁剪后左上角对应的经纬度）——裁剪起点全局像素=x0/y0 本身
    origin_lon = x0 / (2 ** z * 256) * 360.0 - 180.0
    o_lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y0 / (2 ** z * 256))))
    origin_lat = math.degrees(o_lat_rad)
    return {"w": crop.size[0], "h": crop.size[1], "origin_lon": origin_lon, "origin_lat": origin_lat, "z": z}

def lonlat_to_img_px(lon, lat, meta):
    """经纬度→输出图片像素"""
    x, y = lonlat_to_tile_px(lon, lat, meta["z"])
    ox, oy = lonlat_to_tile_px(meta["origin_lon"], meta["origin_lat"], meta["z"])
    return x - ox, y - oy

if __name__ == "__main__":
    OUT = os.path.dirname(os.path.abspath(__file__))
    # 皖南黟县：宏村(117.985,30.0035) 为中心，村落群西递/塔川/木坑/卢村/南屏/屏山/碧山/奇墅湖
    jobs = [
        ("overview", (117.880, 29.925, 118.065, 30.095), 13),  # 黟县村落群全景
        ("day1",     (114.200, 29.780, 118.120, 30.780), 8),   # 武汉→宏村路途（横长条）
        ("day2",     (117.960, 29.945, 118.065, 30.045), 13),  # 宏村-塔川-木坑-卢村
        ("day3",     (117.900, 29.925, 118.030, 30.085), 13),  # 宏村-西递-南屏-屏山-碧山
    ]
    metas = {}
    for name, bbox, z in jobs:
        print(f"[{name}]")
        meta = stitch(bbox, z, os.path.join(OUT, f"basemap_{name}.png"))
        if meta:
            metas[name] = meta
    with open(os.path.join(OUT, "basemap_meta.json"), "w", encoding="utf-8") as f:
        json.dump(metas, f, ensure_ascii=False, indent=1)
    print("meta 已存 basemap_meta.json")

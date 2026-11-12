# -*- coding: utf-8 -*-
"""route_map.py —— v1.20 真底图导览图通用生成器（数据驱动，替代每册手写地图脚本）
任务书二-1/二-2 + WW 2026-11-04 复核：地图由「册级专用脚本+硬编码时刻」改为
「通用渲染器 + trip_data.map_spec 数据」。换目的地=填 map_spec，不改工具。

用法: 从包根（或任意目录）跑: py tools/route_map.py <trip_data.json>
行为: 读顶层 map_spec → 逐图渲染（底图瓦片拼接+点位/连线/底注+图下列表）→
      写 maps/<base>.png 与 svg 文本 → 注入 trip_data（overview_structured.figure_html /
      days[].svg_html）→ 审计通过后回写 trip_data.json；审计失败不回写、exit 1。

硬闸（WW 二轮复核四项的机制化）:
  A1 单源审计：产物文本中一切 HH:MM 必须经 slot/transport 引用或 EST 推算登记，
     孤儿时刻=FAIL（「读了数据≠渲染了该数据」——M7 假单源案）；
  A2 挂点校验：points[].slot_refs 与 ev 引用必须解析到本册真实 slot/transport（悬空=FAIL）
     ——「时刻挂在正确地点」的机检层；事件语义是否准确仍须人工逐节点复核（边界如实声明）；
  A3 出界断言：标注超 viewBox=WARN>0=FAIL；
  A4 未核实口径：points[].solid=false 渲染空心虚线点+「（示意）」——示意位与实现同规则。

底图: 包内 assets/basemap_tool.py（相对路径，无本机绝对依赖）；瓦片缓存 ~/.amap_tile_cache。
map_spec 形态见 schema.md §5c。print 只 ASCII。
"""
import sys, os, json, io, re, base64

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PKG, "assets"))   # 包内 basemap_tool（相对路径）
sys.path.insert(0, HERE)                          # fact.resolve_slot_t（正文同一闸门）
from basemap_tool import lonlat_to_tile_px, stitch   # noqa: E402
from fact import resolve_slot_t                      # noqa: E402

PAD = 60
FS, FS_S, FS_NOTE = 26, 20, 15
C_MAIN = "#b03a2e"
DASH_BUS = "10 9"
WARN = []
_SRC, _EST, _TXT = [], [], []
W0 = [0, 0]

# ── 登记/解析 ────────────────────────────────────────────────
def T(sid, where=""):
    s = _SLOTS.get(sid)
    if s is None:
        raise ValueError("map_spec%s: slot %r 不存在（A2 悬空引用）" % (where, sid))
    t = str(resolve_slot_t(s["t"], _TR, "map_spec%s" % where))
    assert re.match(r"^\d{1,2}:\d{2}$", t), "slot %s 时刻形态异常: %r" % (sid, t)
    _SRC.append((t, "slot:%s" % sid))
    return t

def TT(ref, where=""):
    tr_id, _, field = ref.partition(".")
    tr = _TR.get(tr_id)
    v = tr
    for part in (field.split(".") if field else []):
        v = v.get(part) if isinstance(v, dict) else None
    if v in (None, ""):
        raise ValueError("map_spec%s: 正本 %r 解析为空（A2）" % (where, ref))
    _SRC.append((str(v), "transport:%s" % ref))
    return str(v)

def EST(sid, add_min, label, where=""):
    base = T(sid, where)
    m = re.match(r"(\d{1,2}):(\d{2})", base)
    mm = int(m.group(1)) * 60 + int(m.group(2)) + add_min
    t = "%02d:%02d" % (mm // 60, mm % 60)
    _EST.append((t, "%s+%dmin(%s)" % (base, add_min, label)))
    return t

def DIFF(t1, t2):
    _SRC.append((t1, "diff")); _SRC.append((t2, "diff"))
    a = re.match(r"(\d{1,2}):(\d{2})", t1); b = re.match(r"(\d{1,2}):(\d{2})", t2)
    return int(b.group(1)) * 60 + int(b.group(2)) - (int(a.group(1)) * 60 + int(a.group(2)))

def TIMES_IN(rec, label):
    for m in re.findall(r"\d{1,2}:\d{2}", json.dumps(rec, ensure_ascii=False)):
        _TXT.append((m, label))

def ev_render(evs, where):
    """ev 数组：{"t":"d2s3"|"tr001.arr_time"} 引用 / {"est":{"ref","add","label"}} 推算 /
    {"diff":{"est_ref","est_add","to"}} 分钟差（余量句）/ {"lit":"..."} 字面"""
    out = []
    for i, e in enumerate(evs):
        w = "%s.ev[%d]" % (where, i)
        if "lit" in e:
            out.append(str(e["lit"]))
        elif "est" in e:
            e2 = e["est"]
            out.append(EST(e2["ref"], int(e2["add"]), e2.get("label", ""), " " + w))
        elif "diff" in e:
            e2 = e["diff"]
            out.append(str(DIFF(EST(e2["est_ref"], int(e2["est_add"]), e2.get("label", ""), " " + w),
                                TT(e2["to"], " " + w))))
        elif "t" in e:
            v = e["t"]
            out.append(TT(v, " " + w) if "." in v and not re.match(r"^d\d+s\d+$", v) else T(v, " " + w))
        else:
            raise ValueError("%s: 未知 ev 形态 %r" % (w, e))
    return "".join(out)

# ── 几何/绘制 ────────────────────────────────────────────────
def node_px(lon, lat, z, bbox):
    lon_min, lat_min, lon_max, lat_max = bbox
    gx, gy = lonlat_to_tile_px(lon, lat, z)
    x0, y1 = lonlat_to_tile_px(lon_min, lat_min, z)
    x1, y0 = lonlat_to_tile_px(lon_max, lat_max, z)
    return gx - (x0 - PAD), gy - (y0 - PAD)

def b64png(path):
    return base64.b64encode(open(path, "rb").read()).decode()

def svg_wrap(base_png, body, note1, note2):
    b64 = b64png(base_png)
    w, h = W0[0], W0[1]
    style = ("width:auto;max-width:100%;max-height:520px;margin:10px auto;"
             "display:block;border-radius:12px")
    return (
        "<svg class='zoomable' xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' "
        "viewBox='0 0 %d %d' width='%d' height='%d' style=\"%s\" role='img'>"
        "<image xlink:href='data:image/png;base64,%s' x='0' y='0' width='%d' height='%d'/>"
        "%s"
        "<text x='14' y='%d' font-size='%d' fill='#5a5246' opacity='0.92'>%s</text>"
        "<text x='14' y='%d' font-size='%d' fill='#5a5246' opacity='0.92'>%s</text>"
        "</svg>" % (w, h, w, h, style, b64, w, h, body, h - 14, FS_NOTE, note1, h - 34, FS_NOTE, note2)
    )

def auto_layout(points, pos, W, H):
    """v1.20 候选十批（M9D 复盘实证：防出界 anchor/dy 人工推算占制作侧约 4 分钟——自动布标替代）。
    未显式指定 anchor/dx/dy 的点：按图内位置自动选边（右 40% 左展/左 40% 右展）+垂直默认位+
    碰撞避让（标签矩形与已放置标签相交则 dy 步进尝试）；spec 显式指定的点照用制作侧值并登记占位。
    返回 [(point, anchor, dx, dy)]；仍出界的极端情形由 A3 出界审计兜底报 WARN。"""
    placed = []

    def est_w(label):
        return int(FS * sum(0.55 if ord(c) < 0x2E80 else 1.0 for c in label))

    def rect(x, y, anchor, dx, dy, w):
        tx = x + dx - (w / 2 if anchor == "middle" else (w if anchor == "end" else 0))
        return (tx, y + dy - FS, tx + w, y + dy + 4)

    def hits(r):
        return any(not (r[2] < q[0] or r[0] > q[2] or r[3] < q[1] or r[1] > q[3]) for q in placed)

    def out(r):
        return r[0] < 0 or r[2] > W or r[1] < 0 or r[3] > H

    layout = []
    for p in points:
        x, y = pos[p["key"]]
        label = p["label"] + ("" if p.get("solid", True) else "（示意）")
        w = est_w(label)
        if ("anchor" in p) or ("dx" in p) or ("dy" in p):
            a = p.get("anchor", "start")
            dx = int(p.get("dx", 14))
            dy = int(p.get("dy", -12))
            placed.append(rect(x, y, a, dx, dy, w))
            layout.append((p, a, dx, dy))
            continue
        a = "end" if x > W * 0.6 else "start"
        dx = -14 if a == "end" else 14
        base = 16 if y < H * 0.15 else (-16 if y > H * 0.85 else -12)
        chosen = None
        fallback = None
        for dy in (base, base + 18, base - 18, base + 36, base - 36, base + 54, base - 54):
            r = rect(x, y, a, dx, dy, w)
            if out(r):
                continue
            if not hits(r):
                chosen = (a, dx, dy, r)
                break
            if fallback is None:
                fallback = (a, dx, dy, r)
        if chosen is None:
            chosen = fallback or (a, dx, base, rect(x, y, a, dx, base, w))
        placed.append(chosen[3])
        layout.append((p, chosen[0], chosen[1], chosen[2]))
    return layout


def dot(x, y, place, solid=True, anchor="start", dx=14, dy=-12):
    label = place if solid else place + "（示意）"
    est_w = int(FS * sum(0.55 if ord(c) < 0x2E80 else 1.0 for c in label))
    tx = x + dx - (est_w / 2 if anchor == "middle" else (est_w if anchor == "end" else 0))
    ty = y + dy
    if tx < 0 or tx + est_w > W0[0] or ty - FS < 0 or ty > W0[1]:
        WARN.append("label out of bounds: %s tx=%d ty=%d" % (label, round(tx), round(ty)))
    if not solid:
        return ("".join([
            "<circle cx='%d' cy='%d' r='11' fill='rgba(255,255,255,0.75)' stroke='%s' "
            "stroke-width='3' stroke-dasharray='5 4'/>" % (x, y, C_MAIN),
            "<text x='%d' y='%d' font-size='%d' font-weight='bold' fill='#2b2620' "
            "stroke='#ffffff' stroke-width='5' paint-order='stroke' text-anchor='%s'>%s</text>"
            % (x + dx, ty, FS, anchor, label)]))
    return ("".join([
        "<circle cx='%d' cy='%d' r='11' fill='%s' stroke='#ffffff' stroke-width='3'/>" % (x, y, C_MAIN),
        "<text x='%d' y='%d' font-size='%d' font-weight='bold' fill='#2b2620' "
        "stroke='#ffffff' stroke-width='5' paint-order='stroke' text-anchor='%s'>%s</text>"
        % (x + dx, ty, FS, anchor, label)]))

def path(points, dash, width=6):
    pts = " ".join("%d,%d" % p for p in points)
    dashattr = "stroke-dasharray='%s'" % dash if dash else ""
    return ("<polyline points='%s' fill='none' stroke='#4a6a8a' stroke-width='%d' "
            "stroke-linecap='round' stroke-linejoin='round' %s opacity='0.85'/>"
            % (pts, width, dashattr))

def list_html(rows):
    h = ["<div style='font-size:14px;line-height:1.85;margin-top:8px'>"]
    for r in rows:
        h.append("<b>%s</b> — %s<br/>" % (esc(r.get("place", "")), esc(r.get("ev_text", ""))))
    h.append("<span style='color:#5a5246'>（「约」=按行程正文时长推算的估计抵达；"
             "空心点=片区示意，精确位待确认）</span></div>")
    return "".join(h)

def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ── 主流程 ────────────────────────────────────────────────────
def main():
    global _SLOTS, _TR
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    data_path = os.path.abspath(sys.argv[1])
    d = json.load(io.open(data_path, encoding="utf-8"))
    spec = d.get("map_spec")
    if not isinstance(spec, dict) or not spec.get("maps"):
        # v1.20 候选九批（v128，M9 实证）：禁静默跳过——无真底图必须显式声明，
        # 制作侧与 pipeline 输出都能看到，杜绝「渲染静默退回已否定样式」无感知通过。
        print("WARN: no map_spec / maps empty -> NO real-basemap guide map this book.")
        print("  Rendering falls back to schematic SVG; declare schematic wording in")
        print("  delivery notes, or fill map_spec per schema.md 5c (survey coords, no fabrication).")
        return
    _SLOTS = {}
    for dy in d["days"]:
        for s in dy["slots"]:
            _SLOTS[s["id"]] = {"t": s["t"], "text": s["text"], "day": dy["day"]}
    _TR = {r["id"]: r for r in list(d.get("transports", [])) + list(d.get("flights", [])) if r.get("id")}
    all_ids = set(_SLOTS.keys())
    # A2 挂点校验：spec 里声明的 slot_refs 必须全部可解析
    for name, mp in (spec.get("maps") or {}).items():
        for p in mp.get("points", []):
            for ref in p.get("slot_refs", []):
                if ref not in all_ids:
                    raise ValueError("map_spec.%s.points[%s].slot_refs: %r 悬空（A2）" % (name, p.get("key"), ref))
    for tr in d.get("transports", []):
        TIMES_IN(tr, "transport:%s" % tr.get("id"))
    for tk in d.get("tickets", []):
        TIMES_IN(tk, "ticket:%s" % tk.get("id"))
    for dy in d["days"]:
        for s in dy["slots"]:
            TIMES_IN(s, "slot:%s" % s.get("id"))

    maps_dir = os.path.join(os.path.dirname(data_path), "maps")
    os.makedirs(maps_dir, exist_ok=True)
    products = []
    for name, mp in (spec.get("maps") or {}).items():
        bbox, z = mp["bbox"], int(mp["z"])
        print("[%s] stitch..." % name)
        meta = stitch(tuple(bbox), z, os.path.join(maps_dir, mp["base"]))
        W0[0], W0[1] = meta["w"], meta["h"]
        P = lambda ll: node_px(ll[0], ll[1], z, tuple(bbox))
        pos = {p["key"]: P(p["lonlat"]) for p in mp["points"]}
        body = []
        for ln in mp.get("lines", []):
            body.append(path([pos[k] for k in ln["via"]],
                             DASH_BUS if ln.get("dash") else "",
                             int(ln.get("width", 6))))
        for p, _a, _dx, _dy in auto_layout(mp["points"], pos, meta["w"], meta["h"]):
            x, y = pos[p["key"]]
            body.append(dot(x, y, p["label"], solid=p.get("solid", True),
                            anchor=_a, dx=_dx, dy=_dy))
        rows = []
        for i, r in enumerate(mp.get("list", [])):
            rows.append({"place": r["place"],
                         "ev_text": ev_render(r["ev"], ".%s.list[%d]" % (name, i))})
        svg = svg_wrap(os.path.join(maps_dir, mp["base"]), "".join(body),
                       mp.get("note1", ""), mp.get("note2", ""))
        html = svg + list_html(rows)
        products.append(html)
        io.open(os.path.join(maps_dir, "%s_map.svg.txt" % name), "w", encoding="utf-8").write(html)
        tgt = mp.get("target", {})
        if tgt.get("figure"):     # 总览：overview_structured.figure_html
            d["overview_structured"]["figure_html"] = html
        if tgt.get("day"):        # 逐日：days[n].svg_html（day 从 1 计）
            d["days"][tgt["day"] - 1]["svg_html"] = html
        print("[%s] ok %dx%d, list=%d" % (name, meta["w"], meta["h"], len(rows)))
    if spec.get("clear_routes"):
        d["routes"] = []   # 真底图接管导览图后，竖向流程图路线数据退役（V15 空列表=ok 声明）

    # A1/A3 审计：产物中一切 HH:MM 须登记在案；出界 WARN>0=FAIL。审计不过不回写。
    blob = "\n".join(products)
    found = re.findall(r"\d{1,2}:\d{2}", blob)
    legal = {t for t, _ in _SRC} | {t for t, _ in _EST} | {t for t, _ in _TXT}
    orphans = sorted({t for t in found if t not in legal})
    ok = True
    if orphans:
        print("AUDIT FAIL: orphan times: %r" % orphans)
        ok = False
    if WARN:
        for w in WARN:
            print("BOUNDS FAIL: %s" % w)
        ok = False
    if not ok:
        sys.exit(1)
    log = io.open(os.path.join(os.path.dirname(data_path), "..", "_maps_audit.txt"), "w", encoding="utf-8") \
        if os.path.isdir(os.path.join(os.path.dirname(data_path), "..")) else io.open("_maps_audit.txt", "w", encoding="utf-8")
    for t, s in _SRC:
        log.write("SRC  %s  <- %s\n" % (t, s))
    for t, s in _EST:
        log.write("EST  %s  <- %s\n" % (t, s))
    for t, s in _TXT:
        log.write("TXT  %s  <- %s\n" % (t, s))
    log.close()
    json.dump(d, io.open(data_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("AUDIT OK: %d times all registered (src=%d est=%d txt=%d); bounds WARN=0; injected+saved"
          % (len(set(found)), len(_SRC), len(_EST), len(_TXT)))


if __name__ == "__main__":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()

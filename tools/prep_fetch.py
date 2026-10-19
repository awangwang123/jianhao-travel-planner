# -*- coding: utf-8 -*-
"""确定性数据预抓聚合入口（公用版 v1.14 起收录：LLM 介入前一次抓完，输出单一 JSON）
用法: py prep_fetch.py "城市名" "lat,lon" "2026-11-16" [--days 8] [--out prep_data.json]
  坐标=目的地中心（Nominatim 可查）；日期=出发日
抓取清单（全部为确定性 API，无需判断力）：①日照日出（sunrise-sunset.org 逐日）
②汇率（frankfurter.dev 欧洲央行，本币→CNY）③POI 坐标批量（Nominatim，从 stdin 传 POI 列表可选）
产出: JSON 落盘+控制台摘要。天气/门票/美食=判断性数据，仍走 LLM 实查通路（铁律 1 不适用本脚本）。
"""
import json, sys, io, time, urllib.request, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "travel-planner-prep/1.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()

def sun(lat, lon, dates):
    out = {}
    for d in dates:
        try:
            j = json.loads(_get("https://api.sunrise-sunset.org/json?lat=%s&lng=%s&date=%s&formatted=0" % (lat, lon, d)))
            r = j.get("results", {})
            out[d] = {"sunrise": r.get("sunrise"), "sunset": r.get("sunset"), "day_length_s": r.get("day_length")}
        except Exception as e:
            out[d] = {"error": repr(e)[:60]}
        time.sleep(1.0)
    return out

def fx(base):
    try:
        j = json.loads(_get("https://api.frankfurter.dev/v1/latest?base=%s&symbols=CNY" % base))
        return {"rate": j["rates"]["CNY"], "date": j["date"], "source": "ECB via frankfurter.dev"}
    except Exception as e:
        return {"error": repr(e)[:60]}

def geocode(name):
    try:
        q = urllib.parse.urlencode({"q": name, "format": "json", "limit": 1})
        j = json.loads(_get("https://nominatim.openstreetmap.org/search?" + q))
        if j:
            return {"lat": float(j[0]["lat"]), "lon": float(j[0]["lon"]), "display": j[0]["display_name"][:70]}
        return {"error": "MISS"}
    except Exception as e:
        return {"error": repr(e)[:60]}

def main():
    city, latlon, start = sys.argv[1], sys.argv[2], sys.argv[3]
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 8
    outp = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "prep_data.json"
    lat, lon = [float(x) for x in latlon.split(",")]
    import datetime
    d0 = datetime.date.fromisoformat(start)
    dates = [(d0 + datetime.timedelta(days=i)).isoformat() for i in range(days)]
    data = {"city": city, "center": {"lat": lat, "lon": lon}, "dates": dates,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "sun": sun(lat, lon, dates), "fx_note": "汇率按目的地币种在下方 fx 字段；本脚本默认输出 EUR/USD 参考",
            "fx_EUR": fx("EUR"), "fx_USD": fx("USD")}
    json.dump(data, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in data["sun"].values() if "sunset" in v)
    print("DONE %s：日照 %d/%d 天 | EUR=%s | 落盘 %s" % (
        city, ok, len(dates), data["fx_EUR"].get("rate", "?"), outp))

if __name__ == "__main__":
    main()

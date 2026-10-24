# -*- coding: utf-8 -*-
"""
make_synth_books.py —— 第 3 步合成数据：3/8/10 天完整 trip_data（过 V01-V12 全量校验）
用法: py make_synth_books.py  → 产出 fixtures/synth/book{3,8,10}.json
设计: 无 blocks 键（禁旧 HTML 直渲，全走结构化渲染）；slot 全带稳定 id；机位 spot 名写入所绑
slot 文案（V12 零噪音）；返程日带真实 SVG+可解码 PNG（真返程图不缺失断言的对象）
"""
import io
import json
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synth")

SVG = ("<svg viewBox='0 0 300 120' data-test='day-svg'>"
       "<polyline points='20,90 120,60 200,75 270,30' fill='none' stroke='#c0392b' stroke-width='3'/>"
       "<polygon points='270,30 260,36 272,42' fill='#c0392b' data-arrow='1'/></svg>")
PHOTO = ("<figure data-test='day-photo'>"
         "<img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='"
         " alt='合成图'></figure>")
WEEK = ["六", "日", "一", "二", "三", "四", "五"]


def make_book(n_days):
    date_of = lambda i: "11-%02d" % i  # noqa: E731  day i（1 起）→ 11 月日期
    days, tickets, transports = [], [], []
    for i in range(1, n_days + 1):
        is_last = i == n_days
        tid = "t%03d" % i
        tickets.append({"id": tid, "name": "合成景点%d" % i, "text": "样张门票",
                        "price_display": "100 元",
                        "applicability": {"reservation": "建议"}})
        slots = [
            # v1.2 R4：默认节奏示范——首项 09:30 起安排行程（吃饭/交通/游玩都算），自然醒合规无需任何标记
            {"id": "d%ds1" % i, "t": "09:40", "type": "meal", "ref": None,
             "text": "早餐·合成宾馆"},
            {"id": "d%ds2" % i, "t": "10:30", "type": "spot", "ref": tid,
             "text": "<b>合成景点%d</b>：样张正文，含机位地点" % i},
            {"id": "d%ds3" % i, "t": "14:00", "type": "spot", "ref": None,
             "text": "<b>合成看点%d</b>：下午慢逛" % i},
            {"id": "d%ds4" % i, "t": "18:00", "type": "meal", "ref": None,
             "text": "晚餐·合成餐馆"},
        ]
        if i > 1:
            slots.insert(0, {"id": "d%ds0" % i, "t": "09:30", "type": "transport",
                             "ref": "tr%03d" % i, "text": "合成站→景区（样张交通）"})
            transports.append({"id": "tr%03d" % i, "name": "合成交通%d" % i, "text": "样张",
                               "billing": {"optional": True, "reason": "合成样张交通（费用样张省略）"}})
        cam = [{"spot": "合成景点%d" % i, "time": "10:00-11:00 顺光", "how": "样张拍法",
                "scope": "slot", "slot_ref": "d%ds2" % i}]
        if is_last:
            slots.append({"id": "d%ds9" % i, "t": "16:00", "type": "transport",
                          "ref": "tr901", "text": "合成站→武汉（返程样张）"})
        days.append({
            "day": i, "date": date_of(i), "weekday": WEEK[i % 7], "city": "合成城",
            "theme": "合成行程%d" % i, "label": date_of(i),
            "h3": "合成城 · 第%d天" % i, "nav_label": "第%d天" % i,
            "brief": "合成样张第 %d 天速览" % i,
            "slots": slots, "meals": {"早餐": None, "午餐": None, "晚餐": None},
            "stay": None, "cam": cam,
            "knowhow": "合成冷知识 %d" % i, "planb": "样张应急",
            "svg_html": SVG, "photos_html": PHOTO,
        })
    transports.append({"id": "tr901", "name": "合成返程高铁", "text": "样张返程",
                       "billing": {"optional": True, "reason": "合成样张返程（费用样张省略）"}})
    book = {
        "schema_version": "1.1",
        "meta": {
            "title": "合成测试 %d 天" % n_days, "destination": "合成城", "home_city": "武汉",
            "date_window": {"start": "2026-11-01", "end": "2026-11-%02d" % n_days},
            "pax": {"adults": 2, "children": 0, "note": "样张"},
            "tier": "standard",
            "timezones": [{"area": "Asia/Shanghai", "utc_offset": "+08:00", "vs_home_hours": 0}],
            "fx": [{"base": "CNY", "quote": "CNY", "rate": 1, "checked_at": "2026-10-21",
                    "source": "synthetic"}],
            "city_code": "sy", "optional_note": "样张自选：无",
            "checked_at_label": "2026-10-21",
        },
        "tickets": tickets,
        "stays": [{"id": "s001", "name": "合成宾馆", "text": "样张住宿"}],
        "meals": [{"id": "m001", "name": "合成餐馆", "text": "样张餐饮",
                    "billing": {"optional": True, "reason": "合成样张餐饮（费用样张省略）"}}],
        "flights": [], "transports": transports,
        "misc": [{"id": "x001", "name": "合成保险", "text": "样张",
                   "billing": {"optional": True, "reason": "合成样张保险（费用样张省略）"}}],
        "expenses": (
            [{"id": "e1%03d" % i, "ref": "t%03d" % i, "category": "门票",
              "label": "合成景点%d" % i, "amount": 100, "currency": "CNY", "unit": "每次",
              "qty": 1, "scope": {"pax": 1}, "price_mode": "含税", "tier": "主选",
              "pay_status": "待付", "verify_status": "verified",
              "checked_at": "2026-10-21", "source": "synthetic"} for i in range(1, n_days + 1)]
            + [{"id": "e2001", "ref": "s001", "category": "住宿", "label": "合成宾馆",
                "amount": 200, "currency": "CNY", "unit": "每间夜", "qty": 1,
                "scope": {"pax": 2, "rooms": 1}, "price_mode": "含税", "tier": "主选",
                "pay_status": "待付", "verify_status": "verified",
                "checked_at": "2026-10-21", "source": "synthetic"}]
        ),
        "days": days,
        "assets": [],
        "overview_structured": {
            "eyebrow": "总览", "h1": "合成测试 %d 天" % n_days,
            "leads": ["合成城｜武汉 → {date_range}｜2 成人",
                      "时差 +08:00（无）｜汇率 CNY→CNY 1.000"],
            "warn_line": "合成样张页（第 3 步回归产物，非真实出行）",
            "weather": [{"d": date_of(i), "w": "晴", "t": "10~18℃"} for i in (1, 2, 3)],
            "weather_note": "样张天气口径", "figure_html": PHOTO, "tail_note": "样张尾注",
        },
        "prep_structured": {"cards": [{
            "card_attr": "data-testid='synth-prep'", "eyebrow": "出发前",
            "lead_p": "样张引导", "items": [{"hot": True, "id": "sy_chk_1", "html": "合成装备一"}],
            "tail_p": "样张尾部"}]},
        "sos_structured": {"eyebrow": "应急", "h2": "应急 · 样张", "lead": "样张口径",
                           "cards": [{"h4": "🆘 紧急号码", "p": "110/120（样张）"}]},
        "boost_structured": {"eyebrow": "锦上添花", "h2": "加分项（样张）", "lead": "样张口径",
                             "items": [{"html": "样张加分项一", "mt10": False},
                                       {"html": "样张加分项二", "mt10": True}]},
        "gift_structured": {"eyebrow": "手信", "h2": "特产（样张）",
                            "table": {"widths": ["40%", "60%"], "cols": ["手信", "说明"],
                                      "rows": [["合成糕点", "样张条目"]]},
                            "tail_notes": []},
        "drive_structured": {"eyebrow": "路程", "h2": "大交通（样张）",
                             "table": {"widths": ["30%", "70%"], "cols": ["段", "说明"],
                                       "rows": [["武汉→合成城", "样张高铁"]]},
                             "tail_notes": ["<p>样张时差注</p>"]},
        "stay_structured": {"eyebrow": "住宿", "h2": "住宿（样张）",
                            "table": {"widths": ["30%", "70%"], "cols": ["晚", "说明"],
                                      "rows": [["全程", "合成宾馆（样张）"]]},
                            "tail_notes": []},
        "ticket_structured": {"eyebrow": "门票", "h2": "门票（样张）",
                              "lead": "样张口径",
                              "table": {"widths": ["40%", "20%", "40%"],
                                        "cols": ["景点", "价格", "说明"],
                                        "rows": [["合成景点%d" % i, "100 元", "样张"]
                                                 for i in range(1, n_days + 1)],
                                        "_row_refs": ["t%03d" % i for i in range(1, n_days + 1)]},
                              "tail_notes": []},
        "tips_structured": {"eyebrow": "提示", "h2": "提示（样张）", "lead": "样张口径",
                            "tips": ["样张提示一"], "tail_cards": []},
        "eat_structured": {"eyebrow": "美食", "h2": "吃什么（样张）", "lead": "样张口径",
                           "groups": [{"title": "Day1（样张）", "widths": ["30%", "70%"],
                                       "cols": ["餐", "推荐"], "rows": [["晚餐", "合成餐馆"]]}],
                           "tail_title": "必吃清单（样张）", "tail_body": "合成馆子一句话。",
                           "tail_cards": [], "tail_footer": None},
    }
    return book


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for n in (3, 8, 10):
        p = os.path.join(OUT_DIR, "book%d.json" % n)
        with io.open(p, "w", encoding="utf-8") as fh:
            json.dump(make_book(n), fh, ensure_ascii=False, indent=1)
        print("wrote", p)

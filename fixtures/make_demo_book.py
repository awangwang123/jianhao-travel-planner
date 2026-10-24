# -*- coding: utf-8 -*-
"""
make_demo_book.py —— 完整示范样本（虚构目的地「云溪镇」3 天，非任何真实地点）
用途: 新手第一次跑通——照 README「工具模式」四步生成含导览图的示范册，
      成品检查（checklist 默认模式）应 FAIL 0。
边界: 全部人名/店名/价格均为虚构演示数据；与 fixtures/synth/（最小合成册，仅测试链路）
      和 fixtures/good_full.json（校验规则演示）分工不同——本样本目标是「完整且检查全过」。
用法: py make_demo_book.py  → 产出 fixtures/demo/demo_full.json
"""
import io
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo", "demo_full.json")

SVG = ("<svg viewBox='0 0 300 120' data-test='day-svg'>"
       "<polyline points='20,90 120,60 200,75 270,30' fill='none' stroke='#c0392b' stroke-width='3'/>"
       "<polygon points='270,30 260,36 272,42' fill='#c0392b' data-arrow='1'/></svg>")
PHOTO = ("<figure data-test='day-photo'>"
         "<img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
         "' alt='（示意）演示配图'></figure>")
PHOTO2 = ("<figure data-test='day-photo'>"
          "<img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
          "' alt='（示意）演示配图二'></figure>")
WEEK = ["五", "六", "日"]

DAYS = [
    {"day": 1, "date": "11-13", "weekday": "五", "city": "云溪镇",
     "theme": "抵达 · 老街慢逛",
     "slots": [
         {"id": "d1s1", "t": "07:30", "type": "meal", "ref": "m101",
          "text": "早餐·家中简餐（出发前吃完，车站不用赶）"},
         {"id": "d1s2", "t": {"tr_ref": "tr001", "field": "dep_time"}, "type": "transport", "ref": "tr001",
          "text": "<b>G1737 武汉→云溪镇</b>（checklist 演示：时刻由正本单源引用）"},
         {"id": "d1s3", "t": {"tr_ref": "tr001", "field": "arr_time"}, "type": "transport", "ref": "tr001",
          "text": "抵达云溪镇站——出站右转出租车点，10 分钟到老街客栈"},
         {"id": "d1s4", "t": "12:30", "type": "meal", "ref": "m102",
          "text": "午餐·老街豆腐宴（人均 40 元，招牌豆腐煲两人份够）"},
         {"id": "d1s5", "t": "13:30", "type": "checkin", "ref": "s001",
          "text": "入住云溪客栈——行李放好再出门，前台可寄存"},
         {"id": "d1s6", "t": "14:30", "type": "spot",
          "text": "<b>云溪老街</b>：青石板路两侧明清铺面，酱菜铺与竹器店值得进（免费开放）"},
         {"id": "d1s7", "t": "16:30", "type": "spot",
          "text": "<b>江滨步道</b>：日落前光线最软，走到底就是渡口遗址"},
         {"id": "d1s8", "t": "18:30", "type": "meal", "ref": "m103",
          "text": "晚餐·溪畔土菜馆（人均 55 元，溪鱼两人份）"},
     ],
     "meals": {"早餐": {"ref": "m101"}, "午餐": {"ref": "m102"}, "晚餐": {"ref": "m103"}},
     "stay": {"ref": "s001"},
     "cam": [{"spot": "云溪老街", "time": "15:00-16:00 侧逆光", "how": "0.5x 广角贴地拍青石板延伸线", "scope": "slot", "slot_ref": "d1s6"},
             {"spot": "江滨步道", "time": "日落前半小时", "how": "长焦压缩渡口剪影", "scope": "slot", "slot_ref": "d1s7"}],
     "knowhow": "云溪老街的青石板是明代漕运码头遗存——缝隙里的凹槽是当年独轮车压出的。",
     "planb": "若抵达晚于 15:00：老街压缩为 1 小时快走，江滨步道移到 D2 早晨。",
     "svg_html": SVG, "photos_html": PHOTO + PHOTO2},
    {"day": 2, "date": "11-14", "weekday": "六", "city": "云溪镇",
     "theme": "漂流 · 古镇一日",
     "slots": [
         {"id": "d2s1", "t": "08:30", "type": "meal", "ref": "m104",
          "text": "早餐·客栈含早（粥+ eggs+本地腌菜，吃到 9 点不赶）"},
         {"id": "d2s2", "t": {"tr_ref": "tr002", "field": "dep_time"}, "type": "transport", "ref": "tr002",
          "text": "客栈门口班线车→漂流码头（20 分钟，班次见路程表）"},
         {"id": "d2s3", "t": "10:10", "type": "spot", "ref": "t001",
          "text": "<b>云溪漂流</b>：全程 2.5 小时，手机防水袋必备"},
         {"id": "d2s4", "t": "12:40", "type": "meal", "ref": "m105",
          "text": "午餐·码头大排档（人均 35 元，烤鱼现杀）"},
         {"id": "d2s5", "t": "13:50", "type": "spot", "ref": "t002",
          "text": "<b>溪南古镇</b>：三座清代廊桥串起来走，尾巴出片"},
         {"id": "d2s6", "t": "16:00", "type": "note",
          "text": "茶歇·古镇茶馆（自愿，40 元/位含点心——恢复体力再逛）"},
         {"id": "d2s7", "t": "17:30", "type": "spot",
          "text": "<b>古镇日落位</b>：西廊桥桥头，日落方向正对水面"},
         {"id": "d2s8", "t": "18:40", "type": "meal", "ref": "m106",
          "text": "晚餐·古镇酒家（人均 60 元，升体验可点溪虾）"},
     ],
     "meals": {"早餐": {"ref": "m104"}, "午餐": {"ref": "m105"}, "晚餐": {"ref": "m106"}},
     "stay": {"ref": "s001"},
     "cam": [{"spot": "云溪漂流", "time": "11:00 前后顺光", "how": "防水袋挂胸前拍第一落差", "scope": "slot", "slot_ref": "d2s3"},
             {"spot": "溪南古镇", "time": "16:00-17:00", "how": "廊桥中轴对称构图", "scope": "slot", "slot_ref": "d2s5"},
             {"spot": "古镇日落位", "time": "日落前 20 分钟", "how": " hdr 三连拍水面反光", "scope": "slot", "slot_ref": "d2s7"}],
     "knowhow": "漂流旺季周末建议提前 1 天在景区公众号预约——现场队可能排 40 分钟。",
     "planb": "雨天漂流停开：替换为溪南古镇+镇史馆半日（ticket 同价退改规则见门票表）。",
     "svg_html": SVG, "photos_html": PHOTO + PHOTO2},
    {"day": 3, "date": "11-15", "weekday": "日", "city": "云溪镇",
     "theme": "手信 · 返程",
     "slots": [
         {"id": "d3s1", "t": "08:40", "type": "meal", "ref": "m107",
          "text": "早餐·镇口豆浆铺（人均 10 元，现磨）"},
         {"id": "d3s2", "t": "09:40", "type": "spot", "ref": "t003",
          "text": "<b>手信街</b>：豆腐乳与竹编两样最值得带"},
         {"id": "d3s3", "t": "11:00", "type": "meal", "ref": "m108",
          "text": "午餐·镇口饭馆（人均 30 元，早午饭出发前吃饱）"},
         {"id": "d3s4", "t": {"tr_ref": "tr003", "field": "dep_time"}, "type": "transport", "ref": "tr003",
          "text": "客栈→云溪镇站（班线车 20 分钟；先回客栈取行李）"},
         {"id": "d3s5", "t": {"tr_ref": "tr004", "field": "dep_time"}, "type": "transport", "ref": "tr004",
          "text": "<b>G1740 云溪镇→武汉</b>（演示：到达时刻与正本联动）"},
         {"id": "d3s6", "t": "18:30", "type": "meal", "ref": "m109",
          "text": "晚餐·武汉家中（自理——到家后用餐，不计入行程支出）"},
     ],
     "meals": {"早餐": {"ref": "m107"}, "午餐": {"ref": "m108"}, "晚餐": {"ref": "m109"}},
     "stay": None,
     "cam": [{"spot": "手信街", "time": "上午顶光弱", "how": "店铺招牌特写+竹编纹理微距", "scope": "slot", "slot_ref": "d3s2"}],
     "knowhow": "云溪豆腐乳只在每年 10 月-次年 3 月生产——错过季节买到的都是去年库存。",
     "planb": "若改签晚班：手信街后可加镇史馆（免费，1 小时）。",
     "svg_html": SVG, "photos_html": PHOTO + PHOTO2},
]


def make_demo():
    tickets = [
        {"id": "t001", "name": "云溪漂流", "text": "全程 2.5 小时，含装备；雨季停开",
         "price_display": "128 元", "applicability": {"reservation": "建议", "date": "11-14"}},
        {"id": "t002", "name": "溪南古镇", "text": "三座廊桥联票",
         "price_display": "60 元", "applicability": {"reservation": "免预约"}},
        {"id": "t003", "name": "手信街", "text": "免费开放", "price_display": "免费",
         "applicability": {"reservation": "免预约"},
         "billing": {"optional": True, "reason": "免费开放，无门票支出"}},
    ]
    stays = [{"id": "s001", "name": "云溪客栈（民宿）", "text": "老街江景房，含早",
              "applicability": {"checkin": "13:30", "checkout": "11:00", "nights": 2}}]
    meals = [
        {"id": "m101", "name": "家中简餐", "text": "出发前",
                "billing": {"optional": True, "reason": "家中自理，无外出支出"}},
        {"id": "m102", "name": "老街豆腐宴", "text": "人均 40 元"},
        {"id": "m103", "name": "溪畔土菜馆", "text": "人均 55 元"},
        {"id": "m104", "name": "客栈含早", "text": "住客免费",
                "billing": {"optional": True, "reason": "房费已含早，不重复计费"}},
        {"id": "m105", "name": "码头大排档", "text": "人均 35 元"},
        {"id": "m106", "name": "古镇酒家", "text": "人均 60 元"},
        {"id": "m107", "name": "镇口豆浆铺", "text": "人均 10 元"},
        {"id": "m108", "name": "镇口饭馆", "text": "人均 30 元"},
        {"id": "m109", "name": "武汉家中", "text": "到家自理",
         "billing": {"optional": True, "reason": "到家用餐，不计入行程支出"}},
    ]
    transports = [
        {"id": "tr001", "name": "G1737 武汉→云溪镇",
         "applicability": {"mode": "高铁", "dep_time": "08:26", "arr_time": "11:59"},
         "text": "二等座 156 元/人"},
        {"id": "tr002", "name": "班线车 客栈→漂流码头",
         "applicability": {"mode": "巴士", "dep_time": "09:30"},
         "text": "20 分钟，8 元/人", "billing": {"optional": True, "reason": "班线车票价低，示范结构化可选口径"}},
        {"id": "tr003", "name": "班线车 客栈→云溪镇站",
         "applicability": {"mode": "巴士", "dep_time": "11:30"},
         "text": "20 分钟，8 元/人", "billing": {"optional": True, "reason": "同上示范"}},
        {"id": "tr004", "name": "G1740 云溪镇→武汉",
         "applicability": {"mode": "高铁", "dep_time": "13:06", "arr_time": "16:38"},
         "text": "二等座 156 元/人"},
    ]
    misc = [{"id": "x001", "name": "旅行意外险（3 天）", "text": "示范：杂项也要有费用落点"}]
    expenses = [
        {"id": "e001", "ref": "tr001", "category": "城际交通", "label": "去程高铁",
         "amount": 156, "currency": "CNY", "unit": "每人", "qty": 2, "price_mode": "含税",
         "tier": "主选", "pay_status": "待付", "verify_status": "verified",
         "checked_at": "2026-10-24", "source": "虚构演示数据"},
        {"id": "e002", "ref": "tr004", "category": "城际交通", "label": "返程高铁",
         "amount": 156, "currency": "CNY", "unit": "每人", "qty": 2, "price_mode": "含税",
         "tier": "主选", "pay_status": "待付", "verify_status": "verified",
         "checked_at": "2026-10-24", "source": "虚构演示数据"},
        {"id": "e003", "ref": "t001", "category": "门票", "label": "云溪漂流",
         "amount": 128, "currency": "CNY", "unit": "每人", "qty": 2, "price_mode": "含税",
         "tier": "主选", "pay_status": "待付", "verify_status": "verified",
         "checked_at": "2026-10-24", "source": "虚构演示数据"},
        {"id": "e004", "ref": "t002", "category": "门票", "label": "溪南古镇",
         "amount": 60, "currency": "CNY", "unit": "每人", "qty": 2, "price_mode": "含税",
         "tier": "主选", "pay_status": "待付", "verify_status": "verified",
         "checked_at": "2026-10-24", "source": "虚构演示数据"},
        {"id": "e005", "ref": "s001", "category": "住宿", "label": "云溪客栈 2 晚",
         "amount": 280, "currency": "CNY", "unit": "每间夜", "qty": 2,
         "scope": {"pax": 2, "rooms": 1}, "price_mode": "含税", "tier": "主选",
         "pay_status": "待付", "verify_status": "verified",
         "checked_at": "2026-10-24", "source": "虚构演示数据"},
    ]
    exp_id = 6
    for m in ("m102", "m103", "m105", "m106", "m107"):
        amount = {"m102": 80, "m103": 110, "m105": 70, "m106": 120, "m107": 20}[m]
        label = next(x["name"] for x in meals if x["id"] == m)
        expenses.append({"id": "e%03d" % exp_id, "ref": m, "category": "餐饮",
                         "label": label, "amount": amount, "currency": "CNY", "unit": "每单",
                         "qty": 1, "price_mode": "含税", "tier": "主选", "pay_status": "待付",
                         "verify_status": "verified", "checked_at": "2026-10-24",
                         "source": "虚构演示数据"})
        exp_id += 1
    expenses.append({"id": "e011", "ref": "m108", "category": "餐饮",
                     "label": "镇口饭馆", "amount": 60, "currency": "CNY", "unit": "每单",
                     "qty": 1, "price_mode": "含税", "tier": "主选", "pay_status": "待付",
                     "verify_status": "verified", "checked_at": "2026-10-24",
                     "source": "虚构演示数据"})
    expenses.append({"id": "e012", "ref": "x001", "category": "杂项", "label": "旅行意外险",
                     "amount": 30, "currency": "CNY", "unit": "每单", "qty": 1,
                     "price_mode": "含税", "tier": "主选", "pay_status": "待付",
                     "verify_status": "verified", "checked_at": "2026-10-24",
                     "source": "虚构演示数据"})

    book = {
        "schema_version": "1.1",
        "meta": {
            "title": "云溪镇 3 天 · 工具模式示范册（虚构）",
            "destination": "云溪镇（虚构演示地）", "home_city": "武汉",
            "date_window": {"start": "2026-11-13", "end": "2026-11-15"},
            "pax": {"adults": 2, "children": 0, "note": "虚构演示：2 成人"},
            "tier": "standard",
            "timezones": [{"area": "Asia/Shanghai", "utc_offset": "+08:00", "vs_home_hours": 0}],
            "fx": [{"base": "CNY", "quote": "CNY", "rate": 1, "checked_at": "2026-10-24",
                    "source": "虚构演示"}],
            "city_code": "yxz",
            "optional_note": "茶歇/手信等自选项单列，不进主线合计",
            "checked_at_label": "2026-10-24",
            "budget_tail_note": "隐藏成本已留行：景区交通/停车/服务费/小费——本册无自驾，"
                                "含班线车 8 元/段与码头寄存 10 元余量口径。",
        },
        "tickets": tickets, "stays": stays, "meals": meals, "flights": [],
        "transports": transports, "misc": misc, "expenses": expenses,
        "days": DAYS,
        "assets": [],
        "routes": [
            {"day": 1, "title": "抵达 · 老街慢逛", "notes": ["示范：节点顺序即拓扑，时刻由数据派生"],
             "nodes": [{"label": "武汉站", "time": "08:00"},
                       {"label": "云溪镇站", "time": "12:00", "arrive_mode": "rail"},
                       {"label": "云溪客栈（放行李）", "time": "13:10", "arrive_mode": "bus"},
                       {"label": "云溪老街", "time": "14:30", "arrive_mode": "walk"},
                       {"label": "江滨步道·日落", "time": "16:30", "arrive_mode": "walk"}]},
            {"day": 2, "title": "漂流 · 古镇一日", "notes": ["示范：三段交通用三种线型区分"],
             "nodes": [{"label": "客栈", "time": "08:30"},
                       {"label": "漂流码头", "time": "09:30", "arrive_mode": "bus"},
                       {"label": "溪南古镇", "time": "13:50", "arrive_mode": "bus"},
                       {"label": "古镇日落位", "time": "17:30", "arrive_mode": "walk"}]},
            {"day": 3, "title": "手信 · 返程", "notes": [],
             "nodes": [{"label": "客栈", "time": "08:40"},
                       {"label": "手信街", "time": "09:40", "arrive_mode": "walk"},
                       {"label": "云溪镇站", "time": "11:30", "arrive_mode": "bus"}]},
        ],
        "overview_structured": {
            "eyebrow": "总览 · 行程速览", "h1": "云溪镇 3 天（虚构示范册）",
            "leads": ["云溪镇｜武汉 → {date_range}｜2 成人",
                      "时差无｜币种 CNY（示范数据，价格均为虚构）"],
            "warn_line": "虚构演示册——地名/店名/价格全部为演示数据，非真实出行建议",
            "weather": [{"d": "11-13", "w": "晴", "t": "12~19℃"},
                        {"d": "11-14", "w": "多云", "t": "11~18℃"},
                        {"d": "11-15", "w": "晴", "t": "10~17℃"}],
            "weather_note": "演示天气口径——出发前按当日预报终判",
            "figure_html": PHOTO, "tail_note": "出发前必办：漂流预约（见门票表）+意外险投保。",
        },
        "prep_structured": {"cards": [{
            "card_attr": "data-testid='demo-prep'", "eyebrow": "出发前",
            "lead_p": "出发前 3 天要办的三件事（示范）",
            "items": [{"hot": True, "id": "yx_chk_1", "html": "漂流预约：景区公众号提前 1 天"},
                      {"id": "yx_chk_2", "html": "意外险投保（见杂项费用）"},
                      {"id": "yx_chk_3", "html": "防水袋/换洗衣物"}],
            "tail_p": "演示数据——正式出行前按当年口径复核"}]},
        "sos_structured": {"eyebrow": "应急", "h2": "应急 · 演示", "lead": "虚构演示数据——真实出行请查当地最新口径",
                           "cards": [{"h4": "🆘 紧急号码", "p": "110 / 120 急诊 / 119（演示口径）"},
                                     {"h4": "🏥 医疗落点", "p": "云溪镇卫生院（演示）——急诊走县医院"}]},
        "boost_structured": {"eyebrow": "可选 · 更从容", "h2": "可选 · 更从容（演示）",
                             "lead": "自愿项目不进主线合计——以下均为到店现付的加分体验，跳过不影响主线完整。",
                             "items": [{"html": "古镇茶歇 40 元/位：含点心与位费，雨天替代漂流下午段", "mt10": False},
                                       {"html": "夜游船 60 元/人：季节性开航，码头现场问当日班次", "mt10": True},
                                       {"html": "镇史馆免费：手信街旁，讲解牌自助扫码", "mt10": True}]},
        "gift_structured": {"eyebrow": "特产 · 带一份回家", "h2": "手信（演示）",
                            "table": {"widths": ["40%", "60%"], "cols": ["手信", "说明"],
                                      "rows": [["豆腐乳", "仅 10 月-次年 3 月生产（演示口径）；坛装 25 元/罐"],
                                               ["竹编食盒", "老街竹器店，可刻字；40-80 元按大小"],
                                               ["云溪绿茶", "镇口铺子散装 60 元/100g，可试饮"]]},
                            "tail_notes": ["<p>演示：三样均可快递到家，运费到付</p>"]},
        "drive_structured": {"eyebrow": "路程 · 交通串联", "h2": "大交通（演示）",
                             "table": {"widths": ["30%", "70%"], "cols": ["段", "说明"],
                                       "rows": [["武汉→云溪镇", "G1737（08:26→11:59）"],
                                                ["云溪镇→武汉", "G1740（13:06→16:38）"]]},
                             "tail_notes": ["<p>班线车/市内段见每日卡（演示）</p>"]},
        "stay_structured": {"eyebrow": "住宿", "h2": "住宿（演示）",
                            "lead": "升级体验可问前台：江景房升层（演示口径）——客栈为两层的民宿型 lodging，共 8 间房",
                            "table": {"widths": ["30%", "70%"], "cols": ["晚", "说明"],
                                      "rows": [["D1、D2", "云溪客栈（民宿）江景房 280 元/晚，含早；周末建议提前一周订"]]},
                            "tail_notes": ["<p>演示：押金 100 元现付，退房时退还</p>"]},
        "ticket_structured": {"eyebrow": "门票 · 预约", "h2": "门票（演示）",
                              "lead": "价格均为虚构演示数据",
                              "table": {"widths": ["40%", "20%", "40%"],
                                        "cols": ["景点", "价格", "说明"],
                                        "rows": [["云溪漂流", "128 元", "全程 2.5 小时含装备；建议提前 1 天公众号预约，雨季停开可全额退"],
                                                 ["溪南古镇", "60 元", "三座清代廊桥联票，当日无限次进出；傍晚光线最好"],
                                                 ["手信街", "免费", "开放街区免票；店铺零售与手信另计，豆腐乳季节限定"]],
                                        "_row_refs": ["t001", "t002", "t003"]},
                              "tail_notes": ["<p>演示口径：价格以景区当日公示为准</p>"]},
        "tips_structured": {"eyebrow": "提示", "h2": "提示（演示）", "lead": "演示口径——正式出行按当年实况",
                            "tips": ["雨天方案：漂流停开时替换古镇+镇史馆半日（Plan B 已排）",
                                     "漂流带防水袋；手机挂绳",
                                     "拍摄参数速查卡：日落 f8/1/250s/ISO100；夜景 f2.8/1/30s/ISO800（一人行自拍可用三脚架+倒计时）"],
                            "tail_cards": []},
        "eat_structured": {"eyebrow": "照着吃就行", "h2": "吃什么（演示）", "lead": "人均为虚构演示口径。升级体验：古镇酒家二楼临水位（+40 元/桌）需提前一天订。",
                           "groups": [{"title": "D1（老街）", "widths": ["25%", "45%", "30%"],
                                       "cols": ["餐", "推荐", "备选"],
                                       "rows": [["午餐", "老街豆腐宴（豆腐煲）", "街口面馆"],
                                                ["晚餐", "溪畔土菜馆（溪鱼）", "老街饭庄"]]},
                                      {"title": "D2（码头/古镇）", "widths": ["25%", "45%", "30%"],
                                       "cols": ["餐", "推荐", "备选"],
                                       "rows": [["午餐", "码头大排档（烤鱼）", "桥头小吃"],
                                                ["晚餐", "古镇酒家（溪虾）", "巷内私房菜"]]}],
                           "tail_title": "必吃清单（演示）", "tail_body": "溪鱼与豆腐煲是本地两样招牌。",
                           "tail_cards": [], "tail_footer": None,
                           "upgrade_note": "升级体验：古镇酒家二楼临水位需提前一天订（演示口径）。"},
    }
    return book


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(make_demo(), fh, ensure_ascii=False, indent=1)
    print("wrote", OUT)

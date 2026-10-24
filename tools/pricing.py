# -*- coding: utf-8 -*-
"""
pricing.py —— 费用计费口径唯一正本（Codex 五/六轮复核立规：r_cost 与 budget_calc 必须共用）
口径（schema §3）：
  每人        → 小计 = amount × qty × pax（人数）
  每间夜/每晚  → 小计 = amount × qty × rooms（房间数；房间价不按人头乘！）
  每次/每天/每单 → 小计 = amount × qty（按次数/天数/订单数；scope.pax 是"适用人数"=适用条件，
                  不是计费因子——两人同乘一次出租车 100 元/单就是 100，不是 200。
                  确需按人头计价时显式写 unit="每人"）
"""


def expense_mult(e, pax_all):
    """按 unit 返回乘数系数（amount×qty 之外的部分）。未知 unit 回退 1。"""
    unit = e.get("unit")
    sc = e.get("scope") or {}
    pax_eff = sc.get("pax") or pax_all or 1
    rooms_eff = sc.get("rooms") or 1
    if unit == "每人":
        return pax_eff
    if unit in ("每间夜", "每晚"):
        return rooms_eff
    if unit in ("每次", "每天", "每单"):
        return 1  # 按次/天/单计，适用人数≠计费数量（Codex 六轮复核）
    return 1

# -*- coding: utf-8 -*-
"""fact.py —— v1.2 事实数据/来源/核实状态/展示文字分离（任务书③；R2 复核修订版）
fact = {
    "candidates": ["20:34", "20:39"],
    "sources":    ["gaotie", "ip138"],   # 必须与 candidates 等长（R2：空 sources 不再放行）
    "checked_at": "2026-10-22",
    "status":     "confirmed | pending_confirmation | unverified",
    "note":       "自由备注（可选）"
}
展示派生（R2 修订）：
    1 值 + confirmed           → 「20:39」
    1 值 + unverified          → 「20:39（未核实）」——状态不再丢失
    1 值 + pending             → 「20:39（待确认）」
    多值 + 有 sources          → 「来源 gaotie 为 20:34、来源 ip138 为 20:39，待确认」——逐来源列出，不拼普通区间、不预设 12306
    多值 + 无 sources          → 「候选 20:34 / 20:39，待确认」
通用模块不预设任何具体票务场景（R2：去除 12306 硬编码——场景话术由调用方 note 传入）。"""
import io

STATUS_ENUM = {"confirmed", "pending_confirmation", "unverified"}
STATUS_TAG = {"pending_confirmation": "待确认", "unverified": "未核实", "confirmed": ""}


def validate_fact(fact, where="fact"):
    if not isinstance(fact, dict):
        raise ValueError("%s: fact 必须是 dict（candidates/sources/checked_at/status）" % where)
    vals = fact.get("candidates")
    if not isinstance(vals, list) or not vals or not all(str(v).strip() for v in vals):
        raise ValueError("%s: candidates 必须是非空字符串列表" % where)
    srcs = fact.get("sources")
    if not isinstance(srcs, list) or len(srcs) != len(vals) or not all(str(s).strip() for s in srcs):
        # R2：sources 必须与 candidates 等长且非空——来源缺失的事实不许过闸
        raise ValueError("%s: sources 必须与 candidates 等长且非空（每候选值带来源）" % where)
    status = fact.get("status")
    if status not in STATUS_ENUM:
        raise ValueError("%s: status %r 不在 %s" % (where, status, sorted(STATUS_ENUM)))
    if len(vals) >= 2 and status == "confirmed":
        raise ValueError("%s: 候选值 %d 个（来源冲突）却标 confirmed——冲突必须 pending_confirmation" % (where, len(vals)))
    if not fact.get("checked_at"):
        raise ValueError("%s: 缺 checked_at" % where)


def fact_display(fact, where="fact"):
    """展示文字派生（唯一实现）。R2：unverified 不再输出裸值；多值逐来源列出；去 12306 硬编码。"""
    validate_fact(fact, where)
    vals = [str(v) for v in fact["candidates"]]
    srcs = [str(s) for s in fact["sources"]]
    status = fact["status"]
    if len(vals) == 1:
        tag = STATUS_TAG.get(status, "")
        return vals[0] + ("（%s）" % tag if tag else "")
    if len(set(srcs)) == len(srcs):
        body = "、".join("来源 %s 为 %s" % (s, v) for s, v in zip(srcs, vals))
    else:
        body = "候选 " + " / ".join(vals)
    return "%s，待确认" % body


def resolve_slot_t(val, tr_idx, where="slot.t"):
    """slot.t 引用形态解析正本（R8，作者复核：值复制+比对≠单源——引用派生才同步）：
      - 字符串 / fact dict（带 candidates）：原样返回（fact 交 fact_display）
      - 引用 dict {tr_ref, field}：查业务记录正本 applicability[field]，返回其值（str/fact）
    悬空引用/字段缺失/引用链（正本字段又是指引用）→ ValueError（fail-closed，毒数据进不了渲染）。"""
    if isinstance(val, dict) and "tr_ref" in val:
        tr = (tr_idx or {}).get(val.get("tr_ref"))
        if tr is None:
            raise ValueError("%s: 引用 tr_ref=%r 不存在于业务表" % (where, val.get("tr_ref")))
        v = (tr.get("applicability") or {}).get(val.get("field"))
        if v is None:
            raise ValueError("%s: 正本 %s 无字段 %r" % (where, val.get("tr_ref"), val.get("field")))
        if isinstance(v, dict) and "tr_ref" in v:
            raise ValueError("%s: 正本字段又是指引用——禁引用链" % where)
        return v
    return val


def fill_slot_text(text, tr, where="slot.text"):
    """班次时刻文案占位符填充（R9，作者复核缺口①：同一班次发车时刻不得手写在正文/地图标题）：
    slot.text 中的 {dep}/{arr} 由该 slot 绑定班次的正本 dep_time/arr_time 派生填充
    （fact 正本经 fact_display 展示——核实状态随文案保留）。无占位符原样返回。"""
    if not isinstance(text, str) or ("{dep}" not in text and "{arr}" not in text):
        return text
    ap = (tr or {}).get("applicability") or {}
    out = text
    for ph, fld in (("{dep}", "dep_time"), ("{arr}", "arr_time")):
        if ph in out:
            v = ap.get(fld)
            if isinstance(v, dict) and "candidates" in v:
                v = fact_display(v, "%s.%s" % (where, fld))
            out = out.replace(ph, str(v) if v is not None else "【%s 未填】" % ph)
    return out


if __name__ == "__main__":
    assert fact_display({"candidates": ["20:39"], "sources": ["gaotie"],
                         "checked_at": "2026-10-22", "status": "confirmed"}) == "20:39"
    assert fact_display({"candidates": ["999"], "sources": ["电话核实"],
                         "checked_at": "2026-10-22", "status": "unverified"}) == "999（未核实）"
    assert fact_display({"candidates": ["20:34", "20:39"], "sources": ["gaotie", "ip138"],
                         "checked_at": "2026-10-22", "status": "pending_confirmation"}) == \
        "来源 gaotie 为 20:34、来源 ip138 为 20:39，待确认"
    for bad, desc in [
        ({"candidates": ["999"], "sources": [], "checked_at": "x", "status": "unverified"}, "R2：空 sources"),
        ({"candidates": ["20:34", "20:39"], "sources": ["a"], "checked_at": "x", "status": "pending_confirmation"}, "不等长"),
        ({"candidates": ["20:34", "20:39"], "sources": ["a", "b"],
          "checked_at": "x", "status": "confirmed"}, "冲突却 confirmed"),
        ({"candidates": ["20:34"], "sources": ["a"], "status": "nope", "checked_at": "x"}, "非法状态"),
    ]:
        try:
            validate_fact(bad)
            raise AssertionError("毒 fact 未被拒绝: " + desc)
        except ValueError:
            pass
    print("FACT SELFTEST OK (R2)")

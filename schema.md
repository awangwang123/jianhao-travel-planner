# trip_data.json Schema v1.1（P3 数据层定稿）

> 定稿：2026-10-17（M1）｜ 正本：本文件 ｜ 校验器：`tools/validate_trip_data.py`（与本文件同步改，改一处必改另一处）
> 上游设计：`..\P3_生成器立项设计.md` v2 §3.1 ｜ 本文件是「表格规范」，校验脚本是「规范的可执行形态」
> 三条总纪律：①金额唯一出现处=`expenses` 费用明细账（业务记录禁存金额，防双写打架）②机械字段（价格/时刻/日期）模型禁手写、引用 ref；文案写在 `text` 字段 ③每条事实带 `checked_at`+`evidence`（字段级挂接，一个链接≠整条已核验）

## 0. 顶层结构

```json
{
  "schema_version": "1.0",
  "meta":       { …行程头（§1） },
  "tickets":    [ …门票/预约（§2.1） ],
  "stays":      [ …住宿（§2.2） ],
  "meals":      [ …餐饮（§2.3） ],
  "flights":    [ …国际航班（§2.4） ],
  "transports": [ …地面/水上交通含高铁（§2.5） ],
  "misc":       [ …签证/保险等杂项（§2.6） ],
  "expenses":   [ …费用明细账=预算唯一计算源（§3） ],
  "days":       [ …逐日行程（§4） ],
  "assets":     [ …配图（§5） ]
}
```

> 对 v2 设计 §3.1 的一处泛化：`flights` 拆为 `flights`（国际航班）+`transports`（高铁/机场线/市内/船票），避免地面交通挤进航班表；`misc` 承载签证/保险等无业务记录的费用载体。已在 ChatGPT 复核确认的「业务记录提供费用依据」框架内，不改变计算源=明细账的原则。

## 1. meta（行程头）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| title | string | ✅ | 册名 |
| destination | string | ✅ | 目的地 |
| home_city | string | ✅ | 出发地 |
| date_window | {start,end} | ✅ | `YYYY-MM-DD` |
| pax | {adults,children,note} | ✅ | 人数 |
| tier | 枚举 | ✅ | `fast`/`standard`/`premium`（档位感知用） |
| timezones | [{area,utc_offset,vs_home_hours}] | ✅ | 时差；`utc_offset` 格式 `+HH:MM`；`vs_home_hours` 数字（意冬令时=-7） |
| fx | [{base,quote,rate,checked_at,source}] | ✅ | 汇率表；预算折算唯一依据；**目标币种缺汇率=校验 FAIL**（无法折算禁出预算） |
| customize | {play_start} | — | 游玩开始锚点（V17，v1.2 R5 终版）：`play_start` 默认游玩开始线（`"09:30"`，09:30—10:00 开始游玩）。**起床不入册**：R4 的 `wake_earliest` 键作废（读到仅 WARN）；早餐/交通按需安排、可在此前，不校验 |
| schema_version | string | ✅ | `"1.0"` |

## 2. 业务记录（六表）

**通用字段**（六表全部适用）：

| 字段 | 必填 | 说明 |
|---|---|---|
| id | ✅ | 全局唯一，前缀按表：`t`=tickets `s`=stays `m`=meals `f`=flights `tr`=transports `x`=misc；**禁数组下标做长期引用** |
| name | ✅ | 显示名 |
| text | — | 文案字段（LLM 写：描述/话术/冷知识），渲染引擎只管版式不管措辞 |
| evidence | — | **字段级证据挂接**：`{"<事实键>": {"source":"…","checked_at":"YYYY-MM-DD","note":"…"}}`；事实键如 `price`/`hours`/`rule`——价格和营业时间可各挂各的证据 |

**各表适用条件字段 `applicability`**（价格之外的限制条件，渲染与核验都用）：

| 表 | applicability 内容 |
|---|---|
| tickets | `date`/`date_range`（适用日）、`ticket_kind`（票种）、`pax_scope`（人群）、`reservation`（`必须`/`建议`/`免预约`）、`combo`（联票结构说明） |
| stays | `city`、`area`、`checkin`/`checkout`、`nights`、`room_type`（房型）、`pax`（入住人数）、`breakfast`（含早 bool） |
| meals | `day_no`（哪天）、`meal_type`（`早餐`/`午餐`/`晚餐`）、`price_basis`（**参考点单范围**——人均口径说明）、`area` |
| flights | `flight_no`、`dep`/`arr`（机场+航站楼）、`dep_time`/`arr_time`、`dep_date`/`arr_date`（YYYY-MM-DD，**V21 必填**——完整当地日期时间核对防「时长多填一天」）、`duration_min`（官方飞行时长分钟，实查项——V21 必填）、`dep_tz_area`/`arr_tz_area`（航段时区，关联 meta.timezones[].area；或 `dep_utc_offset`/`arr_utc_offset` 直给——V21 必填）、`crosses_days`（+1 落地 bool——声明则 V19 强制到达日排 slot）。**V21 输入完备强制（R9）**：flights 表非空时上述任一缺失=「未检」FAIL 阻断验收；不适用仅限无航班 |
| transports | `mode`（`高铁`/`机场快线`/`地铁`/`巴士`/`渡轮`…）、`from`/`to`、`dep_time`/`arr_time`（**班次时刻正本**；字符串或 fact 结构——R6）、`dep_window`（发车时段）、`duration_note` |
| misc | `category`（`签证`/`保险`/`装备`…）、`note` |

## 3. expenses 费用明细账（预算唯一计算源）

```json
{
  "id": "e001",
  "ref": "f001",              // → 业务记录 id；纯杂项可省略
  "category": "机票",          // 枚举：机票|签证|住宿|城际交通|市内交通|门票|餐饮|杂项
  "label": "国际机票往返",      // 预算表显示名
  "amount": 3307,              // 单价（数字）。区间价用 amount_min/amount_max 二选一替代
  "currency": "CNY",           // ISO 三字母
  "unit": "每次",              // 枚举：每人|每间夜|每晚|每次|每天|每单
  "qty": 1,                    // 数量（数字）——小计=amount×qty（×scope 见下）
  "scope": {"pax": 1, "rooms": 0},  // 适用人数/房间数；缺省 pax=meta 全员
  "price_mode": "含税",        // 枚举：含税|净价+税（默认含税）；净价时必填 tax_rate
  "tax_rate": 0.0,             // 净价模式下的税率（小数），小计=amount×(1+tax_rate)×qty
  "tier": "主选",              // 枚举：主选|备选|可选 —— 基础预算只计主选；备选/可选披露不计入
  "inclusion": {"included_in": "e003", "note": "联票含古罗马广场入场"},  // 可选；被包含方求和时剔除并披露
  "pay_status": "待付",        // 枚举：已付|待付
  "verify_status": "verified", // 枚举：verified|estimated|pending
  "checked_at": "2026-10-16",
  "source": "携程列表页（22:56 时戳缓存价）",
  "note": "出签后（11 月上旬）再实查锁定"
}
```

**verify_status 三态语义（未核实金额≠0）**：
- `verified` → 计入合计
- `estimated` → 计入合计，预算输出标注「估算」
- `pending` → **不计入合计**，在「预算完整度」中逐项列名披露（防「未核实默默变 0」

**预算三规则（校验器 §3 用例的判定依据）**：
1. **计算范围**：合计=Σ(expenses 全量中 tier=主选 且 verify_status∈{verified,estimated} 且未被 inclusion 剔除者)——禁「门票×天数」式窄化
2. **数量口径**：小计=amount(或 min~max)×qty×scope，**禁一律乘天数**（每间夜×晚数、每人×人数、每次×次数各按各的）
3. **包含关系与币种**：`inclusion.included_in` 指向的明细被视为已含（剔除+披露，禁循环）；所有币种按 `meta.fx` 折算到 `quote` 币种后求和，**禁跨币种直接相加**
4. **计费口径按 unit 分派**（v1.1 细化，Codex 五/六轮复核）：每人→×pax；**每间夜/每晚→×rooms（房间价禁按人头乘）**；每次/每天/每单→仅×qty（scope.pax 是"适用人数"=适用条件，不是计费因子；按人头计价显式写"每人"）——正本 `tools/pricing.py expense_mult`，r_cost 与校验器预算试算共用

## 4. days 逐日

```json
{
  "day": 1,
  "date": "11-16",
  "weekday": "一",
  "city": "罗马",
  "theme": "上海→罗马",
  "slots": [
    {"id": "d1s1", "t": "12:40", "type": "flight", "ref": "f001",
     "text": "MU787 浦东T1→罗马T3（东航直飞 13h00m）"}
  ],
  "meals": {"早餐": null, "午餐": {"ref": "m001"}, "晚餐": {"ref": "m002"}},
  "stay": {"ref": "s001"},
  "cam": [{"spot": "圣天使堡台伯河畔", "time": "日落前", "how": "0.5x 广角贴栏杆低角度…", "scope": "slot", "slot_ref": "d1s3"}],
  "knowhow": "冷知识/背景一句话",
  "planb": "当日 Plan B"
}
```

- `slots[].type` 枚举：`flight`/`transport`/`spot`/`meal`/`checkin`/`note`；`ref` 必须指向与 type 匹配的表（V-V4 类型正确检查）
- `slots[].t`（v1.2 R8）：三种形态——①字符串 `"HH:MM"`（无正本可引的自由 slot）；②fact 结构 `{candidates, sources, checked_at, status}`（fact 时展示由 `fact_display` 派生，冲突标待确认、未核实带标注）；③**引用形态** `{"tr_ref": "<本 slot.ref>", "field": "dep_time"|"arr_time"}`（R8，作者复核指定：slot 引用「哪条业务记录的哪个字段」，由正本派生——**改正本一处，正文/表格/导览图自动同步**，核实状态由正本唯一承载）。带 `ref` 指向 transports 且被引记录有 dep/arr 时刻时**必须用引用形态**，复制值（字符串/fact 直填）=FAIL（**V20 引用闸**，杜绝值复制带来的状态丢失与 dep/arr 误配）；结构化板块表格行挂 `table._row_refs` 引用业务记录即单源联动（同门票价格单源先例）
- `slots[].id`（v1.1 新增）：稳定标识，格式 `d{day}s{n}`（day 内序号从 1 起）；**机位等页面组件靠 id 关联，显示时刻 `t` 改动不影响关联**（Codex 变更实验 2026-10-21：按时间字符串关联，改时段机位静默消失）。**id 中的 day 数字必须等于所在天**（day1 出现 `d99s4`=FAIL，V11）；id 一次分配后**不随插入/排序重编号**（稳定性承诺——重编号=引用静默错位）
- `cam[].scope`（v1.1 细化，Codex 二轮复核 2026-10-21）：`slot`（默认）=绑定具体时段，**必须给 slot_ref**；`day`=全天型机位，**必须显式声明且不得带 slot_ref**，渲染排当日尾部。**禁用"漏填 slot_ref"隐式代表全天**——漏填=FAIL（V11）
- `cam[].slot_ref`（v1.1 新增）：指向**本 day** 的某 `slots[].id`，悬空/跨日=FAIL（V11）。v1.0 的 `slot_t` 时间匹配已**废弃**：迁移期残留仅 WARN，渲染不再读取
- `meals` 值为 `{ref}` 或 `null`（当日无该餐段）；`ref` 必须指向 meals 表
- `slots[].text`（v1.2 R9）：班次/航段时刻**禁止手写**——用占位符 `{dep}`/`{arr}`（渲染时由 `fill_slot_text` 从该 slot 绑定班次正本填充，fact 核实状态随文案保留）。V20 两类拦截：a) 手写正本当前值（脆弱副本，改正本必漂移，地图标题亦从正文派生）；b) 班次号邻近时刻与正本无一相符（改正本漏改文案的矛盾残留）。普通时段（无班次号邻近，如「17:30 停运」）不受影响
- `slots[].user_ok`（v1.2 R5 游玩开始闸，V17 唯一实质规则）：当日**首个 type=spot**（游玩开始）早于 `play_start`（默认 09:30）时须该 slot 带 `user_ok:{"reason": "…"}`——即用户明确选择的早间玩法（日出/晨雾等）；制作侧不得自行补例外放行，未选择的早起玩法列 planb 可选。**起床/洗漱不入册**（R4 的 `day.wake` 强制字段作废，读到仅 WARN）；**早餐、交通按实际行程需要列出，可安排在游玩线之前**，不校验（R4「吃饭/交通都算首项安排」的扩大化管制作废）；接驳合理、不赶场属制作判断。R3 的 bool `early_ok` 同样废弃——读到仅 WARN，不作为放行依据
- `day` 连续编号（跳号=FAIL，承接 checklist v1.9 天数前置校验精神）

## 5. assets 配图

`[{"id":"a001","file":"…","credit":"…","license":"…","pool_ref":"…"}]`（M2 渲染接入，schema 先占位）

## 6. 校验器规则清单（validate_trip_data.py 必须实现，FAIL 输出规则号）

| 规则号 | 内容 |
|---|---|
| V01 | JSON 可解析+顶层必备键齐全 |
| V02 | ID 全局唯一（跨表禁重号） |
| V03 | 引用存在（days/expenses 里出现的所有 ref 均可解析，悬空=FAIL） |
| V04 | 引用类型正确（meal 槽位→meals 表；flight slot→flights；stay→stays；expenses.ref→六业务表之一） |
| V05 | inclusion 无循环（A 含于 B 且 B 含于 A=FAIL）；included_in 指向存在的 expense |
| V06 | 枚举合法：tier/unit/price_mode/pay_status/verify_status/category/slots.type/meals 键/ticket.reservation |
| V07 | 日期/时区/计价单位格式合法（date_window=YYYY-MM-DD；utc_offset=±HH:MM；fx.rate>0） |
| V08 | 净价+税模式必须带 tax_rate；区间价 amount_min≤amount_max |
| V09 | days.day 从 1 连续编号不跳号 |
| V10 | 预算试算可执行：所有主选明细币种在 meta.fx 有通路，折算求和成功；pending 项不计入但列入完整度披露 |
| V11 | 组件关联稳定（v1.1 细化）：`slots[].id` 存在、day 内唯一、格式 `d{day}s{n}` 且 **day 数字=所在天**；`cam[].scope` 枚举 `slot`(默认)/`day`——scope=slot 必须给合法 slot_ref（缺=FAIL，禁漏填隐式全天），scope=day 不得带 slot_ref；slot_ref 悬空/跨日=FAIL；`slot_t` 旧字段残留=WARN 提示迁移 |
| V12 | 机位归属启发式（WARN 级）：spot 名应在所绑 slot 文案中出现（全名或前 3 字，`cam_affinity_ok` 同函数供测试硬断言）——合法引用≠业务绑对，绑错时段由此闸提示人工 |
| V13 | 门票价格两源一致性（WARN 级）：`tickets.price_display` 与对应 `expenses.amount` 数字不符=数据债务提示；**门票表渲染已单源取 expenses**（改一处门票显示+预算同更新） |
| V14 | 日期对齐（FAIL 级）：`days[].date` 必须 = `date_window.start` 推算（start+day-1 天），总天数与窗口闭合——改窗口不同步每日日期=页面日期互相冲突 |
| V15 | routes 结构+语义闸（v1.2，FAIL 级）：节点≥2/mode 在定义表/禁遗留 edge_from/day 重复；语义层（提供 days 时）：routes[].day 须存在、slot_ref 须解析到该天、相邻可解析时刻禁倒退。由 `gen_route_svg.validate_routes` 同一函数把关 |
| V16 | 事实候选结构闸（v1.2，FAIL 级）：全树扫描带 candidates+status 的 fact dict——候选≥2 却标 confirmed/sources 不等长/状态非法/缺 checked_at 必拒（`fact.py validate_fact` 同一闸门） |
| V17 | 游玩开始闸（v1.2 R5 终版，FAIL 级）：默认 09:30—10:00 开始游玩（play_start 可配）；**唯一实质闸**=当日首个 spot 早于 play_start 须该 slot.user_ok{reason}（用户明确选择的早间玩法）；起床不入册（day.wake 作废仅 WARN）、早餐/交通按需安排可在此前不校验、bool early_ok 废弃不放行 |
| V18 | 费用关联三态闸（v1.2 R3，FAIL 级）：业务记录（六表全类型）必须 a) 被 expenses 计费 b) `billing.included_in` 指向真实落点（expense 或已计费业务）c) `billing.optional+reason` 显式排除——无 ref 无 billing=漏账必拦；stays/meals 不豁免 |
| V20 | 时刻单源引用闸（v1.2 R9 扩展，FAIL 级）：①slot.t 引用形态强制（同 R8）②**班次时刻禁手写正文**（R9）——slot.text 手写正本当前值=FAIL（应改 {dep}/{arr} 占位符）；班次号邻近时刻与正本无一相符=FAIL（改正本漏改文案的矛盾残留）；配套 drive 表 `_row_refs` 渲染单源覆盖 |
| V19 | 跨日航班排天闸（v1.2 R7，FAIL 级，出境语义①）：同 flight ref 复现于到达日（写法约定）时——到达日=紧邻次日、到达 slot 为当日最早、起飞后无非 note 安排、出发当夜 stay 空；crosses_days=true 必须排到达 slot；≥22:00 起飞未复现未声明=WARN 红眼嫌疑 |
| V21 | 跨时区时长自洽闸（v1.2 R9 重写，FAIL 级，出境语义②）：**完整当地日期时间核对**——expected_arr = dep_date+dep_time+duration_min+时差，与 arr_date+arr_time 差 ≤10min（时长多填一天必拦，钟面取模旧法已废）；**输入完备强制**——flights 表非空时缺 dep/arr_time、duration_min、日期、航段时区任一=「未检」FAIL 阻断验收（有航班缺输入≠不适用，不适用仅限无航班） |
| V22 | 门票日期绑定闸（v1.2 R8 重写，FAIL 级，出境语义③）：绑定日经 `_resolve_date` 解析（YYYY-MM-DD 直用；MM-DD 结合窗口定年——**支持跨年窗口**，统一换年份的旧法已废）须落入窗口，且与实际使用日一致（绑错日=当天进不了园）；未绑定不拦 |

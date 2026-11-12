# 快速制作（标准档 2-3 天路书）

正常制作只需以下五步，**无需阅读工具源码**；报错排查才按工具内注释定位。

## 五步流程

```bash
# 0. 开工（仅首次）：校验 SHA256 → 安全解压（中文名不损坏）→ 清点 → 复制工作副本
py tools/setup_pack.py 下载的包.zip --sha256 <发布页标注值>
#    ⚠️ 解包只走这一条路。禁用 unzip/右键解压/资源管理器——它们损坏 assets 中文文件名，
#    后果=基准骨架缺失，pipeline 开跑即拦（报「基准骨架缺失」就是解包走错了路，回本步重来）。

# 1. 建数据骨架：生成可直接填写的 trip_data.json（标准 JSON，任何编辑器可改）
py tools/pipeline.py new 我的目的地 --days 3 --start 2026-11-06

# 2. 填数据（按 schema.md「字段速查」；实查规则见 sources_playbook.md）
#    ★ 填完先跑简表，过了再配图扩写——路线/费用/节奏问题在这一步暴露最便宜
py tools/pipeline.py outline pkg_work/trip_data.json
#
#    填写速记（v1.20 候选九批，M8/M9/M9C 三册踩坑正本——枚举以校验器为准，禁照旧文档默写）：
#    · verify_status 三值 = verified / estimated / pending（没有 unverified）
#    · 全 CNY 册 meta.fx 整表可省略（按 1:1）；含外币才必填
#    · 四表(stay/ticket/drive/gift)行=数组的数组、只放 table.rows（顶层 rows 是死数据，V23 拦）
#    · 美食分组键=groups（不是 sections）；模板里没有的键不要自创，模板示例行整行替换即可
#    · weather 已带合法示例（{d,w,t} 三键对象数组）——逐条替换内容，禁改成字符串数组（V24 拦）
#    · map_spec.maps 为空=新册默认——要真底图导览图按 schema §5c 填 maps（坐标当次实查禁编造，
#      0/null 占位 V26 必拦）；不填则成品无真底图（V26 WARN 提醒），交付说明须声明示意稿口径
#    · 每天三餐=type=meal 的 slot 各绑 meals 表 ref（V25 缺哪餐报哪天）；早餐含房费用
#      billing.included_in 示范（模板 m001）
#    · 总览导语（v1.20 候选十批）：overview_structured.leads 两条——lead[0]=这趟玩什么+逐日节奏
#      （画面感表述），lead[1]=驻点+地理逻辑（动线圆心/行李搬动次数）；参数行渲染器自动出
#    · 市内接驳 slot（type=transport 无 ref）渲染自动紧凑化，班次（有 ref）保持醒目——
#      填写时把接驳写短（几点/什么方式/多久），玩法细节放进对应游玩 slot
#    · map_spec 标签不用手工调 anchor/dx/dy——工具自动布标+避让；只有自动结果不理想才显式指定

# 3. 配图（成品每日配图是硬要求；无 API key 用 Commons）
py tools/fetch_images.py search "洛阳 龙门石窟" --limit 5
py tools/fetch_images.py fetch "File:xxx.jpg" --note "图注文字"
#    下载→逐张亲验→回填只走 embed 入口（写 plan.json 后一条命令；只动 photos_html 字段，
#    写前自动留底+写后断言其余数据零变化）：
py tools/fetch_images.py embed pkg_work/trip_data.json --plan plan.json
#    ⚠️ 禁手写脚本整份读写 trip_data 回填配图——旧数据覆盖已修数据的事故就是这么来的（M9C 实证）。

# 4. 出成品（全链：数据闸→生成→导览图→成品检查含视觉）
py tools/pipeline.py full pkg_work/trip_data.json 成品.html --visual

# 5. 交付：checklist 全绿 + 事实来源清单三态齐全 + images/manifest 署名清单
#    full 成功后自动生成「成品.html.交付摘要.md」（环节耗时/成品闸结果/产物清单/今日计时）——
#    TESTLOG 引用它并只补人工解释（复核结论/绕行记录/口径声明），不再手写长篇战果报告。
#    计时表自动出：py tools/timer.py report --out 计时汇总.md
#    报告口径：FAIL 条数、错误类型数、问题数是三种计数，分开列不混用（不作趋势结论的单一依据）。
```

## 并行查证（省时）

车次时刻、门票与开放、酒店区域、餐饮候选、天气天文**互不依赖，可并行查**。实查止损规则见 `sources_playbook.md`——一句话：单一事实尝试 ≤3 次或 ≤5 分钟，失败换可核实来源或降级为估算+标注，不把时间耗死在单点上。

## 计时

```bash
py tools/timer.py stage 需求加载   # 阶段切换时打点（需求/实查/填数/生成/复核）
py tools/timer.py report --out 计时汇总.md  # 收尾自动出计时表（替代手填）
py tools/timer.py list            # 查看自动记录
```

## 人工复核集中点（自动化不替代）

路线可行性（动线/时刻/体力节奏）、来源可信度、图片与图注对应、关键页面视觉（桌面+手机）——交付前集中抽查这四项，其余一致性由机械闸承接。

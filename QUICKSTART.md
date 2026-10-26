# 快速制作（标准档 2-3 天路书）

正常制作只需以下五步，**无需阅读工具源码**；报错排查才按工具内注释定位。

## 五步流程

```bash
# 0. 开工（仅首次）：校验 SHA256 → 安全解压（中文名不损坏）→ 清点 → 复制工作副本
py tools/setup_pack.py 下载的包.zip --sha256 <发布页标注值>

# 1. 建数据骨架：生成可直接填写的 trip_data.json（标准 JSON，任何编辑器可改）
py tools/pipeline.py new 我的目的地 --days 3 --start 2026-11-06

# 2. 填数据（按 schema.md「字段速查」；实查规则见 sources_playbook.md）
#    ★ 填完先跑简表，过了再配图扩写——路线/费用/节奏问题在这一步暴露最便宜
py tools/pipeline.py outline pkg_work/trip_data.json

# 3. 配图（成品每日配图是硬要求；无 API key 用 Commons）
py tools/fetch_images.py search "洛阳 龙门石窟" --limit 5
py tools/fetch_images.py fetch "File:xxx.jpg" --note "图注文字"

# 4. 出成品（全链：数据闸→生成→导览图→成品检查含视觉）
py tools/pipeline.py full pkg_work/trip_data.json 成品.html --visual

# 5. 交付：checklist 全绿 + 事实来源清单三态齐全 + images/manifest 署名清单
```

## 并行查证（省时）

车次时刻、门票与开放、酒店区域、餐饮候选、天气天文**互不依赖，可并行查**。实查止损规则见 `sources_playbook.md`——一句话：单一事实尝试 ≤3 次或 ≤5 分钟，失败换可核实来源或降级为估算+标注，不把时间耗死在单点上。

## 计时

```bash
py tools/timer.py stage 需求加载   # 阶段切换时打点（需求/实查/填数/生成/复核）
py tools/timer.py list            # 查看自动记录（阶段起止与结果，替代手填）
```

## 人工复核集中点（自动化不替代）

路线可行性（动线/时刻/体力节奏）、来源可信度、图片与图注对应、关键页面视觉（桌面+手机）——交付前集中抽查这四项，其余一致性由机械闸承接。

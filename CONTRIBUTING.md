# 贡献指南

大约三十多个 fork 已经在用这套技能包。修一个真实翻车、补一句文档、报一条装不上的路径，都算贡献。下面是最短路径。

## English (short)

Bugs: open an [Issue](https://github.com/awangwang123/jianhao-travel-planner/issues) and use the bug template (which AI, which step, what you saw). City or feature wishes: [Discussions](https://github.com/awangwang123/jianhao-travel-planner/discussions), including the [city wish pool](https://github.com/awangwang123/jianhao-travel-planner/discussions/1). Pull requests: fork, branch from `main`, keep the diff small, do not summarize or rewrite `SKILL.md`, leave `tools/` and `assets/` in place, and run the offline tests below before you open the PR. [Releases](https://github.com/awangwang123/jianhao-travel-planner/releases) are the stable channel; `main` is development. The rest of this file is Chinese.

## 报错

装不上、生成报错、路书打不开，请到 [Issues](https://github.com/awangwang123/jianhao-travel-planner/issues/new/choose) 选 **「用不了 / 报错反馈」**。模板在 `.github/ISSUE_TEMPLATE/bug-report.md`。

请尽量写上这几样，维护者就不用来回追问：

- 卡在哪一步（安装、放置技能、触发、打开文件，或其他）
- 你用的 AI 助手（Claude Code，或 Kimi / DeepSeek 等，以及你是把文件夹放进工作区还是粘贴内容）
- 发生了什么，以及报错原文或截图
- 系统：Windows 还是 Mac（Linux 也请注明）

同一条报错已经有人提过，在原帖下面补充你的环境即可，不必再开一贴。

## 许愿和想法

- **想看某座城市的官方示例**：到 [旅行许愿池](https://github.com/awangwang123/jianhao-travel-planner/discussions/1) 留言或点赞。点赞最高的城市，下一份官方示例就是它。也可以用 Issue 模板 **「城市许愿」**（`.github/ISSUE_TEMPLATE/city-wish.md`）：城市、几天、同行的人、特别想去的点。
- **功能想法、用法疑问、不着急的讨论**：发到 [Discussions](https://github.com/awangwang123/jianhao-travel-planner/discussions)。还在商量、没有明确改法的，先讨论再提 PR，省得两边各写一版。

## 提 Pull Request

1. Fork 本仓库，从最新的 `main` 拉分支。分支名说清改什么，例如 `fix-checklist-meal-false-positive`。
2. 改动尽量小，一件事一个 PR。不要顺手重排无关文件。
3. 提交说明写三件事：改了什么、为什么改、你怎么验证的。
4. 推到你的 fork，然后向 `awangwang123/jianhao-travel-planner` 的 `main` 开 PR。

请不要改写 `main` 的历史，也不要移动已经发出的 tag 或 Release 附件。修复另开版本，由维护者发 Release。

## 改这个技能包时请守住的几条

工作流正文就是执行正文。这些约定是为了让别人的 AI 还能按同一套流程做路书：

- **不要把 `SKILL.md` 摘要、压缩或改写成精简入口。** 全文在，阶段 0 的提问和交付自查才在。条款要改就改条款本身；翻车实录的档案在 `HISTORY.md`，对外版本记录在 `CHANGELOG.md`。
- **保持 `tools/` 和 `assets/` 的目录结构。** 生成器、校验器和 HTML 基准骨架按这个相对位置互相引用。不要把脚本挪走或改掉 `jianhao-travel-planner` 这个文件夹名。
- **用户看的文档以中文为主**（README、教程、Issue 模板）。英文只做入口，见 `README.en.md`，不要把中文 README 整篇换成英文。
- **Python 3.8+ 标准库即可。** 不要为回归测试引入必须联网、要 API key、或要 Playwright 的依赖。视觉检查是可选项：`checklist.py --visual` 在没有 Playwright 时会 SKIP，不要把它当成 CI 的必过项。
- **样本用合成数据。** `fixtures/` 里不要放真实旅客的个人信息。

## 提交前跑这些

在仓库根目录：

```bash
python tools/test_route_semantics.py
python tools/test_abroad.py
python tools/test_abroad_semantics.py
python tools/test_synth_regression.py
```

四条都不访问网络，也不需要密钥。退出码 0 才算过。结果文本（`*_result.txt`）已被 `.gitignore` 忽略，不要把它们提交进来。

改了路书成品或 `assets/` 骨架时，再对成品跑机械检查（不必装 Playwright）：

```bash
python tools/checklist.py 你的路书.html
```

同一套命令会在推到 `main` 或打开 PR 时由 [`.github/workflows/ci.yml`](.github/workflows/ci.yml) 跑一遍。本地先过，CI 就只是复核。

## 稳定版走 Releases

[Releases](https://github.com/awangwang123/jianhao-travel-planner/releases) 是给使用者的稳定包。`main` 是开发态，两者可以暂时不一致。使用和对外宣传以 Releases 为准。已发布的标签和 zip 不再覆盖；要修就发下一个版本。

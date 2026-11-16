# Jianhao · Travel Roadbooks

[中文说明](README.md) · [Tutorial (Chinese)](TUTORIAL.md) · [Releases](https://github.com/awangwang123/jianhao-travel-planner/releases) · [Contributing](CONTRIBUTING.md)

**An AI skill pack that checks a trip online and writes a roadbook you can open on a phone or a computer.**

This is not a website you log into. It is a folder plus a workflow (`SKILL.md`). Any assistant that can read files and use the web can run it: ask where you leave from, the dates, and who is going; look the facts up; then hand you a roadbook you can actually follow.

The full Chinese guide, screenshots, and version notes are in [README.md](README.md).

## What you get

- A Markdown fact source, plus a **single HTML file**: a full copy that opens offline, and a slim copy you can deploy on your own server
- Checks with sources for the facts that matter (re-check the forecast before you leave)
- A real photo for each day and a hand-drawn route map
- Meals with a place, a dish, and a per-person price when that price was actually checked
- A food-intel card that keeps growing, city by city
- Public pages with no private residue
- `tools/checklist.py`, so you can see whether a draft passed the mechanical gates. A green checklist does not replace checking trains, tickets, and prices yourself

## Install in any AI agent

Python 3.8+ with the standard library is enough for the bundled tools. You do not need Claude Code, a paid API, or a platform login.

1. Download a [release zip](https://github.com/awangwang123/jianhao-travel-planner/releases), or clone this repo. Keep the folder name `jianhao-travel-planner`.
2. Put that folder where the agent can read it (its workspace, or `~/.claude/skills/` if you use Claude Code). The path that must exist is `jianhao-travel-planner/SKILL.md`.
3. Tell the agent:

> This is a travel-planning skill pack. Read **all** of SKILL.md before you do anything. Do **not** rewrite it into a summary or a short entry file — the full workflow is the procedure. Then run stage 0: ask me where I leave from, the date window, and who is traveling. Start only after I confirm.

4. Leave `assets/` (HTML skeletons) and `tools/` (checks and generators) where they are. Do not flatten or rename them.

If the agent starts writing without asking, send: "Follow SKILL.md stage 0 and ask me first (origin, dates, party). Do not assume a departure city."

Say the brief in one go when you can: origin, date window, how many people and how they are related, and anyone with special needs.

Step-by-step with self-checks: [TUTORIAL.md](TUTORIAL.md) (Chinese). One-page tool path: [QUICKSTART.md](QUICKSTART.md).

Stable zips are on [Releases](https://github.com/awangwang123/jianhao-travel-planner/releases). `main` is the development line and can differ from the latest release — **use Releases when you want the stable pack**.

## Tool mode

You can also skip the skill install and fill `trip_data.json` using [schema.md](schema.md):

```bash
python tools/pipeline.py full fixtures/demo/demo_full.json my-demo.html --visual
```

`--visual` checks desktop and phone screenshots and needs Playwright. Without it, that step is reported as SKIP. Offline regression (no network, no API keys):

```bash
python tools/test_route_semantics.py
python tools/test_abroad.py
python tools/test_abroad_semantics.py
python tools/test_synth_regression.py
```

## Links

- [Chinese README](README.md) — the full introduction
- [Changelog](CHANGELOG.md) — v1.0 through the current release
- [Contributing](CONTRIBUTING.md)
- [Issues](https://github.com/awangwang123/jianhao-travel-planner/issues) · [City wish pool](https://github.com/awangwang123/jianhao-travel-planner/discussions/1)
- License: [MIT](LICENSE)

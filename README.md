# MCP Radar 📡

**A directory of new and trending MCP (Model Context Protocol) servers, updated automatically every day.**

MCP Radar scans GitHub for newly created MCP server repositories, filters out the noise, ranks them by momentum (stars, forks, freshness), and publishes the results as structured JSON plus a human-readable weekly digest — all powered by GitHub Actions, with zero servers and zero cost.

## What you get

- [`data/data.json`](data/data.json) — curated list of MCP servers from the last 7 days: name, description, stars, forks, language, topics, and a momentum score. Machine-readable, ready to power a website or newsletter.
- [`data/digest.md`](data/digest.md) — the top 20 new MCP servers this week, in readable Markdown.

Both files are refreshed daily by a scheduled GitHub Actions workflow and committed back to this repo, so the git history doubles as a full archive of every snapshot.

## How it works

```
GitHub Search API ──> scripts/radar.py ──> data/*.json + digest.md
        ▲                                        │
        └──── GitHub Actions (daily cron) ───────┘  auto-commit
```

1. `scripts/radar.py` queries the GitHub Search API for repositories created in the last 7 days matching MCP-related queries (`topic:mcp-server`, `topic:model-context-protocol`, etc.).
2. Noise filtering: forks, archived repos, and repos below a minimum star threshold are dropped.
3. Each repo gets a momentum score: `stars / age_days * 10 + forks * 2` — young repos gaining stars fast rise to the top.
4. The workflow in `.github/workflows/radar.yml` runs daily and commits updated data back using the built-in `GITHUB_TOKEN` (no secrets to configure).

## Run it locally

No dependencies beyond the Python 3 standard library:

```bash
python scripts/radar.py
```

Works without a token (rate-limited); set `GITHUB_TOKEN` for higher API limits.

## Repository layout

```
scripts/   data pipeline (radar.py) + static site generator (build_site.py)
data/      generated data — data.json (weekly window), all.json (cumulative), digest.md
site/      the website: index, full directory, per-server pages, sitemap
```

## One-time setup (for forks)

For the workflow to push data back to the repo, enable write access for Actions:
**Settings → Actions → General → Workflow permissions → Read and write permissions.**

## Roadmap

- [x] Daily automated data pipeline
- [x] Website — live at [mcp.liqiwa.com](https://mcp.liqiwa.com), auto-deployed on every data update
- [x] Cumulative catalog + per-server detail pages + sitemap
- [ ] Weekly newsletter from the digest
- [ ] Historical trend charts per server

## License

[MIT](LICENSE)

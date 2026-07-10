#!/usr/bin/env python3
"""
MCP Radar - v0.2
抓取最近N天新建的 MCP server 仓库，过滤噪音，按热度评分，输出JSON数据 + Markdown digest。
设计目标：可直接放进 GitHub Actions 定时运行（无需服务器、无需token也能跑，加token后限额更高）。

路径约定：脚本放在 scripts/，输出写到 data/（相对仓库根目录，与运行时cwd无关）。
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DAYS = 7          # 回看天数
MIN_STARS = 3     # 噪音过滤线：低于此star数不收录（一周内3星说明至少有真人关注）
PER_PAGE = 50
TOKEN = os.environ.get("GITHUB_TOKEN", "")  # Actions里自动注入，本地可为空

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CATALOG = DATA_DIR / "all.json"

QUERIES = [
    'mcp server in:name,description,topics',
    'topic:mcp-server',
    'topic:model-context-protocol',
]

MAX_PAGES = 3 if TOKEN else 1  # 有token时每个查询翻3页，扩大进货量

def gh_search(query: str, since: str, page: int = 1):
    url = ("https://api.github.com/search/repositories"
           f"?q={urllib.parse.quote(query + f' created:>{since}')}"
           f"&sort=stars&order=desc&per_page={PER_PAGE}&page={page}")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def score(repo: dict) -> float:
    """简单热度分：star权重最高，fork次之，越新越加分"""
    created = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
    age_days = max((datetime.now(timezone.utc) - created).days, 1)
    return repo["stargazers_count"] / age_days * 10 + repo["forks_count"] * 2

def update_catalog(items):
    """把本次扫描结果并入累积总目录 data/all.json（只增不减）。
    每个服务器记录首次/最近上榜日期和star变化历史，是详情页和SEO的数据源。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    catalog = {}
    if CATALOG.exists():
        catalog = {s["name"]: s for s in json.loads(CATALOG.read_text())["servers"]}
    for it in items:
        prev = catalog.get(it["name"])
        entry = dict(it)
        entry["first_seen"] = prev["first_seen"] if prev else today
        entry["last_seen"] = today
        hist = prev.get("stars_history", []) if prev else []
        if not hist or hist[-1]["s"] != it["stars"]:
            hist = hist + [{"d": today, "s": it["stars"]}]
        entry["stars_history"] = hist[-60:]  # 最多留60个变化点，防文件膨胀
        catalog[it["name"]] = entry
    servers = sorted(catalog.values(), key=lambda s: s["stars"], reverse=True)
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump({"updated_at": today, "count": len(servers), "servers": servers},
                  f, ensure_ascii=False, indent=1)
    return len(servers)

def main():
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    seen, items = set(), []
    total_raw = 0

    for q in QUERIES:
      for page in range(1, MAX_PAGES + 1):
        try:
            data = gh_search(q, since, page)
        except Exception as e:
            print(f"[warn] query failed: {q} (page {page}): {e}")
            break
        total_raw = max(total_raw, data.get("total_count", 0))
        page_items = data.get("items", [])
        for repo in page_items:
            if repo["full_name"] in seen:
                continue
            seen.add(repo["full_name"])
            if repo["stargazers_count"] < MIN_STARS:
                continue
            if repo["fork"] or repo["archived"]:
                continue
            items.append({
                "name": repo["full_name"],
                "url": repo["html_url"],
                "description": (repo["description"] or "")[:200],
                "stars": repo["stargazers_count"],
                "forks": repo["forks_count"],
                "language": repo["language"],
                "topics": repo.get("topics", []),
                "created_at": repo["created_at"][:10],
                "homepage": repo["homepage"] or "",
                "score": round(score(repo), 1),
            })
        time.sleep(2)  # 无token时search API限额 10次/分钟，礼貌间隔
        if len(page_items) < PER_PAGE:  # 结果不满一页，后面没有了
            break

    items.sort(key=lambda x: x["score"], reverse=True)

    # 保护：如果所有查询都失败（网络/限流），不要用空结果覆盖已有数据，
    # 直接报错退出——Actions会显示为失败，而不是悄悄commit一份空数据。
    if total_raw == 0 and not items:
        raise SystemExit("[error] all queries returned nothing; keeping existing data untouched")

    DATA_DIR.mkdir(exist_ok=True)

    # 输出1：结构化数据（未来网站的数据源，commit回仓库即可）
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": DAYS,
        "raw_matches_this_week": total_raw,
        "curated_count": len(items),
        "items": items,
    }
    with open(DATA_DIR / "data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 输出1.5：并入累积总目录 data/all.json（详情页和全量目录的数据源）
    catalog_size = update_catalog(items)

    # 输出2：人类可读的周报digest（未来newsletter的底稿）
    lines = [f"# MCP Radar Weekly — {datetime.now():%Y-%m-%d}",
             f"\n本周GitHub新增 **{total_raw}** 个MCP相关仓库，过滤后值得关注的 **{len(items)}** 个：\n"]
    for i, it in enumerate(items[:20], 1):
        lines.append(f"{i}. **[{it['name']}]({it['url']})** ⭐{it['stars']} "
                     f"({it['language'] or 'n/a'}) — {it['description']}")
    with open(DATA_DIR / "digest.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"raw={total_raw}, curated={len(items)}, catalog={catalog_size}, "
          f"top1={items[0]['name'] if items else 'none'}")

if __name__ == "__main__":
    main()

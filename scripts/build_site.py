#!/usr/bin/env python3
"""
MCP Radar - 静态站点生成器
读取 data/all.json（累积总目录），生成：
  site/s/<slug>.html       每个服务器一张详情页（SEO落地页，真实HTML）
  site/lang/<slug>.html    按语言聚合页（"Python MCP servers" 这类搜索词的落地页）
  site/topic/<slug>.html   按主题聚合页（≥3个服务器的topic才生成，避免薄页面）
  site/all.html            全量目录页
  site/feed.xml            RSS订阅源（最新上榜的服务器）
  site/badge.svg           作者徽章（贴进README即是反向链接）
  site/sitemap.xml         站点地图
  site/robots.txt
在 radar.py 之后运行（GitHub Actions 里同一个 job 的下一步）。
"""
import html
import json
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SITE = ROOT / "site"
BASE = "https://mcp.liqiwa.com"

MIN_TOPIC_SERVERS = 3   # topic聚合页的最低服务器数
MIN_LANG_SERVERS = 2    # 语言聚合页的最低服务器数
FEED_SIZE = 30

LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5",
    "Go": "#00ADD8", "Rust": "#dea584", "Java": "#b07219", "Kotlin": "#A97BFF",
    "Swift": "#F05138", "C#": "#178600", "C++": "#f34b7d", "Ruby": "#701516",
    "PHP": "#4F5D95", "HTML": "#e34c26",
}
LANG_SLUGS = {"C#": "csharp", "C++": "cpp", "F#": "fsharp"}

CSS = """
:root{--bg:#0b0f14;--bg-card:#121820;--bg-card-hover:#182130;--border:#1e2936;
--text:#dbe4ee;--text-dim:#7d8fa3;--accent:#3ddc84;--accent-dim:rgba(61,220,132,.12)}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);line-height:1.55;min-height:100vh;
font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:inherit}.wrap{max-width:880px;margin:0 auto;padding:0 20px}
header.top{padding:26px 0 8px;display:flex;align-items:center;gap:10px}
header.top a{text-decoration:none;font-weight:600;font-size:18px}
header.top .radar{color:var(--accent)}
header.top nav{margin-left:auto;display:flex;gap:16px;font-size:14px}
header.top nav a{color:var(--text-dim)}header.top nav a:hover{color:var(--text)}
h1{font-size:26px;letter-spacing:-.5px;margin:26px 0 6px;word-break:break-all}
h1 .owner{color:var(--text-dim);font-weight:400}
.sub{color:var(--text-dim);font-size:15px;margin-bottom:18px}
.sub a{color:var(--accent);text-decoration:none}
.chips{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0;font-size:13.5px;color:var(--text-dim)}
.chip{background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:7px 12px;text-decoration:none}
.chip b{color:var(--text)}
a.chip:hover{border-color:var(--accent)}
.lang-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;background:var(--lang,#8b949e)}
.btn{display:inline-block;background:var(--accent);color:#08130c;font-weight:600;text-decoration:none;
border-radius:8px;padding:10px 18px;margin:10px 12px 22px 0;font-size:14.5px}
.btn.ghost{background:transparent;color:var(--accent);border:1px solid var(--accent)}
.topics{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 20px}
.topic{background:rgba(125,143,163,.1);border-radius:999px;padding:2px 10px;font-size:12px;
color:var(--text-dim);text-decoration:none}
a.topic:hover{color:var(--accent)}
h2{font-size:17px;margin:26px 0 12px}
.card{display:block;text-decoration:none;background:var(--bg-card);border:1px solid var(--border);
border-radius:12px;padding:14px 16px;margin-bottom:10px;transition:background .12s,border-color .12s}
.card:hover{background:var(--bg-card-hover);border-color:#2b3b4f}
.card .name{font-weight:600;font-size:15px;word-break:break-all}
.card .name .owner{color:var(--text-dim);font-weight:400}
.card p{color:var(--text-dim);font-size:13.5px;margin-top:4px}
.card .meta{display:flex;gap:12px;margin-top:8px;font-size:12.5px;color:var(--text-dim)}
.controls{margin:18px 0}
.controls input{width:100%;background:var(--bg-card);border:1px solid var(--border);border-radius:8px;
color:var(--text);padding:9px 12px;font-size:14px;outline:none}
.controls input:focus{border-color:var(--accent)}
pre.snippet{background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:12px 14px;
font-size:12.5px;overflow-x:auto;color:var(--text-dim);margin:8px 0 4px;font-family:ui-monospace,Menlo,monospace}
.copybtn{background:transparent;border:1px solid var(--border);border-radius:6px;color:var(--text-dim);
padding:4px 12px;font-size:12px;cursor:pointer;margin-bottom:18px}
.copybtn:hover{border-color:var(--accent);color:var(--accent)}
.hublinks{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 6px}
footer{margin:48px 0 40px;padding-top:24px;border-top:1px solid var(--border);color:var(--text-dim);font-size:13px}
footer a{color:var(--accent);text-decoration:none}footer a:hover{text-decoration:underline}
"""

def esc(s):
    return html.escape(str(s or ""), quote=True)

def slug(full_name):
    return re.sub(r"[^A-Za-z0-9_.-]", "-", full_name.replace("/", "--"))

def lang_slug(lang):
    return LANG_SLUGS.get(lang) or re.sub(r"[^a-z0-9]+", "-", lang.lower()).strip("-")

def shell(title, desc, canonical, body, jsonld=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<link rel="alternate" type="application/rss+xml" title="MCP Radar — new MCP servers" href="{BASE}/feed.xml">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📡</text></svg>">
<style>{CSS}</style>
{jsonld}
</head>
<body>
<div class="wrap">
<header class="top">
  <a href="/">📡 MCP <span class="radar">Radar</span></a>
  <nav><a href="/">This week</a><a href="/all.html">All servers</a>
  <a href="/feed.xml">RSS</a>
  <a href="https://github.com/liqiwa/mcp-radar" rel="noopener">Data</a></nav>
</header>
{body}
<footer>
  Tracked by <a href="/">MCP Radar</a> — new &amp; trending Model Context Protocol servers, updated daily
  · <a href="/feed.xml">RSS</a>
  · <a href="https://github.com/liqiwa/mcp-radar" rel="noopener">open-source pipeline</a>
</footer>
</div>
</body>
</html>
"""

def related_servers(server, servers, n=6):
    mine = set(server.get("topics", []))
    scored = []
    for other in servers:
        if other["name"] == server["name"]:
            continue
        shared = len(mine & set(other.get("topics", [])))
        same_lang = 1 if other.get("language") and other.get("language") == server.get("language") else 0
        if shared or same_lang:
            scored.append((shared * 10 + same_lang, other["stars"], other))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [t[2] for t in scored[:n]]

def mini_card(s):
    owner, repo = s["name"].split("/", 1)
    desc = f"<p>{esc(s['description'])}</p>" if s.get("description") else ""
    return f"""<a class="card" href="/s/{slug(s['name'])}.html">
  <span class="name"><span class="owner">{esc(owner)}/</span>{esc(repo)}</span>
  {desc}
  <span class="meta"><span>⭐ {s['stars']}</span><span>{esc(s.get('language') or '')}</span></span>
</a>"""

def detail_page(s, servers, lang_hubs, topic_hubs):
    owner, repo = s["name"].split("/", 1)
    desc = s.get("description") or f"{s['name']} is an MCP (Model Context Protocol) server."
    meta_desc = f"{desc[:150]} — stats, momentum and related MCP servers on MCP Radar."
    page_url = f"{BASE}/s/{slug(s['name'])}.html"
    lang = s.get("language")
    lang_color = LANG_COLORS.get(lang, "#8b949e")
    hist = s.get("stars_history", [])
    growth = ""
    if len(hist) >= 2:
        growth = f"""<div class="chip">star trend <b>{hist[0]['s']} → {hist[-1]['s']}</b> since {esc(hist[0]['d'])}</div>"""
    lang_chip = ""
    if lang:
        dot = f'<span class="lang-dot" style="--lang:{lang_color}"></span>'
        if lang in lang_hubs:
            lang_chip = f'<a class="chip" href="/lang/{lang_slug(lang)}.html">{dot}<b>{esc(lang)}</b></a>'
        else:
            lang_chip = f'<div class="chip">{dot}<b>{esc(lang)}</b></div>'
    topics = "".join(
        (f'<a class="topic" href="/topic/{esc(t)}.html">{esc(t)}</a>' if t in topic_hubs
         else f'<span class="topic">{esc(t)}</span>')
        for t in s.get("topics", []))
    related = related_servers(s, servers)
    related_html = ""
    if related:
        related_html = "<h2>Related MCP servers</h2>" + "".join(mini_card(r) for r in related)
    homepage = ""
    if s.get("homepage"):
        homepage = f'<a class="btn ghost" href="{esc(s["homepage"])}" rel="noopener nofollow">Homepage ↗</a>'
    badge_md = f"[![On MCP Radar]({BASE}/badge.svg)]({page_url})"
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "SoftwareSourceCode",
        "name": s["name"], "description": desc, "codeRepository": s["url"],
        "programmingLanguage": lang or "Unknown", "url": page_url,
        "dateCreated": s.get("created_at", ""),
    }, ensure_ascii=False)
    body = f"""
<h1><span class="owner">{esc(owner)}/</span>{esc(repo)}</h1>
<p class="sub">{esc(desc)}</p>
<div class="chips">
  <div class="chip">⭐ <b>{s['stars']}</b> stars</div>
  <div class="chip">⑂ <b>{s['forks']}</b> forks</div>
  {lang_chip}
  <div class="chip">momentum <b>▲ {s['score']}</b></div>
  <div class="chip">created <b>{esc(s['created_at'])}</b></div>
  <div class="chip">on radar since <b>{esc(s['first_seen'])}</b></div>
  {growth}
</div>
{f'<div class="topics">{topics}</div>' if topics else ''}
<a class="btn" href="{esc(s['url'])}" rel="noopener">View on GitHub ↗</a>{homepage}
<h2>Maintaining this server?</h2>
<p class="sub">Add the radar badge to your README — it shows your project was picked up by MCP Radar and links to this page:</p>
<pre class="snippet">{esc(badge_md)}</pre>
<button class="copybtn" onclick="navigator.clipboard.writeText(this.previousElementSibling.textContent);this.textContent='Copied ✓'">Copy markdown</button>
{related_html}
"""
    return shell(f"{s['name']} — MCP Server | MCP Radar", meta_desc, page_url, body,
                 f'<script type="application/ld+json">{jsonld}</script>')

def hub_page(kind, key, servers_in, total_title, canonical):
    """kind: 'lang' | 'topic'"""
    cards = "".join(mini_card(s) for s in servers_in)
    n = len(servers_in)
    if kind == "lang":
        h1 = f"{key} MCP Servers"
        sub = (f"<b>{n}</b> Model Context Protocol servers written in {esc(key)}, "
               f"auto-discovered from GitHub and ranked by stars. Updated daily.")
        desc = (f"Browse {n} MCP (Model Context Protocol) servers written in {key}. "
                "Auto-curated from GitHub, updated daily by MCP Radar.")
    else:
        h1 = f"MCP servers for {key}"
        sub = (f"<b>{n}</b> Model Context Protocol servers tagged <i>{esc(key)}</i>, "
               f"ranked by stars. Updated daily.")
        desc = (f"Discover {n} MCP (Model Context Protocol) servers for {key}. "
                "Auto-curated from GitHub, updated daily by MCP Radar.")
    body = f"""
<h1>{esc(h1)}</h1>
<p class="sub">{sub} <a href="/all.html">Browse all servers →</a></p>
<main>{cards}</main>
"""
    return shell(total_title, desc, canonical, body)

def hub_links_block(lang_hubs, topic_hubs):
    langs = "".join(
        f'<a class="chip" href="/lang/{lang_slug(l)}.html">{esc(l)} <b>{n}</b></a>'
        for l, n in sorted(lang_hubs.items(), key=lambda kv: -kv[1]))
    topics = "".join(
        f'<a class="topic" href="/topic/{esc(t)}.html">{esc(t)} ({n})</a>'
        for t, n in sorted(topic_hubs.items(), key=lambda kv: -kv[1])[:40])
    return f"""
<h2>Browse by language</h2>
<div class="hublinks">{langs}</div>
<h2>Browse by topic</h2>
<div class="topics">{topics}</div>
"""

def all_page(servers, lang_hubs, topic_hubs):
    cards = "".join(mini_card(s) for s in servers)
    body = f"""
<h1>All MCP servers on the radar</h1>
<p class="sub"><b>{len(servers)}</b> Model Context Protocol servers discovered and tracked since launch,
sorted by stars. Grows every day — <a href="/">see this week's trending</a>.</p>
<div class="controls"><input type="search" id="q" placeholder="Filter servers…"></div>
<main id="list">{cards}</main>
{hub_links_block(lang_hubs, topic_hubs)}
<script>
document.getElementById("q").addEventListener("input", function() {{
  var q = this.value.trim().toLowerCase();
  document.querySelectorAll("#list .card").forEach(function(c) {{
    c.style.display = c.textContent.toLowerCase().includes(q) ? "" : "none";
  }});
}});
</script>
"""
    return shell(f"All MCP Servers — Complete Directory ({len(servers)}) | MCP Radar",
                 f"Browse all {len(servers)} MCP (Model Context Protocol) servers tracked by MCP Radar. "
                 "Auto-discovered from GitHub, updated daily.",
                 f"{BASE}/all.html", body)

def rss_feed(servers):
    """最新上榜的服务器（按first_seen倒序），给订阅者的'今天有什么新东西'"""
    newest = sorted(servers, key=lambda s: (s["first_seen"], s["stars"]), reverse=True)[:FEED_SIZE]
    items = []
    for s in newest:
        pub = format_datetime(datetime.strptime(s["first_seen"], "%Y-%m-%d").replace(tzinfo=timezone.utc))
        link = f"{BASE}/s/{slug(s['name'])}.html"
        desc = esc(f"{s.get('description') or ''} — ⭐{s['stars']}, {s.get('language') or 'n/a'}")
        items.append(
            f"<item><title>{esc(s['name'])}</title><link>{link}</link>"
            f"<guid isPermaLink=\"true\">{link}</guid><pubDate>{pub}</pubDate>"
            f"<description>{desc}</description></item>")
    joined = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>MCP Radar — new MCP servers</title>
<link>{BASE}</link>
<description>New and trending Model Context Protocol servers, auto-discovered from GitHub daily.</description>
{joined}
</channel></rss>
"""

BADGE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="126" height="20" role="img" aria-label="on MCP Radar">
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<clipPath id="r"><rect width="126" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)"><rect width="45" height="20" fill="#0b0f14"/><rect x="45" width="81" height="20" fill="#3ddc84"/><rect width="126" height="20" fill="url(#s)"/></g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="110" text-rendering="geometricPrecision">
<text x="235" y="140" transform="scale(.1)" fill="#fff">📡 on</text>
<text x="845" y="140" transform="scale(.1)" fill="#08130c" font-weight="bold">MCP Radar</text>
</g></svg>
"""

def main():
    catalog = json.loads((DATA_DIR / "all.json").read_text())
    servers = catalog["servers"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 统计聚合页
    lang_count, topic_count = {}, {}
    for s in servers:
        if s.get("language"):
            lang_count[s["language"]] = lang_count.get(s["language"], 0) + 1
        for t in s.get("topics", []):
            topic_count[t] = topic_count.get(t, 0) + 1
    lang_hubs = {l: n for l, n in lang_count.items() if n >= MIN_LANG_SERVERS}
    topic_hubs = {t: n for t, n in topic_count.items() if n >= MIN_TOPIC_SERVERS}

    # 详情页
    pages_dir = SITE / "s"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for s in servers:
        (pages_dir / f"{slug(s['name'])}.html").write_text(
            detail_page(s, servers, lang_hubs, topic_hubs), encoding="utf-8")

    # 聚合页
    lang_dir = SITE / "lang"
    lang_dir.mkdir(exist_ok=True)
    for lang, n in lang_hubs.items():
        subset = [s for s in servers if s.get("language") == lang]
        (lang_dir / f"{lang_slug(lang)}.html").write_text(
            hub_page("lang", lang, subset,
                     f"{lang} MCP Servers — {n} tracked | MCP Radar",
                     f"{BASE}/lang/{lang_slug(lang)}.html"), encoding="utf-8")
    topic_dir = SITE / "topic"
    topic_dir.mkdir(exist_ok=True)
    for topic, n in topic_hubs.items():
        subset = [s for s in servers if topic in s.get("topics", [])]
        (topic_dir / f"{topic}.html").write_text(
            hub_page("topic", topic, subset,
                     f"MCP servers for {topic} — {n} tracked | MCP Radar",
                     f"{BASE}/topic/{topic}.html"), encoding="utf-8")

    # 目录页、RSS、徽章
    (SITE / "all.html").write_text(all_page(servers, lang_hubs, topic_hubs), encoding="utf-8")
    (SITE / "feed.xml").write_text(rss_feed(servers), encoding="utf-8")
    (SITE / "badge.svg").write_text(BADGE_SVG, encoding="utf-8")

    # sitemap + robots
    urls = ([f"{BASE}/", f"{BASE}/all.html"]
            + [f"{BASE}/lang/{lang_slug(l)}.html" for l in lang_hubs]
            + [f"{BASE}/topic/{t}.html" for t in topic_hubs]
            + [f"{BASE}/s/{slug(s['name'])}.html" for s in servers])
    entries = "\n".join(
        f"  <url><loc>{esc(u)}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n',
        encoding="utf-8")
    (SITE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")

    print(f"generated {len(servers)} detail pages, {len(lang_hubs)} language hubs, "
          f"{len(topic_hubs)} topic hubs, all.html, feed.xml, badge.svg, sitemap ({len(urls)} urls)")

if __name__ == "__main__":
    main()

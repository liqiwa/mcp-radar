#!/usr/bin/env python3
"""
MCP Radar - 周报发送
每周一运行：取上一个完整周的快照（data/weekly/YYYY-Www.json），
渲染成 Markdown 邮件，通过 Buttondown API 群发给订阅者。

环境：
    BUTTONDOWN_API_KEY  Buttondown 的 API Key（仓库 Actions secret 注入）。
                        没配置时打印提示并以 0 退出——不让定时任务在
                        newsletter 还没开通时天天报红。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEEKLY_DIR = ROOT / "data" / "weekly"
BASE = "https://mcp.liqiwa.com"
API = "https://api.buttondown.com/v1/emails"

def slug(full_name):
    import re
    return re.sub(r"[^A-Za-z0-9_.-]", "-", full_name.replace("/", "--"))

def build_body(w):
    lines = [
        f"GitHub saw **{w['raw_matches']:,}** new MCP-related repositories in week {w['week']}. "
        f"These are the {len(w['items'])} that mattered, ranked by momentum:",
        "",
    ]
    for i, it in enumerate(w["items"], 1):
        detail = f"{BASE}/s/{slug(it['name'])}.html"
        desc = (it["description"] or "").strip()
        lang = it["language"] or "n/a"
        lines.append(f"**{i}. [{it['name']}]({detail})** ⭐{it['stars']} · {lang}")
        if desc:
            lines.append(f"   {desc}")
        lines.append("")
    lines += [
        "---",
        f"[Browse the full directory]({BASE}/all.html) · "
        f"[Weekly archive]({BASE}/weekly/) · "
        f"[How ranking works]({BASE}/about.html)",
        "",
        "You're receiving this because you subscribed at mcp.liqiwa.com. "
        "Unsubscribe any time with the link below.",
    ]
    return "\n".join(lines)

def main() -> int:
    key = os.environ.get("BUTTONDOWN_API_KEY", "").strip()
    if not key:
        print("BUTTONDOWN_API_KEY not set; skipping newsletter send.")
        return 0

    # 上一个完整周：今天（周一）减7天所在的ISO周
    prev = datetime.now(timezone.utc) - timedelta(days=7)
    iso = prev.isocalendar()
    week_id = f"{iso[0]}-W{iso[1]:02d}"
    path = WEEKLY_DIR / f"{week_id}.json"
    if not path.exists():
        print(f"no snapshot for {week_id}; nothing to send.")
        return 0
    w = json.loads(path.read_text())
    if not w.get("items"):
        print(f"{week_id} snapshot empty; nothing to send.")
        return 0

    payload = json.dumps({
        "subject": f"MCP Radar Weekly — {len(w['items'])} rising MCP servers ({w['week']})",
        "body": build_body(w),
        "status": "about_to_send",   # 直接群发；改成 "draft" 可先人工过目
    }).encode("utf-8")
    req = urllib.request.Request(API, data=payload, method="POST", headers={
        "Authorization": f"Token {key}",
        "Content-Type": "application/json",
        # Buttondown要求群发(status=about_to_send)必须带这个确认头，
        # 否则返回400 sending_requires_confirmation。
        "X-Buttondown-Live-Dangerously": "true",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
            print(f"sent: {resp.get('id', 'ok')} — {week_id}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"[error] Buttondown API {e.code}: {body}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""issues.json から共有用の静的ページを生成する。

出力:
  index.html            … 最新号＋バックナンバー一覧（サイトのトップ）
  i/<YYYY-MM-DD>/index.html … 号ごとのページ（アプリの共有リンク先。記事は #s1 #s2 #s3 でアンカー）

GitHub Actions（.github/workflows/build-site.yml）が issues.json の更新のたびに実行してコミットする。
手元で試すときは  python3 tools/build_site.py  をリポジトリ直下で実行。
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://shonakamura345-creator.github.io/kenchiku3min-feed"
APP_STORE_URL = "https://apps.apple.com/jp/app/id6800172328"
SITE_NAME = "建築3分ニュース"
OG_IMAGE = f"{BASE_URL}/assets/og.jpg"

CSS = """
:root{--paper:#FAF9F5;--ink:#2D2A26;--orange:#F97316;--orange-bg:#FFF7ED;--line:rgba(45,42,38,.10);--sub:rgba(45,42,38,.58);--blue:#3B82F6}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Hiragino Kaku Gothic ProN","Noto Sans JP",sans-serif;line-height:1.85;font-size:16px}
a{color:#EA580C}
.wrap{max-width:680px;margin:0 auto;padding:20px 18px 64px}
header.site{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:6px 0 18px}
header.site .brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink)}
header.site .badge{background:var(--ink);color:#fff;border-radius:8px;padding:2px 8px;font-weight:800;font-size:.8rem;letter-spacing:.02em;white-space:nowrap}
header.site .badge b{background:var(--orange);border-radius:5px;padding:0 5px;margin-left:4px}
header.site .name{font-weight:800;font-size:1rem;white-space:nowrap}
.cta{display:inline-block;background:var(--orange);color:#fff;text-decoration:none;font-weight:700;border-radius:999px;padding:8px 16px;font-size:.9rem;white-space:nowrap}
.cta.small{padding:6px 12px;font-size:.82rem}
.issue-head{margin:4px 0 18px}
.issue-head .kicker{font-size:.72rem;letter-spacing:.18em;color:var(--sub);font-weight:700;text-transform:uppercase}
.issue-head h1{font-size:1.6rem;line-height:1.35;margin:4px 0 6px;font-weight:800}
.issue-head .meta{color:var(--sub);font-size:.9rem}
.toc{background:#fff;border:1px solid var(--line);border-radius:18px;padding:14px 16px;margin:0 0 22px}
.toc .kicker{font-size:.7rem;letter-spacing:.18em;color:var(--sub);font-weight:700;margin-bottom:6px}
.toc ol{margin:0;padding-left:0;list-style:none}
.toc li{display:flex;gap:10px;padding:8px 0;border-top:1px solid var(--line);align-items:flex-start}
.toc li:first-child{border-top:0}
.toc .num{flex:0 0 26px;height:26px;border-radius:50%;background:var(--orange);color:#fff;font-weight:800;font-size:.8rem;display:flex;align-items:center;justify-content:center;margin-top:3px}
.toc li:nth-child(2) .num{background:var(--blue)}
.toc li:nth-child(3) .num{background:#10B981}
.toc a{color:var(--ink);text-decoration:none;font-weight:700;line-height:1.5}
article{background:#fff;border:1px solid var(--line);border-radius:22px;padding:22px 20px;margin:0 0 22px;scroll-margin-top:12px}
article .src{font-size:.72rem;letter-spacing:.16em;color:var(--sub);font-weight:700;text-transform:uppercase}
article h2{font-size:1.35rem;line-height:1.4;margin:6px 0 8px;font-weight:800}
article .summary{color:var(--sub);margin:0 0 14px;font-size:.95rem}
article p{margin:0 0 14px}
.sec-label{font-size:.72rem;letter-spacing:.16em;color:var(--sub);font-weight:700;margin:18px 0 6px;text-transform:uppercase}
.briefing{margin:0 0 6px;padding-left:1.2em}
.briefing li{margin:0 0 6px;font-size:.95rem}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 4px}
.chips a{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:.82rem;text-decoration:none;color:var(--ink);background:var(--paper)}
.chips a::before{content:"↗ ";color:var(--sub)}
.commentary{background:var(--orange-bg);border-left:5px solid var(--orange);border-radius:16px;padding:16px 18px;margin:18px 0 0}
.commentary .label{color:var(--orange);font-weight:800;font-size:.85rem;margin-bottom:6px}
.commentary p{margin:0;font-size:.97rem}
.sho{background:#fff;border:1px solid var(--line);border-left:5px solid var(--orange);border-radius:16px;padding:16px 18px;margin:12px 0 0}
.sho .label{font-weight:800;font-size:.85rem;margin-bottom:6px}
.sho .label b{background:var(--orange);color:#fff;border-radius:999px;padding:1px 8px;font-size:.7rem;margin-left:6px}
.hojosen{margin:14px 0 0}
.hojosen .item{background:var(--paper);border-radius:14px;padding:12px 14px;margin:0 0 8px}
.hojosen .item b{display:block;margin-bottom:2px}
.hojosen .item p{margin:0;font-size:.93rem}
.rel{display:inline-block;margin-top:14px;font-size:.75rem;color:var(--sub);border:1px solid var(--line);border-radius:999px;padding:2px 10px}
.appbox{background:var(--ink);color:#fff;border-radius:22px;padding:22px 20px;margin:8px 0 22px;text-align:center}
.appbox p{margin:0 0 12px;font-size:.95rem;opacity:.9}
.appbox .cta{background:var(--orange)}
.list a.row{display:block;background:#fff;border:1px solid var(--line);border-radius:18px;padding:14px 16px;margin:0 0 10px;text-decoration:none;color:var(--ink)}
.list .date{font-weight:800;font-size:.95rem}
.list .date span{color:var(--sub);font-weight:600;font-size:.8rem;margin-left:8px}
.list ul{margin:6px 0 0;padding-left:1.2em;font-size:.9rem;color:rgba(45,42,38,.8)}
.list li{margin:2px 0}
nav.pn{display:flex;justify-content:space-between;gap:12px;margin:0 0 18px;font-size:.9rem}
nav.pn a{text-decoration:none;color:var(--ink);background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 14px}
footer{color:var(--sub);font-size:.8rem;margin-top:28px;line-height:1.7}
footer a{color:var(--sub)}
@media (prefers-color-scheme: dark){
  :root{--paper:#1C1A18;--ink:#F5F2EE;--orange-bg:#3A2A1A;--line:rgba(245,242,238,.12);--sub:rgba(245,242,238,.6)}
  article,.toc,.list a.row,nav.pn a,.sho{background:#262320}
  .hojosen .item,.chips a{background:#1C1A18}
  a{color:#FDBA74}
}
"""

WEEKDAYS = "月火水木金土日"


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def jp_date(date: str, weekday: str = "") -> str:
    y, m, d = date.split("-")
    wd = f"（{weekday}）" if weekday else ""
    return f"{int(m)}月{int(d)}日{wd}"


def issue_url(date: str) -> str:
    return f"{BASE_URL}/i/{date}/"


def head(title: str, desc: str, url: str, extra_css: str = "") -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(url)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:image" content="{OG_IMAGE}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{OG_IMAGE}">
<meta name="apple-itunes-app" content="app-id=6800172328">
<link rel="icon" href="{BASE_URL}/assets/favicon.png">
<link rel="apple-touch-icon" href="{BASE_URL}/assets/apple-touch-icon.png">
<style>{CSS}{extra_css}</style>
</head>
<body><div class="wrap">
<header class="site">
  <a class="brand" href="{BASE_URL}/"><span class="badge">建築<b>NEWS</b></span><span class="name">{SITE_NAME}</span></a>
  <a class="cta small" href="{APP_STORE_URL}">アプリで読む</a>
</header>
"""


FOOTER = f"""
<footer>
  <p>「{SITE_NAME}」は、毎朝3分で読める建築ニュースのiPhoneアプリです。記事は出典を要約・再構成したもので、詳細は各出典をご覧ください。解説は「Sho建築士AI」が生成しています。</p>
  <p><a href="{APP_STORE_URL}">App Store</a> ・ <a href="https://kenchiku3min.web.app/">サポート</a> ・ <a href="https://kenchiku3min.web.app/privacy.html">プライバシーポリシー</a><br>© 2026 Sho Nakamura / 株式会社ATAP Works</p>
</footer>
</div></body></html>
"""


def render_story(story: dict) -> str:
    n = story.get("number", 0)
    parts = [f'<article id="s{n}">']
    parts.append(f'<div class="src">{esc(story.get("sourceName", ""))}</div>')
    parts.append(f"<h2>{esc(story.get('title', ''))}</h2>")
    if story.get("summary"):
        parts.append(f'<p class="summary">{esc(story["summary"])}</p>')
    for p in story.get("body") or []:
        parts.append(f"<p>{esc(p)}</p>")

    briefing = story.get("briefing") or []
    if briefing:
        parts.append('<div class="sec-label">Briefing</div><ul class="briefing">')
        parts.extend(f"<li>{esc(b)}</li>" for b in briefing)
        parts.append("</ul>")

    sources = story.get("sources") or []
    if not sources and story.get("sourceURL"):
        sources = [{"name": story.get("sourceName", "出典"), "url": story["sourceURL"]}]
    if sources:
        parts.append('<div class="sec-label">From</div><div class="chips">')
        for s in sources:
            parts.append(f'<a href="{esc(s.get("url", ""))}" target="_blank" rel="noopener">{esc(s.get("name", ""))}</a>')
        parts.append("</div>")

    if story.get("commentary"):
        parts.append(
            '<div class="commentary"><div class="label">💡 ニュース解説 by Sho建築士AI</div>'
            f'<p>{esc(story["commentary"])}</p></div>'
        )
    sho = (story.get("shoComment") or "").strip()
    if sho:
        parts.append(
            '<div class="sho"><div class="label">Shoのコメント<b>本人</b></div>'
            f"<p>{esc(sho)}</p></div>"
        )

    hojosen = story.get("hojosen") or []
    if hojosen:
        parts.append('<div class="sec-label">背景</div><div class="hojosen">')
        for h in hojosen:
            parts.append(f'<div class="item"><b>{esc(h.get("title", ""))}</b><p>{esc(h.get("body", ""))}</p></div>')
        parts.append("</div>")

    rel = story.get("reliability")
    if rel:
        parts.append(f'<span class="rel">情報の信頼性：{esc(rel)}</span>')
    parts.append("</article>")
    return "\n".join(parts)


def render_issue(issue: dict, prev_issue: dict | None, next_issue: dict | None) -> str:
    date = issue["date"]
    wd = issue.get("weekday", "")
    stories = issue.get("stories") or []
    first_title = stories[0]["title"] if stories else ""
    title = f"{jp_date(date)}号「{first_title}」ほか{max(len(stories) - 1, 0)}本 | {SITE_NAME}" if stories else f"{jp_date(date)}号 | {SITE_NAME}"
    desc = " / ".join(s.get("title", "") for s in stories)[:180]
    url = issue_url(date)

    out = [head(title, desc, url)]
    out.append(
        f'<div class="issue-head"><div class="kicker">Architecture news in 3 minutes</div>'
        f"<h1>{jp_date(date, wd)}号</h1>"
        f'<div class="meta">{len(stories)} stories ・ 要点約{issue.get("readingMinutesSummary", 3)}分／全文約{issue.get("readingMinutesFull", 10)}分</div></div>'
    )
    out.append('<div class="toc"><div class="kicker">IN THIS ISSUE</div><ol>')
    for s in stories:
        out.append(f'<li><span class="num">{s.get("number", "")}</span><a href="#s{s.get("number", "")}">{esc(s.get("title", ""))}</a></li>')
    out.append("</ol></div>")

    for s in stories:
        out.append(render_story(s))

    out.append(
        f'<div class="appbox"><p>毎朝6時すぎに新しい号が届きます。<br>通知・バックナンバー・Podcastはアプリで。</p>'
        f'<a class="cta" href="{APP_STORE_URL}">App Storeで「{SITE_NAME}」を入手</a></div>'
    )
    nav = []
    nav.append(f'<a href="{issue_url(prev_issue["date"])}">← {jp_date(prev_issue["date"])}号</a>' if prev_issue else "<span></span>")
    nav.append(f'<a href="{issue_url(next_issue["date"])}">{jp_date(next_issue["date"])}号 →</a>' if next_issue else f'<a href="{BASE_URL}/">一覧へ</a>')
    out.append(f'<nav class="pn">{nav[0]}{nav[1]}</nav>')
    out.append(FOOTER)
    return "\n".join(out)


def render_index(issues: list[dict]) -> str:
    latest = issues[0] if issues else None
    title = f"{SITE_NAME} | 毎朝3分で読める建築ニュース"
    desc = "建築業界のニュースを毎朝3本、Sho建築士AIの解説付きで。iPhoneアプリ「建築3分ニュース」のWeb版バックナンバー。"
    out = [head(title, desc, f"{BASE_URL}/")]
    if latest:
        stories = latest.get("stories") or []
        out.append(
            f'<div class="issue-head"><div class="kicker">Latest issue</div>'
            f'<h1><a href="{issue_url(latest["date"])}" style="color:inherit;text-decoration:none">{jp_date(latest["date"], latest.get("weekday", ""))}号</a></h1></div>'
        )
        out.append('<div class="toc"><div class="kicker">IN THIS ISSUE</div><ol>')
        for s in stories:
            out.append(f'<li><span class="num">{s.get("number", "")}</span><a href="{issue_url(latest["date"])}#s{s.get("number", "")}">{esc(s.get("title", ""))}</a></li>')
        out.append("</ol></div>")
    out.append(
        f'<div class="appbox"><p>毎朝6時すぎに新しい号が届きます。<br>通知・保存・Podcastはアプリで。</p>'
        f'<a class="cta" href="{APP_STORE_URL}">App Storeで「{SITE_NAME}」を入手</a></div>'
    )
    out.append('<div class="sec-label">Daily archive</div><div class="list">')
    for iss in issues:
        out.append(f'<a class="row" href="{issue_url(iss["date"])}"><div class="date">{jp_date(iss["date"], iss.get("weekday", ""))}<span>{esc(iss["date"])}</span></div><ul>')
        for s in iss.get("stories") or []:
            out.append(f"<li>{esc(s.get('title', ''))}</li>")
        out.append("</ul></a>")
    out.append("</div>")
    out.append(FOOTER)
    return "\n".join(out)


def main() -> int:
    data = json.loads((ROOT / "issues.json").read_text(encoding="utf-8"))
    issues = sorted(data.get("issues", []), key=lambda i: i["date"], reverse=True)
    if not issues:
        print("issues.json に号がありません", file=sys.stderr)
        return 1

    written = 0
    for idx, issue in enumerate(issues):
        newer = issues[idx - 1] if idx > 0 else None
        older = issues[idx + 1] if idx + 1 < len(issues) else None
        page = render_issue(issue, prev_issue=older, next_issue=newer)
        d = ROOT / "i" / issue["date"]
        d.mkdir(parents=True, exist_ok=True)
        path = d / "index.html"
        if not path.exists() or path.read_text(encoding="utf-8") != page:
            path.write_text(page, encoding="utf-8")
            written += 1

    index = render_index(issues)
    ipath = ROOT / "index.html"
    if not ipath.exists() or ipath.read_text(encoding="utf-8") != index:
        ipath.write_text(index, encoding="utf-8")
        written += 1

    # 保持は直近30号なので、それより古い号のページは消さずに残す（過去の共有リンクを生かす）
    print(f"生成完了: {len(issues)}号 / 更新ファイル {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

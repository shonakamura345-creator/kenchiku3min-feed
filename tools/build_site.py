#!/usr/bin/env python3
"""issues.json から共有用の静的ページを生成する。

出力:
  index.html            … 最新号＋バックナンバー一覧（サイトのトップ）
  i/<YYYY-MM-DD>/index.html … 号ごとのページ（アプリの共有リンク先。記事は #s1 #s2 #s3 でアンカー）
  en/index.html         … 英語版のトップ（記事に en がある号だけ）
  en/i/<YYYY-MM-DD>/index.html … 英語版の号ページ（英語の画面からの共有リンク先。OGPも英語）

毎朝の号生成ルーチン（クラウド常設セッション）が issues.json 更新後に実行し、生成物を同じコミットに含める。
（GitHub Actions化はトークンのworkflow権限がなく2026-09-06時点では見送り）
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
LINE_URL = "https://line.me/R/ti/p/@860krbpe"
SITE_NAME = "建築3分ニュース"
OG_IMAGE = f"{BASE_URL}/assets/og.jpg"
# 英語版（v1.5〜）
APP_STORE_URL_EN = "https://apps.apple.com/app/id6800172328"
SITE_NAME_EN = "Kenchiku 3min"
TAGLINE_EN = "Japan's architecture news in 3 minutes"
RELIABILITY_EN = {"高": "High", "中": "Medium", "低": "Low"}
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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
header.site .right{display:flex;align-items:center;gap:10px}
header.site .lang{font-size:.82rem;color:var(--sub);text-decoration:none;white-space:nowrap}
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
.appbox .cta.line{background:#06C755;margin-top:10px}
.appbox .btns{display:flex;flex-direction:column;align-items:center;gap:2px}
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


def en_issue_url(date: str) -> str:
    return f"{BASE_URL}/en/i/{date}/"


def en_date(date: str, with_weekday: bool = False, with_year: bool = False) -> str:
    import datetime as _dt
    d = _dt.date.fromisoformat(date)
    s = f"{MONTHS_EN[d.month - 1]} {d.day}"
    if with_year:
        s += f", {d.year}"
    if with_weekday:
        s = f"{WEEKDAYS_EN[d.weekday()]}, {s}"
    return s


def has_en(issue: dict) -> bool:
    return any(isinstance(s.get("en"), dict) for s in issue.get("stories") or [])


def alternates(ja_url: str, en_url: str | None) -> str:
    if not en_url:
        return ""
    return (f'<link rel="alternate" hreflang="ja" href="{esc(ja_url)}">\n'
            f'<link rel="alternate" hreflang="en" href="{esc(en_url)}">\n')


def head(title: str, desc: str, url: str, extra_css: str = "", alt: str = "", lang_link: str = "") -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(url)}">
{alt}<meta property="og:type" content="article">
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
  {f'<span class="right">{lang_link}<a class="cta small" href="{APP_STORE_URL}">アプリで読む</a></span>' if lang_link else f'<a class="cta small" href="{APP_STORE_URL}">アプリで読む</a>'}
</header>
"""


FOOTER = f"""
<footer>
  <p>「{SITE_NAME}」は、毎朝3分で読める建築ニュースのiPhoneアプリです。記事は出典を要約・再構成したもので、詳細は各出典をご覧ください。解説は「Sho建築士AI」が生成しています。</p>
  <p><a href="{APP_STORE_URL}">App Store</a> ・ <a href="{LINE_URL}">公式LINE</a> ・ <a href="https://kenchiku3min.web.app/">サポート</a> ・ <a href="https://kenchiku3min.web.app/privacy.html">プライバシーポリシー</a><br>© 2026 Sho Nakamura / 株式会社ATAP Works</p>
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
    en_url = en_issue_url(date) if has_en(issue) else None

    out = [head(title, desc, url, alt=alternates(url, en_url),
                lang_link=f'<a class="lang" href="{en_url}" hreflang="en">English</a>' if en_url else "")]
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
        f'<div class="btns"><a class="cta" href="{APP_STORE_URL}">App Storeで「{SITE_NAME}」を入手</a>'
        f'<a class="cta line" href="{LINE_URL}">Sho建築士の公式LINEに登録（ツアー・登壇の告知）</a></div></div>'
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
    en_top = f"{BASE_URL}/en/" if any(has_en(i) for i in issues) else None
    out = [head(title, desc, f"{BASE_URL}/", alt=alternates(f"{BASE_URL}/", en_top),
                lang_link=f'<a class="lang" href="{en_top}" hreflang="en">English</a>' if en_top else "")]
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
        f'<div class="btns"><a class="cta" href="{APP_STORE_URL}">App Storeで「{SITE_NAME}」を入手</a>'
        f'<a class="cta line" href="{LINE_URL}">Sho建築士の公式LINEに登録（ツアー・登壇の告知）</a></div></div>'
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


# ---------------------------------------------------------------- 英語版（/en/）

def head_en(title: str, desc: str, url: str, ja_url: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(url)}">
{alternates(ja_url, url)}<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE_NAME_EN}">
<meta property="og:locale" content="en_US">
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
<style>{CSS}body{{line-height:1.7}}</style>
</head>
<body><div class="wrap">
<header class="site">
  <a class="brand" href="{BASE_URL}/en/"><span class="badge">建築<b>NEWS</b></span><span class="name">{SITE_NAME_EN}</span></a>
  <span class="right"><a class="lang" href="{esc(ja_url)}" hreflang="ja" lang="ja">日本語</a><a class="cta small" href="{APP_STORE_URL_EN}">Get the app</a></span>
</header>
"""


FOOTER_EN = f"""
<footer>
  <p>{SITE_NAME_EN} is a daily app with three short stories on architecture and construction in Japan, each with commentary from an architect's point of view. Stories are summaries of the linked sources, most of which are in Japanese. The commentary is generated by "Sho Architect AI".</p>
  <p><a href="{APP_STORE_URL_EN}">App Store</a> · <a href="https://kenchiku3min.web.app/">Support</a> · <a href="https://kenchiku3min.web.app/privacy.html">Privacy policy</a><br>© 2026 Sho Nakamura / ATAP Works Inc.</p>
</footer>
</div></body></html>
"""


def story_en(story: dict) -> dict:
    """英語の欄が無い記事は日本語のまま（アプリと同じ扱い）。"""
    en = story.get("en") if isinstance(story.get("en"), dict) else None
    if not en:
        return {"_ja": True, **story}
    return {**en, "_ja": False}


def render_story_en(story: dict) -> str:
    n = story.get("number", 0)
    st = story_en(story)
    lang = ' lang="ja"' if st["_ja"] else ""
    parts = [f'<article id="s{n}"{lang}>']
    parts.append(f'<div class="src">{esc(story.get("sourceName", ""))}</div>')
    parts.append(f"<h2>{esc(st.get('title', ''))}</h2>")
    if st.get("summary"):
        parts.append(f'<p class="summary">{esc(st["summary"])}</p>')
    for p in st.get("body") or []:
        parts.append(f"<p>{esc(p)}</p>")

    briefing = st.get("briefing") or []
    if briefing:
        parts.append('<div class="sec-label">Briefing</div><ul class="briefing">')
        parts.extend(f"<li>{esc(b)}</li>" for b in briefing)
        parts.append("</ul>")

    sources = story.get("sources") or []
    if not sources and story.get("sourceURL"):
        sources = [{"name": story.get("sourceName", "Source"), "url": story["sourceURL"]}]
    if sources:
        parts.append('<div class="sec-label">Sources</div><div class="chips">')
        for s in sources:
            parts.append(f'<a href="{esc(s.get("url", ""))}" target="_blank" rel="noopener">{esc(s.get("name", ""))}</a>')
        parts.append("</div>")

    if st.get("commentary"):
        parts.append(
            '<div class="commentary"><div class="label">💡 Commentary by Sho Architect AI</div>'
            f'<p>{esc(st["commentary"])}</p></div>'
        )
    sho = (story.get("shoComment") or "").strip()
    if sho:
        parts.append(
            '<div class="sho"><div class="label">Sho&#39;s comment (in Japanese)<b>Human</b></div>'
            f'<p lang="ja">{esc(sho)}</p></div>'
        )

    hojosen = st.get("hojosen") or []
    if hojosen:
        parts.append('<div class="sec-label">Background</div><div class="hojosen">')
        for h in hojosen:
            parts.append(f'<div class="item"><b>{esc(h.get("title", ""))}</b><p>{esc(h.get("body", ""))}</p></div>')
        parts.append("</div>")

    rel = story.get("reliability")
    if rel:
        parts.append(f'<span class="rel">Reliability of this AI summary: {esc(RELIABILITY_EN.get(rel, rel))}</span>')
    parts.append("</article>")
    return "\n".join(parts)


APPBOX_EN = (
    f'<div class="appbox"><p>A new issue arrives every morning, Japan time.<br>Notifications, back issues and bookmarks are in the app.</p>'
    f'<div class="btns"><a class="cta" href="{APP_STORE_URL_EN}">Get {SITE_NAME_EN} on the App Store</a></div></div>'
)


def render_issue_en(issue: dict, prev_issue: dict | None, next_issue: dict | None) -> str:
    date = issue["date"]
    stories = issue.get("stories") or []
    titles = [story_en(s).get("title", "") for s in stories]
    more = max(len(stories) - 1, 0)
    title = (f'{en_date(date)}: "{titles[0]}"' + (f" and {more} more" if more else "") + f" – {SITE_NAME_EN}") if stories else f"{en_date(date)} – {SITE_NAME_EN}"
    desc = " / ".join(titles)[:200]
    url = en_issue_url(date)

    out = [head_en(title, desc, url, issue_url(date))]
    out.append(
        f'<div class="issue-head"><div class="kicker">{TAGLINE_EN}</div>'
        f"<h1>{en_date(date, with_weekday=True, with_year=True)}</h1>"
        f'<div class="meta">{len(stories)} stories · Key points ~{issue.get("readingMinutesSummary", 3)} min / Full read ~{issue.get("readingMinutesFull", 10)} min</div></div>'
    )
    out.append('<div class="toc"><div class="kicker">IN THIS ISSUE</div><ol>')
    for s, t in zip(stories, titles):
        out.append(f'<li><span class="num">{s.get("number", "")}</span><a href="#s{s.get("number", "")}">{esc(t)}</a></li>')
    out.append("</ol></div>")

    for s in stories:
        out.append(render_story_en(s))

    out.append(APPBOX_EN)
    nav = []
    nav.append(f'<a href="{en_issue_url(prev_issue["date"])}">← {en_date(prev_issue["date"])}</a>' if prev_issue else "<span></span>")
    nav.append(f'<a href="{en_issue_url(next_issue["date"])}">{en_date(next_issue["date"])} →</a>' if next_issue else f'<a href="{BASE_URL}/en/">All issues</a>')
    out.append(f'<nav class="pn">{nav[0]}{nav[1]}</nav>')
    out.append(FOOTER_EN)
    return "\n".join(out)


def render_index_en(issues: list[dict]) -> str:
    latest = issues[0] if issues else None
    title = f"{SITE_NAME_EN} | {TAGLINE_EN}"
    desc = "Three stories on architecture and construction in Japan every morning, with an architect's commentary. Back issues of the Kenchiku 3min app."
    out = [head_en(title, desc, f"{BASE_URL}/en/", f"{BASE_URL}/")]
    if latest:
        stories = latest.get("stories") or []
        out.append(
            f'<div class="issue-head"><div class="kicker">Latest issue</div>'
            f'<h1><a href="{en_issue_url(latest["date"])}" style="color:inherit;text-decoration:none">{en_date(latest["date"], with_weekday=True, with_year=True)}</a></h1></div>'
        )
        out.append('<div class="toc"><div class="kicker">IN THIS ISSUE</div><ol>')
        for s in stories:
            out.append(f'<li><span class="num">{s.get("number", "")}</span><a href="{en_issue_url(latest["date"])}#s{s.get("number", "")}">{esc(story_en(s).get("title", ""))}</a></li>')
        out.append("</ol></div>")
    out.append(APPBOX_EN)
    out.append('<div class="sec-label">Daily archive</div><div class="list">')
    for iss in issues:
        out.append(f'<a class="row" href="{en_issue_url(iss["date"])}"><div class="date">{en_date(iss["date"], with_weekday=True)}<span>{esc(iss["date"])}</span></div><ul>')
        for s in iss.get("stories") or []:
            out.append(f"<li>{esc(story_en(s).get('title', ''))}</li>")
        out.append("</ul></a>")
    out.append("</div>")
    out.append(FOOTER_EN)
    return "\n".join(out)


def write_if_changed(path: Path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
        return 1
    return 0


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

    # 英語版：記事に en がある号だけ。号ページの前後リンクも英語のある号どうしでつなぐ
    en_issues = [i for i in issues if has_en(i)]
    for idx, issue in enumerate(en_issues):
        newer = en_issues[idx - 1] if idx > 0 else None
        older = en_issues[idx + 1] if idx + 1 < len(en_issues) else None
        written += write_if_changed(ROOT / "en" / "i" / issue["date"] / "index.html",
                                    render_issue_en(issue, prev_issue=older, next_issue=newer))
    if en_issues:
        written += write_if_changed(ROOT / "en" / "index.html", render_index_en(en_issues))

    # 保持は直近30号なので、それより古い号のページは消さずに残す（過去の共有リンクを生かす）
    print(f"生成完了: {len(issues)}号（英語 {len(en_issues)}号） / 更新ファイル {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

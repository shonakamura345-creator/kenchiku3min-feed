#!/usr/bin/env python3
"""最新号の各記事に写真を1枚付ける（2026-11-16〜）。

毎朝、クラウドのルーチンが号（日本語→英語）を push したあと、Shoの Mac の launchd から動く。
クラウドの実行環境は外部への通信が塞がれていて fal も公式サイトも読めないので、写真づくりだけ手元で行う。

記事ごとの決め方（上から順に）:
  1. 既に imageURL がある → 何もしない
  2. noImage: true、または本文に人が亡くなった語がある → 空の写真 img/sky/<SKY_FOR_LOSS>.jpg（「画像はイメージ」）
  3. 出典にプレスリリース（PR TIMES・@Press・公式発表ページ）があり、その og:image が使える
     → その写真。クレジット「画像：〇〇（プレスリリース）」
  3.5 現地の写真（2026-11-25 Sho「雲だけのやつでも現地の写真を入れられそうなものがある」）
     記事に出てくる実在の建物・場所（まだ建っていなければ計画地の周り、訃報ならその人の作品）を
     fal の LLM に選ばせ、Wikimedia Commons で自由に使える写真（CC BY / BY-SA / CC0 / パブリックドメイン）を探す。
     候補は画像を読むAIで「本当にその場所か・ニュースの写真に向くか」を確かめてから使う。
     クレジット「写真：〇〇／撮影者（Wikimedia Commons・ライセンス）」。人が亡くなった記事も、
     訃報（作品の写真）は使い、事故・災害で亡くなった記事は空の写真のまま。
  4. fal の nano-banana-2 でイメージ写真（場面は imagePrompt があればそれ、無ければ見出し・要約から）。
     クレジット「画像はイメージ（AI生成）」
  5. 作れなかった → 画像なし

書き足す欄（stories[]）:
  imageURL     … 写真の絶対URL（このリポジトリの img/<日付>/s<N>.jpg を GitHub Pages で配信）
  imageCredit  … 日本語のクレジット文（そのまま隅に出す）
  imageKind    … "press" / "commons" / "ai" / "sky"（英語の画面でクレジットを訳すため）
  imageSource  … press のときの会社・団体名
  imageCreditEn… 英語の画面用のクレジット（commons のとき）
  imagePage    … commons の写真のページ（ライセンスの出どころ）
  imageLicense / imageLicenseURL … commons の写真のライセンス名とその条文のURL
  imageCreditURL … クレジットを押したときに開くページ（写真のクレジット一覧 credits/ の該当行）
  namesEn      … 英語の画面用の名前の対応表 {日本語の出典名・会社名: 英語名}（fal の LLM で作る）

使い方:
  python3 tools/make_story_images.py --sync --push        # launchd から（専用クローンで）
  python3 tools/make_story_images.py --date 2026-11-16     # 指定の号に付ける（push しない）
  python3 tools/make_story_images.py --dry-run             # 何をするかだけ表示
  python3 tools/make_story_images.py --date 2026-11-17 --upgrade  # AI・空の写真を現地の写真に差し替えられるか試す
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_BASE = "https://shonakamura345-creator.github.io/kenchiku3min-feed/"
FAL_KEY_PATH = os.path.expanduser("~/.config/fal/key")
FAL_MODEL = "fal-ai/nano-banana-2"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
JST = dt.timezone(dt.timedelta(hours=9))
# 英語が付くのを待つ期限（これを過ぎたら英語なしでも付ける）
WAIT_EN_UNTIL = dt.time(8, 30)
# 人が亡くなった記事に出す空（img/sky/ の6枚から。曇り＝落ち着いた空を既定に。Shoの返事で差し替え）
SKY_FOR_LOSS = "overcast"
# 1回の起動で AI 画像を作る上限（暴走防止。1枚およそ12円）
MAX_AI_PER_RUN = 6

DEATH_RE = re.compile(r"死亡|死者|亡くな|死去|遺体|犠牲|殉職|心肺停止|死傷|命を落と|安否不明|行方不明")
PRESS_HOSTS = ("prtimes.jp", "atpress.ne.jp", "value-press.com", "kyodonewsprwire.jp", "dreamnews.jp")
OFFICIAL_PATH_RE = re.compile(r"news|press|release|topics|info|/pr/|/20\d\d", re.I)
BAD_OG_RE = re.compile(r"logo|default|common|noimage|no_image|share|favicon|icon|sns", re.I)
AI_STYLE = (
    "Photorealistic editorial news photograph, natural light, realistic materials, 3:2 landscape. "
    "Generic scene only: do not depict any specific real, identifiable building, landmark, logo or brand. "
    "No text, no letters, no signage lettering, no watermark. People, if any, are small and seen from a distance, no close-up faces."
)


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def git(*args, check=True):
    return subprocess.run(["git", "-C", ROOT, *args], check=check, capture_output=True, text=True)


def load():
    with open(os.path.join(ROOT, "issues.json"), encoding="utf-8") as f:
        return json.load(f)


def save(d):
    with open(os.path.join(ROOT, "issues.json"), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# ---------- 取得まわり ----------

def http_get(url, timeout=30, max_bytes=15_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(max_bytes), r.headers.get_content_type(), r.geturl()


def meta(html_text, prop):
    for pat in (
        rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]*content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']{prop}["\']',
    ):
        m = re.search(pat, html_text, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return None


def image_size(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path], capture_output=True, text=True).stdout
    w = re.search(r"pixelWidth: (\d+)", out)
    h = re.search(r"pixelHeight: (\d+)", out)
    return (int(w.group(1)), int(h.group(1))) if w and h else (0, 0)


def to_jpeg(src, dst):
    """長辺1080pxのJPEG（品質70）に。sips は macOS 標準。"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70", "-Z", "1080", src, "--out", dst],
                   check=True, capture_output=True)


def press_company(page_html, host, source_name):
    title = meta(page_html, "og:title") or ""
    t = re.search(r"<title>(.*?)</title>", page_html, re.S | re.I)
    page_title = html.unescape(t.group(1)).strip() if t else ""
    for s in (page_title, title):
        m = re.search(r"[｜|]\s*(.+?)のプレスリリース", s)
        if m:
            return m.group(1).strip()
    if any(h in host for h in PRESS_HOSTS):
        return None  # 会社名が取れない配信サイトの写真は使わない
    name = re.sub(r"[（(]公式[)）]", "", source_name or "").strip()
    return name or None


def try_press_image(story, dst):
    """出典のプレスリリースから og:image を取る。成功したら会社名を返す。"""
    cands = []
    for s in story.get("sources") or []:
        url, name = s.get("url") or "", s.get("name") or ""
        host = urllib.parse.urlparse(url).netloc
        if any(h in host for h in PRESS_HOSTS):
            cands.insert(0, (url, name, host))
        elif "公式" in name and OFFICIAL_PATH_RE.search(urllib.parse.urlparse(url).path or ""):
            cands.append((url, name, host))
    for url, name, host in cands:
        try:
            body, ctype, _ = http_get(url)
            if "html" not in ctype:
                continue
            page = body.decode("utf-8", "ignore")
            company = press_company(page, host, name)
            if not company:
                log("  会社名が取れない:", url)
                continue
            imgs = []
            og = meta(page, "og:image")
            if og and not BAD_OG_RE.search(og):
                imgs.append(urllib.parse.urljoin(url, og))
            if "prtimes.jp" in host:  # og:image が横長の帯のことがあるので、本文の写真も順に当たる
                for m in re.findall(r'https://prcdn\.freetls\.fastly\.net/release_image/[^"\'\s?)]+', page):
                    if m not in imgs and not BAD_OG_RE.search(m.rsplit("/", 1)[-1]):
                        imgs.append(m)
            for img_url in imgs[:6]:
                img, itype, _ = http_get(img_url)
                if not itype.startswith("image/"):
                    continue
                with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tf:
                    tf.write(img)
                    tmp = tf.name
                w, h = image_size(tmp)
                if w < 800 or h < 450 or not (1.2 <= w / max(h, 1) <= 2.0):
                    log(f"  写真の大きさ・形が合わない {w}x{h}:", img_url)
                    os.unlink(tmp)
                    continue
                if not looks_like_photo(tmp):
                    log("  地図・ロゴ・文字だけの画像なので使わない:", img_url)
                    os.unlink(tmp)
                    continue
                to_jpeg(tmp, dst)
                os.unlink(tmp)
                log(f"  プレス写真 {w}x{h} ← {img_url}")
                return company
        except Exception as e:  # noqa: BLE001 — 1件失敗しても次へ
            log("  取得失敗:", url, e)
    return None


def looks_like_photo(path):
    """プレスの画像が写真・パースか（地図・ロゴ・表・文字だけの帯は外す）。確かめられなければ通す。"""
    import base64
    try:
        small = path + ".chk.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "768", path, "--out", small], check=True, capture_output=True)
        data = "data:image/jpeg;base64," + base64.b64encode(open(small, "rb").read()).decode()
        os.unlink(small)
        v = llm("Is this image a photograph or architectural rendering of a building, place, interior or scene? "
                "Answer ok=false if it is mainly a map, site plan, logo, chart, table, document or a text banner. "
                "Return only JSON {\"ok\": true/false, \"reason\": \"short\"}", data)
        return v.get("ok", True) is not False
    except Exception as e:  # noqa: BLE001
        log("  画像の確認に失敗（そのまま使う）:", e)
        return True


def fal_req(url, key, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": "Key " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def make_ai_image(prompt, dst):
    key = open(FAL_KEY_PATH).read().strip()
    body = {"prompt": f"{prompt}\n\n{AI_STYLE}", "num_images": 1, "aspect_ratio": "3:2",
            "resolution": "1K", "output_format": "jpeg"}
    s = fal_req(f"https://queue.fal.run/{FAL_MODEL}", key, body)
    for _ in range(90):
        st = fal_req(s["status_url"], key)["status"]
        if st == "COMPLETED":
            break
        if st in ("FAILED", "ERROR"):
            raise RuntimeError("fal failed")
        time.sleep(3)
    r = fal_req(s["response_url"], key)
    img, _, _ = http_get(r["images"][0]["url"], timeout=60)
    with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tf:
        tf.write(img)
        tmp = tf.name
    to_jpeg(tmp, dst)
    os.unlink(tmp)


# ---------- 現地の写真（Wikimedia Commons） ----------

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_UA = "kenchiku3min-images/1.0 (https://kenchiku3min.web.app/; news app photo credit lookup)"
OK_LICENSE_RE = re.compile(r"^(CC BY(-SA)? [0-9.]+|CC0|Public domain|PD|No restrictions)", re.I)
BAD_FILE_RE = re.compile(r"map|logo|plan|diagram|floor|chart|seal|flag|emblem|\.svg|\.pdf|\.tif", re.I)


def llm(prompt, image_data_url=None):
    key = open(FAL_KEY_PATH).read().strip()
    body = {"model": LLM_MODEL, "prompt": prompt}
    ep = "fal-ai/any-llm"
    if image_data_url:
        body["image_urls"] = [image_data_url]
        ep = "fal-ai/any-llm/vision"
    s = fal_req(f"https://queue.fal.run/{ep}", key, body)
    for _ in range(60):
        if fal_req(s["status_url"], key)["status"] == "COMPLETED":
            break
        time.sleep(2)
    out = fal_req(s["response_url"], key).get("output") or ""
    m = re.search(r"\{.*\}", out, re.S)
    return json.loads(m.group(0)) if m else {}


def commons_subject(st, loss):
    """記事から「写真に撮れる実在の場所」を選ばせる。無ければ subject=None。"""
    rule_loss = (
        "This story involves a death. If it is an obituary of an architect/designer, choose a well-known existing building "
        "they designed. If people died in an accident, disaster or crime, return subject null.\n" if loss else "")
    prompt = (
        "You pick a real-world photo subject for a Japanese architecture news story, to be searched on Wikimedia Commons.\n"
        "Choose ONE specific, real, already-existing building, station, landmark, district or site that appears in the story "
        "and that readers would recognize as 'the place' of the story. If the project is not built yet, choose the existing "
        "site, the building being replaced, or the landmark right next to the site. If the story is about statistics, law, "
        "a company's finances or anything without a specific place, return subject null. Never choose a person.\n"
        + rule_loss +
        "Return only JSON: {\"subject\": Japanese name or null, \"queries\": [2-3 Wikimedia Commons search strings "
        "that all name exactly the subject (no broader area, no other nearby place), English first, then Japanese], \"what\": short English description of what the photo should show, "
        "\"caption\": short Japanese caption for the photo (e.g. 名護市庁舎 / 計画地の隣の渋谷ヒカリエ / 現在の旧本店), "
        "\"captionEn\": the same caption in English, "
        "\"minYear\": if the place changed a lot recently (burned, demolished, rebuilt, restored, renovated, newly "
        "opened) so that older photos would show a different state from the story, the earliest year a valid photo can "
        "be from; otherwise null}\n"
        "The caption must describe the place itself, not claim a state (do not write 再建された / 完成した).\n"
        f"Headline: {st.get('title', '')}\nSummary: {st.get('summary', '')}\nBody: {' '.join(st.get('body') or [])[:1500]}"
    )
    try:
        return llm(prompt)
    except Exception as e:  # noqa: BLE001
        log("  場所の選び出しに失敗:", e)
        return {}


def commons_search(q, limit=12):
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrsearch": q,
        "gsrlimit": limit, "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 1280})
    time.sleep(1)  # Commons の API に間をあける（429 を避ける）
    req = urllib.request.Request(f"{COMMONS_API}?{params}", headers={"User-Agent": COMMONS_UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        pages = (json.loads(r.read()).get("query") or {}).get("pages") or {}
    out = []
    for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata") or {}
        lic = (m.get("LicenseShortName") or {}).get("value", "")
        w, h = ii.get("width", 0), ii.get("height", 0)
        if ii.get("mime") not in ("image/jpeg", "image/png") or BAD_FILE_RE.search(p.get("title", "")):
            continue
        if w < 1200 or h < 700 or not (1.25 <= w / max(h, 1) <= 1.9) or not OK_LICENSE_RE.search(lic):
            continue
        when = re.sub(r"<[^>]+>", "", (m.get("DateTimeOriginal") or m.get("DateTime") or {}).get("value", ""))
        y = re.search(r"(19|20)\d\d", when)
        artist = re.sub(r"<[^>]+>", "", html.unescape((m.get("Artist") or {}).get("value", ""))).strip()
        artist = re.sub(r"\s+", " ", artist)[:40] or "不明"
        lic_url = (m.get("LicenseUrl") or {}).get("value", "") or license_url(lic)
        out.append({"title": p["title"], "thumb": ii.get("thumburl"), "page": ii.get("descriptionurl"), "license_url": lic_url,
                    "license": lic, "artist": artist, "year": int(y.group(0)) if y else None})
    return out


def license_url(lic):
    """ライセンス名から条文のURL（Commons に LicenseUrl が無いとき用）。"""
    m = re.match(r"CC (BY(?:-SA)?) ([0-9.]+)", lic or "", re.I)
    if m:
        return f"https://creativecommons.org/licenses/{m.group(1).lower()}/{m.group(2)}/deed.ja"
    if (lic or "").upper().startswith("CC0"):
        return "https://creativecommons.org/publicdomain/zero/1.0/deed.ja"
    return ""


def text_width(t):
    """アプリのクレジット（10pt・1行）での幅（pt）。ヒラギノで測る（無ければ全角10・半角6.5の目安）。
    アプリは写真の左右20pt＋帯の余白で、iPhone SE・mini（幅375）だと約305ptまで。余裕を見て290に収める。"""
    try:
        from PIL import ImageFont
        return ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 10).getlength(t)
    except Exception:  # noqa: BLE001
        return sum(10 if ord(ch) > 0x2000 else 6.5 for ch in t)


def commons_credit(artist, lic):
    """アプリの1行に収まるクレジット。撮影者とライセンスは必ず残す（場所・撮影年はクレジットページへ）。"""
    for fmt in ("写真：{a}／{l}（Wikimedia Commons・切り抜き）", "写真：{a}／{l}（Commons・切り抜き）", "写真：{a}／{l}・切り抜き"):
        t = fmt.format(a=artist, l=lic)
        if text_width(t) <= 290:
            return t
    a = artist
    while a and text_width(f"写真：{a}…／{lic}・切り抜き") > 290:
        a = a[:-1]
    return f"写真：{a}…／{lic}・切り抜き"


def credit_url(date, n):
    return f"{PAGES_BASE}credits/#p-{date}-s{n}"


def commons_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": COMMONS_UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def try_commons_image(st, dst, loss=False):
    """現地の写真を探して dst に置く。成功したら欄（dict）を返す。"""
    sub = commons_subject(st, loss)
    if not sub or not sub.get("subject"):
        log("  現地の写真：写せる場所がない記事")
        return None
    log(f"  現地の写真：{sub.get('subject')} を探す {sub.get('queries')}")
    seen, cands = set(), []
    for q in (sub.get("queries") or [])[:3]:
        try:
            for c in commons_search(q):
                if c["title"] not in seen:
                    seen.add(c["title"])
                    cands.append(c)
        except Exception as e:  # noqa: BLE001
            log("  Commons 検索失敗:", q, e)
    import base64
    min_year = sub.get("minYear")
    if isinstance(min_year, int):
        cands = [c for c in cands if c["year"] and c["year"] >= min_year]
        log(f"  {min_year}年以降に撮った写真だけ：{len(cands)}枚")
    for c in cands[:6]:
        try:
            img = commons_get(c["thumb"])
            data_url = "data:image/jpeg;base64," + base64.b64encode(img).decode()
            v = llm(
                f"Is this photo clearly {sub.get('what')} ({sub.get('subject')})? It will be the thumbnail of a news story. "
                f"The file on Wikimedia Commons is titled: {c['title']!r}. If the title names a different place, branch, "
                "city, street or building (for example another bank, another town's gymnasium, a different street nearby), "
                "answer ok=false. "
                "Answer ok=true only if (1) it really shows that place, recognizably, (2) it is a clear, well-exposed, "
                "pleasant general view (exterior or the main space), not a map, drawing, document, sign close-up, "
                "small detail or blurry night shot, (3) people are not the main subject. "
                "Return only JSON {\"ok\": true/false, \"reason\": \"short\"}", data_url)
            if not v.get("ok"):
                log(f"  × {c['title'][:60]}（{v.get('reason', '')}）")
                continue
            with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tf:
                tf.write(img)
                tmp = tf.name
            to_jpeg(tmp, dst)
            os.unlink(tmp)
            log(f"  ○ {c['title'][:60]} {c['license']} {c['artist']}")
            cap = sub.get("caption") or sub["subject"]
            if c["year"]:
                cap = f"{cap}（{c['year']}年撮影）"
            return {
                "imageCredit": commons_credit(c["artist"], c["license"]),
                "imageCreditEn": f"Photo: {c['artist']} / {c['license']} (Wikimedia Commons, cropped)",
                "imageCaption": cap,
                "imageKind": "commons", "imageSource": c["artist"], "imagePage": c["page"],
                "imageLicense": c["license"], "imageLicenseURL": c["license_url"],
            }
        except Exception as e:  # noqa: BLE001
            log("  候補の確認に失敗:", c["title"][:60], e)
    log("  現地の写真：使える写真が見つからない")
    return None


# ---------- 本体 ----------

def auto_prompt(st):
    """imagePrompt が無いとき、見出しと要約から場面を作らせる（実在の建物そのものは描かせない）。"""
    return (
        "Create one photograph that illustrates the general theme of this Japanese architecture news story. "
        "Show a typical, generic scene of that kind of place, work or material in Japan (for example a street, "
        "a construction site, an interior, building materials, a town) rather than the actual building, project, "
        "people or event in the story.\n"
        f"Headline: {st.get('title', '')}\nSummary: {st.get('summary', '')}"
    )


JA_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uff00-\uffef]")
LLM_MODEL = "google/gemini-2.5-flash"


def ja_names(st):
    """英語の画面に出る名前（出典名・写真の会社名）のうち、日本語の文字を含むもの。"""
    names = [st.get("sourceName") or "", *[x.get("name") or "" for x in st.get("sources") or []], st.get("imageSource") or ""]
    have = st.get("namesEn") or {}
    return sorted({n for n in names if n and JA_RE.search(n) and n not in have})


def translate_names(names):
    """fal の LLM で団体・媒体名を英語に。日本語が残った訳は捨てる。"""
    if not names:
        return {}
    key = open(FAL_KEY_PATH).read().strip()
    prompt = ("Translate these Japanese organization / media names into the names English-language readers would use "
              "(official English name if one exists, otherwise a romanized name). Keep parenthetical notes and translate "
              "them (公式 → official, プレスリリース → press release). Return only a JSON object mapping each input string "
              "to its English name.\n" + json.dumps(names, ensure_ascii=False))
    s = fal_req("https://queue.fal.run/fal-ai/any-llm", key, {"model": LLM_MODEL, "prompt": prompt})
    for _ in range(60):
        if fal_req(s["status_url"], key)["status"] == "COMPLETED":
            break
        time.sleep(2)
    out = fal_req(s["response_url"], key).get("output") or ""
    m = re.search(r"\{.*\}", out, re.S)
    data = json.loads(m.group(0)) if m else {}
    return {k: v.strip() for k, v in data.items() if k in names and isinstance(v, str) and v.strip() and not JA_RE.search(v)}


def add_names(st, fields):
    """fields に namesEn を足す（今ある対応表に追記）。"""
    todo = sorted(set(ja_names(st)) | ({fields["imageSource"]} if fields.get("imageSource") and JA_RE.search(fields["imageSource"]) else set()))
    if not todo:
        return
    try:
        got = translate_names(todo)
    except Exception as e:  # noqa: BLE001
        log("  英語名の作成に失敗:", e)
        return
    if got:
        fields["namesEn"] = {**(st.get("namesEn") or {}), **got}
        log("  英語名:", got)


def story_text(st):
    return " ".join([st.get("title", ""), st.get("summary", ""), *(st.get("body") or [])])


def plan_and_make(issue, dry_run, upgrade=False):
    """記事ごとに写真を作り、{story_id: 欄} を返す（JSONにはまだ書かない）。
    upgrade=True のときは、AI・空の写真の記事だけ現地の写真に差し替えられるか試す。"""
    date = issue["date"]
    results = {}
    ai_count = 0
    for st in issue.get("stories") or []:
        sid, n = st["id"], st.get("number", 0)
        rel = f"img/{date}/s{n}.jpg"
        dst = os.path.join(ROOT, rel)
        url = PAGES_BASE + rel
        loss = bool(st.get("noImage") or DEATH_RE.search(story_text(st)))
        if upgrade:
            if st.get("imageKind") not in ("ai", "sky") or st.get("noImage"):
                continue
            log(f"s{n}: {st.get('imageKind')} → 現地の写真を試す")
            if dry_run:
                continue
            got = try_commons_image(st, dst, loss)
            if got:
                results[sid] = {"imageURL": url, **got, "imageCreditURL": credit_url(date, n), "_force": True}
            continue
        if st.get("imageURL"):
            log(f"s{n}: 写真は付いている")
            if not dry_run:
                fields = {}
                add_names(st, fields)
                if fields:
                    results[sid] = fields
            continue
        if dry_run:
            log(f"s{n}: 亡くなった語={loss} / プレス候補={[s.get('url') for s in st.get('sources') or []]} / imagePrompt={'あり' if st.get('imagePrompt') else 'なし'}")
            continue
        if not loss:
            company = try_press_image(st, dst)
            if company:
                results[sid] = {"imageURL": url, "imageCredit": f"画像：{company}（プレスリリース）",
                                "imageKind": "press", "imageSource": company}
                continue
        if not st.get("noImage"):
            got = try_commons_image(st, dst, loss)
            if got:
                results[sid] = {"imageURL": url, **got, "imageCreditURL": credit_url(date, n)}
                continue
        if loss:
            # 事故・災害で人が亡くなった記事は、現場の絵を作らず、落ち着いた空の写真にする（11/16 Sho）
            log(f"s{n}: 人が亡くなった記事 → 空の写真（{SKY_FOR_LOSS}）")
            results[sid] = {"imageURL": f"{PAGES_BASE}img/sky/{SKY_FOR_LOSS}.jpg",
                            "imageCredit": "画像はイメージ", "imageKind": "sky"}
            continue
        prompt = (st.get("imagePrompt") or "").strip() or auto_prompt(st)
        if ai_count >= MAX_AI_PER_RUN:
            log(f"s{n}: AI画像の上限 → 画像なし")
            continue
        try:
            make_ai_image(prompt, dst)
            ai_count += 1
            log(f"s{n}: AI画像を作成 ({FAL_MODEL})")
            results[sid] = {"imageURL": url, "imageCredit": "画像はイメージ（AI生成）", "imageKind": "ai"}
        except Exception as e:  # noqa: BLE001
            log(f"s{n}: AI画像の作成に失敗:", e)
    for st in issue.get("stories") or []:
        fields = results.get(st["id"])
        if fields and fields.get("imageURL") and not dry_run:
            fields.setdefault("imageCreditURL", credit_url(date, st.get("number", 0)))
            add_names(st, fields)
    return results


def apply(d, issue_id, results):
    changed = False
    for iss in d["issues"]:
        if iss["id"] != issue_id:
            continue
        for st in iss.get("stories") or []:
            fields = dict(results.get(st["id"]) or {})
            if fields.pop("_force", False):
                for k in ("imageCreditEn", "imageSource", "imagePage", "imageLicense", "imageLicenseURL", "imageCreditURL"):
                    st.pop(k, None)
                for k, v in fields.items():
                    if k != "namesEn" and st.get(k) != v:
                        st[k] = v
                        changed = True
                fields = {k: v for k, v in fields.items() if k == "namesEn"}
            for k, v in fields.items():
                if k == "namesEn":
                    merged = {**(st.get("namesEn") or {}), **v}
                    if merged != st.get("namesEn"):
                        st["namesEn"] = merged
                        changed = True
                elif not st.get(k):
                    st[k] = v
                    changed = True
    return changed


def has_en(issue):
    ss = issue.get("stories") or []
    return bool(ss) and all(isinstance(s.get("en"), dict) and s["en"].get("title") for s in ss)


def backfill_names(d, push):
    changed = 0
    for iss in d["issues"]:
        for st in iss.get("stories") or []:
            fields = {}
            add_names(st, fields)
            if fields.get("namesEn"):
                st["namesEn"] = fields["namesEn"]
                changed += 1
    log("英語名を付けた記事:", changed)
    if changed:
        save(d)
        if push:
            git("add", "issues.json")
            git("commit", "-q", "-m", "過去号の出典名・写真の会社名に英語名（namesEn）を追加")
            git("push", "-q", "origin", "HEAD:main")
            log("push 済み")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="対象の号の日付（省略時は最新号）")
    p.add_argument("--sync", action="store_true", help="始める前に origin/main に合わせる（専用クローン用）")
    p.add_argument("--push", action="store_true", help="コミットして push する")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--names-all", action="store_true", help="全号の出典名・会社名に英語名を付ける（一度だけの埋め戻し）")
    p.add_argument("--upgrade", action="store_true", help="AI・空の写真の記事を現地の写真に差し替えられるか試す（--date と一緒に）")
    p.add_argument("--no-wait-en", action="store_true", help="英語が付くのを待たない")
    a = p.parse_args()

    if a.sync:
        git("fetch", "-q", "origin", "main")
        git("checkout", "-q", "main")
        git("reset", "-q", "--hard", "origin/main")

    d = load()
    issue = next((i for i in d["issues"] if i["date"] == a.date), None) if a.date else d["issues"][0]
    if not issue:
        log("号が見つからない:", a.date)
        return 1
    today = dt.datetime.now(JST).strftime("%Y-%m-%d")
    if not a.date and issue["date"] != today:
        log(f"今日（{today}）の号がまだない（最新は {issue['date']}）→ 次の起動で")
        return 0
    if not a.date and not a.no_wait_en and not has_en(issue) and dt.datetime.now(JST).time() < WAIT_EN_UNTIL:
        log("英語版の push 待ち（ルーチンと push がぶつからないように）→ 次の起動で")
        return 0
    if a.names_all:
        return backfill_names(d, a.push)
    if not a.upgrade and all(s.get("imageURL") and not ja_names(s) for s in issue.get("stories") or []):
        log(issue["id"], "は写真も英語名も付いている")
        return 0

    log("対象:", issue["id"])
    results = plan_and_make(issue, a.dry_run, a.upgrade)
    if a.dry_run or not results:
        log("書き足すものなし" if not a.dry_run else "dry-run 終了")
        return 0

    for attempt in range(3):
        d = load()
        if not apply(d, issue["id"], results):
            log("反映するものなし（既に付いている）")
            return 0
        save(d)
        json.load(open(os.path.join(ROOT, "issues.json"), encoding="utf-8"))  # 壊れていないか
        if not a.push:
            log("issues.json に反映（push はしない）")
            return 0
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_site.py")], cwd=ROOT, capture_output=True)  # 英語ページの出典名も更新
        git("add", "issues.json", "index.html", "i", "en")
        if os.path.isdir(os.path.join(ROOT, "img", issue["date"])):
            git("add", f"img/{issue['date']}")
        git("commit", "-q", "-m", f"{issue['date']}号の記事の写真を{'現地の写真に差し替え' if a.upgrade else '追加'}")
        r = git("push", "-q", "origin", "HEAD:main", check=False)
        if r.returncode == 0:
            log("push 済み:", ", ".join(f"{k}={v.get('imageKind', 'names')}" for k, v in results.items()))
            return 0
        log("push が弾かれた → 最新に合わせて付け直す", r.stderr.strip()[:200])
        git("fetch", "-q", "origin", "main")
        git("reset", "-q", "--mixed", "origin/main")  # 作った img/ は作業ツリーに残す
        git("checkout", "--", "issues.json")          # issues.json は最新に戻して付け直す
        time.sleep(5)
    log("push に3回失敗")
    return 1


if __name__ == "__main__":
    sys.exit(main())

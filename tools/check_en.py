#!/usr/bin/env python3
"""issues.json の英語欄（en）をチェックする。

見ること:
  1. JSONとして読めるか
  2. 日本語の欄が基準（既定は git の HEAD）から1文字も変わっていないか
     … 記事・週間特集から `en` を取り除いた残りを丸ごと比べる
  3. `en` の形（必須欄・型・余計な欄が無いか）
  4. `en` の中身（日本語の文字が無い／m² に sq ft がある／英国式つづりが無い／長さの目安）
  5. 日本語版に無い数字が英語に出ていないか（警告。換算した sq ft・ft・miles は除く）

使い方（リポジトリ直下で）:
  python3 tools/check_en.py --base HEAD --require-latest   … 毎朝ルーチンの英語手順
  python3 tools/check_en.py --base origin/main --require-all … 過去号に一括で付けたとき
エラーが1件でもあれば終了コード1。警告だけなら0。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STORY_REQUIRED = {"title": str, "summary": str, "body": list, "commentary": str}
STORY_OPTIONAL = {"briefing": list, "hojosen": list}
FEATURE_REQUIRED = {"title": str, "heroTitle": str, "dateRangeText": str}

JA_CHARS = re.compile(r"[぀-ヿ㐀-䶿一-鿿！-｠　-〿]")
BRITISH = re.compile(
    r"\b(centre|centres|metre|metres|colour|colours|organisation|organisations|organise[ds]?|"
    r"realise[ds]?|neighbourhood|neighbourhoods|programme|programmes|labour|favour|favourite|"
    r"behaviour|honour|catalogue|analyse[ds]?|licence|defence|travelled|modelling|grey|storey|storeys|"
    r"utilise[ds]?|recognise[ds]?|prioritise[ds]?|minimise[ds]?|maximise[ds]?)\b",
)  # 小文字で始まる語だけ見る（固有名詞の Centre・Theatre などはそのまま書いてよい）
CLICHES = re.compile(
    r"\b(it goes without saying|a testament to|at the end of the day|in conclusion|game[- ]changer|"
    r"paradigm shift|nestled|boasts|it's worth noting|tapestry)\b",
    re.I,
)
SQM = re.compile(r"m²")
SQM_ASCII = re.compile(r"\d\s*(m2|sqm|sq\. ?m|square met(er|re)s?)\b", re.I)


def strip_en(data):
    """記事と週間特集から en を取り除いた写しを返す。"""
    out = json.loads(json.dumps(data))
    for iss in out.get("issues", []):
        for s in iss.get("stories", []):
            s.pop("en", None)
    for f in out.get("weeklyFeatures", []):
        f.pop("en", None)
    return out


def diff_paths(a, b, path="$"):
    if type(a) is not type(b):
        yield f"{path}: 型が違う"
        return
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                yield f"{path}.{k}: 増えた"
            elif k not in b:
                yield f"{path}.{k}: 消えた"
            else:
                yield from diff_paths(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            yield f"{path}: 要素数 {len(a)} → {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diff_paths(x, y, f"{path}[{i}]")
    elif a != b:
        yield f"{path}: 値が変わった"


def texts_of(en: dict) -> list[str]:
    t = [en.get("title", ""), en.get("summary", ""), en.get("commentary", "")]
    t += [p for p in en.get("body", []) if isinstance(p, str)]
    t += [p for p in en.get("briefing", []) if isinstance(p, str)]
    for h in en.get("hojosen", []):
        if isinstance(h, dict):
            t += [h.get("title", ""), h.get("body", "")]
    return [x for x in t if isinstance(x, str)]


def ja_text(story: dict) -> str:
    t = [story.get("title", ""), story.get("summary", ""), story.get("commentary", "")]
    t += story.get("body", []) + story.get("briefing", [])
    for h in story.get("hojosen", []):
        t += [h.get("title", ""), h.get("body", "")]
    s = "".join(x for x in t if isinstance(x, str))
    return s.translate(str.maketrans("０１２３４５６７８９．，", "0123456789.,"))


NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
CONVERTED = re.compile(r"\(\s*(?:about |roughly |around |nearly |over |more than )?[\d,.\s–-]+(?:million |thousand )?(sq ft|square feet|ft|feet|miles?|acres?)[^)]*\)", re.I)
WORD_NUM = {"million": 10**6, "billion": 10**9, "trillion": 10**12, "thousand": 10**3}


def _norm(v: str) -> str:
    return v.rstrip("0").rstrip(".") if "." in v else v


def _fmt(x: float) -> str:
    return _norm(f"{x:.6f}") if x != int(x) else str(int(x))


KANJI_NUM = re.compile(r"(\d+(?:\.\d+)?)(兆|億|万)(?:(\d+(?:\.\d+)?)(億|万))?(\d{1,4})?")
WARI = re.compile(r"(\d+(?:\.\d+)?)割")


def numbers_not_in_ja(en: dict, ja: str) -> list[str]:
    ja = ja.replace(",", "")
    ja_nums = set()
    for m in NUM.finditer(ja):
        ja_nums.add(_norm(m.group()))
    # 「1万2000」「3.3万」「7億4179万9000」「4割」も数字として読む
    unit = {"兆": 10**12, "億": 10**8, "万": 10**4}
    for m in KANJI_NUM.finditer(ja):
        total = float(m.group(1)) * unit[m.group(2)]
        if m.group(3):
            total += float(m.group(3)) * unit[m.group(4)]
        if m.group(5):
            total += int(m.group(5))
        ja_nums.add(_fmt(total))
    for m in WARI.finditer(ja):
        ja_nums.add(_fmt(float(m.group(1)) * 10))
    missing = []
    for text in texts_of(en):
        text = CONVERTED.sub("", text)
        for m in NUM.finditer(text):
            raw = m.group().replace(",", "").rstrip(".")
            v = _norm(raw)
            if not v or v in ja_nums:
                continue
            if len(v) <= 1:  # 1桁は「3 stories」「2 phases」など言い換えが多いので見ない
                continue
            # 「¥1.2 trillion」「100 million」などは、日本語の「1.2兆」「1億」と照合しきれないので、前後の語から許す
            tail = text[m.end():m.end() + 10].strip().lower()
            if any(tail.startswith(w) for w in WORD_NUM):
                continue
            # 序数・年代（1980s, 21st）
            if re.match(r"(st|nd|rd|th|s)\b", text[m.end():m.end() + 3]):
                if v in ja_nums or v[:4] in ja_nums:
                    continue
            missing.append(raw)
    return sorted(set(missing))


def check_story_en(sid: str, story: dict, errors: list, warns: list):
    en = story["en"]
    if not isinstance(en, dict):
        errors.append(f"{sid}: en がオブジェクトではない")
        return
    for k, typ in STORY_REQUIRED.items():
        if k not in en:
            errors.append(f"{sid}: en.{k} が無い")
        elif not isinstance(en[k], typ):
            errors.append(f"{sid}: en.{k} の型が違う（{typ.__name__} のはず）")
    for k, typ in STORY_OPTIONAL.items():
        if k in en and not isinstance(en[k], typ):
            errors.append(f"{sid}: en.{k} の型が違う（{typ.__name__} のはず）")
    extra = set(en) - set(STORY_REQUIRED) - set(STORY_OPTIONAL)
    if extra:
        errors.append(f"{sid}: en に余計な欄 {sorted(extra)}（出典・信頼性は共通の欄に置く）")
    if isinstance(en.get("body"), list):
        if not en["body"] or not all(isinstance(p, str) and p.strip() for p in en["body"]):
            errors.append(f"{sid}: en.body が空、または空の段落がある")
    if isinstance(en.get("briefing"), list) and not all(isinstance(p, str) and p.strip() for p in en["briefing"]):
        errors.append(f"{sid}: en.briefing に空・文字列でない項目がある")
    if isinstance(en.get("hojosen"), list):
        for i, h in enumerate(en["hojosen"]):
            if not (isinstance(h, dict) and set(h) == {"title", "body"} and all(isinstance(h[x], str) and h[x].strip() for x in h)):
                errors.append(f"{sid}: en.hojosen[{i}] は {{title, body}} の文字列で")
    for k in ("title", "summary", "commentary"):
        if isinstance(en.get(k), str) and not en[k].strip():
            errors.append(f"{sid}: en.{k} が空")

    for k, ja_key in (("briefing", "briefing"), ("hojosen", "hojosen")):
        ja_n = len(story.get(ja_key) or [])
        en_n = len(en.get(k) or [])
        if ja_n and k not in en:
            warns.append(f"{sid}: 日本語に {ja_key} があるのに en.{k} が無い")
        elif k in en and en_n != ja_n:
            warns.append(f"{sid}: en.{k} の項目数 {en_n} が日本語 {ja_n} と違う")

    texts = texts_of(en)
    joined = "\n".join(texts)
    if JA_CHARS.search(joined):
        bad = sorted(set(JA_CHARS.findall(joined)))[:10]
        errors.append(f"{sid}: en に日本語の文字・全角記号がある {bad}")
    for t in texts:
        for m in SQM.finditer(t):
            if not re.match(r"\s*\([^)]*sq ft", t[m.end():]):
                errors.append(f"{sid}: m² のあとに (… sq ft) が無い：…{t[max(0, m.start() - 20):m.end() + 20]}…")
        if SQM_ASCII.search(t):
            errors.append(f"{sid}: 面積は m² で書く：…{SQM_ASCII.search(t).group()}…")
    for w in sorted(set(m.group().lower() for m in BRITISH.finditer(joined))):
        errors.append(f"{sid}: 英国式つづり「{w}」→ 米国式に")
    for m in set(x.group().lower() for x in CLICHES.finditer(joined)):
        warns.append(f"{sid}: 決まり文句「{m}」は避ける")
    if re.search(r"\b(?:Hi|Hello),? I'?m Sho\b", joined):
        errors.append(f"{sid}: 名乗り・挨拶は入れない")

    title = en.get("title") or ""
    if isinstance(title, str):
        if not 30 <= len(title) <= 120:
            warns.append(f"{sid}: en.title が {len(title)} 字（目安50〜100）")
        if title.rstrip().endswith("."):
            warns.append(f"{sid}: en.title の文末にピリオド")
    summ = en.get("summary") or ""
    if isinstance(summ, str) and not 80 <= len(summ) <= 360:
        warns.append(f"{sid}: en.summary が {len(summ)} 字（目安120〜300）")
    com = en.get("commentary") or ""
    if isinstance(com, str):
        words = len(com.split())
        if not 90 <= words <= 300:
            warns.append(f"{sid}: en.commentary が {words} 語（目安120〜250）")

    extra_nums = numbers_not_in_ja(en, ja_text(story))
    if extra_nums:
        warns.append(f"{sid}: 日本語版に見当たらない数字 {extra_nums}（換算や言い換えなら可。新しい事実なら消す）")


def load_base(ref: str | None, base_file: str | None):
    if base_file:
        return json.loads(Path(base_file).read_text(encoding="utf-8"))
    raw = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:issues.json"], capture_output=True, text=True, check=True).stdout
    return json.loads(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / "issues.json"))
    ap.add_argument("--base", default="HEAD", help="比べる git ref（既定 HEAD）")
    ap.add_argument("--base-file", help="git の代わりにファイルと比べる")
    ap.add_argument("--no-base", action="store_true", help="日本語欄の照合をしない")
    ap.add_argument("--require-latest", action="store_true", help="最新号の全記事に en が必要")
    ap.add_argument("--require-all", action="store_true", help="全号の全記事に en が必要")
    args = ap.parse_args()

    errors: list[str] = []
    warns: list[str] = []
    try:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"エラー: issues.json が JSON として読めません: {e}")
        return 1

    if not args.no_base:
        try:
            base = load_base(args.base, args.base_file)
        except Exception as e:
            print(f"エラー: 基準（{args.base_file or args.base}）の issues.json を読めません: {e}")
            return 1
        diffs = list(diff_paths(strip_en(base), strip_en(data)))
        if diffs:
            errors.append(f"日本語の欄が基準から変わっています（{len(diffs)}か所）:")
            errors.extend("  " + d for d in diffs[:40])

    issues = data.get("issues", [])
    n_en = n_all = 0
    for idx, iss in enumerate(issues):
        must = args.require_all or (args.require_latest and idx == 0)
        for s in iss.get("stories", []):
            n_all += 1
            sid = s.get("id", f"{iss.get('id')}-?")
            if "en" in s:
                n_en += 1
                check_story_en(sid, s, errors, warns)
            elif must:
                errors.append(f"{sid}: en が無い")
    for f in data.get("weeklyFeatures", []):
        if "en" not in f:
            continue
        en = f["en"]
        fid = f.get("id", "feature-?")
        if not isinstance(en, dict):
            errors.append(f"{fid}: en がオブジェクトではない")
            continue
        for k, typ in FEATURE_REQUIRED.items():
            if not isinstance(en.get(k), typ) or not en.get(k).strip():
                errors.append(f"{fid}: en.{k} が無い・空")
        if set(en) - set(FEATURE_REQUIRED):
            errors.append(f"{fid}: en に余計な欄 {sorted(set(en) - set(FEATURE_REQUIRED))}")
        if JA_CHARS.search(json.dumps(en, ensure_ascii=False)):
            errors.append(f"{fid}: en に日本語の文字がある")

    for w in warns:
        print("警告:", w)
    for e in errors:
        print("エラー:", e)
    print(f"英語あり {n_en}/{n_all} 本 / エラー {sum(1 for e in errors if not e.startswith('  '))} 件 / 警告 {len(warns)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

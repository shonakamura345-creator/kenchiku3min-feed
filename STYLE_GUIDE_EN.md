# 英語版の書き方ルール（STYLE_GUIDE_EN）

作成：技術・効率化部門／2026-11-03（v1.5 英語版・Sho決定「日本の建築ニュースを英語で届ける」）
用途：毎朝のルーチンと、過去号の英語化で、各記事の `en` 欄を書くときの決まり。英語の記事は**承認なしで配信される**ので、品質はこのルールと `tools/check_en.py` で担保する。

---

## 0. 誰に向けて書くか

- 読者は**海外の建築好き・建築関係者**（建築家、設計事務所の人、学生、都市やデザインに興味のある一般の人）。日本語は読めない。日本の地名・制度・業界の慣習も知らない前提。
- 目的は「日本でいま建築まわりに何が起きているか」を英語で伝えること。日本語の記事を**直訳しない**。同じ事実を、英語圏の読者がつまずかない順番と言葉で書き直す。
- 例：「皇居東御苑内」→ *the East Gardens of the Imperial Palace, the public part of the palace grounds in central Tokyo*

## 1. 守ること（最重要）

1. **事実は日本語の記事と同じ。足さない・盛らない・変えない。** 数字・日付・固有名詞・発言は日本語版にあるものだけ。日本語版に無い数値、理由、見通し、評価を英語で付け足さない。
2. **足してよいのは「説明」だけ。** 地名・制度・組織・業界用語に、海外の読者向けの短い説明（数語〜1文）を足す。説明に使ってよいのは、変わらない一般常識（「建築確認は着工前に図面が建築基準法に合っているかを確かめる手続き」「大手町は東京駅の西側のオフィス街」など）だけ。ニュースの中身に関わる新しい事実を説明のふりをして足さない。自信がない説明は書かない。
3. **解説（commentary）は日本語の解説と同じ主張にする。** 結論・問いかけ・例え・締めの型を変えない。言い回しは英語として自然にしてよいが、日本語に無い意見や、より強い断定を足さない。
4. **体験・感想の創作禁止は英語でも同じ。** 日本語の解説に無い「I visited」「I love」などを書かない。
5. **容疑・推定の表現を弱めない。** 「〜の疑い」は *allegedly / is suspected of / on suspicion of*。有罪と読める書き方にしない。
6. **出典は共通。** `sources` `sourceName` `sourceURL` `reliability` `shoComment` は英語にしない・`en` の中に入れない。日本語の出典しかなくても、そのまま。

## 2. 表記

- **米国英語**（color, center, meter, organization, neighborhood, program, gray, theater。固有名詞の Theatre・Centre はそのまま（チェックは小文字の語だけ見る））。日付は *Nov 3, 2026* / *November 3*。
- **面積**：`m²` のあとに括弧で平方フィート。*about 1,300 m² (14,000 sq ft)*。換算は 1 m² = 10.764 sq ft。換算後は**有効数字2〜3桁に丸める**（元の数字が「約」なら about を付ける）。日本語版の `m2` は英語では `m²` と書く。坪は *tsubo (about 3.3 m² / 35.6 sq ft)* と最初に一度説明する。
- **長さ・高さ**：メートルのあとに括弧でフィート。*180 m (590 ft)*。km は *12 km (7.5 miles)*。階数は *a 40-story tower*。
- **お金**：円のまま書き、括弧で概算ドルを足さない（為替で変わるため）。大きい数は *¥1.2 trillion*、*¥100 million*（1億円）。「1億円を超えた」は *topped ¥100 million*。
- **人名**：名→姓の順（*Toyo Ito*、*Kengo Kuma*）。報道で広く出ている名前だけ。肩書きは *architect Toyo Ito*。
- **社名**：英語の正式名があればそれ（*Takenaka Corporation*、*Nikken Sekkei*、*Kajima Corporation*、*Taisei Corporation*、*Mitsui Fudosan*、*Mori Building*）。無ければローマ字。
- **地名**：ローマ字＋必要なら場所の説明。*Shibuya's Sakuragaoka district*、*Hamamatsu, a city in Shizuoka Prefecture between Tokyo and Osaka*。都道府県は *Prefecture*、区は *ward*（*Chiyoda Ward*）。
- **固有名詞の訳**：施設名は英語の公式名があればそれ。無ければローマ字＋意味（*Sannomaru Shozokan (the Museum of the Imperial Collections)*）。
- **組織・制度の略語**：初出でフルスペル＋何の組織か。*the Japan Federation of Construction Contractors (Nikkenren), the main lobby group for Japan's general contractors*。国土交通省は *the Ministry of Land, Infrastructure, Transport and Tourism (MLIT)*。
- 長音記号（ō, ū）は付けない（*Tokyo*, *Osaka*, *Kyoto*。他の語も *Shozokan* のように付けない）。
- 日本語の文字（ひらがな・カタカナ・漢字）、全角記号（「」『』、。・（）〜）を `en` に入れない。かぎ括弧は英語の引用符 “ ” か ' に。

## 3. 欄ごとの書き方

| 欄 | 目安 | 書き方 |
|---|---|---|
| `title` | 50〜100字（半角） | 何が起きたかを主語＋動詞で。先頭は大文字、文末にピリオドなし。日本語の「続報：」は *Update:*。地名は国外読者向けに Tokyo / Osaka などを入れる |
| `summary` | 120〜300字 | 2文程度。誰が・何を・どこで・いつ。地名に一言の説明を入れてよい |
| `body` | 段落2〜4個 | 日本語の段落と同じ事実を、英語ニュースの順番（結論→詳細→今後）で。説明はここで足す。日本語の「◯月◯日号でお伝えした」は *as we reported on Oct 12* |
| `commentary` | 120〜250語 | 下の「解説の声」を守る |
| `briefing` | 日本語と同じ項目数 | 箇条書きの各項目を英語に。説明を足してよい |
| `hojosen` | 日本語と同じ項目数 | `title` は2〜5語の見出し（*Rebuilding while staying open*）、`body` は2〜4文。アプリでは「Background」として出る |

- `en` に入れるのは `title` `summary` `body` `commentary`（必須）と `briefing` `hojosen`（日本語版にあれば付ける）だけ。
- 建築の専門用語は英語圏の言い方に（*building permit review* / *floor area ratio (FAR)* / *seismic retrofit* / *design-build* / *general contractor* / *glulam* / *CLT*）。日本独自の制度は、英語名＋一言の説明。

### よく出る日本の言葉の説明例
- 建築確認：*building confirmation, Japan's pre-construction check that a design complies with the Building Standards Act*
- 一級建築士：*first-class kenchikushi, Japan's top architect license, which covers buildings of any size*
- 二級建築士：*second-class kenchikushi, a license limited to smaller buildings*
- 容積率：*floor area ratio (FAR)*、容積率の緩和：*a floor-area bonus*
- ゼネコン：*general contractor*。スーパーゼネコン：*Japan's five largest general contractors (Kajima, Obayashi, Shimizu, Taisei and Takenaka)*
- 重要文化財：*Important Cultural Property, Japan's main national heritage designation for buildings and objects*
- 再開発：*redevelopment*。市街地再開発事業：*an urban redevelopment project, a Japanese scheme in which landowners pool their plots to build a larger complex*
- 耐震基準：*seismic code*。新耐震基準（1981年）：*the 1981 seismic code, the line that separates older and newer buildings in Japan*
- 文化の日：*Culture Day, a national holiday on November 3*
- 週休2日・4週8閉所：*two days off a week* / *closing sites eight days every four weeks*

## 4. 解説（commentary）の声

- 名義は「Sho建築士AI」（アプリとWebは *Commentary by Sho Architect AI* と出す）。**一人称は I**。読者には **you**。
- 話し言葉の短い文。*Here's the thing.* / *That's the key part.* のような軽いつなぎはよいが、毎回同じものを使わない。
- 日本語の問いかけ（〜ですよね／〜じゃないですか）は *right?* / *Don't you think?* / *Isn't it?* などで1回残す（事件・災害の記事では軽くしない）。
- 日本語の例え（コンビニ、お風呂の残響など）はそのまま使う。海外の読者に通じにくいものは一言足す（*a Japanese convenience store, the kind on every corner*）。例えを別のものに差し替えない。
- 締めの型は日本語と同じ型（行動提案／問いを残す／事実で落とす／短い所感）。日本語の行動提案が日本国内でしかできない行動なら、意味を変えずに *If you're ever in Tokyo, …* と前置きしてよい。
- 禁止表現：*It goes without saying* / *a testament to* / *at the end of the day* / *In conclusion* / *truly* の多用 / *game-changer* / *paradigm shift* / *nestled* / *boasts* / *it's worth noting that* などのAIっぽい決まり文句。抽象語（*story*, *journey*, *tapestry*）で締めない。
- 名乗りや挨拶（*Hi, I'm Sho*）は入れない。

## 5. 自己チェック（コミット前に必ず）

1. `python3 tools/check_en.py --base HEAD` を実行し、**エラー0件**であること。警告は読んで直せるものは直す。
   - これは「日本語の欄が1文字も変わっていない」「`en` の必須欄がある」「`en` に日本語の文字が無い」「`m²` に sq ft がある」「英国式のつづりが無い」などを機械的に見る。
2. 1本ずつ日本語版と並べて、**数字・日付・固有名詞が一致しているか**を目で確かめる（換算した sq ft と ft 以外に、日本語版に無い数字が無いこと）。
3. 説明として足した文が、一般常識の範囲か（ニュースの新事実を足していないか）。
4. 解説の主張・締めの型が日本語版と同じか。体験談を足していないか。
5. 容疑・推定の表現が弱まっていないか。

## 6. 例（2026-11-03号 s1 の書き出し）

- 日本語：皇居三の丸尚蔵館がきょう全面開館 2期棟が加わり展示面積は約8倍、若冲の全30幅も
- 英語 title：*Imperial Palace museum Sannomaru Shozokan fully reopens with 8x the gallery space*
- 英語 body の一部：*The museum, which holds art passed down through Japan's imperial family, sits in the East Gardens of the Imperial Palace, the part of the palace grounds in central Tokyo that is open to the public. … Total gallery space grew about eightfold, from about 160 m² (1,700 sq ft) to about 1,300 m² (14,000 sq ft).*

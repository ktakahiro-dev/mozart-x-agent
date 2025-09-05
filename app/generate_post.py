
import os, sys, re, json, base64, time, datetime
from zoneinfo import ZoneInfo
import tweepy
from PIL import Image
from openai import OpenAI

# ====== Config via env ======
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TEXT_MODEL = os.getenv("OPENAI_MODEL_TEXT", "gpt-4o-mini")
TEXT_MODEL_FALLBACK = os.getenv("OPENAI_MODEL_TEXT_FALLBACK", "gpt-4o")
IMAGE_MODEL = os.getenv("OPENAI_MODEL_IMAGE", "gpt-image-1")

X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

OUT_DIR = os.getenv("OUT_DIR", "out")
IMG_FILENAME = os.getenv("IMG_FILENAME", "mozart_post.png")
MAX_TRIES = int(os.getenv("OPENAI_MAX_TRIES", "3"))

# final output 16:9 for X
TARGET_W, TARGET_H = 1600, 900
# allowed by gpt-image-1 (landscape)
GEN_SIZE = "1536x1024"

os.makedirs(OUT_DIR, exist_ok=True)

# ---- famous works (curated) ----
def famous_works():
    # Each item: k, ja_title, en_title, type, seasons, times
    return [
        {"k":"K.525","ja_title":"アイネ・クライネ・ナハトムジーク","en_title":"Serenade No. 13 in G, \"Eine kleine Nachtmusik\"","type":"Serenade","seasons":["夏","春","秋"],"times":["夕暮れ","夜"]},
        {"k":"K.550","ja_title":"交響曲第40番 ト短調","en_title":"Symphony No. 40 in G minor","type":"Symphony","seasons":["秋","冬"],"times":["夕暮れ","夜"]},
        {"k":"K.551","ja_title":"交響曲第41番 ハ長調『ジュピター』","en_title":"Symphony No. 41 in C, \"Jupiter\"","type":"Symphony","seasons":["春","夏"],"times":["朝","昼"]},
        {"k":"K.626","ja_title":"レクイエム ニ短調","en_title":"Requiem in D minor","type":"Choral","seasons":["秋","冬"],"times":["夕暮れ","夜"]},
        {"k":"K.620","ja_title":"歌劇『魔笛』","en_title":"The Magic Flute","type":"Opera","seasons":["夏","秋"],"times":["夕暮れ","夜"]},
        {"k":"K.492","ja_title":"歌劇『フィガロの結婚』","en_title":"The Marriage of Figaro","type":"Opera","seasons":["春"],"times":["朝","昼"]},
        {"k":"K.527","ja_title":"歌劇『ドン・ジョヴァンニ』","en_title":"Don Giovanni","type":"Opera","seasons":["秋"],"times":["夜"]},
        {"k":"K.467","ja_title":"ピアノ協奏曲第21番 ハ長調","en_title":"Piano Concerto No. 21 in C","type":"Piano Concerto","seasons":["春","夏"],"times":["朝","昼"]},
        {"k":"K.488","ja_title":"ピアノ協奏曲第23番 イ長調","en_title":"Piano Concerto No. 23 in A","type":"Piano Concerto","seasons":["春","秋"],"times":["昼","夕暮れ"]},
        {"k":"K.466","ja_title":"ピアノ協奏曲第20番 ニ短調","en_title":"Piano Concerto No. 20 in D minor","type":"Piano Concerto","seasons":["冬","秋"],"times":["夕暮れ","夜"]},
        {"k":"K.331","ja_title":"ピアノソナタ第11番 イ長調『トルコ行進曲付き』","en_title":"Piano Sonata No. 11 in A (\"Alla Turca\")","type":"Piano Sonata","seasons":["春","夏"],"times":["朝","昼"]},
        {"k":"K.183","ja_title":"交響曲第25番 ト短調","en_title":"Symphony No. 25 in G minor","type":"Symphony","seasons":["秋","冬"],"times":["夕暮れ","夜"]},
        {"k":"K.201","ja_title":"交響曲第29番 イ長調","en_title":"Symphony No. 29 in A","type":"Symphony","seasons":["春","夏"],"times":["朝","昼"]},
        {"k":"K.361","ja_title":"セレナード第10番 変ロ長調『グラン・パルティータ』","en_title":"Serenade No. 10 in B♭, \"Gran Partita\"","type":"Serenade","seasons":["春","夏"],"times":["夕暮れ","夜"]},
        {"k":"K.622","ja_title":"クラリネット協奏曲 イ長調","en_title":"Clarinet Concerto in A","type":"Concerto","seasons":["秋"],"times":["夕暮れ","夜"]},
        {"k":"K.581","ja_title":"クラリネット五重奏曲 イ長調","en_title":"Clarinet Quintet in A","type":"Chamber","seasons":["秋"],"times":["夕暮れ","夜"]},
        {"k":"K.618","ja_title":"アヴェ・ヴェルム・コルプス","en_title":"Ave verum corpus","type":"Choral","seasons":["夏"],"times":["夕暮れ","夜"]},
        {"k":"K.265","ja_title":"きらきら星変奏曲","en_title":"Twelve Variations on \"Ah vous dirai-je, Maman\" (Twinkle Variations)","type":"Piano","seasons":["春","夏","秋","冬"],"times":["朝","昼"]},
        {"k":"K.397","ja_title":"幻想曲 ニ短調","en_title":"Fantasia in D minor","type":"Piano","seasons":["冬","秋"],"times":["夜"]},
        {"k":"K.216","ja_title":"ヴァイオリン協奏曲第3番 ト長調","en_title":"Violin Concerto No. 3 in G","type":"Violin Concerto","seasons":["春"],"times":["昼","朝"]},
        {"k":"K.218","ja_title":"ヴァイオリン協奏曲第4番 ニ長調","en_title":"Violin Concerto No. 4 in D","type":"Violin Concerto","seasons":["春","夏"],"times":["昼"]},
        {"k":"K.219","ja_title":"ヴァイオリン協奏曲第5番 イ長調『トルコ風』","en_title":"Violin Concerto No. 5 in A \"Turkish\"","type":"Violin Concerto","seasons":["夏","秋"],"times":["昼","夕暮れ"]},
        {"k":"K.317","ja_title":"ミサ曲 ハ長調『戴冠式ミサ』","en_title":"Coronation Mass in C","type":"Choral","seasons":["春"],"times":["朝","昼"]},
        {"k":"K.320","ja_title":"セレナード第9番 ニ長調『ポストホルン』","en_title":"Serenade No. 9 in D, \"Posthorn\"","type":"Serenade","seasons":["夏"],"times":["夕暮れ","夜"]},
        {"k":"K.545","ja_title":"ピアノソナタ第16番 ハ長調『ソナタ・ファチレ』","en_title":"Piano Sonata No. 16 in C, \"Sonata facile\"","type":"Piano Sonata","seasons":["春","夏","秋","冬"],"times":["朝","昼"]},
        {"k":"K.136","ja_title":"ディヴェルティメント ニ長調","en_title":"Divertimento in D, K.136","type":"Divertimento","seasons":["春"],"times":["朝","昼"]},
        {"k":"K.314","ja_title":"オーボエ協奏曲 ハ長調","en_title":"Oboe Concerto in C","type":"Concerto","seasons":["春"],"times":["昼"]},
    ]

# ---- helpers ----
EMOJI_RE = re.compile(r"[\\U0001F300-\\U0001FAFF\\U00002700-\\U000027BF]")
HASHTAG_RE = re.compile(r"#\\S+")

def now_jst():
    return datetime.datetime.now(ZoneInfo("Asia/Tokyo"))

def part_of_day(hour: int) -> str:
    if 5 <= hour < 11: return "朝"
    if 11 <= hour < 16: return "昼"
    if 16 <= hour < 20: return "夕暮れ"
    return "夜"

def season_by_month(m: int) -> dict:
    if m in (3,4,5):
        return {"jp":"春","palette":"soft sakura pink, fresh green, ivory","motifs":"petals, gentle breeze","text_hint":"春のやわらかな空気"}
    if m in (6,7,8):
        return {"jp":"夏","palette":"deep indigo, night blue, gold","motifs":"fireflies, cool water ripples, starry sky","text_hint":"夏の夜風"}
    if m in (9,10,11):
        return {"jp":"秋","palette":"amber, russet, smoky blue","motifs":"falling leaves, harvest glow","text_hint":"秋の深まる色合い"}
    return {"jp":"冬","palette":"snow white, silver, charcoal","motifs":"snowflakes, crisp air","text_hint":"冬の澄んだ空気"}

def clamp(s: str, max_len: int):
    s = (s or "").strip()
    return s if len(s) <= max_len else s[:max_len-1] + "…"

def strip_hashtags(s: str) -> str:
    s = HASHTAG_RE.sub("", s or "")
    s = re.sub(r"\\s{2,}", " ", s).strip()
    return s

def ensure_one_emoji(s: str) -> str:
    if not EMOJI_RE.search(s or ""):
        s2 = (s + " 🎵").strip()
        return clamp(s2, 120)
    return s

def extract_json(text: str) -> str:
    m = re.search(r"\\{.*\\}", text, re.S)
    if m:
        return m.group(0)
    m2 = re.search(r"```(?:json)?\\s*(\\{.*\\})\\s*```", text, re.S|re.I)
    if m2:
        return m2.group(1)
    return text.strip()

def choose_piece_auto(today: datetime.date):
    works = famous_works()
    jst = now_jst()
    pod = part_of_day(jst.hour)
    sea = season_by_month(jst.month)["jp"]

    # Filter by season & time
    cands = [w for w in works if (sea in w["seasons"] or "春夏秋冬" in "".join(w["seasons"])) and (pod in w["times"] or "朝昼夕暮れ夜" in "".join(w["times"]))]
    if not cands:
        # relax: match either season or time
        cands = [w for w in works if sea in w["seasons"] or pod in w["times"]]
    if not cands:
        cands = works[:]  # fallback all

    # Deterministic pick for the day
    seed = int(today.strftime("%Y%m%d"))
    idx = seed % len(cands)
    return cands[idx]

def prompt_text(piece: dict) -> str:
    jst = now_jst()
    dow = "月火水木金土日"[jst.weekday()]
    pod = part_of_day(jst.hour)
    sea = season_by_month(jst.month)
    date_str = jst.strftime("%Y年%m月%d日")
    time_str = jst.strftime("%H:%M")
    return f"""日本語でモーツァルト作品のX投稿文をJSONで返してください。JSON以外は一切書かないでください。
以下の要素を自然に織り込みます：日付({date_str})、時刻({time_str} JST)、曜日({dow})、時間帯({pod})、季節({sea['jp']}:{sea['text_hint']})。
{{
  "tweet": "<全角込み120字以内。季節感と時間帯に触れる。絵文字を1つ入れる。ハッシュタグは入れない（記号#を使わない）>",
  "alt": "<画像の代替テキスト。80-120字。『モーツァルトのイラスト』＋季節/時間帯の雰囲気（色・モチーフ）を簡潔に。絵文字/ハッシュタグは入れない>",
  "img_caption": "<画像に入れる短い見出し（8-12字）。絵文字とハッシュタグは入れない>"
}}
対象作品: {piece["ja_title"]}（{piece["en_title"]}） / {piece["k"]}
口調: 温かく簡潔。専門用語を避ける。
"""

def infer_mood(piece: dict):
    title_en = (piece.get("en_title","") or "").lower()
    title_ja = piece.get("ja_title","") or ""
    ptype = (piece.get("type","") or "").lower()
    is_minor = " minor" in title_en or "短調" in title_ja
    mood = {"palette":"cream, gray, subtle gold","mood":"elegant, balanced","motifs":"abstract staves and notes"}

    if "requiem" in title_en or "レクイエム" in title_ja or piece.get("k")=="K.626":
        mood = {"palette":"deep purple, charcoal, candlelight gold","mood":"solemn, spiritual, reverent","motifs":"soft choir silhouettes, candlelight glow"}
    elif "nachtmusik" in title_en or "ナハトムジーク" in title_ja:
        mood = {"palette":"midnight blue, silver, soft cream","mood":"serene, nocturnal, tender","motifs":"starry night hints, crescent moon"}
    elif "clarinet" in title_en or "クラリネット" in title_ja:
        mood = {"palette":"warm amber, ivory, slate","mood":"warm, lyrical, woody","motifs":"clarinet silhouette, flowing breath lines"}
    elif "piano" in ptype or "sonata" in title_en:
        mood = {"palette":"ivory, ebony, antique gold","mood":"graceful, clear, intimate","motifs":"piano keys silhouette, delicate staves"}
    elif "symphony" in ptype:
        if is_minor:
            mood = {"palette":"smoky indigo, graphite, silver","mood":"dramatic, tense, stormy","motifs":"bold diagonal staves, energetic accents"}
        else:
            mood = {"palette":"cream, gold, light blue","mood":"bright, spirited, festive","motifs":"radiant staves, airy ornaments"}
    elif "opera" in ptype:
        mood = {"palette":"crimson velvet, gold, ebony","mood":"theatrical, lively","motifs":"stage curtains, mask hints"}
    return mood

def prompt_image(piece: dict, caption: str) -> str:
    jst = now_jst()
    pod = part_of_day(jst.hour)
    sea = season_by_month(jst.month)
    m = infer_mood(piece)
    return f"""Elegant poster-like illustration, landscape 1536x1024.
Include a tasteful illustrated bust/portrait of Wolfgang Amadeus Mozart (non-photorealistic, engraving/etching style).
Base mood from piece: palette {m['palette']}, mood {m['mood']}, motifs {m['motifs']}.
Blend seasonal atmosphere ({sea['jp']}): palette accents {sea['palette']}; motifs {sea['motifs']}.
Reflect time of day ({pod}) with lighting (e.g., morning soft light / dusk glow / night calm).
Background: soft paper texture. Keep key elements near center; leave generous top/bottom margins for safe 16:9 crop.
Place the Japanese headline "{caption}" centered with high readability.
"""

def call_chat(client: OpenAI, model: str, prompt: str) -> str:
    rsp = client.chat.completions.create(
        model=model,
        messages=[{"role":"user","content":prompt}],
        temperature=0.7
    )
    return rsp.choices[0].message.content or ""

def gen_text_alt_caption(client: OpenAI, piece: dict):
    last_error = None
    for model in [TEXT_MODEL, TEXT_MODEL_FALLBACK]:
        for attempt in range(1, MAX_TRIES+1):
            try:
                raw = call_chat(client, model, prompt_text(piece))
                blob = extract_json(raw)
                data = json.loads(blob)
                tweet = clamp(strip_hashtags(data.get("tweet","")), 120)
                alt = clamp(strip_hashtags(data.get("alt","")), 120)
                caption = clamp(strip_hashtags(data.get("img_caption", piece["ja_title"])), 12)
                tweet = ensure_one_emoji(tweet)
                print(f"[INFO] used_model={model}, attempt={attempt}, json_ok=True")
                return tweet, alt, caption
            except Exception as e:
                last_error = e
                print(f"[WARN] JSON parse failed (model={model}, attempt={attempt}): {e}")
                time.sleep(1.2 * attempt)

    jst = now_jst()
    pod = part_of_day(jst.hour)
    sea = season_by_month(jst.month)
    tweet = ensure_one_emoji(clamp(f"{pod}のひと息に、{sea['text_hint']}とともに{piece['ja_title']}を。", 120))
    alt = clamp(f"モーツァルトのイラスト。{sea['jp']}の雰囲気と{pod}の光を感じる上品な背景ポスター。", 120)
    caption = clamp(piece['ja_title'], 12)
    print(f"[INFO] used_model=fallback_template, json_ok=False")
    return tweet, alt, caption

def gen_image_and_fit(client: OpenAI, piece: dict, caption: str, out_path: str):
    img = client.images.generate(model=IMAGE_MODEL, prompt=prompt_image(piece, caption), size=GEN_SIZE)
    b64 = img.data[0].b64_json
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))

    im = Image.open(out_path)
    w, h = im.size  # expect 1536x1024
    target_ratio = TARGET_W / TARGET_H
    new_h = int(round(w / target_ratio))  # 1536 -> 864
    if new_h <= h:
        top = (h - new_h) // 2  # 1024-864=160 -> 80px top/bottom
        im = im.crop((0, top, w, top + new_h))
    else:
        new_w = int(round(h * target_ratio))
        left = (w - new_w) // 2
        im = im.crop((left, 0, left + new_w, h))
    im = im.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    im.save(out_path)

def post_to_x(text: str, image_path: str, alt_text: str):
    client_v2 = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET,
        bearer_token=X_BEARER_TOKEN
    )

    media_ids = None
    try:
        auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(filename=image_path)
        api_v1.create_media_metadata(media_id=media.media_id, alt_text=alt_text)
        media_ids = [media.media_id]
    except tweepy.errors.BadRequest as e:
        print("[WARN] media upload BadRequest. Posting text-only.", e)
    except tweepy.errors.Forbidden as e:
        print("[WARN] media upload Forbidden. Posting text-only.", e)

    if media_ids:
        return client_v2.create_tweet(text=text, media_ids=media_ids)
    else:
        return client_v2.create_tweet(text=text)

def main():
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=OPENAI_API_KEY)

    today = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).date()
    piece = choose_piece_auto(today)

    tweet, alt, caption = gen_text_alt_caption(client, piece)
    print("[OUT] piece:", piece["k"], piece["ja_title"])
    print("[OUT] tweet:", tweet)
    print("[OUT] alt  :", alt)
    print("[OUT] caption:", caption)

    out_img = os.path.join(OUT_DIR, IMG_FILENAME)
    gen_image_and_fit(client, piece, caption, out_img)
    print("[OUT] image saved:", out_img)

    if all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, X_BEARER_TOKEN]):
        resp = post_to_x(tweet, out_img, alt)
        print("[OK] tweeted:", resp.data)
    else:
        print("[SKIP] X credentials missing; tweet not posted.")

if __name__ == "__main__":
    main()

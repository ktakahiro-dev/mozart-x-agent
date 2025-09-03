
import os, sys, re, json, base64, time, datetime
import pandas as pd
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

CATALOG_CSV = os.getenv("CATALOG_CSV", "data/mozart_catalog.csv")
OUT_DIR = os.getenv("OUT_DIR", "out")
IMG_FILENAME = os.getenv("IMG_FILENAME", "mozart_post.png")
MAX_TRIES = int(os.getenv("OPENAI_MAX_TRIES", "3"))

# final output 16:9 for X
TARGET_W, TARGET_H = 1600, 900
# allowed by gpt-image-1 (landscape)
GEN_SIZE = "1536x1024"

os.makedirs(OUT_DIR, exist_ok=True)

# ---- helpers ----
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF]")  # broad emoji range
HASHTAG_RE = re.compile(r"#\S+")

def choose_piece(today: datetime.date, path: str):
    df = pd.read_csv(path)
    row = df.iloc[today.toordinal() % len(df)]
    return row.to_dict()

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
    m = re.search(r'\\{.*\\}', text, re.S)
    if m:
        return m.group(0)
    m2 = re.search(r'```(?:json)?\\s*(\\{.*\\})\\s*```', text, re.S|re.I)
    if m2:
        return m2.group(1)
    return text.strip()

def infer_mood(piece: dict):
    title_en = (piece.get("en_title","") or "").lower()
    title_ja = piece.get("ja_title","") or ""
    ptype = (piece.get("type","") or "").lower()
    kcat = piece.get("k","") or ""

    is_minor = " minor" in title_en or "短調" in title_ja
    mood = {"palette":"cream, gray, subtle gold","mood":"elegant, balanced","motifs":"abstract staves and notes"}

    if "requiem" in title_en or "レクイエム" in title_ja or "K.626" in kcat:
        mood = {"palette":"deep purple, charcoal, candlelight gold",
                "mood":"solemn, spiritual, reverent",
                "motifs":"soft choir silhouettes, candlelight glow"}
    elif "serenade" in title_en or "ナハトムジーク" in title_ja:
        mood = {"palette":"midnight blue, silver, soft cream",
                "mood":"serene, nocturnal, tender",
                "motifs":"starry night hints, crescent moon"}
    elif "clarinet" in title_en or "クラリネット" in title_ja:
        mood = {"palette":"warm amber, ivory, slate",
                "mood":"warm, lyrical, woody",
                "motifs":"clarinet silhouette, flowing breath lines"}
    elif "piano" in title_en or "ピアノ" in title_ja or "sonata" in title_en:
        mood = {"palette":"ivory, ebony, antique gold",
                "mood":"graceful, clear, intimate",
                "motifs":"piano keys silhouette, delicate staves"}
    elif "symphony" in ptype:
        if is_minor:
            mood = {"palette":"smoky indigo, graphite, silver",
                    "mood":"dramatic, tense, stormy",
                    "motifs":"bold diagonal staves, energetic accents"}
        else:
            mood = {"palette":"cream, gold, light blue",
                    "mood":"bright, spirited, festive",
                    "motifs":"radiant staves, airy ornaments"}
    return mood

def prompt_text(piece: dict) -> str:
    return f"""日本語でモーツァルト作品のX投稿文をJSONで返してください。JSON以外は一切書かないでください。
{{
  "tweet": "<全角込み120字以内。絵文字を1つ入れる。ハッシュタグは入れない（記号#を使わない）>",
  "alt": "<画像の代替テキスト。80-120字。『モーツァルトのイラスト』と背景の雰囲気（色・モチーフ）を簡潔に説明。絵文字/ハッシュタグは入れない>",
  "img_caption": "<画像に入れる短い見出し（8-12字）。絵文字とハッシュタグは入れない>"
}}
対象作品: {piece["ja_title"]}（{piece["en_title"]}） / {piece["k"]}
口調: 温かく簡潔。専門用語を避ける。
"""

def prompt_image(piece: dict, caption: str) -> str:
    m = infer_mood(piece)
    return f"""Elegant poster-like illustration, landscape 1536x1024.
Include a tasteful **illustrated bust/portrait of Wolfgang Amadeus Mozart** in engraving/etching style (non-photorealistic), balanced with the layout so text remains readable.
Background: soft paper texture. Motifs: {m['motifs']}.
Color palette: {m['palette']}. Mood: {m['mood']}.
Place the Japanese headline "{caption}" centered, high readability (ample contrast).
Keep key elements near center; leave generous top/bottom margins to allow safe 16:9 cropping.
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
                print(f"[INFO] used_model={{model}}, attempt={{attempt}}, json_ok=True")
                return tweet, alt, caption
            except Exception as e:
                last_error = e
                print(f"[WARN] JSON parse failed (model={{model}}, attempt={{attempt}}): {{e}}")
                time.sleep(1.2 * attempt)

    tweet = ensure_one_emoji(clamp(f"{piece['ja_title']}。朝のひと時にどうぞ。", 120))
    alt = clamp(f"モーツァルトのイラストと{piece['ja_title']}の雰囲気を表す上品な背景ポスター。", 120)
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

    today = datetime.date.today()
    piece = choose_piece(today, CATALOG_CSV)

    tweet, alt, caption = gen_text_alt_caption(client, piece)
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

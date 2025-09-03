
import os, sys, re, json, base64, time, datetime
import pandas as pd
import tweepy
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

os.makedirs(OUT_DIR, exist_ok=True)

def choose_piece(today: datetime.date, path: str):
    df = pd.read_csv(path)
    row = df.iloc[today.toordinal() % len(df)]
    return row.to_dict()

def clamp(s: str, max_len: int):
    s = (s or "").strip()
    return s if len(s) <= max_len else s[:max_len-1] + "…"

def extract_json(text: str) -> str:
    # 1) direct JSON block
    m = re.search(r'\{.*\}', text, re.S)
    if m:
        return m.group(0)
    # 2) if fenced code block with json
    m2 = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.S|re.I)
    if m2:
        return m2.group(1)
    return text.strip()

def prompt_text(piece: dict) -> str:
    return f"""日本語でモーツァルト作品のX投稿文をJSONで返してください。JSON以外は一切書かないでください。
{{
  "tweet": "<全角込み120字以内。ハッシュタグ #Mozart #クラシック を含める>",
  "alt": "<画像の代替テキスト。80-120字>",
  "img_caption": "<画像に入れる短い見出し（8-12字）>"
}}
対象作品: {piece["ja_title"]}（{piece["en_title"]}） / {piece["k"]}
口調: 温かく簡潔。専門用語を避ける。
"""

def prompt_image(piece: dict, caption: str) -> str:
    return f"""横長16:9（1600x900px）。上品で落ち着いたビジュアル。背景は柔らかな紙質、譜面・五線・楽器シルエットを抽象的に。
中央に「{caption}」だけを明瞭に配置。色調は白〜生成・グレー基調に金のアクセント。余白多めで可読性重視。"""

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
                tweet = clamp(data.get("tweet",""), 120)
                alt = clamp(data.get("alt",""), 120)
                caption = clamp(data.get("img_caption", piece["ja_title"]), 12)
                print(f"[INFO] used_model={model}, attempt={attempt}, json_ok=True")
                return tweet, alt, caption, model, True, raw
            except Exception as e:
                last_error = e
                print(f"[WARN] JSON parse failed (model={model}, attempt={attempt}): {e}")
                time.sleep(1.2 * attempt)

    # Fallback: template text
    tweet = clamp(f"{piece['ja_title']}。朝のひと時にどうぞ。 #Mozart #クラシック", 120)
    alt = clamp(f"{piece['ja_title']}（{piece['en_title']}）。モーツァルトの魅力をやさしく伝えるイメージ。", 120)
    caption = clamp(piece['ja_title'], 12)
    print(f"[INFO] used_model=fallback_template, json_ok=False, last_error={last_error}")
    return tweet, alt, caption, "fallback", False, ""

def gen_image(client: OpenAI, piece: dict, caption: str, out_path: str):
    img = client.images.generate(model=IMAGE_MODEL, prompt=prompt_image(piece, caption), size="1600x900")
    b64 = img.data[0].b64_json
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))

def post_to_x(text: str, image_path: str, alt_text: str):
    # v1.1 for media upload
    auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
    api_v1 = tweepy.API(auth)
    media = api_v1.media_upload(filename=image_path)
    api_v1.create_media_metadata(media_id=media.media_id, alt_text=alt_text)

    # v2 for tweet
    client_v2 = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET,
        bearer_token=X_BEARER_TOKEN
    )
    return client_v2.create_tweet(text=text, media_ids=[media.media_id])

def main():
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=OPENAI_API_KEY)

    today = datetime.date.today()
    piece = choose_piece(today, CATALOG_CSV)

    tweet, alt, caption, used_model, json_ok, raw = gen_text_alt_caption(client, piece)
    print("[OUT] tweet:", tweet)
    print("[OUT] alt  :", alt)
    print("[OUT] caption:", caption)
    if not json_ok and raw:
        print("[DBG] raw model output:", raw)

    img_path = os.path.join(OUT_DIR, IMG_FILENAME)
    gen_image(client, piece, caption, img_path)
    print("[OUT] image saved:", img_path)

    if all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, X_BEARER_TOKEN]):
        resp = post_to_x(tweet, img_path, alt)
        print("[OK] tweeted:", resp.data)
    else:
        print("[SKIP] X credentials missing; tweet not posted.")

if __name__ == "__main__":
    main()

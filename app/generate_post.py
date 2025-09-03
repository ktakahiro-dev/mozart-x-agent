
import os, datetime
import pandas as pd
from openai import OpenAI
import tweepy

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_TEXT = os.getenv("OPENAI_MODEL_TEXT", "gpt-4o-mini")
OPENAI_MODEL_IMAGE = os.getenv("OPENAI_MODEL_IMAGE", "gpt-image-1")

X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

CATALOG_CSV = os.getenv("CATALOG_CSV", "data/mozart_catalog.csv")
OUT_DIR = os.getenv("OUT_DIR", "out")
IMG_FILENAME = os.getenv("IMG_FILENAME", "mozart_post.png")

os.makedirs(OUT_DIR, exist_ok=True)

def choose_piece(today: datetime.date, path: str):
    df = pd.read_csv(path)
    row = df.iloc[today.toordinal() % len(df)]
    return row.to_dict()

def build_prompt_for_text(piece):
    return f"""日本語で、Mozartの作品をX投稿用に短く紹介します。
JSONのみを出力：
{{
  "tweet": "<120字以内。#Mozart #クラシックを含む>",
  "alt": "<80-120字のALT>",
  "img_caption": "<画像内見出し 8-12字>"
}}
対象: {piece["ja_title"]}（{piece["en_title"]}） / {piece["k"]}
"""

def build_prompt_for_image(piece, caption):
    return f"""1600x900の上品な音楽ビジュアル。背景は落ち着き、譜面等の抽象モチーフ。中央に「{caption}」のみ明瞭に配置。"""

def main():
    today = datetime.date.today()
    piece = choose_piece(today, CATALOG_CSV)

    client = OpenAI(api_key=OPENAI_API_KEY)
    # text
    rsp = client.responses.create(model=OPENAI_MODEL_TEXT, input=[{"role":"user","content":build_prompt_for_text(piece)}])
    import json as _json
    data = _json.loads(rsp.output_text)
    tweet, alt, caption = data["tweet"], data["alt"], data["img_caption"]

    # image
    img = client.images.generate(model=OPENAI_MODEL_IMAGE, prompt=build_prompt_for_image(piece, caption), size="1600x900")
    import base64
    with open(os.path.join(OUT_DIR, IMG_FILENAME),"wb") as f:
        f.write(base64.b64decode(img.data[0].b64_json))

    print("Tweet:", tweet)
    print("ALT:", alt)

    # post to X if keys exist
    if all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, X_BEARER_TOKEN]):
        auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(filename=os.path.join(OUT_DIR, IMG_FILENAME))
        api_v1.create_media_metadata(media_id=media.media_id, alt_text=alt)

        client_v2 = tweepy.Client(consumer_key=X_API_KEY, consumer_secret=X_API_SECRET,
                                  access_token=X_ACCESS_TOKEN, access_token_secret=X_ACCESS_SECRET,
                                  bearer_token=X_BEARER_TOKEN)
        client_v2.create_tweet(text=tweet, media_ids=[media.media_id])
    else:
        print("X keys missing; skipped posting.")

if __name__ == "__main__":
    main()


import os, sys, re, json, base64, time, datetime, secrets
from zoneinfo import ZoneInfo
import tweepy
from PIL import Image
from openai import OpenAI

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
PROOFREAD = os.getenv("PROOFREAD", "1") != "0"
STRICT_WEEKDAY = os.getenv("STRICT_WEEKDAY", "1") != "0"

TARGET_W, TARGET_H = 1600, 900
GEN_SIZE = "1536x1024"  # API許容 → 後段で1600x900へ厳密変換

os.makedirs(OUT_DIR, exist_ok=True)

def famous_works():
    return [
        {"k":"K.525","ja_title":"アイネ・クライネ・ナハトムジーク","type":"Serenade","key":"ト長調","seasons":["夏","春","秋"],"times":["夕暮れ","夜"]},
        {"k":"K.550","ja_title":"交響曲第40番","type":"Symphony","key":"ト短調","seasons":["秋","冬"],"times":["夕暮れ","夜"]},
        {"k":"K.551","ja_title":"交響曲第41番『ジュピター』","type":"Symphony","key":"ハ長調","seasons":["春","夏"],"times":["朝","昼"]},
        {"k":"K.626","ja_title":"レクイエム","type":"Choral","key":"ニ短調","seasons":["秋","冬"],"times":["夕暮れ","夜"]},
        {"k":"K.620","ja_title":"歌劇『魔笛』","type":"Opera","key":"変ホ長調","seasons":["夏","秋"],"times":["夕暮れ","夜","朝","昼"]},
        {"k":"K.492","ja_title":"歌劇『フィガロの結婚』","type":"Opera","key":"ニ長調","seasons":["春"],"times":["朝","昼","夜"]},
        {"k":"K.527","ja_title":"歌劇『ドン・ジョヴァンニ』","type":"Opera","key":"ニ短調","seasons":["秋"],"times":["夜","夕暮れ"]},
        {"k":"K.467","ja_title":"ピアノ協奏曲第21番","type":"Piano Concerto","key":"ハ長調","seasons":["春","夏"],"times":["朝","昼"]},
        {"k":"K.488","ja_title":"ピアノ協奏曲第23番","type":"Piano Concerto","key":"イ長調","seasons":["春","秋"],"times":["昼","夕暮れ"]},
        {"k":"K.466","ja_title":"ピアノ協奏曲第20番","type":"Piano Concerto","key":"ニ短調","seasons":["冬","秋"],"times":["夕暮れ","夜"]},
        {"k":"K.331","ja_title":"ピアノソナタ第11番『トルコ行進曲付き』","type":"Piano Sonata","key":"イ長調","seasons":["春","夏"],"times":["朝","昼"]},
        {"k":"K.183","ja_title":"交響曲第25番","type":"Symphony","key":"ト短調","seasons":["秋","冬"],"times":["夕暮れ","夜"]},
        {"k":"K.201","ja_title":"交響曲第29番","type":"Symphony","key":"イ長調","seasons":["春","夏"],"times":["朝","昼"]},
        {"k":"K.361","ja_title":"セレナード第10番『グラン・パルティータ』","type":"Serenade","key":"変ロ長調","seasons":["春","夏"],"times":["夕暮れ","夜"]},
        {"k":"K.622","ja_title":"クラリネット協奏曲","type":"Concerto","key":"イ長調","seasons":["秋"],"times":["夕暮れ","夜"]},
        {"k":"K.581","ja_title":"クラリネット五重奏曲","type":"Chamber","key":"イ長調","seasons":["秋"],"times":["夕暮れ","夜"]},
        {"k":"K.618","ja_title":"アヴェ・ヴェルム・コルプス","type":"Choral","key":"ニ長調","seasons":["夏"],"times":["夕暮れ","夜"]},
        {"k":"K.265","ja_title":"きらきら星変奏曲","type":"Piano","key":"ハ長調","seasons":["春","夏","秋","冬"],"times":["朝","昼"]},
        {"k":"K.397","ja_title":"幻想曲 ニ短調","type":"Piano","key":"ニ短調","seasons":["冬","秋"],"times":["夜"]},
        {"k":"K.216","ja_title":"ヴァイオリン協奏曲第3番","type":"Violin Concerto","key":"ト長調","seasons":["春"],"times":["昼","朝"]},
        {"k":"K.218","ja_title":"ヴァイオリン協奏曲第4番","type":"Violin Concerto","key":"ニ長調","seasons":["春","夏"],"times":["昼"]},
        {"k":"K.219","ja_title":"ヴァイオリン協奏曲第5番『トルコ風』","type":"Violin Concerto","key":"イ長調","seasons":["夏","秋"],"times":["昼","夕暮れ"]},
        {"k":"K.317","ja_title":"戴冠式ミサ","type":"Choral","key":"ハ長調","seasons":["春"],"times":["朝","昼"]},
        {"k":"K.320","ja_title":"セレナード第9番『ポストホルン』","type":"Serenade","key":"ニ長調","seasons":["夏"],"times":["夕暮れ","夜"]},
        {"k":"K.545","ja_title":"ピアノソナタ第16番『ソナタ・ファチレ』","type":"Piano Sonata","key":"ハ長調","seasons":["春","夏","秋","冬"],"times":["朝","昼"]},
        {"k":"K.136","ja_title":"ディヴェルティメント","type":"Divertimento","key":"ニ長調","seasons":["春"],"times":["朝","昼"]},
        {"k":"K.314","ja_title":"オーボエ協奏曲","type":"Concerto","key":"ハ長調","seasons":["春"],"times":["昼"]},
    ]

EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF]")
HASHTAG_RE = re.compile(r"#\S+")
K_RE = re.compile(r"(?:K|KV)\s*\.?\s*\d+[a-z]?(?:/\d+[a-z]?)?", re.I)
YMD_PATTERNS = [
    re.compile(r"\d{1,4}年\d{1,2}月\d{1,2}日"),
    re.compile(r"\d{1,2}月\d{1,2}日"),
    re.compile(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"),
    re.compile(r"\b\d{1,2}:\d{2}\b"),
]
WEEKDAYS_RE = re.compile(r"(月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日|月曜|火曜|水曜|木曜|金曜|土曜|日曜)")

def now_jst():
    return datetime.datetime.now(ZoneInfo("Asia/Tokyo"))

def part_of_day(hour: int) -> str:
    if 5 <= hour < 11: return "朝"
    if 11 <= hour < 16: return "昼"
    if 16 <= hour < 20: return "夕暮れ"
    return "夜"

def slot_index(hour: int) -> int:
    if 5 <= hour < 11: return 0
    if 11 <= hour < 16: return 1
    return 2

def season_by_month(m: int) -> dict:
    if m in (3,4,5):
        return {"jp":"春","emoji":["🌸","🌱","🌼"],"palette":"soft sakura pink, fresh green, ivory","motifs":"petals, gentle breeze","text_hint":"春のやわらかな空気"}
    if m in (6,7,8):
        return {"jp":"夏","emoji":["🎐","🌊","🌞","🌌"],"palette":"deep indigo, night blue, gold","motifs":"fireflies, cool water ripples, starry sky","text_hint":"夏の夜風"}
    if m in (9,10,11):
        return {"jp":"秋","emoji":["🍁","🌾","🍂"],"palette":"amber, russet, smoky blue","motifs":"falling leaves, harvest glow","text_hint":"秋の深まる色合い"}
    return {"jp":"冬","emoji":["❄️","☃️","🌨️"],"palette":"snow white, silver, charcoal","motifs":"snowflakes, crisp air","text_hint":"冬の澄んだ空気"}

def clamp(s: str, max_len: int):
    s = (s or "").strip()
    return s if len(s) <= max_len else s[:max_len-1] + "…"

def strip_hashtags(s: str) -> str:
    s = HASHTAG_RE.sub("", s or "")
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def strip_emojis(s: str) -> str:
    return EMOJI_RE.sub("", s or "").strip()

def remove_ymd_time(text: str) -> str:
    s = text or ""
    for pat in YMD_PATTERNS:
        s = pat.sub("", s)
    s = re.sub(r"[（）()]", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" 、。-—")
    return s.strip()

def remove_weekdays(text: str) -> str:
    return WEEKDAYS_RE.sub("", text or "")

def is_opera(piece: dict) -> bool:
    return "opera" in (piece.get("type","") or "").lower() or "歌劇" in (piece.get("ja_title","") or "")

def piece_label(piece: dict) -> str:
    if is_opera(piece):
        return f"{piece['ja_title']} {piece['k']}"
    key = (piece.get("key") or "").strip()
    return f"{piece['ja_title']} {key} {piece['k']}" if key else f"{piece['ja_title']} {piece['k']}"

def emoji_pool(piece: dict, sea: dict, pod: str):
    pool = []
    t = (piece.get("type","") or "").lower()
    title = piece.get("ja_title","")
    if "opera" in t: pool += ["🎭","🎟️","✨"]
    if "symphony" in t: pool += ["🎻","🎼"]
    if "piano" in t: pool += ["🎹","🎼"]
    if "violin" in t: pool += ["🎻"]
    if "クラリネット" in title: pool += ["🪈","🎼"]
    if "choral" in t or "ミサ" in title: pool += ["🎶","✨"]
    if "serenade" in t or "divertimento" in t: pool += ["🎶","🌙"]
    if "concerto" in t and not pool: pool += ["🎼"]
    if pod == "朝": pool += ["🌅","☀️"]
    elif pod == "昼": pool += ["☀️"]
    elif pod == "夕暮れ": pool += ["🌇"]
    else: pool += ["🌙","✨"]
    pool += sea["emoji"]
    pool += ["🎵","🎶"]
    # unique
    seen, uniq = set(), []
    for e in pool:
        if e not in seen:
            uniq.append(e); seen.add(e)
    return uniq or ["🎵"]

def pick_rotated_emoji(piece: dict, sea: dict, pod: str, seed_int: int) -> str:
    pool = emoji_pool(piece, sea, pod)
    return pool[seed_int % len(pool)]

def compose_tweet_with_protected_label(body: str, label: str, piece: dict, sea: dict, pod: str, seed_int: int) -> str:
    body = strip_emojis(strip_hashtags(body))
    body = K_RE.sub("", body)
    body = remove_ymd_time(body)
    body = remove_weekdays(body)
    body = re.sub(r"\s{2,}", " ", body).strip(" 、。")
    em = pick_rotated_emoji(piece, sea, pod, seed_int)
    room_for_label = len(label) + 1
    room_for_emoji = 2
    max_body = 120 - room_for_label - room_for_emoji
    if max_body < 0: max_body = 0
    body = body[:max_body].rstrip(" 、。")
    sep = " — " if body else ""
    tweet = f"{body}{sep}{label} {em}".strip()
    if len(tweet) > 120:
        over = len(tweet) - 120
        body_cut = max(0, len(body) - over)
        body = body[:body_cut].rstrip(" 、。")
        sep = " — " if body else ""
        tweet = f"{body}{sep}{label} {em}".strip()
    return tweet

def extract_json(text: str) -> str:
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        return m.group(0)
    m2 = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S|re.I)
    if m2:
        return m2.group(1)
    return text.strip()

def proofread_body(client: OpenAI, body: str) -> (str, str):
    if not PROOFREAD:
        return body, "校正OFF"
    rules = """
# 校正ルール（日本語）
- 文体は温かく簡潔。重複や冗長を削る。
- 誤字・読点の過不足を調整。全角記号を基本に。
- 絵文字・ハッシュタグ・K番号は入れない（後工程で付与・挿入）。
- 年月日や具体的な時刻（HH:MM）は書かない。
- 曜日（例：月曜/土曜日）は書かない。
- 120字以内にまとめる。出力は本文のみ。
"""
    prompt = f"以下の日本語ツイート本文を上のルールで校正してください。本文のみを返してください。\n---\n{body}\n---"
    try:
        rsp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role":"user","content":rules + prompt}],
            temperature=0.2
        )
        cleaned = (rsp.choices[0].message.content or "").strip()
        cleaned = remove_ymd_time(remove_weekdays(cleaned))
        cleaned = K_RE.sub("", cleaned)
        cleaned = HASHTAG_RE.sub("", cleaned)
        cleaned = EMOJI_RE.sub("", cleaned)
        cleaned = cleaned[:120]
        return cleaned, "校正OK"
    except Exception as e:
        return body, f"校正失敗: {e}"

def choose_piece_auto(today: datetime.date):
    works = famous_works()
    jst = now_jst()
    pod = part_of_day(jst.hour)
    sea = season_by_month(jst.month)["jp"]
    cands = [w for w in works if (sea in w["seasons"]) and (pod in w["times"])]
    if not cands:
        cands = [w for w in works if sea in w["seasons"] or pod in w["times"]]
    if not cands:
        cands = works[:]
    sidx = slot_index(jst.hour)
    idx = (int(today.strftime("%Y%m%d")) * 3 + sidx) % len(cands)
    return cands[idx]

def prompt_text(piece: dict) -> str:
    jst = now_jst()
    pod = part_of_day(jst.hour)
    sea = season_by_month(jst.month)
    label = piece_label(piece)
    return f"""日本語でモーツァルト作品のX投稿文をJSONで返してください。JSON以外は一切書かないでください。
以下のヒントを自然に織り込みます：時間帯({pod})、季節({sea['jp']}:{sea['text_hint']}).
必ず、ツイート本文の中に **{label}** を一度だけ含めます。
- オペラ作品は**調性を書かずK番号のみ**（例：歌劇『魔笛』 K.620）
- オペラ以外は**調性＋K番号**（例：交響曲第40番 ト短調 K.550）
ハッシュタグは禁止。絵文字は入れなくて良い（後工程で付与）。年月日や具体時刻・曜日は書かないでください。
{{
  "tweet": "<全角込み120字以内。上の条件を満たす。年月日や時刻・曜日は書かない。絵文字は入れない>",
  "alt": "<画像の代替テキスト。80-120字。ツイート内容の要素（季節/時間帯/楽器/雰囲気）を簡潔に。絵文字/ハッシュタグは入れない>",
  "img_caption": "<画像に入れる短い見出し（8-12字）。絵文字とハッシュタグは入れない>"
}}
対象作品: {label}
口調: 温かく簡潔。専門用語を避ける。
"""

def gen_text_alt_caption(client: OpenAI, piece: dict):
    label = piece_label(piece)
    last_error = None
    for model in [TEXT_MODEL, TEXT_MODEL_FALLBACK]:
        for attempt in range(1, MAX_TRIES+1):
            try:
                raw = client.chat.completions.create(
                    model=model,
                    messages=[{"role":"user","content":prompt_text(piece)}],
                    temperature=0.7
                ).choices[0].message.content or ""
                blob = extract_json(raw)
                data = json.loads(blob)
                body0 = (data.get("tweet","") or "")
                alt = (data.get("alt","") or "")
                caption = (data.get("img_caption", piece["ja_title"]) or "")
                # 校正
                body1, report = proofread_body(client, body0)
                print(f"[PROOF] {report} | before='{body0}' | after='{body1}'")
                # ラベル保護ツイート
                jst = now_jst()
                pod = part_of_day(jst.hour)
                sea = season_by_month(jst.month)
                sidx = slot_index(jst.hour)
                seed_int = int(jst.strftime("%Y%m%d")) * 3 + sidx
                tweet = compose_tweet_with_protected_label(body1, label, piece, sea, pod, seed_int)
                # alt/caption 調整
                alt = clamp( strip_hashtags( remove_ymd_time(alt) ), 120)
                caption = clamp( strip_hashtags( remove_ymd_time(caption) ), 12)
                print(f"[INFO] used_model={model}, attempt={attempt}, json_ok=True")
                return tweet, alt, caption
            except Exception as e:
                last_error = e
                print(f"[WARN] JSON parse failed (model={model}, attempt={attempt}): {e}")
                time.sleep(1.2 * attempt)
    # Fallback
    jst = now_jst()
    pod = part_of_day(jst.hour)
    sea = season_by_month(jst.month)
    sidx = slot_index(jst.hour)
    seed_int = int(jst.strftime("%Y%m%d")) * 3 + sidx
    body = "ひと息ついて、旋律に耳を澄ませて。"
    tweet = compose_tweet_with_protected_label(body, label, piece, sea, pod, seed_int)
    alt = "季節と時間帯の光を感じる静かなイラスト。作品のモチーフを柔らかく表現。"
    caption = piece.get('ja_title', 'モーツァルト')[:12]
    print(f"[INFO] used_model=fallback_template, json_ok=False")
    return tweet, alt, caption

def infer_mood(piece: dict):
    title_ja = piece.get("ja_title","") or ""
    t = (piece.get("type","") or "").lower()
    key = piece.get("key")
    is_minor = key and key.endswith("短調")
    mood = {"palette":"cream, gray, subtle gold","mood":"elegant, balanced","motifs":"abstract staves and notes"}
    if "レクイエム" in title_ja or piece.get("k")=="K.626":
        mood = {"palette":"deep purple, charcoal, candlelight gold","mood":"solemn, spiritual, reverent","motifs":"soft choir silhouettes, candlelight glow"}
    elif "ナハトムジーク" in title_ja:
        mood = {"palette":"midnight blue, silver, soft cream","mood":"serene, nocturnal, tender","motifs":"starry night hints, crescent moon"}
    elif "クラリネット" in title_ja:
        mood = {"palette":"warm amber, ivory, slate","mood":"warm, lyrical, woody","motifs":"clarinet silhouette, flowing breath lines"}
    elif "ピアノ" in title_ja or "piano" in t:
        mood = {"palette":"ivory, ebony, antique gold","mood":"graceful, clear, intimate","motifs":"piano keys silhouette, delicate staves"}
    elif "交響曲" in title_ja or "symphony" in t:
        if is_minor:
            mood = {"palette":"smoky indigo, graphite, silver","mood":"dramatic, tense, stormy","motifs":"bold diagonal staves, energetic accents"}
        else:
            mood = {"palette":"cream, gold, light blue","mood":"bright, spirited, festive","motifs":"radiant staves, airy ornaments"}
    elif "歌劇" in title_ja or "opera" in t:
        mood = {"palette":"crimson velvet, gold, ebony","mood":"theatrical, lively","motifs":"stage curtains, mask hints"}
    return mood

def opera_scene_motifs(piece: dict, pod: str) -> str:
    k = piece.get("k","")
    title = piece.get("ja_title","")
    if k == "K.620" or "魔笛" in title:
        if pod == "夜":
            return "Magic Flute (Queen of the Night): starry sky, crescent moon, dramatic starbursts"
        elif pod in ["朝","昼"]:
            return "Magic Flute (Papageno): birds feathers, rustic pan flute (glockenspiel), playful motifs"
        else:
            return "Magic Flute (Sarastro): golden temple geometry, warm lanterns, solemn symmetry"
    if k == "K.492" or "フィガロ" in title:
        if pod in ["朝","昼"]:
            return "Marriage of Figaro: sealed letters, playful footsteps in corridors, household doors ajar"
        else:
            return "Marriage of Figaro: masquerade ribbons, candle-lit hall, swirling dance hints"
    if k == "K.527" or "ドン・ジョヴァンニ" in title:
        if pod == "夜":
            return "Don Giovanni: masked ball, candelabras, looming marble statue (Commendatore), infernal swirl"
        else:
            return "Don Giovanni: shadowed alleys, dramatic cape, distant bells, ominous marble presence"
    return ""

def prompt_image(piece: dict, caption: str, tweet_text: str):
    jst = now_jst()
    pod = part_of_day(jst.hour)
    sea = season_by_month(jst.month)
    m = infer_mood(piece)
    opera_scene = opera_scene_motifs(piece, pod)
    scene_line = f"Opera scene motifs: {opera_scene}." if opera_scene else ""
    return f"""Design a content-driven illustration (not photorealistic), landscape 1536x1024, matching the tweet's mood and semantics.
- Core idea from tweet: "{tweet_text}"
- Piece mood: palette {m['palette']}; mood {m['mood']}; motifs {m['motifs']}
- {scene_line}
- Season ({sea['jp']}): accents {sea['palette']}; motifs {sea['motifs']}
- Time of day ({pod}): lighting cues (morning soft light / noon clarity / dusk glow / night calm)
- Instrument/genre hints should be visible if relevant (piano keys, violin, clarinet-like woodwind, choir texture, stage curtains/masks etc.)
- Background: soft paper texture. Provide a clean central area for Japanese caption "{caption}" with high readability.
- Keep key elements near center; allow safe 16:9 crop.
"""

def gen_image_and_fit(client: OpenAI, piece: dict, caption: str, out_path: str, tweet_text: str):
    prompt = prompt_image(piece, caption, tweet_text)
    img = client.images.generate(model=IMAGE_MODEL, prompt=prompt, size=GEN_SIZE)
    gen_id = "im-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(4)
    b64 = img.data[0].b64_json
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))
    im = Image.open(out_path)
    w, h = im.size
    target_ratio = TARGET_W / TARGET_H
    new_h = int(round(w / target_ratio))
    if new_h <= h:
        top = (h - new_h) // 2
        im = im.crop((0, top, w, top + new_h))
    else:
        new_w = int(round(h * target_ratio))
        left = (w - new_w) // 2
        im = im.crop((left, 0, left + new_w, h))
    im = im.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    im.save(out_path)
    print(f"[IMG] gen_id={gen_id} file={out_path}")
    return gen_id

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
    today = now_jst().date()
    piece = choose_piece_auto(today)
    label = piece_label(piece)
    tweet, alt, caption = gen_text_alt_caption(client, piece)
    print("[OUT] piece:", label)
    print("[OUT] tweet:", tweet)
    print("[OUT] alt  :", alt)
    print("[OUT] caption:", caption)
    out_img = os.path.join(OUT_DIR, IMG_FILENAME)
    gen_id = gen_image_and_fit(client, piece, caption, out_img, tweet_text=tweet)
    print("[OUT] image saved:", out_img)
    print(f"[OUT] gen_id: {gen_id}")
    if all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, X_BEARER_TOKEN]):
        resp = post_to_x(tweet, out_img, alt)
        print("[OK] tweeted:", resp.data)
    else:
        print("[SKIP] X credentials missing; tweet not posted.")

if __name__ == "__main__":
    main()

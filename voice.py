"""配音 + 时间轴：读分镜源 -> 核对字幕和文案逐字一致 -> 豆包语音合成 2.0 逐场景配音 -> 拼成一条人声 ->
用 TTS 返回的逐字时间戳，算出每一拍（每句字幕）和每个高亮词的准确时刻 -> out/timeline.json + out/vo.wav

  python voice.py           真配音（需要 .env 里的 VOLC_TTS_API_KEY）
  python voice.py --dry     不调接口：按每秒 4.5 字估算时间，人声是静音（先把画面做出来用）
  python voice.py --voices  把 CANDIDATES 里的音色各念一遍开头，存到 out/音色小样/ 挑音色

分镜源格式（script/storyboard.txt）：
  == 章节名                                   ← 顶部进度条的一段
  ## S01 场景名 | 地点                         ← 一个场景（一个 Python 函数）
  - 字幕 | 高亮词（空格分隔） | 画面 | 音效       ← 一拍 = 一句字幕
  @ 秒数 | 画面 | 音效                          ← 没有口播的留白
"""
import base64, hashlib, io, json, os, re, subprocess, sys, uuid
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
CACHE = os.path.join(OUT, "tts_cache")
SRC = os.path.join(ROOT, "script", "storyboard.txt")
COPY = os.path.join(ROOT, "script", "copy.md")
SR = 48000

URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
VOICE = os.environ.get("VOICE", "zh_male_taocheng_uranus_bigtts")      # 小天 2.0：旁白默认
SPEECH_RATE = int(os.environ.get("SPEECH_RATE", "0"))                  # 0 = 正常，100 = 两倍速
STYLE = ""            # 语气提示词（TTS 2.0 才有）。实测：讲故事提示词会让语速变慢，旁白默认不加
CANDIDATES = [
    ("小天", "zh_male_taocheng_uranus_bigtts"), ("云舟", "zh_male_m191_uranus_bigtts"),
    ("渊博小叔", "zh_male_yuanboxiaoshu_uranus_bigtts"), ("磁性解说男声", "zh_male_cixingjieshuonan_uranus_bigtts"),
    ("小何", "zh_female_xiaohe_uranus_bigtts"), ("知性女声", "zh_female_zhixingnv_uranus_bigtts"),
]
SAY = []              # [(屏幕上写法, 念法)]，例如 ("3%", "百分之三")；只影响念，不影响字幕
# 停顿（秒）：逗号 0.25、句号 0.5、换场景 0.35 —— 按参考视频量出来的节奏
GAP = {"，": 0.25, "、": 0.15, "：": 0.35, "；": 0.3, "。": 0.5, "？": 0.55, "！": 0.5}
SCENE_GAP, LEAD_IN, TAIL = 0.35, 0.6, 1.0
DRY_RATE = 4.5        # --dry 时每秒字数


def norm(s):
    return re.sub(r"[^一-鿿0-9A-Za-z]", "", s)


# ---------------------------------------------------------------- 分镜源
def parse(path=SRC):
    acts = []
    for raw in io.open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip() or line.startswith("# "):
            continue
        if line.startswith("== "):
            acts.append({"name": line[3:].strip(), "scenes": []})
        elif line.startswith("## "):
            head, where = (line[3:].split("|", 1) + [""])[:2]
            sid, name = (head.strip().split(None, 1) + [""])[:2]
            acts[-1]["scenes"].append({"id": sid, "name": name, "where": where.strip(), "beats": []})
        elif line.startswith("- "):
            f = [x.strip() for x in line[2:].split("|")] + [""] * 4
            acts[-1]["scenes"][-1]["beats"].append({"sub": f[0], "hi": f[1].split(), "pic": f[2], "sfx": f[3]})
        elif line.startswith("@ "):
            f = [x.strip() for x in line[2:].split("|")] + [""] * 3
            acts[-1]["scenes"][-1]["beats"].append({"sub": "", "pause": float(f[0]), "pic": f[1], "sfx": f[2]})
        else:
            raise SystemExit("看不懂这一行：" + line)
    return acts


def check_coverage(acts):
    """字幕连起来必须和文案正文一字不差（标点不算）。文案正文 = 第一条 --- 之后、去掉 # 标题和 > 备注。"""
    body = io.open(COPY, encoding="utf-8").read().split("\n---\n", 1)[1]
    want = norm("".join(l.replace("**", "") for l in body.split("\n")
                        if l.strip() and not l.lstrip().startswith(("#", ">", "（"))))
    got = norm("".join(b["sub"] for a in acts for s in a["scenes"] for b in s["beats"]))
    if want != got:
        i = next((k for k in range(min(len(want), len(got))) if want[k] != got[k]), min(len(want), len(got)))
        raise SystemExit(f"字幕和文案对不上，第 {i} 字附近：\n  文案：{want[max(0, i - 15):i + 25]}\n  字幕：{got[max(0, i - 15):i + 25]}")
    print(f"字幕核对通过：{len(got)} 字")


# ---------------------------------------------------------------- 豆包语音合成 2.0（V3 HTTP 单向流式）
def api_key():
    key = os.environ.get("VOLC_TTS_API_KEY")
    env = os.path.join(ROOT, ".env")
    if not key and os.path.exists(env):
        for line in io.open(env, encoding="utf-8"):
            if line.startswith("VOLC_TTS_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("缺少 API Key：在 .env 里写 VOLC_TTS_API_KEY=...（或先用 --dry）")
    return key


def synth(text, speaker=VOICE, style=STYLE, rate=SPEECH_RATE):
    """返回 (mp3 字节, 逐字时间戳 [{word, startTime, endTime}...])。按文本+音色缓存，改一句只重配一句。"""
    import requests
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.md5(f"{speaker}|{style}|{rate}|{text}".encode("utf-8")).hexdigest()[:12]
    mp3, js = os.path.join(CACHE, key + ".mp3"), os.path.join(CACHE, key + ".json")
    if os.path.exists(mp3) and os.path.exists(js):
        return open(mp3, "rb").read(), json.load(open(js, encoding="utf-8"))
    headers = {"X-Api-Key": api_key(), "X-Api-Resource-Id": "seed-tts-2.0",
               "X-Api-Request-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
    additions = {"disable_markdown_filter": True}
    if style:
        additions["context_texts"] = [style]
    body = {"user": {"uid": "pixel-video"},
            "req_params": {"text": text, "speaker": speaker,
                           "audio_params": {"format": "mp3", "sample_rate": 24000, "speech_rate": rate,
                                            "enable_subtitle": True},
                           "additions": json.dumps(additions, ensure_ascii=False)}}
    r = requests.post(URL, headers=headers, json=body, stream=True, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    audio, words = bytearray(), []
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        msg = json.loads(line)
        if msg.get("code", 0) not in (0, 20000000):
            raise RuntimeError(f"code={msg.get('code')} {msg.get('message')}")
        if msg.get("data"):
            audio += base64.b64decode(msg["data"])
        if msg.get("sentence"):
            words += msg["sentence"].get("words", [])
    open(mp3, "wb").write(audio)
    json.dump(words, open(js, "w", encoding="utf-8"), ensure_ascii=False)
    return bytes(audio), words


def decode(mp3_bytes):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", str(SR), "pipe:1"],
                       input=mp3_bytes, capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.int16).astype(np.float32) / 32768


def trim(x, thr_db=-42):
    """切掉首尾静音（前留 30ms、后留 80ms）。返回 (片段, 前面切掉了几秒)。"""
    hop = SR // 100
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, mode="same"))
    loud = np.nonzero(rms > 10 ** (thr_db / 20))[0]
    if len(loud) == 0:
        return x, 0.0
    a, b = max(0, loud[0] - int(0.03 * SR)), min(len(x), loud[-1] + int(0.08 * SR))
    return x[a:b], a / SR


def char_times(words, n):
    """把 TTS 的逐字时间戳摊成 n 个字的 (开始, 结束)。字数对不上（数字、英文）时按比例插值。"""
    st = []
    for w in words:
        cs = norm(w.get("word", "")) or "_"
        a, b = w["startTime"], w["endTime"]
        for k in range(len(cs)):
            st.append((a + (b - a) * k / len(cs), a + (b - a) * (k + 1) / len(cs)))
    if len(st) == n:
        return st
    idx = np.linspace(0, len(st) - 1, n)
    return [(float(np.interp(i, range(len(st)), [s[0] for s in st])),
             float(np.interp(i, range(len(st)), [s[1] for s in st]))) for i in idx]


def dry_times(text):
    """估算：每秒 DRY_RATE 字，标点处加停顿。"""
    t, out = 0.0, []
    for ch in text:
        if norm(ch):
            out.append((t, t + 1 / DRY_RATE))
            t += 1 / DRY_RATE
        else:
            t += GAP.get(ch, 0.0)
    return out, t


# ---------------------------------------------------------------- 主流程
def build(dry=False):
    acts = parse()
    check_coverage(acts)
    t, chunks = LEAD_IN, [np.zeros(int(LEAD_IN * SR), np.float32)]
    for act in acts:
        act["t0"] = t
        for sc in act["scenes"]:
            sc["t0"] = t
            spoken = [b for b in sc["beats"] if b["sub"]]
            text = "".join(b["sub"] for b in spoken)
            # 一个场景整段合成（语气连贯），再用逐字时间戳切回每一句
            if text and not dry:
                say = text
                for a, b in SAY:
                    say = say.replace(a, b)
                audio, words = synth(say)
                x, lead = trim(decode(audio))
                ct = [(a - lead, b - lead) for a, b in char_times(words, len(norm(text)))]
                dur = len(x) / SR
            elif text:
                ct, dur = dry_times(text)
                x = np.zeros(int(dur * SR), np.float32)
            else:
                ct, dur, x = [], 0.0, np.zeros(0, np.float32)
            k = 0
            for b in sc["beats"]:
                if b.get("pause") is not None:          # 留白：插静音
                    b["t0"], b["t_end"], b["hi_t"] = round(t + dur, 3), round(t + dur + b["pause"], 3), []
                    x = np.concatenate([x, np.zeros(int(b["pause"] * SR), np.float32)])
                    dur += b["pause"]
                    continue
                n = len(norm(b["sub"]))
                seg = ct[k:k + n]
                b["t0"], b["t_end"] = round(t + seg[0][0], 3), round(t + seg[-1][1], 3)
                hs, s_norm = [], norm(b["sub"])
                for w in b["hi"]:
                    q = s_norm.find(norm(w))
                    if q >= 0:
                        hs.append(round(t + seg[q][0], 3))
                b["hi_t"] = hs
                k += n
            chunks.append(x)
            t += dur
            sc["t1"] = t + SCENE_GAP
            chunks.append(np.zeros(int(SCENE_GAP * SR), np.float32))
            t += SCENE_GAP
        act["t1"] = t
    chunks.append(np.zeros(int(TAIL * SR), np.float32))
    total = t + TAIL
    acts[-1]["t1"] = acts[-1]["scenes"][-1]["t1"] = total
    os.makedirs(OUT, exist_ok=True)
    y = np.concatenate(chunks)
    import soundfile as sf
    sf.write(os.path.join(OUT, "vo.wav"), y, SR)
    json.dump({"total": round(total, 3), "acts": acts}, io.open(os.path.join(OUT, "timeline.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    nb = sum(1 for a in acts for s in a["scenes"] for b in s["beats"] if b["sub"])
    print(f"{'估算' if dry else '配音'}完成：{total:.1f}s，{len(acts)} 章，{sum(len(a['scenes']) for a in acts)} 场，{nb} 句"
          f" -> out/vo.wav, out/timeline.json")


def voices():
    body = io.open(COPY, encoding="utf-8").read().split("\n---\n", 1)[1]
    first = next(l for l in body.split("\n") if l.strip() and not l.startswith(("#", ">")))
    d = os.path.join(OUT, "音色小样")
    os.makedirs(d, exist_ok=True)
    for i, (name, vid) in enumerate(CANDIDATES, 1):
        audio, _ = synth(first.replace("**", ""), vid)
        open(os.path.join(d, f"{i:02d}_{name}.mp3"), "wb").write(audio)
        print("wrote", name)


if __name__ == "__main__":
    if "--voices" in sys.argv:
        voices()
    else:
        build(dry="--dry" in sys.argv)

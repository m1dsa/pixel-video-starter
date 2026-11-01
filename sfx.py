"""音效 + 混音。所有音效都用代码合成（不用素材库，没有版权问题）。BGM 可选：放一个 music/bgm.wav 就混进去，没有就不配。

音效写在分镜源的第 4 栏，空格分隔，每个是「名字」或「名字@时间」：
  pop          -> 这一拍开始时
  coin@hi      -> 这一拍第 1 个高亮词被念到时（@hi2 = 第 2 个）
  tick@hi+0.4  -> 高亮词之后 0.4 秒
  whoosh@-0.2  -> 这一拍开始前 0.2 秒
  tick@end     -> 这一拍念完时
场景代码里也可以直接加：在场景文件里 EXTRA.append((时间, "ding"))。

混音规则（实测下来不吞字）：人声 RMS 归一到 -18 dB；音效在说话时被自动压到比人声低 ≥10 dB；
整体 -14 LUFS（抖音/B 站/YouTube 的常用响度），峰值上限 -1.2 dBFS。
BGM（music/bgm.wav，和成片一样长或更短；更短会循环）：压到人声下约 12 dB，说话时再自动让开 6 dB，首尾淡入淡出。
要随情节起伏，就按章节做好几段音乐，拼成一条 bgm.wav 再放进去。

  python sfx.py            -> out/mix.wav
  python sfx.py --preview  -> out/音效试听/（音效库里每个音效一份，先试听再挑）
"""
import json, os, re
import numpy as np
import soundfile as sf
import scipy.signal as ss
from scipy.ndimage import minimum_filter1d

SR = 48000
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
EXTRA = []          # 场景代码追加的 (时间, 音效名)
BGM = os.path.join(ROOT, "music", "bgm.wav")   # 可选：整条 BGM（自己做的，或有版权许可的），没有就不配


def R(seed):
    return np.random.default_rng(seed)


def T(d):
    return np.arange(int(d * SR)) / SR


def lowpass(x, k):
    return x if k <= 1 else np.convolve(x, np.ones(k) / k, mode="same")


def highpass(x, k):
    return x - lowpass(x, k)


def hann(n, p=1.0):
    return np.sin(np.linspace(0, np.pi, n)) ** p


def mx(*xs):
    out = np.zeros(max(len(x) for x in xs))
    for x in xs:
        out[:len(x)] += x
    return out


def tone(f, d, decay=8.0, gain=0.3, kind="sine"):
    t = T(d)
    w = np.sin(2 * np.pi * f * t) if kind == "sine" else np.sign(np.sin(2 * np.pi * f * t)) * 0.5
    return w * np.exp(-t * decay) * gain


def seq(freqs, gap, d=0.15, decay=10, kind="sine", gain=0.25):
    out = np.zeros(int((gap * len(freqs) + d + 0.1) * SR))
    for i, f in enumerate(freqs):
        s = tone(f, d, decay, gain, kind)
        a = int(i * gap * SR)
        out[a:a + len(s)] += s
    return out


# ---------------------------------------------------------------- 音效库
def pop(gain=0.25, f=900):            # 标签弹出「啵」
    t = T(0.12)
    return np.sin(2 * np.pi * (f + 900 * t) * t) * np.exp(-t * 40) * gain


def ding(f=1568, d=0.5, gain=0.2):    # 提示「叮」
    return mx(tone(f, d, 7, gain), tone(f * 2.01, d, 11, gain * 0.3))


def coin(gain=0.2):                   # 金币（8-bit 两音）
    return seq([988, 1319], 0.06, 0.2, 14, "square", gain * 0.6)


def thud(gain=0.4):                   # 低沉「咚」（大数字砸下来）
    t = T(0.3)
    return np.sin(2 * np.pi * (90 - 40 * t) * t) * np.exp(-t * 14) * gain


def click(seed=3, pitch=1.0, gain=0.35):
    t = T(0.06)
    s = (np.sin(2 * np.pi * 1450 * pitch * t) * 0.6 + np.sin(2 * np.pi * 2900 * pitch * t) * 0.3) * np.exp(-t * 90)
    s[:int(0.004 * SR)] += R(seed).normal(0, 0.6, int(0.004 * SR))
    return s * gain


def whoosh(d=0.4, gain=0.25, seed=9):  # 转场「唰」
    n = int(d * SR)
    return lowpass(R(seed).normal(0, 1, n), 10) * hann(n, 2) * gain


def tick(gain=0.12):                  # 钟「嗒」
    return mx(click(5, 1.6, gain), tone(3200, 0.03, 120, gain * 0.5))


def stamp(gain=0.55):                 # 盖章
    return mx(thud(gain), whoosh(0.12, 0.15, 13))


def shaker(gain=0.15, seed=21):       # 摇雪克杯「沙沙」
    n = int(0.4 * SR)
    s = highpass(R(seed).normal(0, 1, n), 3)
    return s * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 9 * T(0.4)))) * hann(n, 0.3) * gain


def sparkle(gain=0.06):               # 闪光
    return seq([1319, 1568, 1976, 2637], 0.05, 0.2, 10, "sine", gain)


def error(gain=0.12):                 # 错误「哔哔」
    return seq([220, 180], 0.12, 0.12, 6, "square", gain)


def item_get(gain=0.22):              # 获得道具（上行琶音）
    return seq([523, 659, 784, 1047], 0.09, 0.35, 5, "sine", gain)


def typing(n=6, gain=0.05):           # 打字
    out = np.zeros(int((n * 0.09 + 0.1) * SR))
    for i in range(n):
        s = tone(1800 + R(i).uniform(-200, 200), 0.03, 90, gain, "square")
        a = int(i * 0.09 * SR)
        out[a:a + len(s)] += s
    return out


LIB = {"pop": pop, "ding": ding, "coin": coin, "thud": thud, "click": click, "whoosh": whoosh, "tick": tick,
       "stamp": stamp, "shaker": shaker, "sparkle": sparkle, "error": error, "item": item_get, "typing": typing}


# ---------------------------------------------------------------- 分镜里的音效 -> 时间点
def events():
    tl = json.load(open(os.path.join(OUT, "timeline.json"), encoding="utf-8"))
    ev = []
    for a in tl["acts"]:
        for s in a["scenes"]:
            for b in s["beats"]:
                for tok in (b.get("sfx") or "").split():
                    name, _, at = tok.partition("@")
                    if name not in LIB:
                        continue                       # 分镜里写的中文描述（「沙沙」）忽略，只认库里的名字
                    m = re.match(r"^(hi(\d*)|end)?([+-][\d.]+)?$", at)
                    if not m:
                        raise SystemExit(f"看不懂的音效时间：{tok}")
                    t = b["t0"]
                    if m.group(1) == "end":
                        t = b["t_end"]
                    elif m.group(1):
                        hs = b.get("hi_t") or [b["t0"]]
                        t = hs[min(int(m.group(2) or 1) - 1, len(hs) - 1)]
                    t += float(m.group(3) or 0)
                    ev.append((t, name))
    return sorted(ev + EXTRA), tl["total"]


# ---------------------------------------------------------------- 响度
def k_weight(x):
    """ITU-R BS.1770 K 加权（48 kHz 系数）。"""
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]
    return ss.lfilter(b2, a2, ss.lfilter(b1, a1, x, axis=0), axis=0)


def lufs(st):
    k = k_weight(st)
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    z = np.array([(k[i:i + blk] ** 2).mean(0).sum() for i in range(0, max(1, len(k) - blk), hop)])
    z = z[-0.691 + 10 * np.log10(z + 1e-12) > -70]
    rel = -0.691 + 10 * np.log10(z.mean() + 1e-12) - 10
    z2 = z[-0.691 + 10 * np.log10(z + 1e-12) > rel]
    return -0.691 + 10 * np.log10(z2.mean() + 1e-12)


def limiter(st, ceiling, look=0.004, smooth=0.012):
    g = np.minimum(1.0, ceiling / np.maximum(np.abs(st).max(1), 1e-9))
    gmin = minimum_filter1d(g, size=2 * max(1, int(look * SR)) + 1)
    k = max(1, int(smooth * SR))
    return st * np.minimum(gmin, np.convolve(gmin, np.ones(k) / k, mode="same"))[:, None]


def env_db(x, win=0.05):
    n = int(win * SR)
    return 10 * np.log10(np.convolve(k_weight(x) ** 2, np.ones(n) / n, mode="same") + 1e-12)


def mix(path=os.path.join(OUT, "mix.wav")):
    ev, total = events()
    n = int(total * SR)
    vo, sr = sf.read(os.path.join(OUT, "vo.wav"), always_2d=True)
    vo = vo.mean(1)
    if sr != SR:
        vo = ss.resample_poly(vo, SR, sr)
    vo = np.pad(vo, (0, max(0, n - len(vo))))[:n]
    sp = np.abs(vo) > 0.01
    if sp.any():
        vo *= 10 ** ((-18 - 20 * np.log10(np.sqrt((vo[sp] ** 2).mean()) + 1e-9)) / 20)
    fx = np.zeros(n)
    for t, name in ev:
        buf = LIB[name]()
        i = int(t * SR)
        a, b = max(0, i), min(n, i + len(buf))
        if b > a:
            fx[a:b] += buf[a - i:b - i]
    if sp.any():                                         # 说话时把音效压到人声下 10 dB
        v_db, f_db = env_db(vo), env_db(fx)
        over = np.where(v_db > -45, np.minimum(0, (v_db - 10) - f_db), 0)
        k = int(0.08 * SR)
        fx *= 10 ** (np.convolve(over, np.ones(k) / k, mode="same") / 20)
    bg = np.zeros(n)
    if os.path.exists(BGM):
        bg, bsr = sf.read(BGM, always_2d=True)
        bg = bg.mean(1)
        if bsr != SR:
            bg = ss.resample_poly(bg, SR, bsr)
        bg = np.tile(bg, n // max(1, len(bg)) + 1)[:n]
        bg *= 10 ** ((-30 - 20 * np.log10(np.sqrt((bg ** 2).mean()) + 1e-9)) / 20)   # 比人声低约 12 dB
        f = min(n // 2, int(1.5 * SR))
        bg[:f] *= np.linspace(0, 1, f)
        bg[n - f:] *= np.linspace(1, 0, f)
        if sp.any():                                     # 说话时 BGM 再让开 6 dB，0.3 秒平滑
            k = int(0.3 * SR)
            talk = np.convolve((env_db(vo) > -45).astype(float), np.ones(k) / k, mode="same")
            bg *= 10 ** (-6 * talk / 20)
    st = np.stack([vo + fx + bg, vo + fx + bg], 1)
    if np.abs(st).max() > 1e-4:
        st *= 10 ** ((-14 - lufs(st)) / 20)
        st = limiter(st, 10 ** (-1.2 / 20))
    sf.write(path, st, SR)
    print(f"wrote {path}: {len(ev)} 个音效, {total:.1f}s" + (f", {lufs(st):.1f} LUFS" if np.abs(st).max() > 1e-4 else ""))


def preview(folder=os.path.join(OUT, "音效试听")):
    """把音效库里每个音效单独导出一份，先试听、挑好再往分镜里写。"""
    os.makedirs(folder, exist_ok=True)
    for name, fn in LIB.items():
        buf = np.pad(fn(), (int(0.2 * SR), int(0.3 * SR)))
        sf.write(os.path.join(folder, f"{name}.wav"), np.stack([buf, buf], 1), SR)
    print(f"wrote {len(LIB)} 个音效 -> {folder}")


if __name__ == "__main__":
    import sys
    preview() if "--preview" in sys.argv else mix()

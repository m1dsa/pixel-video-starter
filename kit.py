"""画面工具箱：时间轴上下文、缓动、缓存、参考风格的 UI（章节进度条、像素字幕、标签牌、大数字）、小道具。
所有东西都经过 pxv 画（浮点像素格）。场景文件只 import 这里。
"""
import json
import math
import os
import random
from collections import OrderedDict
import numpy as np
from PIL import ImageFont
import pxv
import sprites as X
from pxv import Frame, Cam, W, H, PIXEL_FONT  # noqa: F401

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
CORNER = "小满  ·  像素风示例"            # 右上角的系列名（改成你的）

# ---------------------------------------------------------------- 调色（暗底 + 暖/冷光池）
GOLD, GOLD_LT, ORANGE, CREAM = (232, 186, 74), (250, 220, 130), (226, 140, 40), (236, 228, 210)
INK, DARK_TXT = (14, 12, 14), (52, 48, 40)
CYAN, RED, GREEN = (92, 206, 204), (214, 64, 52), (110, 200, 110)
SUB_STROKE = (219, 216, 210)               # 字幕奶油色描边


# ---------------------------------------------------------------- 缓动
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def back_out(x, s=1.7):
    x = clamp(x) - 1
    return x * x * ((s + 1) * x + s) + 1


def lerp(a, b, x):
    return a + (b - a) * x


# ---------------------------------------------------------------- 时间轴（voice.py 生成 out/timeline.json）
_TL = None


def tl():
    global _TL
    if _TL is None:
        _TL = json.load(open(os.path.join(OUT, "timeline.json"), encoding="utf-8"))
        _TL["scenes"] = {s["id"]: s for a in _TL["acts"] for s in a["scenes"]}
        _TL["order"] = [s["id"] for a in _TL["acts"] for s in a["scenes"]]
    return _TL


class K:
    """场景上下文。动作挂在台词上，不写死秒数：
    k.b(i) 第 i 拍开始；k.e(i) 第 i 拍结束；k.h(i, j) 第 i 拍第 j 个高亮词被念到的时刻；
    k.p(t0, d) 从 t0 开始 d 秒的 0..1 进度；k.lt 场景内的本地时间。"""

    def __init__(self, sid, t):
        self.sid, self.t = sid, t
        self.s = tl()["scenes"][sid]
        self.beats = self.s["beats"]
        self.t0, self.t1 = self.s["t0"], self.s["t1"]
        self.lt = t - self.t0

    def b(self, i):
        return self.beats[min(i, len(self.beats) - 1)]["t0"]

    def e(self, i):
        i = min(i, len(self.beats) - 1)
        return self.beats[i]["t_end"]

    def h(self, i, j=0):
        i = min(i, len(self.beats) - 1)
        ht = self.beats[i].get("hi_t") or []
        return ht[min(j, len(ht) - 1)] if ht else self.b(i)

    def p(self, t0, d=0.4):
        return clamp((self.t - t0) / d) if d > 0 else float(self.t >= t0)

    def on(self, t0):
        return self.t >= t0


# ---------------------------------------------------------------- 缓存（静态背景只画一次）
_CACHE = OrderedDict()


def cached(fr, key, fn, size=6):
    ck = (key, round(fr.cam.cx, 2), round(fr.cam.cy, 2), round(fr.cam.zoom, 4))
    if ck in _CACHE:
        fr.a[:] = _CACHE[ck]
        _CACHE.move_to_end(ck)
        return
    fn(fr)
    _CACHE[ck] = fr.a.copy()
    while len(_CACHE) > size:
        _CACHE.popitem(last=False)


_VIG = {}


def vignette(fr, k=0.5, start=0.45, power=1.6):
    key = (k, start, power)
    if key not in _VIG:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        _VIG[key] = (1 - k * np.clip((r - start) / (1.42 - start), 0, 1) ** power)[..., None].astype(np.float32)
    fr.a *= _VIG[key]


def darken(fr, k):
    if k < 1:
        fr.a *= k


def iris(fr, cx, cy, r):
    """圆形开合转场：圆外全黑，3px 软边。"""
    if r >= 2400:
        return
    yy, xx = np.ogrid[0:H, 0:W]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2).astype(np.float32)
    fr.a *= np.clip((r - d) / 3 + 0.5, 0, 1)[..., None]


# ---------------------------------------------------------------- 文字（渲染一次缓存成 RGBA）
_TXT = OrderedDict()


def _render_rgba(fn, key):
    if key in _TXT:
        _TXT.move_to_end(key)
        return _TXT[key]
    fb, fw = Frame((0, 0, 0)), Frame((255, 255, 255))
    fn(fb)
    fn(fw)
    al = 1 - (fw.a - fb.a).mean(2) / 255
    ys, xs = np.nonzero(al > 0.003)
    if len(ys) == 0:
        _TXT[key] = None
        return None
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    a = np.clip(al[y0:y1, x0:x1], 0, 1)
    col = np.where(a[..., None] > 0.003, fb.a[y0:y1, x0:x1] / np.maximum(a[..., None], 1e-3), 0)
    item = (x0, y0, col.astype(np.float32), a.astype(np.float32))
    _TXT[key] = item
    while len(_TXT) > 80:
        _TXT.popitem(last=False)
    return item


def paste_rgba(fr, item, dx=0, dy=0, alpha=1.0):
    if item is None:
        return
    x0, y0, col, a = item
    x0, y0 = int(round(x0 + dx)), int(round(y0 + dy))
    h, w = a.shape
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    aa = a[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0, None] * alpha
    reg = fr.a[Y0:Y1, X0:X1]
    reg += (col[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0] - reg) * aa


def text(fr, parts, x, y, unit, stroke=None, stroke_r=0, alpha=1.0, anchor="mm"):
    """屏幕坐标的像素字。parts: 字符串，或 [(文字, rgb), ...]；unit = 每个字体像素占几个屏幕像素。"""
    if isinstance(parts, str):
        parts = [(parts, CREAM)]
    key = ("t", tuple(parts), round(unit, 2), stroke, round(stroke_r, 2), anchor)

    def fn(f):
        f.pixel_text(list(parts), 960, 540, unit, anchor=anchor, stroke=stroke, stroke_r=stroke_r)
    paste_rgba(fr, _render_rgba(fn, key), x - 960, y - 540, alpha)


def ui(fr, s, x, y, size, color, weight="Medium", anchor="mm", alpha=1.0):
    """屏幕坐标的黑体字（只用于进度条、角标这类「界面」文字）。"""
    key = ("u", s, size, color, weight, anchor)
    paste_rgba(fr, _render_rgba(lambda f: f.ui_text(s, 960, 540, size, color, weight, anchor), key), x - 960, y - 540,
               alpha)


def text_width(s, unit):
    return ImageFont.truetype(PIXEL_FONT, 12).getlength(s) * unit


# ---------------------------------------------------------------- 顶部章节进度条 + 底部字幕
def act_of(t):
    acts = tl()["acts"]
    for i, a in enumerate(acts):
        if a["t0"] - 0.05 <= t < a["t1"]:
            return i
    return len(acts) - 1


def chapter_bar(fr, t):
    """每一章一段，当前章从左往右填满；读完的章底部一条暗金线。高 56px。"""
    acts = tl()["acts"]
    i = act_of(t)
    a = acts[i]
    prog = clamp((t - a["t0"]) / max(0.01, a["t1"] - a["t0"]))
    bh, seg = 56, W / len(acts)
    fr.srect(0, 0, W, bh, (14, 14, 15))
    fr.srect(i * seg, 0, (i + 1) * seg, bh, (32, 32, 33))
    fr.srect(i * seg, 0, i * seg + seg * prog, bh, (62, 62, 63))
    for j in range(i):
        fr.srect(j * seg, bh - 3, (j + 1) * seg, bh, (90, 78, 50))
    for j, act in enumerate(acts):
        ui(fr, act["name"], j * seg + seg / 2, bh / 2, 26, (236, 236, 236) if j == i else (128, 128, 130), "Medium")
        if j:
            fr.srect(j * seg - 1, 15, j * seg + 1, bh - 15, (66, 66, 68))
    ui(fr, CORNER, W - 42, 91, 26, (108, 108, 110), "Regular", anchor="rm")


def _sub_parts(sub, his):
    marks = [False] * len(sub)
    for w in his or []:
        k = sub.find(w)
        while k >= 0:
            for q in range(k, k + len(w)):
                marks[q] = True
            k = sub.find(w, k + len(w))
    parts, cur, curm = [], "", None
    for ch, m in zip(sub, marks):
        if m != curm and cur:
            parts.append((cur, pxv.ORANGE_TXT if curm else pxv.DARK_TXT))
            cur = ""
        cur += ch
        curm = m
    if cur:
        parts.append((cur, pxv.ORANGE_TXT if curm else pxv.DARK_TXT))
    return parts


_BEATS = None


def beat_list():
    global _BEATS
    if _BEATS is None:
        L = []
        for a in tl()["acts"]:
            for s in a["scenes"]:
                for b in s["beats"]:
                    if b.get("sub", "").strip():
                        L.append((b["t0"], b["t_end"], b["sub"].strip(), tuple(b.get("hi") or [])))
        _BEATS = sorted(L)
    return _BEATS


def subtitle(fr, t, y=993):
    """深色像素字 + 粗圆角奶油描边；高亮词橙色。≤14 字 unit 7.2，更长的按比例缩小（最小 5.6）。"""
    L = beat_list()
    cur = None
    for i, (a, e, sub, hi) in enumerate(L):
        nxt = L[i + 1][0] if i + 1 < len(L) else e + 1
        if a - 0.03 <= t < min(max(e + 0.35, a + 0.6), nxt - 0.02):
            cur = (sub, hi)
    if not cur:
        return
    sub, hi = cur
    sub = sub.rstrip("，。、；：,.")                     # 句尾标点不上屏
    unit = 7.2 if len(sub) <= 14 else max(5.6, 7.2 * 15 / len(sub))
    text(fr, _sub_parts(sub, hi), 960, y, unit, stroke=SUB_STROKE, stroke_r=unit * 1.45)


def voice_on(t, margin=0.05):
    return any(a - margin <= t <= e + margin for a, e, _, _ in beat_list())


# ---------------------------------------------------------------- 参考风格的 UI 小件（屏幕坐标）
def tag(fr, x, y, s, t=None, t0=None, unit=3.4, fg=(200, 200, 202), bg=(26, 28, 34), edge=(104, 106, 112),
        alpha=1.0, until=None):
    """深色小牌 + 细亮边 + 像素字；t0 时刻回弹弹出，until 之后 0.2s 淡出。"""
    if until is not None and t is not None:
        if t > until + 0.2:
            return
        if t > until:
            alpha *= 1 - (t - until) / 0.2
    sc = 1.0
    if t is not None and t0 is not None:
        if t < t0:
            return
        sc = back_out((t - t0) / 0.28)
    w, h = (text_width(s, unit) + unit * 8) * sc, unit * 18 * sc
    if w < 2:
        return
    fr.srect(x - w / 2 - 3, y - h / 2 - 3, x + w / 2 + 3, y + h / 2 + 3, edge, alpha)
    fr.srect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, bg, alpha)
    if sc > 0.6:
        text(fr, [(s, fg)], x, y + unit * 0.5, unit * min(1, sc), alpha=alpha)


def plate(fr, x, y, w, h, title=None, gold=True, alpha=1.0):
    """金边深色面板。"""
    e1 = (40, 30, 18) if gold else (20, 20, 24)
    e2 = (176, 132, 56) if gold else (96, 98, 106)
    fr.srect(x - w / 2 - 6, y - h / 2 - 6, x + w / 2 + 6, y + h / 2 + 6, e1, alpha)
    fr.srect(x - w / 2 - 3, y - h / 2 - 3, x + w / 2 + 3, y + h / 2 + 3, e2, alpha)
    fr.srect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, (30, 24, 20) if gold else (24, 26, 32), alpha)
    if title:
        text(fr, [(title, GOLD_LT if gold else CREAM)], x, y - h / 2 + 26, 3.2, alpha=alpha)


def big(fr, x, y, s, t=None, t0=None, unit=9.0, color=GOLD_LT, glow=True, alpha=1.0):
    """大数字 / 大字：深色粗描边 + 柔光，t0 时刻回弹砸出来。"""
    sc = 1.0
    if t is not None and t0 is not None:
        if t < t0:
            return
        sc = back_out((t - t0) / 0.32, 2.2)
    if sc <= 0.05:
        return
    u = unit * sc
    if glow and sc > 0.5:
        fr.glow([(x, y, text_width(s, u) * 0.9, 0.18)], (color[0] * 0.6, color[1] * 0.5, color[2] * 0.3))
    text(fr, [(s, color)], x, y, round(u, 1), stroke=(20, 16, 14), stroke_r=max(2, u * 0.9), alpha=alpha)


def sparkles(fr, x, y, t, n=8, r=60, color=(255, 236, 160), seed=0):
    rnd = random.Random(seed)
    for _ in range(n):
        a = rnd.uniform(0, 6.28)
        ph = (t * rnd.uniform(1.5, 3) + rnd.random()) % 1
        rr, sz = r * (0.4 + 0.6 * ph), 6 * (1 - ph)
        if sz > 0.5:
            px, py = x + math.cos(a) * rr, y + math.sin(a) * rr
            fr.srect(px - sz / 2, py - sz * 1.5, px + sz / 2, py + sz * 1.5, color, 1 - ph)
            fr.srect(px - sz * 1.5, py - sz / 2, px + sz * 1.5, py + sz / 2, color, 1 - ph)


def coin(fr, x, y, cell=6.0, alpha=1.0):
    fr.sprite([".KKK.", "KYYYK", "KYyYK", "KYYYK", ".KKK."],
              {"K": (60, 40, 10), "Y": (226, 182, 70), "y": (252, 232, 150)}, x - 2.5 * cell, y - 2.5 * cell, cell,
              alpha=alpha)


# ---------------------------------------------------------------- 角色快捷方式 + 小循环
def xm(fr, x, y, cell, eyes="open", mouth="line", legs="stand", hands=((-3.2, 16.5), (16.6, 16.5)), bust=False,
       flip=False, alpha=1.0, outfit="C"):
    X.draw(fr, x, y, cell, outfit, eyes, mouth, legs, hands, bust, flip, alpha)


def talk_mouth(t, speaking=True, rate=7.0):
    return ("talk" if int(t * rate) % 2 == 0 else "line") if speaking else "line"


def blink_eyes(t, base="open", period=3.7, seed=0.0):
    return "blink" if (t + seed) % period < 0.12 else base

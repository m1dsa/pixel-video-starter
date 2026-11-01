"""场景零件库（像素材质画法）：一点透视的房间外壳、木地板 / 地砖、墙纸、踢脚线、护墙板、窗户 + 窗外小景、窗帘、
书架和书、盆栽、挂钟、地毯、门、桌子、抽屉、挂画、吊灯、想象泡泡的云、对话气泡、砖墙、叶子丛……

每样东西都用 pix.Scene.obj 逐格上色（色阶 + 体积 + 材质 + 选择性描边 + 投影），不拿大块平涂形状凑。
写新场景：照 px_demo.py 的样子，s = Scene() 之后从后往前摆这些零件，场景特有的东西自己用 s.obj 画。
来源：我做过最好的一期像素动画的场景共用零件（2026-10）。
"""
import math
import random
import numpy as np

import pix as P


class Scene(P.Scene):
    """和 pix.Scene 一样，只是「离边几格」只在物体外框里算：大画布上快很多，画出来的结果不变。"""

    def _dist(self, m, dx, dy, cap=8):
        rows, cols = np.flatnonzero(m.any(1)), np.flatnonzero(m.any(0))
        out = np.full(m.shape, cap, np.int16)
        if len(rows) == 0:
            return out
        j0, j1, i0, i1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
        out[j0:j1, i0:i1] = P.Scene._dist(self, m[j0:j1, i0:i1], dx, dy, cap)
        return out


def tone(c, k):
    return tuple(min(255.0, max(0.0, v * k)) for v in c[:3])


def mix(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


# ====================================================================== 房间外壳（一点透视）

def leaves(s, cx, cy, n, size, base=(70, 136, 76), spread=(1.0, 1.0), seed=0, droop=False):
    """一丛叶子：一片一片画（每片有自己的明暗和描边），后面的暗、前面的亮。"""
    rnd = random.Random(seed)
    for k in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(0.2, 1.0)
        x = cx + math.cos(a) * size * 2.2 * r * spread[0]
        y = cy + math.sin(a) * size * 1.6 * r * spread[1] + (k / n * size * 3 if droop else 0)
        w, h = size * rnd.uniform(0.8, 1.2), size * rnd.uniform(0.5, 0.75)
        tone = 0.75 + 0.5 * (k / n)
        col = tuple(min(255, c * tone) for c in base)
        s.obj(s.ell(x, y, w, h), col, "round", outline=True)


def brick_wall(s, x0, y0, x1, y1, base=(150, 78, 58), mortar=(96, 66, 56), bw=64, bh=26, seed=1):
    rnd = random.Random(seed)
    s.flat(s.rect(x0, y0, x1, y1), mortar)
    row = 0
    y = y0
    while y < y1:
        off = (bw / 2) if row % 2 else 0
        x = x0 - off
        while x < x1:
            col = tuple(c * rnd.uniform(0.86, 1.1) for c in base)
            m = s.rect(max(x0, x + 3), y + 3, min(x1, x + bw - 1), min(y1, y + bh - 1))
            s.obj(m, col, "box", outline=True, bands=(1, 1))
            if rnd.random() < 0.12:                                   # 偶尔一块砖缺了个角
                s.flat(s.rect(x + bw - 14, y + 3, x + bw - 2, y + 10), mortar)
            x += bw
        y += bh
        row += 1


def frame_art(s, x, y, w, h, inner, seed=0):
    s.obj(s.rect(x, y, x + w, y + h), (70, 48, 34), "box", "wood", shadow=(2, 2, 0.35), seed=seed)
    s.obj(s.rect(x + 8, y + 8, x + w - 8, y + h - 8), (236, 226, 204), "flat", outline=False)
    inner(x + 12, y + 12, w - 24, h - 24)

def room(s, back, vp):
    """back = 后墙 (x0, y0, x1, y1)，y1 = 墙脚线；vp = 消失点。返回各个面占哪些格子：floor / ceil / left / right / back。"""
    bx0, by0, bx1, by1 = back
    VX, VY = vp
    X, Y = s.X, s.Y

    def edge(yb):
        cx = np.where(X < VX, bx0, bx1)
        return np.where((X >= bx0) & (X < bx1), yb, VY + (X - VX) * (yb - VY) / (cx - VX))
    floor = Y >= edge(by1)
    ceil = Y < edge(by0)
    side = ~floor & ~ceil & ((X < bx0) | (X >= bx1))
    return dict(floor=floor, ceil=ceil, left=side & (X < VX), right=side & (X > VX), back=~floor & ~ceil & ~side)


def _changed(a, axis):
    """a 在这一格和左边（axis=1）/ 上边（axis=0）那一格不一样 → 正好一格宽的线。"""
    d = np.zeros(a.shape, bool)
    if axis == 1:
        d[:, 1:] = a[:, 1:] != a[:, :-1]
    else:
        d[1:] = a[1:] != a[:-1]
    return d


def wood_floor(s, mask, vp, base, pw=0.34, depth=900.0, plank=3.0, seed=0, grain=True):
    """透视木地板：木板缝朝消失点收（一格宽的暗缝 + 缝右边一格亮边），每块木板颜色有固定的小差别，
    接缝错开，板面上有断续的木纹线。全是有规律的线，没有随机碎点。"""
    VX, VY = vp
    X, Y = s.X, s.Y
    d = np.maximum(Y - VY, 1.0)
    lat, dep = (X - VX) / d / pw, depth / d
    pi = np.floor(lat).astype(int)
    off = ((pi * 0.618 + seed * 0.3) % 1.0) * plank
    pj = np.floor((dep + off) / plank).astype(int)
    h = ((pi * 7919 + pj * 104729 + seed * 31) % 101) / 100.0
    k = np.where(h < 0.33, 0.93, np.where(h < 0.66, 1.0, 1.06))
    R = np.asarray(P.ramp(base), np.float32)
    col = R[2][None, None, :] * k[..., None]
    if grain:
        g = np.floor((lat - pi) * 4 + 0.5 * np.sin(dep * 0.9 + pi * 1.7)).astype(int)
        gl = _changed(g, 1) & (((np.floor(dep * 1.6) + pi) % 3) != 0)
        col = np.where(gl[..., None], col * 0.93, col)
    seam = _changed(pi, 1)
    joint = _changed(pj, 0) & ~seam
    lit = np.zeros_like(seam)
    lit[:, 1:] = seam[:, :-1]
    col = np.where(lit[..., None], np.minimum(255, col * 1.08 + 6), col)
    col = np.where(seam[..., None], R[0][None, None, :], col)
    col = np.where(joint[..., None], R[1][None, None, :] * 0.9, col)
    s.cv.a[mask, :3] = col[mask]
    s.cv.a[mask, 3] = 1.0


def tile_floor(s, mask, vp, c1, c2, tw=0.42, depth=900.0, td=1.0, grout=None):
    """透视地砖（两色棋盘）：砖缝一格宽，每块砖上沿 / 左沿亮一格。"""
    VX, VY = vp
    X, Y = s.X, s.Y
    d = np.maximum(Y - VY, 1.0)
    ti, tj = np.floor((X - VX) / d / tw).astype(int), np.floor(depth / d / td).astype(int)
    chk = (ti + tj) % 2 == 0
    col = np.where(chk[..., None], np.asarray(c1, np.float32), np.asarray(c2, np.float32))
    li = np.zeros_like(chk)
    li[:, 1:] = _changed(ti, 1)[:, :-1]
    lj = np.zeros_like(chk)
    lj[1:] = _changed(tj, 0)[:-1]
    col = np.where((li | lj)[..., None], np.minimum(255, col * 1.07 + 5), col)
    g = _changed(ti, 1) | _changed(tj, 0)
    gc = np.asarray(grout or tone(c2, 0.78), np.float32)
    col = np.where(g[..., None], gc, col)
    s.cv.a[mask, :3] = col[mask]
    s.cv.a[mask, 3] = 1.0


def wallpaper(s, mask, base, motif="diamond", k=0.94, step=(12, 9)):
    """墙纸：本色 + 很淡的规则小花纹（菱形 / 竖条 / 小点），不是随机点。"""
    s.flat(mask, base)
    gx, gy = s.cv.gx, s.cv.gy
    sx, sy = step
    if motif == "stripe":
        m = mask & ((gx // sx) % 2 == 0)
    elif motif == "dots":
        m = mask & (gy % sy == 0) & ((gx + (gy // sy % 2) * (sx // 2)) % sx == 0)
    elif motif == "diamond":
        cx = (gx + (gy // sy % 2) * (sx // 2)) % sx - sx // 2
        cy = gy % sy - sy // 2
        m = mask & (np.abs(cx) + np.abs(cy) == 1)
    else:
        m = mask & False
    s.flat(m, tone(base, k))


def side_wall(s, mask, base, vp, depth_shade=True):
    """侧墙：比后墙暗一点，离消失点越近越亮（一级一级，不渐变）。"""
    s.flat(mask, base)
    if depth_shade:
        VX = vp[0]
        far = np.abs(s.X - VX)
        for i, k in enumerate((0.96, 0.92, 0.88)):
            s.flat(mask & (far > 760 + i * 120), tone(base, k))


def baseboard(s, x0, x1, y, h=16, col=(236, 232, 222)):
    s.obj(s.rect(x0, y - h, x1, y), col, "box", bands=(1, 1))
    s.band_ao(y, depth=4, k=0.28, x0=x0, x1=x1)


def wainscot(s, x0, x1, y0, y1, col, panel=120, rail=(0, 0, 0)):
    """护墙板：一块块凹进去的方框（外框亮边 + 里面一圈暗边）+ 顶上一条压条。"""
    s.obj(s.rect(x0, y0, x1, y1), col, "box", bands=(1, 1))
    n = max(1, int(round((x1 - x0) / panel)))
    w = (x1 - x0) / n
    for k in range(n):
        a, b = x0 + k * w + 14, x0 + (k + 1) * w - 14
        s.obj(s.rect(a, y0 + 18, b, y1 - 14), tone(col, 0.94), "box", bands=(1, 1), light=(1, 1))
    s.obj(s.rect(x0 - 4, y0 - 10, x1 + 4, y0 + 2), tone(col, 1.04), "box", bands=(1, 1), shadow=(0, 2, 0.3))


# ====================================================================== 窗户、窗外、窗帘
def sky(s, x0, y0, x1, y1, top, bot, n=8):
    """天空：n 条横色带，每条一个颜色（不渐变、不抖动）。"""
    for k in range(n):
        c = mix(top, bot, k / max(1, n - 1))
        s.flat(s.rect(x0, y0 + (y1 - y0) * k / n, x1, y0 + (y1 - y0) * (k + 1) / n + 4), c)


def city(s, x0, y0, x1, y1, seed=0, night=False, base=(150, 160, 178), lit=(250, 214, 140), far=True, lit_p=0.3):
    """窗外的楼：远处一排浅色楼（不描边）+ 近一点的几栋（有窗户格子，晚上一部分窗户亮着）。只画在 (x0, y0, x1, y1) 里面。"""
    rnd = random.Random(seed)
    clip = s.rect(x0, y0, x1, y1)
    if far:
        x = x0 - 20
        while x < x1:
            w = rnd.uniform(40, 90)
            top = y0 + (y1 - y0) * rnd.uniform(0.25, 0.55)
            s.obj(s.rect(x, top, x + w, y1) & clip, tone(base, 1.08 if not night else 0.8), "flat", outline=False)
            x += w + rnd.uniform(-6, 8)
    x = x0 - 30
    while x < x1:
        w = rnd.uniform(70, 130)
        top = y0 + (y1 - y0) * rnd.uniform(0.35, 0.7)
        c = tone(base, rnd.uniform(0.82, 0.95) * (0.62 if night else 1.0))
        s.obj(s.rect(x, top, x + w, y1 + 10) & clip, c, "box", bands=(1, 1))
        for wy in np.arange(top + 12, y1 - 6, 20):
            for wx in np.arange(x + 10, x + w - 12, 18):
                on = night and rnd.random() < lit_p
                s.flat(s.rect(wx, wy, wx + 10, wy + 12) & clip, lit if on else tone(c, 0.78 if not night else 0.7))
                if not on and not night:
                    s.flat(s.rect(wx, wy, wx + 4, wy + 4) & clip, tone(c, 1.12))
        x += w + rnd.uniform(4, 16)


def tree(s, cx, base_y, h, leaf=(76, 140, 80), trunk=(96, 70, 50), seed=0, n=26):
    s.obj(s.poly([(cx - 8, base_y), (cx + 8, base_y), (cx + 5, base_y - h * 0.55), (cx - 5, base_y - h * 0.55)]), trunk, "cylv")
    leaves(s, cx, base_y - h * 0.72, n, h * 0.13, leaf, seed=seed)


_RT_BLOBS = ((0, -120, 58), (-40, -92, 42), (42, -90, 44), (-8, -150, 40), (26, -140, 36), (-30, -132, 30))


def round_tree(s, x, base_y, sc, pal, seed=0):
    """K12 岔路口同款圆冠树（paint.Canvas.round_tree）：树干 + 5~6 团树叶，向阳面亮、底下暗。
    pal = (树叶, 亮面, 暗面, 树干, 树干暗)。返回整棵树（树干 + 树冠）占的格子。"""
    s.cv.round_tree(x, base_y, sc, *pal, seed=seed)
    m = s.rect(x - 7 * sc, base_y - 70 * sc, x + 7 * sc, base_y)
    for dx, dy, rad in _RT_BLOBS:
        m |= s.ell(x + dx * sc, base_y + dy * sc, rad * sc, rad * sc * 0.9)
    return m


def window(s, x0, y0, x1, y1, outside, frame=(236, 232, 222), cols=2, rows=1, sill=True, fw=14, glare=True):
    """窗户：先画窗外（outside(s, x0, y0, x1, y1)），再叠斜着的玻璃反光，最后画窗框、窗格、窗台。"""
    outside(s, x0, y0, x1, y1)
    if glare:
        gx, gy = s.cv.gx, s.cv.gy
        band = (gx + gy) % 46
        inside = s.rect(x0, y0, x1, y1)
        s.flat(inside & (band < 5), (255, 255, 255), 0.16)
        s.flat(inside & (band >= 7) & (band < 9), (255, 255, 255), 0.12)
    s.obj(s.rect(x0 - fw, y0 - fw, x1 + fw, y0), frame, "box", bands=(1, 1), shadow=(0, 2, 0.3))
    s.obj(s.rect(x0 - fw, y1, x1 + fw, y1 + fw), frame, "box", bands=(1, 1))
    s.obj(s.rect(x0 - fw, y0, x0, y1), frame, "box", bands=(1, 1), shadow=(2, 0, 0.25))
    s.obj(s.rect(x1, y0, x1 + fw, y1), frame, "box", bands=(1, 1))
    for k in range(1, cols):
        x = x0 + (x1 - x0) * k / cols
        s.obj(s.rect(x - fw / 2, y0, x + fw / 2, y1), frame, "box", bands=(1, 1), shadow=(2, 0, 0.25))
    for k in range(1, rows):
        y = y0 + (y1 - y0) * k / rows
        s.obj(s.rect(x0, y - fw / 2, x1, y + fw / 2), frame, "box", bands=(1, 1), shadow=(0, 2, 0.25))
    if sill:
        s.obj(s.rect(x0 - fw - 16, y1 + fw, x1 + fw + 16, y1 + fw + 14), tone(frame, 1.02), "box", bands=(1, 1),
              shadow=(0, 3, 0.35))


def curtain(s, x0, y0, x1, y1, base, side="l", tie=0.55, pull=0.45, folds=None, seed=0):
    """拉到一边、用绑带系住的窗帘：一道道褶子（每道一个竖圆柱，深浅交替），在绑带那儿收窄，下面再散开。
    side = 窗帘收在哪一边（"l" 往左收、"r" 往右收）。"""
    n = folds or max(3, int((x1 - x0) / 20))
    w = x1 - x0
    yt = y0 + (y1 - y0) * tie
    anchor = x0 if side == "l" else x1
    pts_x = lambda f, squeeze: anchor + ((x0 + w * f) - anchor) * squeeze
    for k in range(n):
        f0, f1 = k / n, (k + 1) / n
        c = tone(base, (0.9, 1.0, 1.06, 0.96)[(k + seed) % 4])
        poly = [(x0 + w * f0, y0), (x0 + w * f1 + 2, y0), (pts_x(f1, pull) + 2, yt), (pts_x(f1, 0.8) + 2, y1),
                (pts_x(f0, 0.8), y1), (pts_x(f0, pull), yt)]
        s.obj(s.poly(poly), c, "cylv", outline=k in (0, n - 1))
    tx0, tx1 = pts_x(0, pull) - 4, pts_x(1, pull) + 4
    s.obj(s.rect(min(tx0, tx1), yt - 8, max(tx0, tx1), yt + 8), tone(base, 0.7), "cylh")


def drape(s, x0, y0, x1, y1, base, folds=None, seed=0):
    """垂下来的窗帘（没系起来）：竖褶子 + 下摆。"""
    n = folds or max(2, int((x1 - x0) / 22))
    w = (x1 - x0) / n
    for k in range(n):
        c = tone(base, (0.9, 1.0, 1.06, 0.96)[(k + seed) % 4])
        s.obj(s.rect(x0 + k * w, y0, x0 + (k + 1) * w + 2, y1), c, "cylv", outline=k in (0, n - 1))
    s.obj(s.rect(x0, y1 - 10, x1, y1), tone(base, 0.84), "box", bands=(1, 1))


def rod(s, x0, x1, y, col=(150, 120, 80)):
    s.obj(s.rect(x0, y - 5, x1, y + 5), col, "cylh", "metal", shadow=(0, 2, 0.3))
    for x in (x0, x1):
        s.obj(s.ell(x, y, 10, 10), col, "round")


# ====================================================================== 书架、书、小摆件
BOOK_COLS = [(176, 64, 58), (60, 100, 150), (220, 180, 90), (80, 130, 90), (140, 90, 150), (230, 226, 214),
             (200, 120, 70), (60, 60, 70), (110, 160, 190), (190, 150, 110)]


def books(s, x0, x1, base_y, hmax, seed=0, cols=None, lean=True, gap=0.08, deco=None):
    """一排书：宽窄高矮不一，每本有亮边 / 暗边 / 描边，书脊上一道标签条；偶尔留个空、斜靠一本。"""
    rnd = random.Random(seed)
    cols = cols or BOOK_COLS
    x = x0
    while x < x1 - 8:
        w = rnd.choice((10, 12, 14, 16, 18, 22))
        if x + w > x1:
            break
        if rnd.random() < gap:
            x += rnd.choice((12, 20))
            continue
        h = hmax * rnd.uniform(0.66, 1.0)
        c = rnd.choice(cols)
        if lean and rnd.random() < 0.07 and x + h * 0.6 < x1:     # 斜靠的一本
            s.obj(s.poly([(x, base_y), (x + w * 1.2, base_y), (x + w * 1.2 + h * 0.5, base_y - h * 0.86),
                          (x + h * 0.5, base_y - h * 0.86)]), c, "box", bands=(1, 1))
            x += w * 1.2 + h * 0.5 + 4
            continue
        s.obj(s.rect(x, base_y - h, x + w, base_y), c, "box", bands=(1, 1), shadow=(1, 0, 0.3))
        ly = base_y - h + h * rnd.uniform(0.15, 0.3)
        s.flat(s.rect(x + 4, ly, x + w - 4, ly + 4), tone(c, 1.3) if sum(c) < 500 else tone(c, 0.7))
        if rnd.random() < 0.4:
            s.flat(s.rect(x + 4, base_y - 10, x + w - 4, base_y - 7), tone(c, 0.75))
        x += w
    return x


def bookcase(s, x0, y0, x1, y1, shelves=4, wood=(120, 82, 56), seed=0, fill=None, back=None):
    """书架：木框 + 背板 + 一层层隔板 + 书。fill(s, k, x0, x1, base_y, h) 可以自己往第 k 层放东西（返回 True 就不放书）。"""
    s.obj(s.rect(x0, y0, x1, y1), wood, "box", "woodv", shadow=(4, 2, 0.4), seed=seed)
    s.obj(s.rect(x0 + 12, y0 + 12, x1 - 12, y1 - 16), back or tone(wood, 0.55), "flat", outline=False)
    hh = (y1 - y0 - 28) / shelves
    for k in range(shelves):
        by = y0 + 12 + hh * (k + 1)
        s.obj(s.rect(x0 + 8, by - 8, x1 - 8, by + 2), tone(wood, 1.06), "box", "wood", seed=seed + k)
        if fill and fill(s, k, x0 + 14, x1 - 14, by - 8, hh - 14):
            continue
        books(s, x0 + 14, x1 - 14, by - 8, hh - 18, seed=seed * 10 + k)
    s.obj(s.rect(x0 - 6, y0 - 8, x1 + 6, y0 + 4), tone(wood, 1.08), "box", "wood", seed=seed + 9)


def pot(s, cx, base_y, w, h, col=(196, 110, 80), shadow=True, rim=True):
    s.obj(s.poly([(cx - w / 2, base_y - h), (cx + w / 2, base_y - h), (cx + w * 0.38, base_y), (cx - w * 0.38, base_y)]),
          col, "cylv", "ceramic", shadow=(3, 1, 0.4) if shadow else None)
    if rim:
        s.obj(s.rect(cx - w / 2 - 3, base_y - h - 3, cx + w / 2 + 3, base_y - h + 6), tone(col, 1.06), "cylh")


def plant(s, cx, base_y, size=1.0, kind="bush", pot_col=(196, 110, 80), leaf=(76, 140, 80), seed=0):
    """盆栽：kind = bush 一团叶子 / snake 虎尾兰（竖着的尖叶）/ hang 吊兰垂下来 / tall 高的观叶植物。"""
    pw, ph = 46 * size, 40 * size
    if kind == "snake":
        rnd = random.Random(seed)
        for k in range(7):
            x = cx + (k - 3) * 6 * size + rnd.uniform(-2, 2)
            hh = ph * rnd.uniform(1.6, 2.6)
            lean = (k - 3) * 4 * size
            c = tone(leaf, rnd.uniform(0.85, 1.1))
            s.obj(s.poly([(x - 6 * size, base_y - ph + 4), (x + 6 * size, base_y - ph + 4), (x + lean + 1, base_y - ph - hh)]),
                  c, "cylv")
            s.flat(s.poly([(x - 2, base_y - ph), (x + 2, base_y - ph), (x + lean, base_y - ph - hh * 0.8)]), (210, 200, 110), 0.5)
    elif kind == "hang":
        leaves(s, cx, base_y - ph - 10 * size, 12, 10 * size, leaf, seed=seed)
        for k, dx in enumerate((-1, 1)):
            for m in range(5):
                leaves(s, cx + dx * (pw * 0.55 + m * 3), base_y - ph + m * 18 * size, 2, 8 * size, leaf, seed=seed + k * 9 + m)
    elif kind == "tall":
        s.obj(s.rect(cx - 3, base_y - ph - 120 * size, cx + 3, base_y - ph), (96, 76, 52), "cylv")
        leaves(s, cx, base_y - ph - 130 * size, 30, 20 * size, leaf, spread=(1.0, 1.3), seed=seed)
    else:
        leaves(s, cx, base_y - ph - 14 * size, 16, 14 * size, leaf, seed=seed)
    pot(s, cx, base_y, pw, ph, pot_col)


def wall_clock(s, cx, cy, r, rim=(70, 50, 36), face=(244, 238, 222)):
    """挂钟（不带指针，指针按时间另画 clock_hands）：木边 + 白表盘 + 12 个刻度。"""
    s.obj(s.ell(cx, cy, r, r), rim, "round", "wood", shadow=(2, 2, 0.35))
    s.obj(s.ell(cx, cy, r * 0.8, r * 0.8), face, "round", outline=False, light=(-0.6, -0.6))
    for k in range(12):
        a = k / 12 * 2 * math.pi
        L = 6 if k % 3 == 0 else 3
        x, y = cx + math.sin(a) * r * 0.66, cy - math.cos(a) * r * 0.66
        s.flat(s.rect(x - 2, y - 2, x + 2 + (2 if k % 3 == 0 else 0), y + L - 2), (50, 40, 36))
    s.obj(s.ell(cx, cy, 4, 4), (60, 50, 44), "round", outline=False)


def clock_hands(fr, cx, cy, r, hour, minute, col=(40, 32, 30)):
    """指针：一格一格的小方块排成线（像素风，不用矢量线）。"""
    for frac, L, w in (((hour % 12 + minute / 60) / 12, r * 0.42, 6), (minute / 60, r * 0.6, 4)):
        a = frac * 2 * math.pi
        for k in range(int(L / 3)):
            x, y = cx + math.sin(a) * k * 3, cy - math.cos(a) * k * 3
            fr.rect(x - w / 2, y - w / 2, w, w, col)


def rug(s, pts, base, border, stripes=2):
    """地毯：外圈一道边、里面再一道细边、中间本色 + 几道横纹（都是透视里的多边形，往中心缩）。"""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)

    def shrink(k):
        return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in pts]
    s.obj(s.poly(pts), border, "flat", outline=True)
    s.obj(s.poly(shrink(0.9)), base, "flat", outline=False)
    s.obj(s.poly(shrink(0.82)), border, "flat", outline=False)
    s.obj(s.poly(shrink(0.78)), base, "flat", outline=False)
    if stripes:
        s.obj(s.poly(shrink(0.4)), mix(base, border, 0.5), "flat", outline=False)
        s.obj(s.poly(shrink(0.32)), base, "flat", outline=False)


def door(s, x0, y0, x1, y1, col=(150, 104, 66), frame=(236, 232, 222), knob="r", panels=True):
    """木门：门框 + 门板 + 四块凹板 + 黄铜把手。"""
    s.obj(s.rect(x0 - 14, y0 - 14, x1 + 14, y1), frame, "box", bands=(1, 1), shadow=(3, 0, 0.3))
    s.obj(s.rect(x0, y0, x1, y1), col, "box", "woodv", seed=int(x0))
    if panels:
        w, h = x1 - x0, y1 - y0
        for (a, b, c, d) in ((0.14, 0.08, 0.46, 0.44), (0.54, 0.08, 0.86, 0.44), (0.14, 0.52, 0.46, 0.92),
                             (0.54, 0.52, 0.86, 0.92)):
            s.obj(s.rect(x0 + w * a, y0 + h * b, x0 + w * c, y0 + h * d), tone(col, 0.94), "box", bands=(1, 1), light=(1, 1))
    kx = x1 - 22 if knob == "r" else x0 + 22
    s.obj(s.ell(kx, (y0 + y1) / 2 + 10, 7, 7), (220, 180, 90), "round")
    s.obj(s.rect(kx - 3, (y0 + y1) / 2 - 10, kx + 3, (y0 + y1) / 2 + 2), (190, 150, 70), "cylv", "metal")


def table(s, x0, y, x1, h, wood=(140, 96, 62), top=14, legs=True, apron=12, seed=0, leg_w=12, shadow=True):
    """桌子（正面看）：桌面（木纹 + 投影）+ 下面一圈牙板 + 两条腿。y = 桌面上沿；h = 桌面到地面。"""
    s.obj(s.rect(x0, y, x1, y + top), wood, "box", "wood", shadow=(0, 4, 0.45) if shadow else None, seed=seed,
          bands=(1, 1))
    if apron:
        s.obj(s.rect(x0 + 10, y + top, x1 - 10, y + top + apron), tone(wood, 0.8), "box", bands=(1, 1))
    if legs:
        for lx in (x0 + 12, x1 - 12 - leg_w):
            s.obj(s.rect(lx, y + top, lx + leg_w, y + h), tone(wood, 0.86), "cylv", seed=seed)


def drawers(s, x0, y0, x1, y1, n, wood=(140, 96, 62), knob=(200, 170, 110)):
    s.obj(s.rect(x0, y0, x1, y1), wood, "box", "wood", seed=int(x0))
    hh = (y1 - y0) / n
    for k in range(n):
        a = y0 + k * hh
        s.obj(s.rect(x0 + 8, a + 6, x1 - 8, a + hh - 4), tone(wood, 1.03), "box", bands=(1, 1))
        s.obj(s.rect((x0 + x1) / 2 - 14, a + hh / 2 - 2, (x0 + x1) / 2 + 14, a + hh / 2 + 4), knob, "cylh", "metal")


def frame_pic(s, x0, y0, x1, y1, inner, wood=(70, 48, 34), mat=(236, 226, 204), seed=0):
    """挂画 / 相框：木框 + 白卡纸 + 画心（inner(x0, y0, x1, y1) 自己画）。"""
    s.obj(s.rect(x0, y0, x1, y1), wood, "box", "wood", shadow=(3, 3, 0.35), seed=seed, bands=(1, 1))
    s.obj(s.rect(x0 + 8, y0 + 8, x1 - 8, y1 - 8), mat, "flat", outline=False)
    inner(x0 + 14, y0 + 14, x1 - 14, y1 - 14)


def landscape(s, x0, y0, x1, y1, sky_c=(150, 196, 226), hill=(110, 160, 100), sun=(250, 214, 120)):
    """挂画里的小风景：天 + 太阳 + 两层山。"""
    s.obj(s.rect(x0, y0, x1, y1), sky_c, "flat", outline=False)
    s.obj(s.ell(x0 + (x1 - x0) * 0.7, y0 + (y1 - y0) * 0.35, (x1 - x0) * 0.1, (x1 - x0) * 0.1), sun, "round",
          outline=False)
    s.obj(s.poly([(x0, y1), (x0, y0 + (y1 - y0) * 0.6), (x0 + (x1 - x0) * 0.35, y0 + (y1 - y0) * 0.45),
                  (x0 + (x1 - x0) * 0.7, y0 + (y1 - y0) * 0.7), (x1, y0 + (y1 - y0) * 0.55), (x1, y1)]), hill, "flat",
          outline=False)
    s.obj(s.poly([(x0, y1), (x0, y0 + (y1 - y0) * 0.8), (x0 + (x1 - x0) * 0.5, y0 + (y1 - y0) * 0.72), (x1, y0 + (y1 - y0) * 0.85),
                  (x1, y1)]), tone(hill, 0.8), "flat", outline=False)


def pendant(s, x, top, y, shade=(40, 70, 66), w=48):
    """吊灯：灯线 + 金属灯罩 + 亮着的灯泡。"""
    s.flat(s.rect(x - 2, top, x + 2, y - 46), (30, 26, 24))
    s.obj(s.poly([(x - w, y), (x + w, y), (x + w * 0.46, y - 50), (x - w * 0.46, y - 50)]), shade, "cylv", "metal")
    s.obj(s.rect(x - w - 2, y - 4, x + w + 2, y + 4), (190, 150, 80), "cylh", "metal")
    s.obj(s.ell(x, y + 8, 16, 9), (255, 236, 170), "round", outline=False)


def ceiling_lamp(s, x, y, w=120, col=(244, 240, 228)):
    """吸顶灯：扁扁的乳白灯罩 + 一圈金属边。"""
    s.obj(s.ell(x, y, w / 2, 16), col, "round", light=(-0.3, -1))
    s.obj(s.rect(x - w / 2 + 6, y - 18, x + w / 2 - 6, y - 10), (200, 196, 190), "cylh", "metal")


# ====================================================================== 想象泡泡（像素画法）
def think_cloud(s, cx, cy, w, h, seed=0, col=(240, 236, 226)):
    """云朵泡泡：一圈大小不一的圆鼓包叠起来，奶白色、底边暗一点、外圈描边。返回云的格子（泡泡里的小场景只画在里面）。"""
    rnd = random.Random(seed)
    m = s.ell(cx, cy, w * 0.42, h * 0.38)
    for k in range(11):
        a = k / 11 * 2 * math.pi
        m |= s.ell(cx + math.cos(a) * w * 0.38, cy + math.sin(a) * h * 0.34, w * rnd.uniform(0.15, 0.2), h * rnd.uniform(0.2, 0.26))
    s.obj(m, col, "round", light=(-0.6, -0.8), shadow=(3, 3, 0.35))
    return m


def cloud_tail(s, pts, col=(240, 236, 226)):
    """泡泡的尾巴：从头顶往上一串越来越大的小圆。pts = [(x, y, r), ...]。"""
    for x, y, r in pts:
        s.obj(s.ell(x, y, r, r * 0.85), col, "round")


def speech_px(s, x0, y0, x1, y1, tail, col=(250, 246, 234)):
    """像素画法的对话气泡（圆角框 + 小尾巴），字另外写。tail = 尾巴尖 (x, y)。"""
    r = 12
    m = s.rect(x0 + r, y0, x1 - r, y1) | s.rect(x0, y0 + r, x1, y1 - r)
    for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
        m |= s.ell(cx, cy, r, r)
    tx, ty = tail
    bx = min(max(tx, x0 + 30), x1 - 30)
    m |= s.poly([(bx - 14, y1 - 2), (bx + 14, y1 - 2), (tx, ty)]) if ty > y1 else s.poly([(bx - 14, y0 + 2), (bx + 14, y0 + 2), (tx, ty)])
    s.obj(m, col, "flat", shadow=(2, 3, 0.3))
    return m


def monstera_leaf(s, cx, cy, r, ang, col, seed=0):
    """一片龟背竹叶子：心形大叶（圆 + 叶柄那头凹进去）+ 从边上往中间切的几道裂口 + 中间一条叶脉。ang = 叶尖朝哪个方向（弧度）。"""
    ca, sa = math.cos(ang), math.sin(ang)
    m = s.ell(cx, cy, r, r * 0.86)
    bx, by = cx - ca * r * 0.95, cy - sa * r * 0.95                      # 叶柄那头的凹口
    m &= ~s.ell(bx, by, r * 0.28, r * 0.28)
    rnd = random.Random(seed)
    for side in (-1, 1):                                                  # 两边各两三道裂口（细长的楔形）
        for k in range(rnd.choice((2, 3))):
            t = -0.5 + k * 0.45 + rnd.uniform(-0.08, 0.08)
            px, py = cx + ca * r * t, cy + sa * r * t
            ex, ey = px - sa * side * r * 1.1, py + ca * side * r * 1.1
            ix, iy = px - sa * side * r * 0.35, py + ca * side * r * 0.35
            w = r * 0.07
            m &= ~s.poly([(ix - ca * w * 0.3, iy - sa * w * 0.3), (ex - ca * w, ey - sa * w), (ex + ca * w, ey + sa * w),
                          (ix + ca * w * 0.3, iy + sa * w * 0.3)])
    s.obj(m, col, "round", shadow=(3, 2, 0.35), light=(-0.5, -0.8))
    vein = s.poly([(bx + sa * 2, by - ca * 2), (cx + ca * r * 0.85 + sa * 2, cy + sa * r * 0.85 - ca * 2),
                   (cx + ca * r * 0.85 - sa * 2, cy + sa * r * 0.85 + ca * 2), (bx - sa * 2, by + ca * 2)])
    s.flat(m & vein, tone(col, 0.72))
    return m

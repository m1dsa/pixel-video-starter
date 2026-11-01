"""场景库（静态环境）。世界坐标 = 1080p 像素（镜头 zoom=1 时）；地形格 U=6。
每个场景分「静态部分」（交给 kit.cached 只画一次）和「光」（每帧乘一遍）。
画法统一：先画底色大块 -> 再画细节（6px 网格对齐）-> 角色/道具 -> light() 打光 -> vignette()。
"""
import math
import random
import numpy as np
from kit import W, H, text, lerp

U = 6.0


def ring_cells(cx, cy, r0, r1, u):
    """像素化圆环（钟面、太阳、树冠）：返回落在 r0..r1 之间的格子，用 fr.cells(...) 一次画出，没有接缝。"""
    out = []
    n = int(r1 / u) + 2
    gx0, gy0 = int(cx // u), int(cy // u)
    for gy in range(gy0 - n, gy0 + n + 1):
        for gx in range(gx0 - n, gx0 + n + 1):
            if r0 <= math.hypot(gx * u + u / 2 - cx, gy * u + u / 2 - cy) < r1:
                out.append((gx, gy))
    return out



def planks(fr, x0, y0, x1, y1, base, line, step=48, seed=0):
    fr.srect(x0, y0, x1, y1, base)
    rnd = random.Random(seed)
    x = x0
    while x < x1:
        fr.rect(x, y0, 4, y1 - y0, line)
        for _ in range(3):
            fr.rect(x + rnd.uniform(8, step - 12), rnd.uniform(y0, y1 - 30), 3, rnd.choice([18, 30, 42]), line, 0.5)
        x += step


# ====================================================================== 奶茶店 · 店内
def shop_static(fr):
    planks(fr, 0, 56, W, 700, (74, 52, 38), (58, 40, 29), 48, 1)
    fr.srect(0, 466, W, 480, (98, 70, 48))
    fr.srect(0, 480, W, 486, (44, 30, 22))
    # menu board
    fr.rect(690, 104, 540, 236, (40, 26, 18))
    fr.rect(702, 116, 516, 212, (28, 36, 33))
    sx, sy = fr.cam.pt(960, 150)
    z = fr.cam.zoom
    text(fr, [("满杯奶茶", (240, 214, 150))], sx, sy, round(4.6 * z, 1))
    for i, (n, p) in enumerate([("珍珠奶茶", "¥12"), ("杨枝甘露", "¥16"), ("芋泥波波", "¥15")]):
        a, b = fr.cam.pt(800, 206 + i * 38)
        text(fr, [(n, (210, 210, 200))], a, b, round(2.6 * z, 1), anchor="lm")
        a, b = fr.cam.pt(1120, 206 + i * 38)
        text(fr, [(p, (236, 190, 90))], a, b, round(2.6 * z, 1))
    # shelves with cups & syrups
    rnd = random.Random(4)
    for sx0 in (130, 1350):
        for sy0 in (300, 420):
            fr.rect(sx0, sy0, 440, 12, (110, 80, 52))
            fr.rect(sx0, sy0 + 12, 440, 6, (40, 28, 20))
            x = sx0 + 14
            while x < sx0 + 410:
                if rnd.random() < 0.55:
                    fr.rect(x, sy0 - 48, 30, 48, (30, 22, 18))
                    fr.rect(x + 3, sy0 - 45, 24, 45, (226, 220, 206))
                    fr.rect(x + 3, sy0 - 30, 24, 9, (150, 96, 60))
                    x += 36
                else:
                    c = rnd.choice([(196, 70, 60), (220, 170, 70), (110, 160, 90), (150, 90, 160)])
                    fr.rect(x + 6, sy0 - 66, 18, 66, (24, 18, 16))
                    fr.rect(x + 9, sy0 - 54, 12, 51, c)
                    fr.rect(x + 12, sy0 - 64, 6, 10, (60, 44, 34))
                    x += 30
    # pendant lamps
    for lx in (420, 960, 1500):
        fr.rect(lx - 2, 56, 4, 92, (30, 24, 20))
        fr.sprite(["...KKKKKK...", "..KGGGGGGK..", ".KGGGGGGGGK.", "KGgggggggggK" if False else "KGGGGGGGGGGK",
                   "KKKKKKKKKKKK", "....YYYY...."],
                  {"K": (20, 22, 20), "G": (44, 74, 62), "Y": (255, 230, 160)}, lx - 36, 146, 6.0)
    # wall clock (face only; hands are dynamic)
    cx, cy = 300, 186
    fr.cells(ring_cells(cx, cy, 0, 72, U), (30, 20, 16), 0, 0, U)
    fr.cells(ring_cells(cx, cy, 0, 64, U), (232, 224, 204), 0, 0, U)
    for k in range(12):
        a = k * math.pi / 6
        r = 52
        fr.rect(round((cx + math.sin(a) * r) / U) * U - 3, round((cy - math.cos(a) * r) / U) * U - 3,
                6 if k % 3 else 9, 6 if k % 3 else 9, (60, 44, 36))
    # counter
    fr.srect(0, 700, W, 728, (212, 198, 172))
    fr.srect(0, 700, W, 704, (240, 230, 210))
    fr.srect(0, 728, W, 736, (70, 48, 32))
    planks(fr, 0, 736, W, H, (124, 80, 48), (100, 62, 36), 60, 2)
    # register
    fr.rect(1440, 600, 210, 100, (26, 26, 30))
    fr.rect(1452, 612, 120, 44, (40, 80, 60))
    fr.rect(1590, 612, 46, 70, (50, 50, 56))
    fr.rect(1430, 690, 230, 12, (40, 40, 44))


def shop_clock_hands(fr, minute=10.0, cx=300, cy=186):
    def hand(ang, ln, w, col):
        ca, sa = math.cos(ang), math.sin(ang)
        nx, ny = -sa * w / 2, ca * w / 2
        fr.poly([(cx + nx, cy + ny), (cx + ca * ln + nx * 0.6, cy + sa * ln + ny * 0.6),
                 (cx + ca * ln - nx * 0.6, cy + sa * ln - ny * 0.6), (cx - nx, cy - ny)], col)
    hand(math.radians(minute * 6 - 90), 50, 7, (40, 30, 26))
    hand(math.radians((10 + minute / 60) * 30 - 90), 34, 9, (40, 30, 26))
    fr.rect(cx - 5, cy - 5, 10, 10, (190, 60, 50))


def shop_light(fr, extra=()):
    fr.light([(420, 560, 560, 0.55), (960, 600, 680, 0.95), (1500, 560, 560, 0.55)] + list(extra), ambient=0.22,
             tint=(1.0, 0.92, 0.8), cap=1.15)


def cup(fr, x, y, cell=6.0, sealed=True, fill=(176, 120, 76)):
    rows = ["KKKKKK" if sealed else "......", "KccccK", "KffffK", "KffffK", "KbbbbK", ".KbbK."]
    if sealed:
        rows = ["..s...", "KKsKKK", "KccccK", "KffffK", "KffffK", "KbbbbK", ".KKKK."]
    fr.sprite(rows, {"K": (40, 30, 24), "c": (240, 236, 226), "f": fill, "b": (40, 28, 24), "s": (214, 70, 60)},
              x, y, cell)


def shaker(fr, x, y, cell=6.0):
    fr.sprite([".KKK.", "KgggK", "KGGGK", "KGgGK", "KGgGK", "KGGGK", "KGGGK", ".KKK."],
              {"K": (30, 32, 36), "G": (196, 202, 210), "g": (236, 240, 246)}, x, y, cell)


# ====================================================================== 店门口 · 夜
def shop_front_static(fr, sign="满杯奶茶"):
    fr.srect(0, 56, W, H, (16, 18, 26))
    rnd = random.Random(2)
    for _ in range(60):
        fr.rect(rnd.uniform(0, W), rnd.uniform(60, 300), 3, 3, (180, 190, 220), rnd.uniform(0.2, 0.6))
    # building facade
    fr.rect(300, 180, 1320, 720, (58, 44, 40))
    planks(fr, 300, 180, 1620, 900, (58, 44, 40), (48, 36, 33), 72, 3)
    fr.rect(300, 180, 1320, 18, (30, 22, 20))
    # sign board
    fr.rect(520, 220, 880, 120, (26, 18, 14))
    fr.rect(530, 230, 860, 100, (90, 46, 30))
    sx, sy = fr.cam.pt(960, 282)
    text(fr, [(sign, (255, 214, 140))], sx, sy, round(6.4 * fr.cam.zoom, 1))
    # big window (warm interior)
    fr.rect(420, 400, 1080, 440, (24, 18, 16))
    fr.rect(432, 412, 1056, 416, (150, 106, 66))
    for k in range(1, 4):
        fr.rect(432 + k * 264 - 3, 412, 6, 416, (24, 18, 16))
    for i in range(14):
        fr.rect(470 + i * 72, 760, 30, 52, (226, 220, 206), 0.7)
    # pavement
    fr.srect(0, 900, W, H, (40, 40, 46))
    for x in range(0, W, 96):
        fr.rect(x, 900, 3, 180, (30, 30, 36))
    fr.srect(0, 900, W, 906, (70, 70, 76))


def shutter(fr, p):
    """Rolling shutter over the window, p 0 (up) .. 1 (down)."""
    if p <= 0:
        return
    h = 416 * p
    fr.rect(432, 412, 1056, h, (120, 124, 132))
    y = 412
    while y < 412 + h:
        fr.rect(432, y, 1056, 4, (84, 88, 96))
        y += 22
    fr.rect(426, 412 + h - 10, 1068, 12, (60, 62, 70))


def front_light(fr, window=1.0, extra=()):
    spots = [(960, 640, 900, 0.75 * window, 1.6), (960, 280, 700, 0.5, 2.0)] + list(extra)
    fr.light(spots, ambient=0.28, tint=(1.0, 0.9, 0.75), cap=1.2)


# ====================================================================== 卧室 (小满 home base)
def bedroom_static(fr, season="night"):
    WALL = (70, 74, 96) if season != "day" else (120, 118, 130)
    fr.srect(0, 56, W, 760, WALL)
    for y in range(80, 760, 30):
        fr.rect(0, y, W, 2, (WALL[0] - 8, WALL[1] - 8, WALL[2] - 10), 0.7)
    fr.srect(0, 760, W, H, (86, 60, 44))
    for y in range(780, H, 36):
        fr.rect(0, y, W, 3, (70, 48, 34))
    # window (sky drawn dynamically into the opening)
    fr.rect(1250, 150, 420, 330, (40, 30, 26))
    fr.rect(1262, 162, 396, 306, (10, 12, 20))
    # poster + shelf
    fr.rect(860, 170, 180, 230, (30, 24, 24))
    fr.rect(870, 180, 160, 210, (210, 196, 170))
    fr.rect(900, 220, 100, 120, (120, 150, 170))
    fr.rect(900, 300, 100, 40, (90, 120, 80))
    fr.rect(500, 280, 260, 12, (110, 80, 52))
    for i, c in enumerate([(180, 70, 60), (70, 110, 170), (220, 180, 80), (90, 150, 90), (150, 90, 160)]):
        fr.rect(512 + i * 30, 214, 24, 66, c)
        fr.rect(512 + i * 30, 214, 24, 6, (30, 24, 22))
    # bed (left)
    fr.rect(60, 600, 620, 200, (40, 28, 24))
    fr.rect(70, 610, 600, 120, (180, 170, 150))
    fr.rect(70, 690, 600, 110, (60, 80, 130))
    fr.rect(60, 520, 30, 280, (60, 40, 30))
    # desk (right)
    fr.rect(1080, 700, 760, 30, (96, 64, 40))
    fr.rect(1080, 730, 760, 10, (50, 32, 22))
    fr.rect(1100, 740, 26, 220, (70, 46, 30))
    fr.rect(1794, 740, 26, 220, (70, 46, 30))


def window_sky(fr, mode="night", t=0.0):
    x0, y0, w, h = 1262, 162, 396, 306
    if mode == "night":
        fr.rect(x0, y0, w, h, (14, 18, 36))
        rnd = random.Random(3)
        for _ in range(26):
            fr.rect(x0 + rnd.uniform(6, w - 12), y0 + rnd.uniform(6, h - 120), 4, 4, (220, 226, 255),
                    0.5 + 0.5 * math.sin(t * 2 + rnd.random() * 6))
        fr.sprite(["..KKK", ".KCCK", "KCCK.", "KCK..", "KCCK.", ".KCCK", "..KKK"],
                  {"K": (40, 40, 60), "C": (246, 232, 170)}, x0 + 300, y0 + 40, 7)
    elif mode == "dawn":
        for i in range(10):
            c = lerp(np.array((240, 180, 120)), np.array((120, 150, 210)), i / 9)
            fr.rect(x0, y0 + i * h / 10, w, h / 10 + 1, tuple(c))
        fr.rect(x0 + 80, y0 + 190, 60, 60, (255, 230, 150))
    else:   # seasons: spring/summer/autumn/winter
        sky = {"spring": (150, 196, 230), "summer": (110, 170, 236), "autumn": (220, 170, 110), "winter": (170, 180, 196)}[mode]
        fr.rect(x0, y0, w, h, sky)
        tree = {"spring": (240, 170, 190), "summer": (70, 150, 70), "autumn": (220, 120, 50), "winter": (230, 236, 244)}[mode]
        fr.rect(x0 + 170, y0 + 180, 30, 126, (90, 60, 40))
        for dx, dy, r in [(185, 150, 80), (130, 190, 50), (240, 190, 56)]:
            fr.cells(ring_cells(x0 + dx, y0 + dy, 0, r, 6), tree, 0, 0, 6)
        if mode == "winter":
            rnd = random.Random(int(t * 4))
            for _ in range(30):
                fr.rect(x0 + rnd.uniform(0, w), y0 + rnd.uniform(0, h), 5, 5, (250, 250, 255))
    fr.rect(x0 + w / 2 - 4, y0, 8, h, (40, 30, 26))
    fr.rect(x0, y0 + h / 2 - 4, w, 8, (40, 30, 26))


def desk_lamp(fr, on=True, x=1700, y=700):
    fr.sprite(["....KKKKK", "...KGGGGGK", "..KGGGGGGGK", ".KKKKKKKKKK", "......K", "......K", "......K", ".....K",
               "....K", "...K", "..KKKKK", ".KKKKKKK"],
              {"K": (30, 30, 34), "G": (196, 170, 80) if on else (110, 100, 70)}, x - 60, y - 140, 10)
    if on:
        fr.rect(x - 40, y - 100, 60, 6, (255, 236, 170))


def bedroom_light(fr, lamp=True, extra=(), amb=0.22):
    spots = list(extra)
    if lamp:
        spots += [(1640, 640, 760, 0.95, 1.2)]
    fr.light(spots, ambient=amb, tint=(1.0, 0.9, 0.76), cap=1.2)


def monitor(fr, x, y, w=220, h=150, screen=(40, 80, 120), on=True):
    fr.rect(x - 6, y - 6, w + 12, h + 12, (24, 24, 28))
    fr.rect(x, y, w, h, screen if on else (16, 18, 22))
    fr.rect(x + w / 2 - 12, y + h + 6, 24, 30, (30, 30, 34))
    fr.rect(x + w / 2 - 50, y + h + 34, 100, 10, (30, 30, 34))


# ====================================================================== 黑色舞台 (abstract beats)
def stage_static(fr, floor=760, col=(26, 24, 30)):
    fr.srect(0, 56, W, H, (12, 11, 14))
    fr.srect(0, floor, W, H, col)
    fr.srect(0, floor, W, floor + 4, (46, 42, 50))


def spot(fr, x, y=None, r=420, s=1.0, cone=True):
    """Stage spotlight: soft cone from the top + pool. Call before light() as extra spot list."""
    return [(x, (y or 700), r, s, 0.9)]


def stage_light(fr, spots, amb=0.18):
    fr.light(spots, ambient=amb, tint=(1.0, 0.94, 0.84), cap=1.25)


def beam(fr, x, top=56, bottom=780, w0=80, w1=420, alpha=0.10, color=(255, 236, 190)):
    """Visible light cone (additive, drawn after light())."""
    import cv2
    m = np.zeros((H // 4, W // 4), np.float32)
    pts = np.array([[(x - w0 / 2) / 4, top / 4], [(x + w0 / 2) / 4, top / 4], [(x + w1 / 2) / 4, bottom / 4],
                    [(x - w1 / 2) / 4, bottom / 4]], np.int32)
    cv2.fillPoly(m, [pts], 1.0)
    m = cv2.GaussianBlur(m, (0, 0), 6)
    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
    fr.a += m[..., None] * alpha * np.asarray(color, np.float32)


# ====================================================================== 夜街 · 公交站
def street_static(fr):
    fr.srect(0, 56, W, H, (12, 14, 24))
    rnd = random.Random(5)
    x = 0
    while x < W:
        bw = rnd.choice([150, 200, 240])
        bh = rnd.uniform(260, 520)
        fr.rect(x, 760 - bh, bw - 8, bh, (26, 28, 42))
        for wy in range(int(780 - bh), 740, 36):
            for wx in range(int(x + 16), int(x + bw - 30), 30):
                if rnd.random() < 0.3:
                    fr.rect(wx, wy, 14, 18, (240, 200, 120), 0.85)
        x += bw
    fr.srect(0, 760, W, 820, (50, 50, 58))
    fr.srect(0, 820, W, H, (30, 30, 36))
    for x in range(40, W, 220):
        fr.rect(x, 940, 110, 10, (200, 196, 160), 0.6)


def streetlamp(fr, x, y_top=330, on=True):
    fr.rect(x - 6, y_top, 12, 760 - y_top, (40, 42, 48))
    fr.rect(x - 6, y_top, 80, 12, (40, 42, 48))
    fr.rect(x + 50, y_top + 10, 44, 16, (30, 32, 36))
    if on:
        fr.rect(x + 54, y_top + 26, 36, 6, (255, 230, 170))


def busstop(fr, x=820):
    fr.rect(x, 430, 12, 330, (60, 64, 72))
    fr.rect(x + 560, 430, 12, 330, (60, 64, 72))
    fr.rect(x - 20, 410, 612, 24, (70, 74, 84))
    fr.rect(x + 20, 450, 300, 250, (120, 150, 170), 0.18)
    fr.rect(x + 340, 450, 200, 260, (30, 34, 40))
    fr.rect(x + 350, 460, 180, 240, (200, 120, 90))
    fr.rect(x + 60, 690, 440, 18, (90, 70, 50))
    fr.rect(x + 80, 708, 12, 52, (50, 40, 34))
    fr.rect(x + 468, 708, 12, 52, (50, 40, 34))


def street_light(fr, spots, amb=0.3):
    fr.light(spots, ambient=amb, tint=(1.0, 0.9, 0.72), cap=1.25)

"""像素材质画法样张：夜里的房间一角 + 书桌，主角坐在桌后。照着它写你自己的场景。

  python px_demo.py      -> out/像素材质样张.png

写法要点（规则全文见 docs/pixel-material.md）：
  - 场景分层：build() 画墙上 / 远景，build_desk() 画桌子和桌上的东西（前景），人物夹在两层中间画，就能「坐在桌后」；
  - 室内至少十几样东西，分墙上 / 中景 / 前景三层，每样都用 s.obj 逐格上色，不用大块平涂凑；
  - 场景用 lru_cache 只画一次，每帧只 blit（在 scenes_*.py 里也一样）；
  - 最后整体打光：把整间屋照亮，不只亮一小块；不抖动、不撒噪点、不加大光晕。
"""
import math
import os
from functools import lru_cache

import kit as KIT
import px_parts as K
from px_parts import tone

VP = (900.0, 420.0)                        # 一点透视的消失点
BACK = (60.0, 60.0, 1860.0, 790.0)         # 后墙
DESK_Y, DESK_FRONT = 790.0, 830.0
LAMP = (1720.0, 640.0)
MUG = (1500.0, 780.0)


def _night(s, x0, y0, x1, y1):
    """窗外：夜空、月亮、星星、对面楼几扇亮着的窗。"""
    K.sky(s, x0, y0, x1, y1, (16, 20, 48), (44, 48, 90), n=6)
    for k in range(10):
        x = x0 + 10 + (k * 97) % max(1, int(x1 - x0 - 20))
        y = y0 + 10 + (k * 53) % max(1, int((y1 - y0) * 0.5))
        s.flat(s.rect(x, y, x + 4, y + 4), (230, 230, 250))
    s.obj(s.ell(x0 + 80, y0 + 70, 26, 26), (246, 236, 196), "round", outline=False)
    s.obj(s.ell(x0 + 90, y0 + 62, 22, 22), (18, 22, 50), "flat", outline=False)
    K.city(s, x0, y0 + 120, x1, y1, seed=21, night=True, base=(70, 76, 110), lit_p=0.4)


@lru_cache(maxsize=None)
def build():
    """墙上 / 远景：墙纸、护墙板、窗 + 窗帘、海报、挂钟、隔板（书、盆栽、相框、木头小人）、一串小灯。"""
    s = K.Scene()
    bx0, by0, bx1, by1 = BACK
    R = K.room(s, BACK, VP)
    K.wallpaper(s, R["back"], (92, 106, 140), "stripe", k=0.95, step=(8, 8))
    s.flat(R["ceil"], (70, 74, 96))
    K.wood_floor(s, R["floor"], VP, (150, 108, 76), seed=4)
    K.wainscot(s, bx0, bx1, 600, by1, (82, 70, 66), panel=160)
    K.window(s, 150, 130, 470, 430, _night, frame=(200, 196, 190), cols=2)
    K.rod(s, 110, 510, 102, (120, 120, 130))
    K.drape(s, 106, 102, 170, 500, (40, 58, 110))
    K.drape(s, 450, 102, 514, 500, (40, 58, 110), seed=1)
    K.frame_pic(s, 940, 120, 1080, 300, lambda *r: K.landscape(s, *r, sky_c=(236, 150, 110), hill=(80, 70, 110),
                                                                sun=(250, 210, 120)), wood=(30, 30, 36), mat=(30, 30, 36))
    K.wall_clock(s, 1200, 190, 36)
    s.obj(s.rect(1300, 330, 1760, 344), (120, 90, 64), "box", "wood", shadow=(0, 4, 0.4), seed=3)
    K.books(s, 1316, 1460, 330, 74, seed=33)
    K.plant(s, 1500, 330, 0.6, "hang", pot_col=(200, 196, 190), seed=4)
    s.obj(s.rect(1560, 266, 1630, 330), (60, 50, 44), "box", shadow=(2, 1, 0.3))
    s.obj(s.rect(1566, 272, 1624, 322), (110, 150, 120), "flat", outline=False)
    s.obj(s.ell(1690, 290, 12, 12), (200, 160, 110), "round", "wood")
    s.obj(s.rect(1680, 302, 1700, 330), (200, 160, 110), "box", "wood")
    for k in range(22):
        x = 1310 + k * 20
        y = 360 + 8 * math.sin(k / 21 * math.pi * 2) ** 2
        s.flat(s.rect(x, y, x + 20, y + 2), (60, 50, 40))
        s.obj(s.ell(x + 10, y + 9, 5, 6), ((255, 214, 120), (255, 180, 120), (255, 236, 170))[k % 3], "round", outline=False)
    return s


@lru_cache(maxsize=None)
def build_desk():
    """前景：书桌（胡桃木 + 抽屉）、台灯、一摞书、马克杯、摊开的笔记本和笔、小仙人掌、眼镜。"""
    s = K.Scene(-200, 600, 2120, 1140)
    wood = (110, 76, 54)
    s.obj(s.poly([(0, DESK_Y), (1920, DESK_Y), (1960, DESK_FRONT), (-40, DESK_FRONT)]), wood, "flat", "wood", seed=8, tex_k=0.7)
    s.obj(s.rect(-40, DESK_FRONT, 1960, DESK_FRONT + 22), tone(wood, 0.9), "box", bands=(1, 1))
    s.obj(s.rect(-20, DESK_FRONT + 22, 1940, 1140), tone(wood, 0.82), "box", "wood", seed=9, tex_k=0.5)
    for x0 in (1300, 1620):
        s.obj(s.rect(x0, DESK_FRONT + 50, x0 + 260, DESK_FRONT + 140), tone(wood, 0.9), "box", bands=(1, 1))
        s.obj(s.rect(x0 + 110, DESK_FRONT + 90, x0 + 150, DESK_FRONT + 100), (210, 190, 150), "cylh", "metal")
    lx, ly = LAMP
    s.obj(s.ell(lx + 100, DESK_Y + 6, 46, 12), (40, 40, 46), "round", shadow=(3, 1, 0.4))
    s.obj(s.poly([(lx + 94, DESK_Y + 4), (lx + 104, DESK_Y + 4), (lx + 56, 520), (lx + 46, 520)]), (50, 50, 56), "cylv", "metal")
    s.obj(s.poly([(lx + 46, 524), (lx + 56, 516), (lx + 12, 590), (lx + 2, 584)]), (50, 50, 56), "cylv", "metal")
    s.obj(s.ell(lx + 51, 520, 9, 9), (200, 80, 60), "round")
    s.obj(s.poly([(lx - 60, ly), (lx + 46, ly), (lx + 16, ly - 56), (lx - 20, ly - 60)]), (214, 90, 60), "cylv", "ceramic")
    s.obj(s.ell(lx - 7, ly + 2, 46, 7), (255, 236, 170), "round", outline=False)
    for k, c in enumerate(((180, 70, 60), (60, 110, 150), (230, 200, 120), (90, 140, 90))):
        s.obj(s.rect(120 + k * 6, 800 - k * 16, 300 - k * 8, 816 - k * 16), c, "box", bands=(1, 1), shadow=(2, 1, 0.35))
        s.flat(s.rect(290 - k * 8, 803 - k * 16, 296 - k * 8, 813 - k * 16), (250, 248, 240))
    mx, my = MUG
    s.obj(s.rect(mx - 22, my - 50, mx + 22, my + 6), (236, 232, 222), "cylv", "ceramic", shadow=(2, 1, 0.4))
    s.obj(s.rect(mx + 22, my - 40, mx + 34, my - 14), (236, 232, 222), "cylv")
    s.obj(s.ell(mx, my - 50, 20, 5), (150, 90, 50), "round", outline=False)
    s.obj(s.poly([(980, 800), (1220, 800), (1236, 824), (964, 824)]), (250, 248, 238), "flat", "paper")
    s.flat(s.rect(1098, 800, 1102, 824), (210, 206, 196))
    for k in range(3):
        s.flat(s.rect(990, 806 + k * 6, 1090 - k * 20, 808 + k * 6), (120, 120, 140))
    s.obj(s.poly([(1130, 818), (1220, 798), (1224, 804), (1134, 824)]), (60, 60, 70), "cylv")
    s.obj(s.rect(1620, 770, 1650, 812), (200, 120, 80), "cylv", "ceramic")
    s.obj(s.ell(1635, 756, 12, 18), (90, 150, 90), "round")
    for x in (1360, 1400):
        s.obj(s.ell(x, 806, 16, 10), (200, 220, 236), "round", "glass")
    s.flat(s.rect(1374, 804, 1388, 808), (60, 60, 70))
    return s


def frame():
    fr = KIT.Frame((20, 20, 28))
    fr.cam = KIT.Cam()
    build().blit(fr)                                                  # 墙上 / 远景
    KIT.xm(fr, 760, 528, 13.0, "open", "line", hands=((-3.2, 15.5), (16.6, 15.5)), bust=True)   # 人物夹在两层中间
    build_desk().blit(fr)                                             # 前景桌子挡住人物下半身
    fr.light([(1660, 640, 700, 1.0), (320, 280, 600, 0.45), (900, 420, 1300, 0.55)], ambient=0.62,
             tint=(1.0, 0.94, 0.84), cap=1.2)                         # 整间屋都照到，台灯处最亮
    KIT.vignette(fr, 0.35, 0.45, 1.6)
    return fr


if __name__ == "__main__":
    os.makedirs(KIT.OUT, exist_ok=True)
    p = os.path.join(KIT.OUT, "像素材质样张.png")
    frame().image().save(p)
    print("wrote", p)

"""角色像素图：主角小满（造型 C）+ 路人生成器。全部是「字符画」，每个字符 = 一格像素，颜色查调色板。

行语法（S 函数）："5:KHHK 12:KK" = 从第 5 列开始画 KHHK，再从第 12 列开始画 KK，其余是透明的「.」。
网格 20 列宽：头 15 行 + 身体 8 行 + 腿 2 行；手是单独的 5×5 小块，浮在身体两侧（参考作品的画法）。
规则：选择性深色描边 K、每种材质 2~3 阶色（亮 / 本色 / 暗）、表情只换眼睛和嘴两块零件。
"""


def S(rows):
    out = []
    for r in rows:
        line = {}
        for seg in r.split():
            col, chars = seg.split(":", 1)
            for i, ch in enumerate(chars):
                line[int(col) + i] = ch
        width = max(line) + 1 if line else 0
        out.append("".join(line.get(i, ".") for i in range(width)))
    w = max(len(r) for r in out)
    return [r.ljust(w, ".") for r in out]


# ---------------------------------------------------------------- 可替换零件
EYES = {   # 第 8-10 行，第 4..15 列（12 宽）
    "open":  ["ssssssssssss", "sswppssppwss", "ssssssssssss"],
    "look":  ["ssssssssssss", "sswppsswppss", "ssssssssssss"],
    "blink": ["ssssssssssss", "sseeesseeess", "ssssssssssss"],
    "happy": ["sssessssesss", "ssesessesess", "ssssssssssss"],
    "sad":   ["ssssssssssss", "sseeesseeess", "ssseessseess"],
    "wide":  ["sswwwsswwwss", "sswppssppwss", "ssssssssssss"],
    "tired": ["sseeesseeess", "sswppssppwss", "ssssssssssss"],
}
MOUTH = {  # 第 12 行，第 8..11 列
    "line": "sMMs", "talk": "MrrM", "smile": "MssM", "o": "sMMs", "frown": "sMMs", "grin": "MrrM", "none": "ssss",
}
MOUTH2 = {  # 第 13 行
    "smile": "sMMs", "talk": "sMMs", "frown": "MssM", "o": "sMMs", "grin": "sMMs",
}
HAND = [".KKK.", "KNssK", "KsssK", "KssqK", ".KKK."]
LEGS = {
    "stand": ["5:KPPPK 10:KPPPK", "5:KBBBK 10:KBBBK"],
    "walk1": ["4:KPPPK 10:KPPPK", "3:KBBBK 11:KBBBK"],
    "walk2": ["5:KPPPK 9:KPPPK", "5:KBBBKBBBK"],
    "sit":   [],
}


def compose(head, body, eyes="open", mouth="line", legs="stand"):
    rows = [list(r.ljust(20, ".")) for r in S(head + body + LEGS[legs])]
    for i, er in enumerate(EYES[eyes]):
        for j, ch in enumerate(er):
            if rows[8 + i][4 + j] in "swpeG":
                rows[8 + i][4 + j] = ch
    for j, ch in enumerate(MOUTH[mouth]):
        rows[12][8 + j] = ch
    if mouth in MOUTH2:
        for j, ch in enumerate(MOUTH2[mouth]):
            if rows[13][8 + j] == "s":
                rows[13][8 + j] = ch
    return ["".join(r) for r in rows]


# ---------------------------------------------------------------- 小满 · 造型 C：藏青白点头巾 · 雀斑 · 棕围裙
C_HEAD = [
    "6:KK 12:KK",
    "5:KHHKKKKHHK",
    "4:KNNNNNNNNNNK",
    "3:KNnNNNNNNNNNNK",
    "3:KNNNNnNNNNNnNK",
    "3:KNNNNNNNNNNNNK",
    "3:KHHHHHHHHHHHHK",
    "3:KHsbbbssbbbsHK",
    "2:KSssssssssssssSK",
    "2:KSswpsssswpsssSK",
    "2:KSsfsfssssfsfsSK",
    "3:KsssssSssssssK",
    "3:KksssssssssskK",
    "4:KssssssssssK",
    "5:KKssssssKK",
]
C_BODY = [
    "4:KTTOKssKOTTK",
    "3:KTTTOOOOOOTTTK",
    "3:KTTOOOOOOOOTTK",
    "3:KtTOOOooOOOTtK",
    "3:KtTOOOooOOOTtK",
    "3:KttOOOOOOOOttK",
    "4:KKOOOOOOOOKK",
    "4:KPPPPPPPPPPK",
]
C_PAL = {
    "K": (22, 18, 22), "N": (40, 54, 98), "n": (226, 230, 240), "H": (178, 92, 46),
    "s": (236, 178, 132), "S": (200, 140, 98), "b": (120, 60, 30), "w": (240, 238, 232),
    "p": (24, 20, 24), "e": (44, 30, 28), "f": (196, 120, 82), "M": (92, 36, 32), "r": (134, 56, 48),
    "k": (232, 150, 140), "T": (228, 226, 218), "t": (188, 184, 176), "O": (150, 92, 50), "o": (226, 196, 120),
    "P": (52, 50, 64), "B": (30, 28, 32), "q": (196, 140, 102),
}

DESIGNS = {"C": dict(head=C_HEAD, body=C_BODY, pal=C_PAL, name="C 围裙（店里）")}


def outfit(base, key, name, **colors):
    """同一套行、只换颜色 = 换衣服。例：outfit("C", "Cj", "便装", T=..., O=...)"""
    d = dict(DESIGNS[base])
    p = dict(d["pal"])
    p.update(colors)
    d.update(pal=p, name=name)
    DESIGNS[key] = d


outfit("C", "Cj", "C 便装：白 T + 深绿外套", T=(54, 94, 72), t=(34, 64, 50), O=(230, 228, 220), o=(230, 228, 220))
outfit("C", "Cp", "C 睡衣：灰蓝", T=(104, 112, 136), t=(78, 84, 104), O=(150, 158, 182), o=(150, 158, 182))


def sprite(design="C", eyes="open", mouth="line", legs="stand", bust=False):
    d = DESIGNS[design]
    rows = compose(d["head"], d["body"], eyes, mouth, legs)
    return rows[:21] if bust else rows


def draw(fr, x, y, cell, design="C", eyes="open", mouth="line", legs="stand", hands=((-3.2, 16.5), (16.6, 16.5)),
         bust=False, flip=False, alpha=1.0):
    """(x, y) = 20 列网格左上角（世界坐标）；cell = 每格多少像素；hands = 两只手相对网格的格数偏移。"""
    pal = DESIGNS[design]["pal"]
    fr.sprite(sprite(design, eyes, mouth, legs, bust), pal, x, y, cell, alpha=alpha, flip=flip)
    hp = dict(pal)
    hp["N"] = (250, 222, 196)                    # 手心高光
    for hx, hy in hands or ():
        if flip:
            hx = 20 - 5 - hx
        fr.sprite(HAND, hp, x + hx * cell, y + hy * cell, cell, alpha=alpha)


# ---------------------------------------------------------------- 路人（随机配色，同一套骨架）
GEN_HEAD = [
    "5:KKKKKKKKK",
    "4:KHHHHHHHHHK",
    "3:KHhHHHHHHHHHK",
    "3:KHhHHHHHHHHHHK",
    "3:KHHHHHHHHHHHHK",
    "3:KHHHHHHHHHHHHK",
    "3:KHssHHssHHssHK",
    "3:KHsbbbssbbbsHK",
    "2:KSssssssssssssSK",
    "2:KSssssssssssssSK",
    "2:KSssssssssssssSK",
    "3:KssssssSsssssK",
    "3:KssssssssssssK",
    "4:KssssssssssK",
    "5:KKssssssKK",
]
GEN_BODY = [
    "4:KTTTKssKTTTK",
    "3:KTTTTTTTTTTTTK",
    "3:KTTTTTTTTTTTTK",
    "3:KtTTTTTTTTTTtK",
    "3:KtTTTTTTTTTTtK",
    "3:KttTTTTTTTTttK",
    "4:KKttttttttKK",
    "4:KPPPPPPPPPPK",
]
SKINS = [(236, 182, 140), (224, 166, 120), (210, 150, 106), (240, 196, 160)]
HAIRS = [(40, 36, 40), (90, 56, 34), (140, 90, 50), (60, 44, 36), (170, 170, 176)]
SHIRTS = [(70, 110, 170), (170, 70, 70), (90, 140, 90), (200, 170, 80), (130, 90, 150), (80, 80, 92), (220, 220, 214)]


def _shade(c, k):
    return tuple(int(min(255, max(0, v * k))) for v in c)


def person_pal(seed=0, hair=None, shirt=None, skin=None):
    import random
    r = random.Random(seed)
    sk, hr, sh = skin or r.choice(SKINS), hair or r.choice(HAIRS), shirt or r.choice(SHIRTS)
    return {"K": (20, 18, 20), "H": hr, "h": _shade(hr, 1.5), "s": sk, "S": _shade(sk, 0.85), "b": _shade(hr, 0.7),
            "w": (240, 238, 232), "p": (24, 20, 24), "e": (44, 30, 28), "M": (92, 36, 32), "r": (134, 56, 48),
            "k": (232, 150, 140), "T": sh, "t": _shade(sh, 0.75), "P": (46, 48, 60), "B": (28, 26, 30),
            "N": (250, 222, 196), "q": _shade(sk, 0.82)}


def person(fr, x, y, cell, seed=0, eyes="open", mouth="line", legs="stand", hands=((-3.2, 16.5), (16.6, 16.5)),
           pal=None, flip=False, alpha=1.0, bust=False):
    rows = compose(GEN_HEAD, GEN_BODY, eyes, mouth, legs)
    rows = rows[:21] if bust else rows
    p = pal or person_pal(seed)
    fr.sprite(rows, p, x, y, cell, alpha=alpha, flip=flip)
    for hx, hy in hands or ():
        if flip:
            hx = 20 - 5 - hx
        fr.sprite(HAND, p, x + hx * cell, y + hy * cell, cell, alpha=alpha)

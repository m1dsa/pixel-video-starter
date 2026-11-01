"""示例场景：S01 奶茶店里的两分钟，S02 下班。

写场景的固定套路（每一帧都从头画，函数只依赖时间 t -> 同一时刻渲两次结果完全一样）：
  1. Frame(底色, Cam(cx, cy, zoom))           镜头：用缓动做推拉，不要硬切 zoom
  2. KIT.cached(fr, "名字", sets.xxx_static)    静态背景只画一次
  3. 动态道具 + 角色（主动作挂在台词上：k.h(i) = 第 i 句的高亮词被念到的时刻）
  4. 前景遮挡（柜台挡住角色下半身）
  5. sets.xxx_light(fr) 打光 -> KIT.vignette(fr) 压暗角
  6. 屏幕空间 UI：tag 标签 / big 大字（世界坐标用 fr.cam.pt 换算）
每个镜头 = 1 个主动作 + 2 个小循环（眨眼、摇杯、呼吸、灯闪……），画面永远不完全静止。
"""
import math
import kit as KIT
import sets as ST
from kit import Frame, Cam, W, H, tag, big, ease_in_out, back_out, clamp, lerp, xm
from film import scene

XM_CELL = 16.0                      # 主角每格 16px；近景 20~30，远景 6~9


def xm_counter(fr, t, x=800, y=330, eyes=None, mouth="smile", shake=True):
    """小满站在柜台后摇杯（柜台由调用方随后盖上去）。"""
    osc = math.sin(t * 2 * math.pi * 3.2) * 1.4 if shake else 0      # 小循环 1：摇杯
    e = eyes or KIT.blink_eyes(t, "open")                              # 小循环 2：眨眼
    hands = ((3.0, 15.0 + osc), (12.0, 15.0 - osc)) if shake else ((-3.2, 16.5), (16.6, 16.5))
    xm(fr, x, y, XM_CELL, e, mouth, "stand", hands=hands)
    if shake:
        ST.shaker(fr, x + 7.6 * XM_CELL, y + (11.5 + osc * 0.3) * XM_CELL, XM_CELL * 0.9)


def counter_front(fr):
    p = fr.cam.pt
    fr.srect(*p(0, 700), *p(W, 728), (212, 198, 172))
    fr.srect(*p(0, 700), *p(W, 704), (240, 230, 210))
    fr.srect(*p(0, 728), *p(W, 736), (70, 48, 32))
    x0, y0 = p(0, 736)
    x1, y1 = p(W, H + 400)
    fr.srect(x0, y0, x1, y1, (124, 80, 48))
    x = 0
    while x < W:
        a, b = p(x, 736)
        fr.srect(a, b, a + 4 * fr.cam.zoom, y1, (100, 62, 36))
        x += 60
    fr.rect(1440, 600, 210, 100, (26, 26, 30))
    fr.rect(1452, 612, 120, 44, (40, 80, 60))
    fr.rect(1590, 612, 46, 70, (50, 50, 56))
    fr.rect(1430, 690, 230, 12, (40, 40, 44))


@scene("S01", enter="fade")
def S01(k):
    t = k.t
    z = lerp(1.35, 1.0, ease_in_out((t - k.t0 - 0.3) / 1.6))        # 镜头：近景拉开到全店
    cy = lerp(560, 540, ease_in_out((t - k.t0 - 0.3) / 1.6))
    minute = 10 + (1 if t > k.h(1) else 0) + (1 if t > k.h(1) + 0.4 else 0)
    fr = Frame((10, 9, 9), Cam(960, cy, z))
    KIT.cached(fr, "shop", ST.shop_static)
    ST.shop_clock_hands(fr, minute)
    xm_counter(fr, t, mouth="smile" if t < k.b(3) else "grin", eyes="happy" if k.on(k.h(3) + 0.2) else None)
    counter_front(fr)
    if k.on(k.h(1) + 0.1):                                            # 封好的一杯弹到柜台上
        p = back_out((t - k.h(1) - 0.1) / 0.3)
        ST.cup(fr, 1160, 700 - 42 * p, 6.0 * max(0.2, p))
    ST.shop_light(fr)
    KIT.vignette(fr, 0.5, 0.45, 1.6)
    if k.on(k.h(0)):
        tag(fr, *fr.cam.pt(1150, 380), "小满", t, k.h(0), unit=3.6, fg=KIT.GOLD_LT, until=k.b(2))
    if k.on(k.h(1) - 0.2):
        tag(fr, *fr.cam.pt(300, 290), "≈ 2 分钟", t, k.h(1) - 0.2, unit=3.2)
    if k.on(k.h(2)):
        tag(fr, *fr.cam.pt(1290, 560), "时薪 ¥20", t, k.h(2), unit=3.6, fg=KIT.GOLD_LT)
    if k.on(k.h(3) - 0.45):                                           # 硬币掉进围裙口袋
        p = clamp((t - (k.h(3) - 0.45)) / 0.45)
        if p < 1:
            KIT.coin(fr, 960, 420 + p * 230, 6.0)
    if k.on(k.h(3)):
        big(fr, 1300, 440, "¥0.67", t, k.h(3), unit=9, color=KIT.GOLD_LT)
        if t - k.h(3) < 0.8:
            KIT.sparkles(fr, 1300, 440, t, 10, 120)
    return fr


@scene("S02", enter="fade", exit="fade")
def S02(k):
    t = k.t
    off = k.on(k.h(1))                                                # 「停了」：招牌灯灭
    fr = Frame((8, 8, 12), Cam(960, 560, lerp(1.0, 1.08, ease_in_out(k.lt / 4))))   # 慢推
    KIT.cached(fr, "front_on" if not off else "front_off",
               lambda f: ST.shop_front_static(f, "满杯奶茶" if not off else "打烊了"))
    ST.shutter(fr, ease_in_out((t - k.b(0) - 0.2) / 1.0))              # 主动作：拉卷帘门
    for i in range(14):                                               # 小循环 1：星星闪
        sx, sy = 80 + i * 137 % 1800, 80 + (i * 53) % 200
        fr.rect(sx, sy, 6, 6, (220, 226, 255), 0.5 + 0.5 * math.sin(t * 2.5 + i * 1.7))
    sigh = k.on(k.e(1) + 0.3)
    breathe = 6.0 if math.sin(t * 3.0) > 0 else 0.0                   # 小循环 2：呼吸（像素风是两帧跳，不是平滑浮动）
    xm(fr, 1240, 560 + breathe, 12.0, "tired" if sigh else KIT.blink_eyes(t, "open"), "frown" if sigh else "line",
       hands=((-3.2, 12.0 + 0.6 * math.sin(t * 2)), (16.6, 16.5)), outfit="Cj")
    ST.front_light(fr, window=0.25 if off else 1.0 - 0.6 * ease_in_out((t - k.b(0)) / 1.2),
                   extra=[(1340, 700, 520, 0.55)])                     # 路灯打在小满身上：主角永远在光池里
    if not off:
        fr.glow([(960, 282, 520, 0.10 + 0.03 * math.sin(t * 9))], (255, 190, 110))  # 小循环：招牌灯微闪
    KIT.vignette(fr, 0.55, 0.42, 1.6)
    if off:
        big(fr, 760, 520, "¥0.00", t, k.h(1), unit=9, color=(176, 176, 182), glow=False)
        tag(fr, 760, 640, "一下班就归零", t, k.h(1) + 0.3, unit=3.2, fg=(240, 120, 110))
    return fr

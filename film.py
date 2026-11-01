"""渲染器：场景注册、转场、顶部进度条 + 字幕、多进程编码、审片联系表。

  python film.py --chars                 定妆照：主角各表情/服装 -> out/定妆.png
  python film.py --sheet S01 S02         每一拍一张截图拼成联系表 -> out/sheet_S01-S02.png（先看这个再渲视频）
  python film.py --still 3.5             单帧 -> out/still_3.5.png
  python film.py --range 0 8             预览片段（带声音）-> out/预览_0-8.mp4
  python film.py --full                  整片（带声音）-> out/成片.mp4
  python film.py --cover "两分钟" "挣了六毛七"   封面 -> out/封面.png
"""
import glob
import importlib
import math
import multiprocessing as mp
import os
import subprocess
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import kit as KIT
from kit import K, W, H

OUT = KIT.OUT
FPS = 30
FN, META = {}, {}


def scene(sid, enter="cut", exit=None, focus=None):
    """@scene("S01", enter="fade") 注册一个场景函数：def S01(k) -> Frame。enter/exit: cut | fade | iris"""
    def deco(fn):
        FN[sid] = fn
        META[sid] = dict(enter=enter, exit=exit, focus=focus)
        return fn
    return deco


def load():
    sys.modules.setdefault("film", sys.modules[__name__])      # 以脚本运行时，让场景文件注册到同一个表
    for p in sorted(glob.glob(os.path.join(KIT.ROOT, "scenes_*.py"))):
        importlib.import_module(os.path.basename(p)[:-3])


def scene_at(t):
    T = KIT.tl()
    for sid in T["order"]:
        s = T["scenes"][sid]
        if s["t0"] - 0.05 <= t < s["t1"]:
            return sid
    return T["order"][-1] if t > 0 else T["order"][0]


def frame(t, subs=True):
    sid = scene_at(t)
    k = K(sid, t)
    fn = FN.get(sid)
    if fn is None:                                   # 还没写的场景：占位
        fr = KIT.Frame((20, 18, 22))
        KIT.text(fr, [(f"{sid} 待制作", (180, 180, 180))], 960, 500, 6)
    else:
        fr = fn(k)
    m = META.get(sid, {})
    lt, rt = t - k.t0, k.t1 - t
    if m.get("enter") == "fade" and lt < 0.35:
        KIT.darken(fr, KIT.ease_in_out(lt / 0.35))
    elif m.get("enter") == "iris" and lt < 0.6:
        fx, fy = m.get("focus") or (960, 540)
        KIT.iris(fr, fx, fy, KIT.ease_out(lt / 0.6) * 2300)
    if m.get("exit") == "fade" and rt < 0.3:
        KIT.darken(fr, KIT.ease_in_out(rt / 0.3))
    elif m.get("exit") == "iris" and rt < 0.45:
        fx, fy = m.get("focus") or (960, 540)
        KIT.iris(fr, fx, fy, KIT.ease_in_out(rt / 0.45) * 2300)
    KIT.chapter_bar(fr, t)
    if subs:
        KIT.subtitle(fr, t)
    return fr


def _worker(args):
    i0, i1, path = args
    load()
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                          "-crf", "15", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for i in range(i0, i1):
        p.stdin.write(np.clip(frame(i / FPS).a, 0, 255).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    return path


def render(t0, t1, out_mp4, audio=None, procs=None):
    # 每个进程要几百 MB 内存；默认最多 4 个，内存小的电脑设环境变量 PXV_PROCS=2（或 1）
    procs = procs or int(os.environ.get("PXV_PROCS", 0)) or max(1, min(4, (os.cpu_count() or 4) - 1))
    i0, i1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    chunk = max(30, math.ceil((i1 - i0) / (procs * 3)))
    jobs = [(a, min(i1, a + chunk), os.path.join(OUT, f"_part_{k:04d}.mp4")) for k, a in enumerate(range(i0, i1, chunk))]
    with mp.Pool(procs) as pool:
        for j, _ in enumerate(pool.imap(_worker, jobs)):
            print(f"\r{j + 1}/{len(jobs)} 段", end="", flush=True)
    print()
    lst = os.path.join(OUT, "_parts.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for _, _, p in jobs:
            f.write(f"file '{p}'\n")
    silent = os.path.join(OUT, "_silent.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent],
                   check=True)
    if audio and os.path.exists(audio):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", silent, "-ss", str(t0), "-t", str(t1 - t0), "-i", audio,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        out_mp4], check=True)
        os.remove(silent)
    else:
        os.replace(silent, out_mp4)
    for _, _, p in jobs:
        os.remove(p)
    os.remove(lst)
    print("wrote", out_mp4)


def sheet(sid0, sid1, cols=4):
    """审片联系表：每一拍取「第一个高亮词 + 0.45s」那一帧。"""
    load()
    order = KIT.tl()["order"]
    times = []
    for sid in order[order.index(sid0):order.index(sid1) + 1]:
        k = K(sid, 0)
        for i, b in enumerate(k.beats):
            times.append((sid, i, min(k.t1 - 0.05, k.h(i) + 0.45)))
    tw, th = 640, 360
    out = Image.new("RGB", (cols * tw, math.ceil(len(times) / cols) * (th + 26)), (12, 12, 14))
    f = ImageFont.truetype(KIT.pxv.UI_FONT, 18)
    d = ImageDraw.Draw(out)
    for n, (sid, i, t) in enumerate(times):
        x, y = (n % cols) * tw, (n // cols) * (th + 26)
        out.paste(frame(t).image().resize((tw, th), Image.LANCZOS), (x, y + 26))
        d.text((x + 6, y + 3), f"{sid} 第{i + 1}拍  {t:.2f}s", font=f, fill=(255, 220, 120))
    path = os.path.join(OUT, f"sheet_{sid0}-{sid1}.png")
    out.save(path)
    print("wrote", path)


def chars():
    """定妆照：三套服装 × 常用表情。"""
    import sprites as X
    fr = KIT.Frame((24, 22, 28))
    looks = [("open", "line"), ("blink", "line"), ("happy", "grin"), ("wide", "o"), ("tired", "frown"), ("look", "talk")]
    for r, design in enumerate(["C", "Cj", "Cp"]):
        y = 70 + r * 340
        KIT.text(fr, [(X.DESIGNS[design]["name"], KIT.CREAM)], 40, y, 3.0, anchor="lm")
        for c, (e, m) in enumerate(looks):
            X.draw(fr, 110 + c * 300, y + 30, 10.0, design, e, m)
            KIT.text(fr, [(f"{e}/{m}", (150, 150, 156))], 210 + c * 300, y + 300, 2.2)
    fr.image().save(os.path.join(OUT, "定妆.png"))
    print("wrote", os.path.join(OUT, "定妆.png"))


def cover(title, sub=""):
    """封面：同一套 sprite 放大到近景（cell 28）+ 大标题。不重画角色，只换 cell。"""
    import sets as ST
    fr = KIT.Frame((10, 9, 9))
    KIT.cached(fr, "shop", ST.shop_static)
    fr.a[0:56] = fr.a[56:112]                               # 背景顶部给进度条留了 56px，封面没有进度条，用墙面补上
    fr.a *= 0.55                                            # 背景压暗，让人和字跳出来
    fr.cam = KIT.Cam()                                      # 角色和字用 1:1 屏幕坐标
    KIT.xm(fr, 1150, 500, 28.0, "happy", "grin", hands=((-3.2, 15.5), (16.6, 13.0)), bust=True)   # 半身出画
    fr.light([(1430, 560, 900, 0.9), (560, 520, 900, 0.5)], ambient=0.5, tint=(1.0, 0.92, 0.8), cap=1.2)
    KIT.vignette(fr, 0.55, 0.4, 1.6)
    KIT.big(fr, 560, 430, title, unit=12, color=KIT.GOLD_LT)
    if sub:
        KIT.tag(fr, 560, 600, sub, unit=5.0, fg=KIT.CREAM)
    p = os.path.join(OUT, "封面.png")
    fr.image().save(p)
    print("wrote", p)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    a = sys.argv[1:]
    mixwav = os.path.join(OUT, "mix.wav")
    if a[0] == "--chars":
        chars()
    elif a[0] == "--sheet":
        sheet(a[1], a[2] if len(a) > 2 else a[1])
    elif a[0] == "--still":
        load()
        p = os.path.join(OUT, f"still_{a[1]}.png")
        frame(float(a[1])).image().save(p)
        print("wrote", p)
    elif a[0] == "--range":
        render(float(a[1]), float(a[2]), os.path.join(OUT, f"预览_{a[1]}-{a[2]}.mp4"), mixwav)
    elif a[0] == "--cover":
        cover(a[1], a[2] if len(a) > 2 else "")
    elif a[0] == "--full":
        render(0, KIT.tl()["total"], os.path.join(OUT, "成片.mp4"), mixwav)

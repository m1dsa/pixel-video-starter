"""成片自检（在 MP4 上量）：每个场景的运动面积、静止帧比例、跳变次数，外加「同一时刻渲两次是否一模一样」。

  python qa.py out/成片.mp4   -> out/qa.md

判定：静止帧对 > 40% 或平均运动面积 < 0.5% 的场景标为「偏静」—— 回去给它加小循环。
"""
import os, subprocess, sys
import numpy as np
import kit as KIT
import film as F

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(KIT.OUT, "成片.mp4")
w, h, fps = 480, 270, 30
p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}", "-r", str(fps), "-f", "rawvideo",
                      "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
frames = []
while True:
    b = p.stdout.read(w * h)
    if len(b) < w * h:
        break
    frames.append(np.frombuffer(b, np.uint8).astype(np.int16))
diff = np.array([(np.abs(frames[i + 1] - frames[i]) > 12).mean() for i in range(len(frames) - 1)])
T = KIT.tl()
rows, bad = ["| 场景 | 时长 | 运动面积 | 静止帧对 | 跳变 |", "| --- | --- | --- | --- | --- |"], []
for sid in T["order"]:
    s = T["scenes"][sid]
    d = diff[int((s["t0"] + 0.35) * fps):int(s["t1"] * fps) - 1]       # 跳过切镜后 0.35s
    if len(d) < 3:
        continue
    med = max(np.median(d), 1e-4)
    jumps, static = int(((d > 6 * med) & (d > 0.03)).sum()), (d < 0.0005).mean()
    rows.append(f"| {sid} | {s['t1'] - s['t0']:.1f}s | {d.mean() * 100:.1f}% | {static * 100:.0f}% | {jumps} |")
    if static > 0.4 or d.mean() < 0.005:
        bad.append(sid)
F.load()
same = sum(bool((np.asarray(F.frame(t).image()) == np.asarray(F.frame(t).image())).all())
           for t in np.linspace(1, T["total"] - 1, 5))
out = ["# 成片 QA", "", f"- 全片平均运动面积 {diff.mean() * 100:.1f}%", f"- 确定性：同一时刻渲两次逐像素一致 {same}/5",
       "- 偏静的场景：" + ("、".join(bad) if bad else "无"), "", *rows]
open(os.path.join(KIT.OUT, "qa.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))

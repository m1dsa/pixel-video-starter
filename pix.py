"""像素材质画法：像像素画师那样逐格上色，用来画精致的背景场景和道具（约 90% 拟物）。

不要用一大块平涂的形状凑东西。每样东西都走这五步（规则和例子见 docs/pixel-material.md）：
  1. 色阶 ramp：每种材质 5 级（0 最暗 … 4 高光），暗部偏冷偏紫、亮部偏暖偏黄（色相偏移）；
  2. 体积：按形状（box 方块 / round 圆 / cylv 竖圆柱 / cylh 横圆柱 / flat 平面）算每一格该用第几级，分层是一块一块的，不抖动；
  3. 材质纹理：wood 木纹、fabric 布纹、metal 金属高光条、glass 斜反光、ceramic 釉面高光、paper 纸、stone 石纹；
  4. 选择性描边：朝下 / 朝右的边描深色线，朝上 / 朝左的边留亮边；
  5. 投影 + 接触阴影：物体在地面 / 墙面投下一层分明的暗影，物体底边和墙角压暗一两层。
坐标：世界坐标（1080p 像素），一格 U=4px。画好的场景用 sc.blit(fr) 贴进 pxv 的 Frame，镜头推拉照常生效。
场景只画一次：放进 KIT.cached 或自己用 lru_cache 缓存，每帧只 blit。

来源：我做过最好的一期像素动画的背景画法（2026-10 定稿）。
"""
import math
import numpy as np
from PIL import Image, ImageDraw

U = 4.0


# ====================================================================== 格子画板
class Canvas:
    """一张「格子图」：每格一个 RGBA 颜色，最后一次贴到画面上（和 pxv 同一套按面积覆盖的算法，无接缝）。"""

    def __init__(self, x0, y0, x1, y1, u=U):
        self.u, self.x0, self.y0 = u, x0, y0
        self.w, self.h = int(math.ceil((x1 - x0) / u)), int(math.ceil((y1 - y0) / u))
        self.a = np.zeros((self.h, self.w, 4), np.float32)
        self.gy, self.gx = np.mgrid[0:self.h, 0:self.w]

    def i(self, x):
        """世界 x -> 列号"""
        return int((x - self.x0) // self.u)

    def j(self, y):
        return int((y - self.y0) // self.u)

    def X(self, i):
        """列号 -> 世界 x（格子中心）"""
        return self.x0 + (i + 0.5) * self.u

    def Y(self, j):
        return self.y0 + (j + 0.5) * self.u

    def put(self, mask, color, alpha=1.0):
        a = alpha * (color[3] if len(color) == 4 else 1.0)
        c = np.asarray(color[:3], np.float32)
        if a >= 1:
            self.a[mask, :3] = c
            self.a[mask, 3] = 1.0
        else:
            self.a[mask, :3] = self.a[mask, :3] * (1 - a) + c * a
            self.a[mask, 3] = np.maximum(self.a[mask, 3], a)

    def poly_mask(self, pts):
        """多边形（世界坐标）覆盖到的格子。"""
        img = Image.new("1", (self.w, self.h), 0)
        ImageDraw.Draw(img).polygon([((x - self.x0) / self.u - 0.5, (y - self.y0) / self.u - 0.5) for x, y in pts], fill=1)
        return np.asarray(img, bool)

    def ellipse_mask(self, cx, cy, rx, ry):
        x = self.X(self.gx)
        y = self.Y(self.gy)
        return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0

    def vnoise(self, scale, seed=0, octaves=2):
        """低频噪声（0..1）：大片的明暗起伏（石纹、草地深浅）。scale = 一个起伏多少格。固定种子，每次一样。"""
        rnd = np.random.RandomState(seed)
        out = np.zeros((self.h, self.w), np.float32)
        amp, tot = 1.0, 0.0
        for o in range(octaves):
            sc = max(2, scale / (2 ** o))
            gh, gw = int(self.h / sc) + 3, int(self.w / sc) + 3
            g = rnd.rand(gh, gw).astype(np.float32)
            fy, fx = self.gy / sc, self.gx / sc
            iy, ix = fy.astype(int), fx.astype(int)
            ty, tx = fy - iy, fx - ix
            ty, tx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
            v = (g[iy, ix] * (1 - tx) + g[iy, ix + 1] * tx) * (1 - ty) + (g[iy + 1, ix] * (1 - tx) + g[iy + 1, ix + 1] * tx) * ty
            out += v * amp
            tot += amp
            amp *= 0.5
        return out / tot

    def blit(self, fr, alpha=1.0):
        """贴到 pxv 的 Frame 上（跟着 fr.cam 走，推拉、平移都对）。"""
        from pxv import W, H
        s = self.u * fr.cam.zoom
        sx, sy = fr.cam.pt(self.x0, self.y0)
        i0, i1 = max(0, int((0 - sx) // s)), min(self.w, int(math.ceil((W - sx) / s)) + 1)
        j0, j1 = max(0, int((0 - sy) // s)), min(self.h, int(math.ceil((H - sy) / s)) + 1)
        if i1 <= i0 or j1 <= j0:
            return
        ax = _axis(W, sx + i0 * s, s, i1 - i0)
        ay = _axis(H, sy + j0 * s, s, j1 - j0)
        if ax is None or ay is None:
            return
        rgba = self.a[j0:j1, i0:i1]
        A = rgba[..., 3] * alpha
        pre = np.concatenate([rgba[..., :3] * A[..., None], A[..., None]], 2)
        py0, cy0, wy0, cy1, wy1 = ay
        px0, cx0, wx0, cx1, wx1 = ax
        rows = pre[cy0] * wy0[:, None, None] + pre[cy1] * wy1[:, None, None]
        out = rows[:, cx0] * wx0[None, :, None] + rows[:, cx1] * wx1[None, :, None]
        reg = fr.a[py0:py0 + out.shape[0], px0:px0 + out.shape[1]]
        reg[:] = reg * (1 - out[..., 3:4]) + out[..., :3]


def _axis(n, start, size, k):
    """一条轴上：每个屏幕像素压着哪两个格子、各占多少面积（格子要比 1 像素大）。"""
    p0, p1 = max(0, math.floor(start)), min(n, math.ceil(start + size * k))
    if p1 <= p0:
        return None
    p = np.arange(p0, p1, dtype=np.float64)
    c0 = np.clip(np.floor((p - start) / size).astype(np.int64), 0, k - 1)
    c1 = np.minimum(c0 + 1, k - 1)
    e0 = start + size * c0
    e1, e2 = e0 + size, e0 + 2 * size
    w0 = np.clip(np.minimum(p + 1, e1) - np.maximum(p, e0), 0, 1)
    w1 = np.where(c1 == c0, 0.0, np.clip(np.minimum(p + 1, e2) - np.maximum(p, e1), 0, 1))
    return p0, c0, w0.astype(np.float32), c1, w1.astype(np.float32)


# ====================================================================== 色阶
def ramp(base, n=5, dark=0.62, light=1.22, cool=(58, 46, 96), warm=(255, 236, 190)):
    """从本色生成 5 级色阶：0 最暗（压暗 + 混一点冷紫）… 2 本色 … 4 高光（提亮 + 混一点暖黄）。
    这是像素画常用的「色相偏移」：暗部偏冷、亮部偏暖，颜色才有层次、不会发灰。"""
    b = np.asarray(base, np.float32)
    out = []
    for i in range(n):
        k = (i - n // 2) / (n // 2)                               # -1 … 0 … 1
        if k < 0:
            c = b * (1 + (dark - 1) * (-k))
            c = c * (1 - 0.22 * (-k)) + np.asarray(cool, np.float32) * 0.22 * (-k)
        elif k > 0:
            c = np.minimum(255, b * (1 + (light - 1) * k) + 18 * k)
            c = c * (1 - 0.25 * k) + np.asarray(warm, np.float32) * 0.25 * k
        else:
            c = b
        out.append(tuple(np.clip(c, 0, 255)))
    return out


# ====================================================================== 场景画布
class Scene:
    def __init__(self, x0=-200, y0=40, x1=2120, y1=1140, u=U):
        self.cv = Canvas(x0, y0, x1, y1, u)
        self.h, self.w = self.cv.h, self.cv.w
        self.idx = np.full((self.h, self.w), -1, np.int16)        # 每格属于哪个物体（投影时用）
        self.n = 0
        self.X = self.cv.X(self.cv.gx)
        self.Y = self.cv.Y(self.cv.gy)

    # ---------------- 形状 → 格子 mask
    def rect(self, x0, y0, x1, y1):
        c = self.cv
        return (c.gx >= c.i(x0)) & (c.gx < c.i(x1)) & (c.gy >= c.j(y0)) & (c.gy < c.j(y1))

    def ell(self, cx, cy, rx, ry):
        return self.cv.ellipse_mask(cx, cy, rx, ry)

    def poly(self, pts):
        return self.cv.poly_mask(pts)

    # ---------------- 画一个物体
    def obj(self, mask, base, form="box", tex=None, outline=True, light=(-1, -1), ramp_=None, shadow=None,
            seed=0, tex_k=1.0, bands=(2, 2), rim=True):
        """mask：格子；base：本色；form：体积怎么分层；tex：材质；shadow=(dx, dy, 浓度) 投影（格数）。"""
        if not mask.any():
            return mask
        R = np.asarray(ramp_ or ramp(base), np.float32)
        if shadow:
            self.cast(mask, *shadow)
        lvl = self._form(mask, form, light, bands)
        if tex:
            lvl = lvl + self._tex(mask, tex, seed) * tex_k
        lvl = np.clip(np.round(lvl), 0, len(R) - 1).astype(int)
        if outline:
            dn, rt, up, lf = self._edges(mask)
            lvl[dn | rt] = 0                                      # 下 / 右边：最暗一级做描边
            if rim:
                lvl[(up | lf) & ~(dn | rt)] = np.minimum(len(R) - 1, lvl[(up | lf) & ~(dn | rt)] + 1)
        cols = R[lvl]
        self.cv.a[mask, :3] = cols[mask]
        self.cv.a[mask, 3] = 1.0
        self.idx[mask] = self.n
        self.n += 1
        return mask

    def flat(self, mask, col, alpha=1.0):
        self.cv.put(mask, col, alpha)
        return mask

    def sphere(self, cx, cy, r, base, light=(-0.55, -0.6), mask=None, outline=True, cuts=(-0.15, 0.2, 0.5, 0.8)):
        """球（星球、大圆石）：按真实球面法线和光的方向算每格亮几级，再分成 5 块（不渐变）。
        和 obj(form="round") 的区别：球只露出一部分（比如星球下半截出了画面）也照样对，因为是按圆心 + 半径算的，
        不是按露出来那块的外框算。mask = 只画球上的这一部分（例如草地那一圈），不传就是整个圆。"""
        disk = self.ell(cx, cy, r, r)
        m = disk if mask is None else (mask & disk)
        if not m.any():
            return m
        R = np.asarray(ramp(base) if not isinstance(base, list) else base, np.float32)
        u = (self.X - cx) / r
        v = (self.Y - cy) / r
        w = np.sqrt(np.clip(1 - u * u - v * v, 0, 1))
        L = np.asarray((light[0], light[1], 0.8), np.float32)
        L /= np.linalg.norm(L)
        lam = u * L[0] + v * L[1] + w * L[2]
        lvl = np.digitize(lam, cuts).astype(int)
        lvl[lam > 0.95] = 4
        if outline:
            dn, rt, up, lf = self._edges(disk)
            lvl[(dn | rt) & (lam < 0.3)] = 0                      # 背光那一侧的边描最暗
            lvl[(up | lf) & (lam >= 0.3)] = np.minimum(4, lvl[(up | lf) & (lam >= 0.3)] + 1)
        cols = R[np.clip(lvl, 0, 4)]
        self.cv.a[m, :3] = cols[m]
        self.cv.a[m, 3] = 1.0
        self.idx[m] = self.n
        self.n += 1
        return m

    # ---------------- 体积分层
    def _form(self, m, form, light, bands):
        jj, ii = np.nonzero(m)
        j0, j1, i0, i1 = jj.min(), jj.max(), ii.min(), ii.max()
        gy, gx = self.cv.gy, self.cv.gx
        lvl = np.full(m.shape, 2.0, np.float32)
        if form == "flat":
            return lvl
        if form == "box":
            tb, sb = bands
            d_up = self._dist(m, 0, -1)
            d_dn = self._dist(m, 0, 1)
            d_lf = self._dist(m, -1, 0)
            d_rt = self._dist(m, 1, 0)
            lvl[(d_up < tb)] = 3
            lvl[(d_lf < 1)] = 3
            lvl[(d_up < 1)] = 4
            lvl[(d_rt < sb)] = 1
            lvl[(d_dn < sb)] = 1
            return lvl
        if form in ("round", "cylv", "cylh", "dome"):
            cx = (i0 + i1) / 2.0
            cy = (j0 + j1) / 2.0
            rx = max(1.0, (i1 - i0) / 2.0)
            ry = max(1.0, (j1 - j0) / 2.0)
            u = (gx - cx) / rx
            v = (gy - cy) / ry
            lx, ly = light
            if form == "cylv":
                val = np.where(u - lx * 0.35 < -0.25, 3.0, 2.0)
                val = np.where(np.abs(u + 0.45) < 0.12, 4.0, val)
                val = np.where(u > 0.45, 1.0, val)
                val = np.where(u > 0.8, 0.6, val)
                return np.where(m, val, lvl)
            if form == "cylh":
                val = np.where(v < -0.3, 3.0, 2.0)
                val = np.where(np.abs(v + 0.5) < 0.12, 4.0, val)
                val = np.where(v > 0.45, 1.0, val)
                return np.where(m, val, lvl)
            # 圆 / 穹顶：离左上的「光点」越远越暗，分成几块
            d = np.sqrt((u - lx * 0.4) ** 2 + (v - ly * 0.4) ** 2)
            val = 4.0 - np.clip(np.floor(d * 2.2), 0, 4)
            val = np.where(d < 0.18, 4.0, val)
            return np.where(m, np.clip(val, 0.5, 4), lvl)
        return lvl

    def _dist(self, m, dx, dy, cap=8):
        """每格往 (dx, dy) 方向再走几格就出 mask 了（0 = 这一格就是那一侧的边），最多算到 cap。"""
        mm = m
        if dy == 1:
            mm = m[::-1]
        elif dx == -1:
            mm = m.T
        elif dx == 1:
            mm = m.T[::-1]
        d = np.zeros(mm.shape, np.int16)
        for j in range(mm.shape[0]):
            if j == 0:
                d[j] = 0
            else:
                d[j] = np.where(mm[j - 1], np.minimum(d[j - 1] + 1, cap), 0)
        d = np.where(mm, d, cap)
        if dy == 1:
            d = d[::-1]
        elif dx == -1:
            d = d.T
        elif dx == 1:
            d = d[::-1].T
        return d

    def _edges(self, m):
        up = m.copy(); up[1:] &= ~m[:-1]
        dn = m.copy(); dn[:-1] &= ~m[1:]
        lf = m.copy(); lf[:, 1:] &= ~m[:, :-1]
        rt = m.copy(); rt[:, :-1] &= ~m[:, 1:]
        return dn, rt, up, lf

    # ---------------- 材质纹理（返回每格的色阶偏移，有规律、不是随机噪点）
    def _tex(self, m, tex, seed):
        gy, gx = self.cv.gy, self.cv.gx
        rnd = np.random.RandomState(seed)
        off = np.zeros(m.shape, np.float32)
        if tex in ("wood", "woodv"):
            a, b = (gy, gx) if tex == "wood" else (gx, gy)
            wave = np.sin(b * 0.18 + seed) * 1.3 + np.sin(b * 0.05 + seed * 2) * 2.2
            line = ((a + wave.astype(int)) % 5 == 0)
            off[line] -= 1
            long_hi = ((a + wave.astype(int)) % 11 == 3) & ((b // 7) % 3 != 0)
            off[long_hi] += 0.6
            for _ in range(max(1, int(m.sum() / 900))):           # 木结
                jj, ii = np.nonzero(m)
                k = rnd.randint(len(jj))
                cy, cx = jj[k], ii[k]
                knot = ((gx - cx) ** 2 / 4 + (gy - cy) ** 2) < 1.2
                off[knot] -= 1.2
        elif tex == "fabric":                                    # 布：一道道横向织纹 + 隔行错开的小点
            off[(gy % 3 == 0)] -= 0.8
            off[(gy % 3 == 1) & ((gx + gy) % 4 == 0)] += 0.8
        elif tex == "stitch":
            off[(gx % 3 == 0) & (gy % 2 == 0)] -= 0.7
        elif tex == "metal":
            jj, ii = np.nonzero(m)
            i0, i1 = ii.min(), ii.max()
            u = (gx - i0) / max(1, i1 - i0)
            off[(np.abs(u - 0.22) < 0.05)] += 1.6
            off[(np.abs(u - 0.32) < 0.02)] += 0.8
        elif tex == "glass":
            jj, ii = np.nonzero(m)
            s = (gx - ii.min()) + (gy - jj.min()) * 0.6
            off[((s % 34) < 4)] += 1.2
            off[((s % 34) > 6) & ((s % 34) < 8)] += 0.7
        elif tex == "ceramic":
            jj, ii = np.nonzero(m)
            cy, cx = jj.min() + (jj.max() - jj.min()) * 0.3, ii.min() + (ii.max() - ii.min()) * 0.3
            off[((gx - cx) ** 2 + (gy - cy) ** 2) < 2.5] += 2.0
        elif tex == "stone":
            n = self.cv.vnoise(6, seed=seed)
            off += np.round((n - 0.5) * 2.0)
        elif tex == "paper":
            off[(gy % 6 == 0)] -= 0.4
        return np.where(m, off, 0)

    # ---------------- 投影 / 接触阴影
    def cast(self, m, dx=3, dy=2, k=0.55):
        """物体把 mask 往 (dx, dy) 格平移后的影子压到已经画好的东西上（只压暗，不盖住物体自己）。"""
        sh = np.zeros_like(m)
        h, w = m.shape
        ys, xs = slice(max(0, dy), h), slice(max(0, dx), w)
        yd, xd = slice(0, h - max(0, dy)), slice(0, w - max(0, dx))
        sh[ys, xs] = m[yd, xd]
        sh &= ~m
        self.cv.a[sh, :3] *= (1 - k)

    def band_ao(self, y_line, depth=3, k=0.18, x0=None, x1=None, up=False):
        """墙脚 / 物体底边：在 y_line 上方（up=True）或下方压暗 depth 格，每格一层，越靠近越暗。"""
        j = self.cv.j(y_line)
        for d in range(depth):
            jj = j - 1 - d if up else j + d
            if 0 <= jj < self.h:
                sl = slice(self.cv.i(x0) if x0 is not None else 0, self.cv.i(x1) if x1 is not None else self.w)
                self.cv.a[jj, sl, :3] *= (1 - k * (depth - d) / depth)

    def blit(self, fr, alpha=1.0):
        self.cv.blit(fr, alpha)

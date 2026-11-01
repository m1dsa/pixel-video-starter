"""Pixel art drawn as vector rects: one float rectangle per art pixel.

Every art pixel is its own rectangle at float coordinates with exact area-coverage
anti-aliasing, composited one by one (like Canvas fillRect). Consequences, all on purpose:
  * the camera can zoom by any factor (6.27x, 10.4x ...) and pixels stay square-ish;
  * cell widths alternate (10/11 px) at fractional zoom;
  * neighbouring cells drawn separately leave faint seams, the "tiny lines" typical of this look.
Big terrain uses blit() (one joint resample, no seams). Light, glow, text live at screen res.

World units are 1080p screen pixels at zoom 1, so reference coordinates map 1:1.
"""
import math
import os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
ROOT = os.path.dirname(os.path.abspath(__file__))
PIXEL_FONT = os.path.join(ROOT, "fonts", "fusion-pixel.ttf")      # Fusion Pixel 12px 等宽（OFL）
UI_FONT = os.environ.get("PXV_UI_FONT") or os.path.join(ROOT, "fonts", "NotoSansSC-VF.ttf")  # 思源黑体可变字重（OFL）


def C(c):
    return np.asarray(c, np.float32)


class Cam:
    def __init__(self, cx=None, cy=None, zoom=1.0):
        self.cx = W / 2 if cx is None else cx
        self.cy = H / 2 if cy is None else cy
        self.zoom = zoom

    def pt(self, x, y):
        return (x - self.cx) * self.zoom + W / 2, (y - self.cy) * self.zoom + H / 2


def _cov(n, start, size, k):
    """Coverage matrix M[p, i]: how much of screen pixel p is covered by cell i."""
    edges = start + size * np.arange(k + 1, dtype=np.float64)
    p0, p1 = max(0, math.floor(edges[0])), min(n, math.ceil(edges[-1]))
    if p1 <= p0:
        return p0, None
    ps = np.arange(p0, p1, dtype=np.float64)[:, None]
    M = np.clip(np.minimum(ps + 1, edges[None, 1:]) - np.maximum(ps, edges[None, :-1]), 0, 1)
    return p0, M.astype(np.float32)


class Frame:
    def __init__(self, bg=(0, 0, 0), cam=None):
        self.a = np.empty((H, W, 3), np.float32)
        self.a[:] = C(bg)
        self.cam = cam or Cam()

    # ---------- primitives (screen space) ----------
    def srect(self, x0, y0, x1, y1, c, alpha=1.0):
        if x1 <= 0 or y1 <= 0 or x0 >= W or y0 >= H or alpha <= 0:
            return
        ix0, ix1 = max(0, math.floor(x0)), min(W, math.ceil(x1))
        iy0, iy1 = max(0, math.floor(y0)), min(H, math.ceil(y1))
        xs = np.arange(ix0, ix1, dtype=np.float32)
        ys = np.arange(iy0, iy1, dtype=np.float32)
        cx = np.clip(np.minimum(xs + 1, x1) - np.maximum(xs, x0), 0, 1)
        cy = np.clip(np.minimum(ys + 1, y1) - np.maximum(ys, y0), 0, 1)
        cov = (cy[:, None] * cx[None, :] * alpha)[..., None]
        reg = self.a[iy0:iy1, ix0:ix1]
        reg += (C(c) - reg) * cov

    # ---------- world space ----------
    def rect(self, x, y, w, h, c, alpha=1.0):
        z = self.cam.zoom
        sx, sy = self.cam.pt(x, y)
        self.srect(sx, sy, sx + w * z, sy + h * z, c, alpha)

    def sprite(self, rows, pal, x, y, cell, alpha=1.0, flip=False, ov=0.35):
        """rows: list of strings; each mapped char is one separately drawn cell.
        ov: screen-px overlap per cell — 0 gives full Canvas-style seams, ~0.35 leaves faint ones."""
        for j, r in enumerate(rows):
            n = len(r)
            for i, ch in enumerate(r):
                c = pal.get(ch)
                if c is None:
                    continue
                ii = n - 1 - i if flip else i
                z = self.cam.zoom
                sx, sy = self.cam.pt(x + ii * cell, y + j * cell)
                a = alpha * (c[3] if len(c) == 4 else 1.0)
                self.srect(sx, sy, sx + cell * z + ov, sy + cell * z + ov, c[:3], a)

    def blit(self, rgba, x, y, cell):
        """Draw a whole cell map (h,w,4 float, alpha 0..1) with one exact resample (no seams)."""
        h, w = rgba.shape[:2]
        sx, sy = self.cam.pt(x, y)
        s = cell * self.cam.zoom
        px0, Mx = _cov(W, sx, s, w)
        py0, My = _cov(H, sy, s, h)
        if Mx is None or My is None:
            return
        A = rgba[..., 3]
        pre = rgba[..., :3] * A[..., None]
        col = (My @ pre.reshape(h, w * 3)).reshape(My.shape[0], w, 3)
        col = np.einsum("qwc,pw->qpc", col, Mx)
        al = My @ A @ Mx.T
        reg = self.a[py0:py0 + My.shape[0], px0:px0 + Mx.shape[0]]
        reg[:] = reg * (1 - al[..., None]) + col

    def cells(self, coords, color, x0, y0, cell, alpha=1.0):
        """Fill a set of integer cells (gx, gy) relative to (x0, y0) as one seamless map."""
        if not coords:
            return
        gx = np.array([c[0] for c in coords])
        gy = np.array([c[1] for c in coords])
        ox, oy = gx.min(), gy.min()
        m = np.zeros((gy.max() - oy + 1, gx.max() - ox + 1, 4), np.float32)
        m[gy - oy, gx - ox, :3] = C(color)
        m[gy - oy, gx - ox, 3] = alpha
        self.blit(m, x0 + ox * cell, y0 + oy * cell, cell)

    def poly(self, pts, c, alpha=1.0, ss=4):
        """Anti-aliased polygon in world coords (for the few truly vector bits: clock hands)."""
        sp = [self.cam.pt(*p) for p in pts]
        xs, ys = [p[0] for p in sp], [p[1] for p in sp]
        x0, y0 = max(0, int(min(xs)) - 2), max(0, int(min(ys)) - 2)
        x1, y1 = min(W, int(max(xs)) + 3), min(H, int(max(ys)) + 3)
        if x1 <= x0 or y1 <= y0:
            return
        m = np.zeros(((y1 - y0) * ss, (x1 - x0) * ss), np.uint8)
        q = np.array([[(px - x0) * ss, (py - y0) * ss] for px, py in sp], np.int32)
        cv2.fillPoly(m, [q], 255, lineType=cv2.LINE_AA)
        m = cv2.resize(m, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        reg = self.a[y0:y1, x0:x1]
        reg += (C(c) - reg) * (m * alpha)[..., None]

    # ---------- light (screen space) ----------
    def _field(self, spots, scale=4):
        h, w = H // scale, W // scale
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        F = np.zeros((h, w), np.float32)
        for sx, sy, r, s, *sq in spots:
            ax = sq[0] if sq else 1.0                       # horizontal stretch
            px, py = self.cam.pt(sx, sy)
            rr = r * self.cam.zoom / scale
            F += s * np.exp(-(((xx - px / scale) / ax) ** 2 + (yy - py / scale) ** 2) / (2 * (rr / 2) ** 2))
        return cv2.resize(F, (W, H), interpolation=cv2.INTER_LINEAR)

    def light(self, spots, ambient=0.4, tint=(1.0, 0.95, 0.85), cap=1.25):
        """Multiply by ambient + soft spots; the lit part is tinted warm."""
        F = self._field(spots)
        L = np.clip(ambient + F, 0, cap)[..., None]
        warm = 1 + (C(tint) - 1) * np.clip(F, 0, 1)[..., None]
        self.a *= L * warm

    def glow(self, spots, color):
        """Additive glow: spots [(x, y, r, strength)]."""
        F = self._field(spots)
        self.a += F[..., None] * C(color)

    def vignette(self, k=0.6, start=0.35, power=1.6):
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        self.a *= (1 - k * np.clip((r - start) / (1.42 - start), 0, 1) ** power)[..., None]

    def grain(self, amt=3.0, seed=0):
        rng = np.random.default_rng(seed)
        self.a += rng.normal(0, amt, (H, W, 1)).astype(np.float32)

    def bloom(self, thresh=170, strength=0.35, radius=18):
        hi = np.clip(self.a - thresh, 0, None)
        b = cv2.GaussianBlur(hi, (0, 0), radius)
        self.a += b * strength

    # ---------- text ----------
    def pixel_text(self, text_parts, x, y, unit, anchor="mm", stroke=None, stroke_r=0, stroke_seam=False):
        """Pixel font (12px Fusion Pixel) scaled by `unit` (screen px per font pixel).
        text_parts: [(text, fill_rgb)]. Optional rounded stroke behind (screen space)."""
        f = ImageFont.truetype(PIXEL_FONT, 12)
        wpx = sum(int(f.getlength(t)) for t, _ in text_parts) + 2
        mask = Image.new("L", (wpx, 14), 0)
        colmap = np.zeros((14, wpx, 3), np.float32)
        d = ImageDraw.Draw(mask)
        d.fontmode = "1"
        cx = 1
        for t, col in text_parts:
            tmp = Image.new("L", (wpx, 14), 0)
            td = ImageDraw.Draw(tmp)
            td.fontmode = "1"
            td.text((cx, 1), t, font=f, fill=255)
            tm = np.asarray(tmp) > 0
            colmap[tm] = C(col)
            d.text((cx, 1), t, font=f, fill=255)
            cx += int(f.getlength(t))
        m = np.asarray(mask) > 0
        tw, th = wpx * unit, 14 * unit
        ox = x - tw / 2 if anchor[0] == "m" else (x - tw if anchor[0] == "r" else x)
        oy = y - th / 2 if anchor[1] == "m" else y
        if stroke is not None:
            big = cv2.resize(m.astype(np.uint8) * 255, (int(round(tw)), int(round(th))), interpolation=cv2.INTER_NEAREST)
            pad = int(stroke_r) + 2
            big = cv2.copyMakeBorder(big, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(stroke_r) + 1, 2 * int(stroke_r) + 1))
            dil = cv2.dilate(big, k).astype(np.float32) / 255
            dil = cv2.GaussianBlur(dil, (0, 0), 0.7)
            X0, Y0 = int(round(ox)) - pad, int(round(oy)) - pad
            self._paste_mask(dil, X0, Y0, stroke)
        rgba = np.zeros((14, wpx, 4), np.float32)
        rgba[..., :3] = colmap
        rgba[..., 3] = m
        sx, sy = ox, oy
        cam, self.cam = self.cam, Cam()                      # text is screen space
        if stroke_seam:
            ys, xs = np.nonzero(m)
            for yy, xx in zip(ys, xs):
                self.srect(sx + xx * unit, sy + yy * unit, sx + (xx + 1) * unit, sy + (yy + 1) * unit, colmap[yy, xx])
        else:
            self.blit(rgba, sx, sy, unit)
        self.cam = cam

    def _paste_mask(self, m, X0, Y0, color, alpha=1.0):
        h, w = m.shape
        x0, y0, x1, y1 = max(0, X0), max(0, Y0), min(W, X0 + w), min(H, Y0 + h)
        if x1 <= x0 or y1 <= y0:
            return
        mm = m[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0][..., None] * alpha
        reg = self.a[y0:y1, x0:x1]
        reg += (C(color) - reg) * mm

    def ui_text(self, text, x, y, size, color, weight="Medium", anchor="mm", alpha=1.0):
        f = ImageFont.truetype(UI_FONT, size)
        try:
            f.set_variation_by_name(weight)
        except Exception:
            pass
        l, t, r, b = f.getbbox(text)
        w, h = r - l + 4, b - t + 4
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).text((2 - l, 2 - t), text, font=f, fill=255)
        m = np.asarray(im, np.float32) / 255
        X0 = int(round(x - (w / 2 if anchor[0] == "m" else (w if anchor[0] == "r" else 0))))
        Y0 = int(round(y - (h / 2 if anchor[1] == "m" else 0)))
        self._paste_mask(m, X0, Y0, color, alpha)

    def image(self):
        return Image.fromarray(np.clip(self.a, 0, 255).astype(np.uint8))


DARK_TXT, ORANGE_TXT = (52, 48, 40), (206, 132, 28)     # 字幕正文 / 高亮词

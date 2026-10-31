"""Texturierter Raycaster mit runden Bots (numpy). Liefert ein Bild als uint8-Array (Höhe, Breite, 3)."""
import math

import numpy as np

from . import game as G
from . import tex, world

FOV = math.radians(72)
GRID = np.array([[0 if c == "." else int(c) for c in row] for row in world.GRID], dtype=np.int16)
GH, GW = GRID.shape
LIGHT = np.array([-0.5, 0.7, 0.6], dtype=np.float32)
LIGHT /= np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1], dtype=np.float32)
HALF /= np.linalg.norm(HALF)


def _c(hexcolor):
    return np.array([int(hexcolor[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)


class Renderer:
    def __init__(self, w: int, h: int, theme: dict):
        self.set_theme(theme)
        self.resize(w, h)

    def set_theme(self, theme):
        self.theme = theme
        self.tex = tex.make(theme)
        self.fog = _c(theme["sky"]) * 0.6 + _c(theme["floor"]) * 0.3 + 10

    def resize(self, w: int, h: int):
        self.w, self.h = int(w), int(h)
        self.f = (self.w / 2) / math.tan(FOV / 2)
        yy0, xx0 = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        self.rr = np.sqrt(((xx0 + 0.5 - self.w / 2) / self.h) ** 2 + ((yy0 + 0.5 - self.h / 2) / self.h) ** 2)
        self.cam = ((np.arange(self.w, dtype=np.float32) + 0.5) / self.w * 2 - 1)
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        d = np.sqrt(((xx / self.w - 0.5) * 1.15) ** 2 + ((yy / self.h - 0.5) * 1.15) ** 2)
        self.vignette = np.clip(1.08 - d * d * 1.3, 0.55, 1.0)[..., None].astype(np.float32)

    # ------------------------------------------------------------------ Wände
    def _cast(self, g, rdx, rdy):
        w = self.w
        mx = np.full(w, int(math.floor(g.x)))
        my = np.full(w, int(math.floor(g.y)))
        ddx = np.abs(1.0 / np.where(np.abs(rdx) < 1e-9, 1e-9, rdx))
        ddy = np.abs(1.0 / np.where(np.abs(rdy) < 1e-9, 1e-9, rdy))
        sx = np.where(rdx < 0, -1, 1)
        sy = np.where(rdy < 0, -1, 1)
        sdx = np.where(rdx < 0, (g.x - mx) * ddx, (mx + 1 - g.x) * ddx)
        sdy = np.where(rdy < 0, (g.y - my) * ddy, (my + 1 - g.y) * ddy)
        hit = np.zeros(w, bool)
        side = np.zeros(w, np.int8)
        val = np.ones(w, np.int16)
        for _ in range(64):
            mv = ~hit
            if not mv.any():
                break
            mxs = mv & (sdx < sdy)
            mys = mv & ~mxs
            sdx = np.where(mxs, sdx + ddx, sdx)
            sdy = np.where(mys, sdy + ddy, sdy)
            mx = mx + np.where(mxs, sx, 0)
            my = my + np.where(mys, sy, 0)
            side = np.where(mxs, 0, np.where(mys, 1, side)).astype(np.int8)
            oob = (mx < 0) | (my < 0) | (mx >= GW) | (my >= GH)
            cell = GRID[np.clip(my, 0, GH - 1), np.clip(mx, 0, GW - 1)]
            cell = np.where(oob, 1, cell)
            new = mv & (cell > 0)
            val = np.where(new, cell, val)
            hit |= new
        perp = np.maximum(np.where(side == 0, sdx - ddx, sdy - ddy), 0.05)
        wx = np.where(side == 0, g.y + perp * rdy, g.x + perp * rdx)
        u = wx - np.floor(wx)
        u = np.where(((side == 0) & (rdx > 0)) | ((side == 1) & (rdy < 0)), 1 - u, u)
        return perp.astype(np.float32), side, ((val - 1) % 4).astype(np.int64), (u * tex.T).astype(np.int64) % tex.T

    # ------------------------------------------------------------------ Bild
    def frame(self, g) -> np.ndarray:
        w, h = self.w, self.h
        tf = math.tan(getattr(g, "fov_now", FOV) / 2)
        f = (w / 2) / tf
        eye = getattr(g, "eye", G.EYE)
        dx, dy = math.cos(g.ang), math.sin(g.ang)
        rdx = (dx + (-dy * tf) * self.cam).astype(np.float32)
        rdy = (dy + (dx * tf) * self.cam).astype(np.float32)
        perp, side, kind, tx = self._cast(g, rdx, rdy)
        horizon = h / 2 - math.tan(g.pitch) * f
        r0 = int(max(0, min(h, math.ceil(horizon))))
        img = np.empty((h, w, 3), np.float32)
        # Decke und Boden: je Pixelzeile ein Abstand, daraus die Weltposition und der Texturpunkt
        for rows, tex_arr, height, sign in ((slice(0, r0), self.tex["ceil"], 1 - eye, -1), (slice(r0, h), self.tex["floor"], eye, 1)):
            ys = np.arange(rows.start, rows.stop, dtype=np.float32)[:, None] + 0.5
            if ys.size == 0:
                continue
            dist = height * f / np.maximum(sign * (ys - horizon), 0.5)
            fx = g.x + rdx[None, :] * dist
            fy = g.y + rdy[None, :] * dist
            ti = ((fx - np.floor(fx)) * tex.T).astype(np.int32) % tex.T
            tj = ((fy - np.floor(fy)) * tex.T).astype(np.int32) % tex.T
            fogk = np.clip(1 - dist / 17, 0.0, 1)[..., None]
            img[rows] = tex_arr[tj, ti] * fogk * (0.75 if sign < 0 else 1.0) + self.fog * (1 - fogk)
        # Wände
        lineh = f / perp
        top = horizon - (1 - eye) * lineh
        ys = np.arange(h, dtype=np.float32)[:, None] + 0.5
        v = (ys - top[None, :]) / lineh[None, :]
        mask = (v >= 0) & (v < 1)
        ty = np.clip((v * tex.T).astype(np.int32), 0, tex.T - 1)
        wall = self.tex["walls"][kind[None, :], ty, tx[None, :]]
        fogw = np.clip(1 - perp / 19, 0.0, 1)
        shade = (np.where(side == 0, 1.0, 0.8) * (0.35 + 0.65 * fogw)).astype(np.float32)
        edge = np.minimum(v, 1 - v)
        ao = (0.74 + 0.26 * np.clip(edge * 4.5, 0, 1))[..., None]         # Ecken zu Boden und Decke sind dunkler (Umgebungsverdeckung)
        wall = wall * ao * shade[None, :, None] + self.fog * (1 - fogw)[None, :, None] * 0.6
        wall = wall + self.tex["wemit"][kind[None, :], ty, tx[None, :]] * (0.5 + 0.5 * fogw)[None, :, None]
        img = np.where(mask[..., None], wall, img)
        self._holes(img, g, dx, dy, horizon, perp, f, eye)
        for b in sorted((b for b in g.bots if b.alive), key=lambda b: -((b.x - g.x) ** 2 + (b.y - g.y) ** 2)):
            if getattr(b, "kind", "bot") == "target":
                self._target(img, b, g, dx, dy, horizon, perp, f, eye)
            else:
                self._sprite(img, b, g, dx, dy, horizon, perp, f, eye)
        # Nachbearbeitung: Vignette, Zielfernrohr, leichtes Rot bei Treffern
        img = img * self.vignette
        scope = getattr(g, "ads", 0.0) if getattr(g, "weapon_id", "") == "dmr" else 0.0
        if scope > 0.02:
            ring = np.clip((self.rr - 0.36) / 0.02, 0, 1)[..., None]
            img = img * (1 - ring * min(1.0, scope * 1.4))
        if g.recent_events("hurt", 0.3):
            edge = (1 - self.vignette) * 1.6
            img = img + edge * np.array([160, 0, 0], dtype=np.float32)
        return np.clip(img, 0, 255).astype(np.uint8)

    # ------------------------------------------------------------------ Bots (rund, mit Licht)
    def _sprite(self, img, b, g, dx, dy, horizon, zbuf, f, eye):
        w, h = self.w, self.h
        vx, vy = b.x - g.x, b.y - g.y
        fwd = vx * dx + vy * dy
        if fwd < 0.15:
            return
        lat = -vx * dy + vy * dx
        sx = w / 2 + lat / fwd * f
        half = 0.42 * f / fwd
        x0, x1 = int(max(0, sx - half)), int(min(w, sx + half + 1))
        yt = horizon + (eye - 1.05) * f / fwd
        yb = horizon + (eye + 0.06) * f / fwd
        y0, y1 = int(max(0, yt)), int(min(h, yb + 1))
        if x1 <= x0 or y1 <= y0:
            return
        xs = np.arange(x0, x1, dtype=np.float32)[None, :] + 0.5
        ys = np.arange(y0, y1, dtype=np.float32)[:, None] + 0.5
        hx = (xs - sx) * fwd / f
        z = eye - (ys - horizon) * fwd / f
        vis = (zbuf[x0:x1] > fwd)[None, :]
        th = self.theme
        base = _c(th["bot"] if b.team == 0 else th["bot2"])
        fogk = max(0.3, 1 - fwd / 24)
        out = img[y0:y1, x0:x1]
        # weicher Schatten am Boden
        sh = (hx / 0.36) ** 2 + ((z + 0.0) / 0.07) ** 2
        out *= np.where(vis & (sh < 1) & (z < 0.06), 1 - 0.45 * (1 - sh), 1.0)[..., None]
        flash = min(1.0, b.flash / 0.15)

        def part(sd, nx, ny, color, spec=0.4):
            m = (sd < 0) & vis
            if not m.any():
                return
            nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
            lam = 0.3 + 0.7 * np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
            sp = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1) ** 28 * spec
            rim = (1 - nz) ** 3 * 0.22
            col = color[None, None, :] * lam[..., None] + 255 * sp[..., None] + 255 * rim[..., None] * 0.5
            col = col * fogk + self.fog * (1 - fogk)
            if flash > 0:
                col = col * (1 - 0.75 * flash) + 255 * 0.75 * flash
            out[:] = np.where(m[..., None], col, out)

        # Beine (zwei Kapseln), Rumpf (Kapsel), Kopf (Kugel) mit Visier
        for off in (-0.1, 0.1):
            ez = np.clip(z, 0.05, 0.28)
            r = 0.095
            d = np.sqrt((hx - off) ** 2 + (z - ez) ** 2)
            part(d - r, (hx - off) / r, (z - ez) / r, base * 0.42)
        ez = np.clip(z, 0.36, 0.52)
        r = 0.25
        d = np.sqrt(hx ** 2 + (z - ez) ** 2)
        part(d - r, hx / r, (z - ez) / r, base)
        band = (np.abs(z - 0.43) < 0.028)
        out[:] = np.where((band & (d < r) & vis)[..., None], out * 0.55 + 70, out)       # Gürtelstreifen
        r = 0.165
        d = np.sqrt(hx ** 2 + (z - 0.76) ** 2)
        part(d - r, hx / r, (z - 0.76) / r, _c(th["head"]), 0.5)
        visor = (d < r) & vis & (np.abs(z - 0.78) < 0.045) & (np.abs(hx) < 0.115)
        out[:] = np.where(visor[..., None], np.array([20, 30, 40], np.float32) + 90 * np.clip(1 - np.abs(hx + 0.04) / 0.05, 0, 1)[..., None], out)
        # Lebensbalken bei Schaden
        if b.hp < b.max_hp:
            frac = max(0.0, b.hp / b.max_hp)
            bar = (np.abs(hx) < 0.24) & (np.abs(z - 1.0) < 0.022) & vis
            fill = bar & ((hx + 0.24) / 0.48 <= frac)
            out[:] = np.where(bar[..., None], np.array([25, 28, 35], np.float32), out)
            out[:] = np.where(fill[..., None], np.array([239 - 150 * frac, 68 + 150 * frac, 80], np.float32), out)

    # ------------------------------------------------------------------ Einschusslöcher
    def _holes(self, img, g, dx, dy, horizon, zbuf, f, eye):
        w, h = self.w, self.h
        for t0, p in getattr(g, "holes", ()):
            vx, vy = p[0] - g.x, p[1] - g.y
            fwd = vx * dx + vy * dy
            if fwd < 0.2:
                continue
            sx = w / 2 + (-vx * dy + vy * dx) / fwd * f
            sy = horizon - (p[2] - eye) * f / fwd
            rad = max(1.2, 0.022 * f / fwd)
            x0, x1, y0, y1 = int(max(0, sx - rad - 1)), int(min(w, sx + rad + 2)), int(max(0, sy - rad - 1)), int(min(h, sy + rad + 2))
            if x1 <= x0 or y1 <= y0:
                continue
            cx = int(min(w - 1, max(0, sx)))
            if zbuf[cx] + 0.1 < fwd:                       # hinter einer anderen Wand/Kante
                continue
            age = g.t - t0
            fade = 1.0 if age < 7 else max(0.0, 1 - (age - 7) / 5)
            xs = np.arange(x0, x1, dtype=np.float32)[None, :] + 0.5
            ys = np.arange(y0, y1, dtype=np.float32)[:, None] + 0.5
            d = np.sqrt((xs - sx) ** 2 + (ys - sy) ** 2) / rad
            core = np.clip(1 - d, 0, 1) * fade
            ring = np.clip(1 - np.abs(d - 1.15) * 3, 0, 1) * 0.35 * fade
            out = img[y0:y1, x0:x1]
            out *= (1 - 0.8 * core - 0.25 * ring)[..., None]
            if age < 0.5:                                    # frisch: kurz glühend
                out += (np.clip(1.3 - d, 0, 1) * (1 - age / 0.5) * 120)[..., None] * np.array([1.0, 0.65, 0.25], np.float32)

    # ------------------------------------------------------------------ Zielkugel (leuchtend)
    def _target(self, img, b, g, dx, dy, horizon, zbuf, f, eye):
        w, h = self.w, self.h
        vx, vy = b.x - g.x, b.y - g.y
        fwd = vx * dx + vy * dy
        if fwd < 0.2:
            return
        sx = w / 2 + (-vx * dy + vy * dx) / fwd * f
        sy = horizon - (b.z - eye) * f / fwd
        rad = b.r * f / fwd
        halo = rad * 2.1
        x0, x1, y0, y1 = int(max(0, sx - halo)), int(min(w, sx + halo + 1)), int(max(0, sy - halo)), int(min(h, sy + halo + 1))
        if x1 <= x0 or y1 <= y0:
            return
        xs = np.arange(x0, x1, dtype=np.float32)[None, :] + 0.5
        ys = np.arange(y0, y1, dtype=np.float32)[:, None] + 0.5
        vis = (zbuf[x0:x1] > fwd)[None, :]
        dxp, dyp = (xs - sx) / rad, (ys - sy) / rad
        d2 = dxp * dxp + dyp * dyp
        base = _c(self.theme.get("accent", "#ffd479")) * 0.85 + _c(self.theme["bot"]) * 0.15
        out = img[y0:y1, x0:x1]
        glow = np.clip(1 - (np.sqrt(d2) - 1) / 1.1, 0, 1) ** 2 * 0.55
        out += np.where(vis, glow, 0)[..., None] * base[None, None, :]
        inside = (d2 < 1) & vis
        nz = np.sqrt(np.clip(1 - d2, 0, 1))
        lam = 0.45 + 0.55 * np.clip(dxp * LIGHT[0] - dyp * LIGHT[1] + nz * LIGHT[2], 0, 1)
        spec = np.clip(dxp * HALF[0] - dyp * HALF[1] + nz * HALF[2], 0, 1) ** 40
        rim = (1 - nz) ** 2.5
        col = base[None, None, :] * lam[..., None] * 1.1 + 255 * spec[..., None] * 0.7 + base[None, None, :] * rim[..., None] * 0.7
        flash = min(1.0, b.flash / 0.15)
        if flash > 0:
            col = col * (1 - 0.7 * flash) + 255 * 0.7 * flash
        out[:] = np.where(inside[..., None], col, out)

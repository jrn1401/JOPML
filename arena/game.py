"""Spiellogik der Arena: Spieler, Waffen, Rückstoß, Bots, Treffer und Auswertung (ohne Oberfläche, deterministisch mit seed)."""
import math
import random

from . import hit, weapons, world

EYE, EYE_CROUCH = 0.5, 0.34
BOT_H, HEAD_FROM, BOT_R = hit.BOT_TOP, 0.7, 0.28           # nur noch für Anzeige/Altwerte; Treffer laufen über arena.hit
WALK, SPRINT, CROUCH_SPEED = 2.4, 3.6, 1.3
SENS = 0.0009            # Radiant je Pixel Mausbewegung (Regler 1.0 = etwa 0,05 Grad je Zähler, wie Sensitivität ~2.3 in CS)
STEP = 1 / 120           # feste Schrittweite der Spielrechnung: Feuerrate und Rückstoß hängen nicht von der Bildrate ab
JUMP_V, GRAVITY = 1.15, 5.5
FOV_DEFAULT = 72


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class Bot:
    """kind 'bot' = laufender Gegner, kind 'target' = schwebende Kugel (Zielübung)."""

    def __init__(self, x, y, team, hp, kind="bot"):
        self.x, self.y, self.team, self.max_hp, self.hp = x, y, team, hp, hp
        self.target, self.wait, self.respawn, self.cd = None, 0.0, 0.0, 1.0
        self.flash = 0.0
        self.kind, self.z, self.z0, self.r, self.born = kind, 0.5, 0.5, 0.16, 0.0
        self.vx, self.vy, self.phase, self.origin = 0.0, 0.0, 0.0, (x, y)

    @property
    def alive(self):
        return self.hp > 0


class Game:
    def __init__(self, weapon="rifle", style=weapons.DEFAULT_STYLE, bots=4, bots_shoot=False, seed=None, theme="Classic",
                 mode="bots", fov=FOV_DEFAULT, ads_sens=1.0, invert=False):
        self.rnd = random.Random(seed)
        self.sens = SENS
        self.mode = mode if mode in ("bots", "targets") else "bots"
        self.fov = math.radians(max(50, min(110, float(fov))))
        self.fov_now, self.zoom, self.ads, self.ads_sens = self.fov, 1.0, 0.0, max(0.3, min(2.0, float(ads_sens)))
        self.invert = bool(invert)
        self.eye, self.eye_base, self.vx, self.vy = EYE, EYE, 0.0, 0.0
        self.jump_h = self.jump_v = 0.0
        self.pend_p = self.pend_y = 0.0                 # Rückstoß, der noch weich in die Kamera einfließt
        self.buf_until = -1.0                           # vorgemerkter Klick (Halbautomatik)
        self.tracers, self.holes, self.sparks, self.numbers = [], [], [], []
        self.weapon_id = weapon if weapon in weapons.WEAPONS else "rifle"
        self.style = weapons.STYLES.get(style) or weapons.STYLES[weapons.DEFAULT_STYLE]
        self.theme = weapons.THEMES.get(theme) or weapons.THEMES["Classic"]
        self.bots_shoot = bool(bots_shoot)
        self.cells = world.free_cells()
        self.t = 0.0
        self.x, self.y, self.ang, self.pitch = 2.5, 21.5, -math.pi / 2, 0.0
        self.hp, self.dead_until, self.speed = 100, 0.0, 0.0
        self.debt_p = self.debt_y = 0.0
        self.shots_in_row, self.last_shot, self.next_shot, self.fire_prev = 0, -9.0, 0.0, False
        self.w = weapons.WEAPONS[self.weapon_id]
        self.ammo, self.reload_until = self.w["mag"], 0.0
        self.events = []                      # (Zeit, Art) - für Treffermarkierung und Meldungen
        self.stat = {"shots": 0, "hits": 0, "head": 0, "kills": 0, "deaths": 0, "still": 0, "err_sum": 0.0, "err_n": 0, "react_sum": 0.0, "react_n": 0}
        self._spray_start = None
        self.bots = []
        for i in range(max(0, min(12, int(bots)))):
            if self.mode == "targets":
                b = Bot(0, 0, 0, 1, "target")
                self._place_target(b)
                self.bots.append(b)
            else:
                x, y = self._spawn_point()
                self.bots.append(Bot(x, y, i % 2, self.style["bot_hp"]))

    # ---------------------------------------------------------------- Hilfen
    def _spawn_point(self):
        for _ in range(60):
            x, y = self.rnd.choice(self.cells)
            if math.hypot(x - self.x, y - self.y) > 6:
                return x, y
        return self.cells[0]

    def _place_target(self, b):
        """Neuer Platz für eine Zielkugel: frei sichtbar, 4-13 Einheiten entfernt, in zufälliger Höhe."""
        for _ in range(80):
            x, y = self.rnd.choice(self.cells)
            d = math.hypot(x - self.x, y - self.y)
            if 4 <= d <= 13 and world.cast(self.x, self.y, math.atan2(y - self.y, x - self.x))[0] >= d:
                break
        b.x, b.y = x, y
        b.z0 = b.z = self.rnd.uniform(0.28, 0.82)
        b.hp, b.born, b.phase, b.origin = 1, self.t, self.rnd.uniform(0, 6.28), (x, y)
        ang = math.atan2(y - self.y, x - self.x) + math.pi / 2 * self.rnd.choice((-1, 1))
        b.vx, b.vy = math.cos(ang), math.sin(ang)

    @property
    def alive(self):
        return self.hp > 0

    def spread_deg(self) -> float:
        w = self.w
        frac = 1.0 if self.jump_h > 0 else min(1.0, self.speed / WALK)       # in der Luft zählt wie volle Bewegung
        sp = w["spread_stand"] + w["spread_move"] * self.style["move"] / 1.6 * frac
        crouch = max(0.0, min(1.0, (EYE - self.eye_base) / (EYE - EYE_CROUCH)))
        sp *= 1.0 - 0.2 * crouch
        return sp * (1.0 - (1.0 - weapons.ADS_SPREAD) * self.ads)

    def reload(self):
        if self.reload_until <= self.t and self.ammo < self.w["mag"]:
            self.reload_until = self.t + self.w["reload"]

    def set_weapon(self, wid):
        if wid in weapons.WEAPONS and wid != self.weapon_id:
            self.weapon_id, self.w = wid, weapons.WEAPONS[wid]
            self.ammo, self.reload_until, self.shots_in_row = self.w["mag"], 0.0, 0
            self.ads = 0.0

    # ---------------------------------------------------------------- Schritt
    def update(self, dt, keys=(), dmx=0.0, dmy=0.0, firing=False, aim=False):
        """Rechnet dt Sekunden in festen Teilschritten (1/120 s); die Mausbewegung wird gleichmäßig verteilt."""
        dt = max(0.0, min(0.1, dt))
        n = max(1, math.ceil(dt / STEP - 1e-9))
        for _ in range(n):
            self._step(dt / n, keys, dmx / n, dmy / n, firing, aim)

    def _step(self, dt, keys, dmx, dmy, firing, aim):
        self.t += dt
        if not self.alive:
            self.ads, self.speed, self.vx, self.vy, self.jump_h, self.jump_v = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            if self.t >= self.dead_until:
                self.hp, self.x, self.y, self.ang, self.pitch = 100, 2.5, 21.5, -math.pi / 2, 0.0
                self.ammo = self.w["mag"]
            self._bots(dt)
            self._fx_prune()
            return
        crouch = "ctrl" in keys
        self.eye_base += ((EYE_CROUCH if crouch else EYE) - self.eye_base) * min(1.0, 14 * dt)
        self.eye = self.eye_base + self.jump_h
        want = aim and not self.reload_until
        step = dt / weapons.ADS_TIME
        self.ads = min(1.0, self.ads + step) if want else max(0.0, self.ads - step)
        self.zoom = 1.0 + (self.w["zoom"] - 1.0) * _smooth(self.ads)
        self.fov_now = 2 * math.atan(math.tan(self.fov / 2) / self.zoom)
        self._look(dmx, dmy)
        self._move(dt, keys)
        if self.reload_until and self.t >= self.reload_until:
            self.ammo, self.reload_until = self.w["mag"], 0.0
        self._shoot(firing)
        self._kick(dt)
        self._recover(dt, firing)
        self._bots(dt)
        self._fx_prune()

    def _fx_prune(self):
        t = self.t
        self.tracers = [x for x in self.tracers if t - x[0] < 0.3][-24:]
        self.sparks = [x for x in self.sparks if t - x[0] < 0.45][-40:]
        self.numbers = [x for x in self.numbers if t - x[0] < 1.0][-12:]
        self.holes = [x for x in self.holes if t - x[0] < 12.0][-48:]

    def _look(self, dmx, dmy):
        # Empfindlichkeit passt sich dem Zoom an (gleiche Mausstrecke = gleicher Bildausschnitt) und lässt sich beim Visieren extra einstellen
        k = self.sens * (math.tan(self.fov_now / 2) / math.tan(self.fov / 2)) * (1.0 + (self.ads_sens - 1.0) * self.ads)
        dyaw, dpitch = dmx * k, (dmy if self.invert else -dmy) * k
        self.ang += dyaw
        self.pitch = max(-1.0, min(1.0, self.pitch + dpitch))
        # was die Spielerin gegen den Rückstoß zieht, zählt nicht mehr als noch offene "Schuld"
        if self.debt_p > 0 and dpitch < 0:
            self.debt_p = max(0.0, self.debt_p + dpitch)
        if self.debt_y > 0 and dyaw < 0:
            self.debt_y = max(0.0, self.debt_y + dyaw)
        elif self.debt_y < 0 and dyaw > 0:
            self.debt_y = min(0.0, self.debt_y + dyaw)

    def _move(self, dt, keys):
        fx, fy = math.cos(self.ang), math.sin(self.ang)
        sx, sy = -fy, fx
        ax = ay = 0.0
        if "w" in keys:
            ax += fx; ay += fy
        if "s" in keys:
            ax -= fx; ay -= fy
        if "d" in keys:
            ax += sx; ay += sy
        if "a" in keys:
            ax -= sx; ay -= sy
        n = math.hypot(ax, ay)
        cap = WALK
        if "ctrl" in keys:
            cap = CROUCH_SPEED
        elif "shift" in keys and "w" in keys and self.ads < 0.2:
            cap = SPRINT
        cap *= 1.0 - (1.0 - weapons.ADS_MOVE) * self.ads
        if "space" in keys and self.jump_h <= 0.0 and "ctrl" not in keys:
            self.jump_v = JUMP_V
        if self.jump_v or self.jump_h > 0:                  # Sprung: Höhe der Augen, Schwerkraft, Landung
            self.jump_v -= GRAVITY * dt
            self.jump_h += self.jump_v * dt
            if self.jump_h <= 0.0:
                self.jump_h, self.jump_v = 0.0, 0.0
        air = self.jump_h > 0
        tx, ty = (ax / n * cap, ay / n * cap) if n else (0.0, 0.0)
        k = min(1.0, (4.0 if air else (26.0 if n else 22.0)) * dt)     # am Boden knackig, in der Luft kaum Steuerung
        self.vx += (tx - self.vx) * k
        self.vy += (ty - self.vy) * k
        if not n and not air and math.hypot(self.vx, self.vy) < 0.05:
            self.vx = self.vy = 0.0
        mx, my = self.vx * dt, self.vy * dt
        if world.can_stand(self.x + mx, self.y):
            self.x += mx
        else:
            self.vx = 0.0
        if world.can_stand(self.x, self.y + my):
            self.y += my
        else:
            self.vy = 0.0
        self.speed = math.hypot(self.vx, self.vy)

    def _shoot(self, firing):
        edge = firing and not self.fire_prev
        self.fire_prev = firing
        if edge:
            self.buf_until = self.t + 0.15            # ein Klick kurz vor der nächsten Schussbereitschaft wird nicht verschluckt
        want = firing if self.w["auto"] else (edge or self.t < self.buf_until)
        if not want or self.reload_until or self.t < self.next_shot:
            return
        if self.ammo <= 0:
            self.reload()
            return
        self.buf_until = -1.0
        self.ammo -= 1
        self.next_shot = self.t + 1.0 / self.w["rate"]
        if self.t - self.last_shot > 0.35:
            self.shots_in_row = 0
            self._spray_start = (self.ang + self.pend_y, self.pitch + self.pend_p)
        idx = self.shots_in_row
        sp = math.radians(self.spread_deg())
        yaw = self.ang + self.pend_y + self.rnd.gauss(0, sp / 2)
        pit = self.pitch + self.pend_p + self.rnd.gauss(0, sp / 2)
        self.muzzle_t = self.t
        self.stat["shots"] += 1
        if self.speed < 0.3 and self.jump_h == 0:
            self.stat["still"] += 1
        self._hitscan(yaw, pit)
        # Rückstoß: das Muster zieht die Kamera ruckfrei nach oben (fließt über ~0,04 s ein), der offene Rest ("Schuld") baut sich danach ab
        kx, ky = weapons.kick_for(self.weapon_id, idx)
        k = self.style["recoil"] * (1.0 - (1.0 - weapons.ADS_KICK) * self.ads)
        wob = self.w["wobble"] * 0.6
        self.pend_y += math.radians(kx * k + self.rnd.uniform(-wob, wob) * k)
        self.pend_p += math.radians(ky * k + self.rnd.uniform(-wob, wob) * 0.5 * k)
        if self._spray_start is not None:
            ey = ((self.ang + self.pend_y - self._spray_start[0] + math.pi) % (2 * math.pi)) - math.pi
            err = math.degrees(math.hypot(ey, self.pitch + self.pend_p - self._spray_start[1]))
            self.stat["err_sum"] += err
            self.stat["err_n"] += 1
        self.shots_in_row += 1
        self.last_shot = self.t
        if self.ammo <= 0:
            self.reload()

    def _kick(self, dt):
        """Lässt den vorgemerkten Rückstoß weich in die Kamera einfließen (kein Ruck pro Schuss)."""
        if not (self.pend_y or self.pend_p):
            return
        f = 1.0 - math.exp(-dt / 0.04)
        dy, dp = self.pend_y * f, self.pend_p * f
        if abs(self.pend_y) < 1e-5 and abs(self.pend_p) < 1e-5:
            dy, dp = self.pend_y, self.pend_p
        self.pend_y -= dy
        self.pend_p -= dp
        self.ang += dy
        self.pitch = max(-1.0, min(1.0, self.pitch + dp))
        self.debt_y += dy
        self.debt_p += dp

    def _recover(self, dt, firing):
        """Nach dem Feuern kehrt die Kamera weich zurück (schnell am Anfang, dann ausklingend)."""
        if firing or self.t - self.last_shot < 0.12:
            return
        f = 1.0 - math.exp(-dt * self.w["recover"] / 3.0)
        for attr, debt in (("pitch", "debt_p"), ("ang", "debt_y")):
            d = getattr(self, debt)
            if d:
                r = d if abs(d) < math.radians(0.03) else d * f
                setattr(self, attr, getattr(self, attr) - r)
                setattr(self, debt, d - r)

    # ---------------------------------------------------------------- Treffer
    def _hitscan(self, yaw, pit):
        """Ein Schuss als Strahl durch den Raum: Wand/Decke/Boden begrenzen ihn, davor zählen die Körper-Hitboxen (arena.hit)."""
        o = (self.x, self.y, self.eye)
        d = hit.ray_dir(yaw, pit)
        wall_h = world.cast(self.x, self.y, yaw)[0]
        cp = max(math.cos(pit), 1e-6)
        t_wall = wall_h / cp
        t_flat = 1e9
        if d[2] > 1e-6:
            t_flat = (1.0 - o[2]) / d[2]
        elif d[2] < -1e-6:
            t_flat = (0.0 - o[2]) / d[2]
        t_end = min(t_wall, t_flat, 60.0)
        on_wall = t_end == t_wall
        best = None
        for b in self.bots:
            if not b.alive:
                continue
            if b.kind == "target":
                r = hit.hit_target(o, d, b.x, b.y, b.z, b.r)
            else:
                vx, vy = b.x - self.x, b.y - self.y
                dist = math.hypot(vx, vy)
                if dist < 1e-6:
                    continue
                r = hit.hit_bot(o, d, b.x, b.y, (-vy / dist, vx / dist))
            if r and r[0] < t_end and (best is None or r[0] < best[0]):
                best = (r[0], r[1], b)
        if best is not None:
            t_end = best[0]
        p = (o[0] + d[0] * t_end, o[1] + d[1] * t_end, o[2] + d[2] * t_end)
        self.tracers.append((self.t, p, "hit" if best else "miss"))
        if best is None:
            self.sparks.append((self.t, p, "wall"))
            if on_wall and 0.02 < p[2] < 0.98:
                self.holes.append((self.t, p))
            return
        _t, zone, b = best
        if b.kind == "target":
            dmg, text = b.hp, "HIT"
        else:
            mult = self.w["head"] if zone == "head" else hit.ZONES.get(zone, 1.0)
            dmg = self.w["damage"] * mult
            text = str(int(round(dmg)))
        b.hp -= dmg
        b.flash = 0.15
        self.stat["hits"] += 1
        if zone == "head":
            self.stat["head"] += 1
        self.sparks.append((self.t, p, "head" if zone == "head" else "body"))
        self.numbers.append((self.t, p, text, zone))
        if b.hp <= 0:
            self.stat["kills"] += 1
            b.respawn = self.t + (0.35 if b.kind == "target" else 2.0)
            if b.kind == "target":
                self.stat["react_sum"] += self.t - b.born
                self.stat["react_n"] += 1
            self.events.append((self.t, "kill"))
        else:
            self.events.append((self.t, "head" if zone == "head" else "hit"))

    # ---------------------------------------------------------------- Bots
    def _bots(self, dt):
        for b in self.bots:
            b.flash = max(0.0, b.flash - dt)
            if b.kind == "target":
                self._target_step(b, dt)
                continue
            if not b.alive:
                if self.t >= b.respawn:
                    b.x, b.y = self._spawn_point()
                    b.hp, b.target = b.max_hp, None
                continue
            if b.wait > 0:
                b.wait -= dt
            else:
                if b.target is None or math.hypot(b.target[0] - b.x, b.target[1] - b.y) < 0.15:
                    b.target = self.rnd.choice(self.cells)
                    b.wait = self.rnd.uniform(0.2, 1.8)
                else:
                    ang = math.atan2(b.target[1] - b.y, b.target[0] - b.x)
                    nx, ny = b.x + math.cos(ang) * 1.5 * dt, b.y + math.sin(ang) * 1.5 * dt
                    if world.can_stand(nx, ny, 0.3):
                        b.x, b.y = nx, ny
                    else:
                        b.target = None
            if self.bots_shoot and self.alive and self.mode == 'bots':
                self._bot_fire(b, dt)

    def _target_step(self, b, dt):
        if not b.alive:
            if self.t >= b.respawn:
                self._place_target(b)
            return
        speed = self.style.get("target_speed", 0.0)
        if speed > 0:
            nx, ny = b.x + b.vx * speed * dt, b.y + b.vy * speed * dt
            if world.can_stand(nx, ny, 0.3) and math.hypot(nx - b.origin[0], ny - b.origin[1]) < 2.2:
                b.x, b.y = nx, ny
            else:
                b.vx, b.vy = -b.vx, -b.vy
            b.z = b.z0 + 0.05 * math.sin(self.t * 1.6 + b.phase)

    def _bot_fire(self, b, dt):
        b.cd -= dt
        if b.cd > 0:
            return
        dx, dy = self.x - b.x, self.y - b.y
        d = math.hypot(dx, dy)
        if d > 14 or world.cast(b.x, b.y, math.atan2(dy, dx))[0] < d:
            return
        b.cd = self.rnd.uniform(0.8, 1.6)
        if self.rnd.random() < max(0.08, 0.6 - d * 0.04):
            self.hp -= self.style["bot_dmg"]
            self.events.append((self.t, "hurt"))
            if self.hp <= 0:
                self.stat["deaths"] += 1
                self.dead_until = self.t + 2.0

    # ---------------------------------------------------------------- Auswertung
    def summary(self) -> dict:
        s = self.stat
        shots = s["shots"]
        return {"shots": shots, "hits": s["hits"], "kills": s["kills"], "deaths": s["deaths"],
                "accuracy": round(100 * s["hits"] / shots) if shots else 0,
                "headshots": round(100 * s["head"] / s["hits"]) if s["hits"] else 0,
                "still": round(100 * s["still"] / shots) if shots else 0,
                "spray_error": round(s["err_sum"] / s["err_n"], 1) if s["err_n"] else 0.0,
                "avg_time": round(s["react_sum"] / s["react_n"], 2) if s["react_n"] else 0.0}

    def recent_events(self, kind=None, within=0.25):
        return [e for e in self.events if self.t - e[0] <= within and (kind is None or e[1] == kind)]

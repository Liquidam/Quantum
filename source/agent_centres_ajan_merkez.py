# =============================================================================
# SADA ALQUANTUM - AGENT CENTRES (20 soft discs)
#
# The whole social life of the twenty agents lives HERE, on twenty points.
# The million particles never talk to each other across agents: each particle
# only knows which agent it belongs to and follows that agent's disc.
# Twenty points cost nothing on the CPU, so the interaction can be as rich as
# we like without touching the GPU budget.
#
# numpy only. The same file runs in the offline preview and inside a TD
# Script CHOP.
#
# Forces on each centre, all of them LOCAL and varying over space (no uniform
# global push - EMG5 rule):
#   contact   soft spring when two discs come closer than r_i + r_j + gap
#   affinity  Clusters / Particle Life: an asymmetric matrix K[i,j] says
#             whether i is drawn to j or shies away from j, inside a band
#             just outside contact. Asymmetry is what makes them chase,
#             orbit and form short-lived groups.
#   wander    each agent has its own slowly turning heading
#   home      in TERRITORY (form 0) an agent is anchored to its seat;
#             the anchor fades as it becomes a BODY (form 1)
#   wall      soft walls at the box edge
#   tension   listening: everyone leans a little toward the middle and
#             breathes in sync
#   chaos     superposition: radius flicker and random kicks
#   collapse  the drawn agent inflates; contact alone pushes the rest aside
# =============================================================================
import numpy as np

TAU = 2.0 * np.pi


def _mix(a, b, t):
    return a + (b - a) * t


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


DEFAULTS = dict(
    form=0.0,          # 0 = territory, 1 = body
    r_terr=10.0,       # disc radius as territory (world units). 4 x 5 seats on a
                       # 103.6 x 125.2 box leave ~23 units per seat; with rscale up to
                       # 1.15 and the gap, 10 is the largest that never crosses the box
    r_body=9.0,        # disc radius as body (5 packed 26K particles 7x denser than
                       # the original field: no room left between lines)
    gap=2.5,           # the empty band Miranda drew between agents
    k_contact=0.06,
    k_aff_terr=0.0002, k_aff_body=0.0025,
    aff_range=26.0,    # width of the affinity band outside contact
    wander_terr=0.0008, wander_body=0.0025,
    dish=0.92,         # ellipse of the petri dish, fraction of the box
    k_bowl=0.0004,     # bowl that keeps the colony in the middle of the dish
    k_home=0.0025,     # seat anchor at form 0
    k_wall=0.05,
    damp=0.93,         # velocity kept per step
    vmax_terr=0.02, vmax_body=0.07,   # particles top out at ~0.25/frame: a body
                                      # must be slower than its own material or it
                                      # can only be dragged (v1), never followed
    tension=0.0,       # 0..1 listening
    chaos=0.0,         # 0..1 superposition
    winner=-1,
    collapse=0.0,      # 0..1 how far the winner has inflated
    r_win=50.0,        # the answer takes the whole board
    spin_rate=0.0,     # field rotation. 0: a turning field slid under still
                       # particles and kept them re-sorting (no lines settle)
    n_active=20,       # 2026-11-11 Eduardo: how many agents are on stage this
                       # round. Always 20 slots; slot i >= N hands its particles
                       # to agent i % N (alias) and shrinks into it. Nobody dies.
    fade=0.02,         # per frame, how fast a slot leaves / returns (~3 s)
    br_amp=0.14,       # breathing depth (radius +-), each agent its own rhythm (0.05 until 2026-11-11)
    br_rate=0.035,     # breathing speed (radians per frame x the agent's own pace)
    lobe=1.5,          # 2026-11-24 Eduardo: an agent's living edge (amoeba lobes,
                       # breathing) reaches past r. Walls keep r * lobe + pad
    pad=2.5,           # inside the box, so nobody is cut by the frame.
)

N_MIN = 2


class AgentCentres:
    def __init__(self, n=20, hbox=(51.8, 62.59), seed=7):
        self.n = n
        self.hb = np.array(hbox, dtype=np.float64)
        rng = np.random.default_rng(seed)
        self.rng = rng

        self.jit = rng.uniform(-3, 3, (n, 2))
        self.N = n
        self.alive = np.ones(n)                      # 1 on stage, 0 handed over
        self.seat = self._seats(n)
        self.x = self.seat.copy()
        self.v = np.zeros((n, 2))

        K = rng.uniform(-1.0, 1.0, (n, n))
        np.fill_diagonal(K, 0.0)
        self.K = K                                   # asymmetric on purpose

        self.heading = rng.uniform(0, TAU, n)
        self.turn = rng.uniform(0.6, 1.4, n)         # how restless each one is
        self.ang = rng.uniform(0, np.pi, n)          # texture orientation
        self.spin = rng.uniform(-1.0, 1.0, n)
        self.pitch = _mix(0.7, 1.7, rng.random(n))   # stripes per unit radius
        self.phase0 = rng.uniform(0, TAU, n)
        self.rscale = _mix(0.85, 1.15, rng.random(n))  # not twenty equal coins
        # hue order: golden ratio walk so neighbours in index are far in hue
        self.hue = np.mod(np.arange(n) * 0.6180339887, 1.0)

        self.r = np.full(n, DEFAULTS['r_terr'])
        self.t = 0
        self.p = dict(DEFAULTS)

    # -------------------------------------------------------------------------
    def _seats(self, N):
        """Seats on a grid sized for N agents; a slot off stage sits on its alias."""
        hb = self.hb
        cols = max(1, int(round(np.sqrt(N * hb[0] / hb[1]))))
        rows = -(-N // cols)
        seats = np.zeros((self.n, 2))
        for a in range(N):
            cx = ((a % cols) + 0.5) / cols - 0.5
            cy = ((a // cols) + 0.5) / rows - 0.5
            seats[a] = (cx * 2 * hb[0], cy * 2 * hb[1])
        seats[:N] += self.jit[:N] * np.sqrt(20.0 / N)
        for a in range(N, self.n):
            seats[a] = seats[a % N]
        return seats

    def alias(self):
        a = np.arange(self.n)
        return np.where(a < self.N, a, a % self.N)

    def _set_n(self):
        N = int(round(self.p.get('n_active', self.n)))
        N = max(N_MIN, min(self.n, N))
        if N != self.N:
            self.N = N
            self.seat = self._seats(N)
        target = (np.arange(self.n) < N).astype(np.float64)
        self.alive += (target - self.alive) * self.p['fade']

    # -------------------------------------------------------------------------
    def radii(self):
        p = self.p
        f = _smooth(p['form'])
        # fewer agents -> each one takes a bigger share of the board
        # (same coverage as 20: area per agent grows with 20/N)
        g = np.sqrt(self.n / float(self.N))
        r = np.full(self.n, _mix(p['r_terr'], p['r_body'], f)) * self.rscale * g
        # breathing: each agent its own rhythm, listening pulls them into sync
        own = np.sin(self.t * p['br_rate'] * self.turn + self.phase0)
        sync = np.sin(self.t * 0.05)
        br = _mix(own, sync, p['tension'])
        r *= 1.0 + p['br_amp'] * br + 0.04 * p['tension']
        if p['chaos'] > 0:
            r *= 1.0 + p['chaos'] * 0.35 * self.rng.uniform(-1, 1, self.n)
        # 2026-11-24: never bigger than the board's short side allows (few agents
        # on a 16:9 board were taller than the picture and got cut)
        cap = (min(self.hb) * p['dish'] - p['pad']) / p['lobe']
        r = np.minimum(r, max(cap, 1.0))
        w = int(p['winner'])
        c = _smooth(p['collapse'])
        if 0 <= w < self.n and c > 0:
            others = np.arange(self.n) != w
            r[others] *= 1.0 - 0.45 * c
            r[w] = _mix(r[w], p['r_win'], c)
        # off stage: shrink into the alias (0.5 is the shader's floor)
        return np.maximum(r * _smooth(self.alive), 0.5)

    # -------------------------------------------------------------------------
    def step(self):
        p = self.p
        n = self.n
        f = _smooth(p['form'])
        self.t += 1
        self._set_n()
        on = _smooth(self.alive)                              # 0..1 per slot
        pair = on[:, None] * on[None, :]                      # both on stage
        r = self.radii()
        self.r = r

        d = self.x[None, :, :] - self.x[:, None, :]          # d[i,j] = xj - xi
        dist = np.sqrt((d ** 2).sum(-1)) + 1e-6
        u = d / dist[..., None]
        np.fill_diagonal(dist, 1e9)

        reach = r[:, None] + r[None, :] + p['gap']
        F = np.zeros((n, 2))

        # contact: push apart, proportional to overlap
        ov = np.clip(reach - dist, 0, None) * pair
        F -= (u * (ov * p['k_contact'])[..., None]).sum(1)

        # affinity band just outside contact (triangle profile)
        s = (dist - reach) / p['aff_range']
        band = np.where((s > 0) & (s < 1), 1.0 - np.abs(2 * s - 1), 0.0)
        k_aff = _mix(p['k_aff_terr'], p['k_aff_body'], f)
        F += (u * (self.K * band * k_aff * pair)[..., None]).sum(1)

        # the dish: an ellipse inside the box. e > 1 means outside.
        reach_out = r * p['lobe'] + p['pad']
        ax = np.maximum(self.hb[0] * p['dish'] - reach_out, 1.0)
        ay = np.maximum(self.hb[1] * p['dish'] - reach_out, 1.0)
        e = np.sqrt((self.x[:, 0] / ax) ** 2 + (self.x[:, 1] / ay) ** 2) + 1e-9

        # wander: heading turns slowly, every agent at its own pace.
        # Near the rim the heading is steered back toward the middle
        # (Reynolds' containment) so nobody parks against the wall.
        self.heading += self.rng.normal(0, 0.05, n) * self.turn
        inward = np.arctan2(-self.x[:, 1], -self.x[:, 0])
        rim = _smooth((e - 0.75) / 0.25)
        dh = np.angle(np.exp(1j * (inward - self.heading)))
        self.heading += dh * rim * 0.08
        wand = _mix(p['wander_terr'], p['wander_body'], f)
        F += wand * np.stack([np.cos(self.heading), np.sin(self.heading)], 1)

        # home seat, fading with form
        F += (self.seat - self.x) * p['k_home'] * (1.0 - f)

        # listening: lean toward the middle (falloff with distance, not uniform)
        if p['tension'] > 0:
            L = np.sqrt((self.x ** 2).sum(1, keepdims=True)) + 1e-6
            F -= self.x / L * np.minimum(L, 30.0) * 0.0006 * p['tension']

        # collapse: the drawn agent drifts to the middle while it inflates
        w = int(p['winner'])
        if 0 <= w < n and p['collapse'] > 0:
            F[w] -= self.x[w] * 0.004 * _smooth(p['collapse'])

        # superposition: random kicks
        if p['chaos'] > 0:
            F += self.rng.normal(0, 0.06 * p['chaos'], (n, 2))

        # the dish is a shallow BOWL, not only a wall: zero in the middle,
        # rising with e^2 toward the rim. Without it the colony that the
        # affinities form drifts as one block into a corner (seen 2026-10-26).
        # Varies over space, so it never reads as a screen pan.
        F -= self.x * (p['k_bowl'] * f * e ** 2)[:, None]

        # soft dish wall (only in body form; territory is held by its seat)
        out = np.clip(e - 1.0, 0, None)
        F -= (self.x / e[:, None]) * out[:, None] * p['k_wall'] * f
        # and the hard box, always
        lim = np.maximum(self.hb[None, :] - reach_out[:, None], 0.5)
        over = np.clip(np.abs(self.x) - lim, 0, None) * np.sign(self.x)
        F -= over * p['k_wall']

        self.v = self.v * p['damp'] + F
        vmax = _mix(p['vmax_terr'], p['vmax_body'], f) * (1.0 + 2.0 * p['chaos'])
        sp = np.sqrt((self.v ** 2).sum(1, keepdims=True)) + 1e-9
        self.v *= np.minimum(1.0, vmax / sp)
        self.x += self.v

        # 2026-11-24: the soft wall alone let crowded bodies (8 agents in a
        # 16:9 board) be pushed past it and cut by the frame -> hard limit
        hit = np.abs(self.x) > lim
        self.x = np.clip(self.x, -lim, lim)
        self.v[hit] *= -0.3

        # off stage: the slot rides into its alias (its particles go there too)
        al = self.alias()
        off = 1.0 - on
        k = (0.04 * off)[:, None]
        self.x += (self.x[al] - self.x) * k
        self.v *= on[:, None]

        self.ang += p['spin_rate'] * self.spin * (0.3 + f)
        return self

    # -------------------------------------------------------------------------
    def conversion(self):
        """TAKEOVER: how far each agent has been absorbed by the winner.
        0 = still itself, 1 = fully the winner's. The wave leaves the winner
        and runs outward, so near neighbours go first."""
        p = self.p
        conv = np.zeros(self.n)
        w = int(p['winner'])
        if 0 <= w < self.n and p['collapse'] > 0:
            dmax = np.hypot(*self.hb) * 1.15
            dd = np.hypot(*(self.x - self.x[w]).T) / dmax
            conv = _smooth((p['collapse'] * 1.4 - dd) / 0.4)
            conv[w] = 0.0
        return conv

    def table(self):
        """One row per agent - what the GPU gets as uniform arrays.
        alias: who owns this slot's particles (itself when on stage).
        An off-stage slot wears its alias's hue so it never paints a stray dot."""
        al = self.alias()
        conv = self.conversion()
        return dict(cx=self.x[:, 0], cy=self.x[:, 1], r=self.r,
                    vx=self.v[:, 0], vy=self.v[:, 1],
                    ang=self.ang, pitch=self.pitch, hue=self.hue[al],
                    conv=conv[al], alias=al.astype(np.float64))

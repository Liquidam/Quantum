# =============================================================================
# SADA ALQUANTUM - STAGE MANAGER (one round of the piece)
# first built 2026-10-26, rewritten 2026-11-11 for the CONTROL panel
#
#   IDLE -> 1 LISTENING -> 2 SUPERPOSITION -> 3 COLLAPSE -> 4 ANSWER -> 5 RETURN
#                ^                                                      |
#                +------------------ next round -------------------------+
#
# Writes ONLY these channels of ajan_par (the stage's dials):
#   tension    listening: lean to the middle, breaths fall into sync
#   chaos      superposition: radius flicker and random kicks
#   winner     the agent drawn by the qubits, -1 = none
#   collapse   0..1 the winner inflates, the others flow into it
#   n_active   how many agents are on stage this round (2..20)
# 'form' (A territory -> B body) is NOT touched here: the CONTROL panel owns it.
#
# Settings come from the CONTROL panel (/project1/CONTROL/actions.settings()):
#   agents     how many agents (set by hand)
#   time mode  1 = RANDOM RANGE: every round draws a length between
#                  shortest and longest
#              2 = FIXED: every round lasts exactly the given time
#   "time" = from the start of LISTENING to the end of COLLAPSE. The three
#   phases keep their proportions (15 : 2.5 : 3.5). ANSWER and RETURN are fixed.
#
# Real elapsed time, never frame counts. Public calls:
#   basla()   start            yeniden()  restart the listening window
#   bitir()   stop, everyone home
#   durum()   raw state        bilgi()    what the panel shows
# Editing this text reloads the module: a running round stops (state -> IDLE).
# =============================================================================
import time
import math
import random

AJAN_SAYISI = 20      # slots. The agents on stage are the first N of them.
DINLEME_SN  = 15.0    # LISTENING      base length
SUPER_SN    = 2.5     # SUPERPOSITION  base length, short and chaotic
COKUS_SN    = 3.5     # COLLAPSE       base length, one comes forward
CEVAP_SN    = 8.0     # ANSWER         fixed (in performance may wait for a key)
DONUS_SN    = 5.0     # RETURN         fixed, everyone home - same particles
_TABAN      = DINLEME_SN + SUPER_SN + COKUS_SN    # 21 s = scale 1.0

FAZ_ADI = {'BEKLE': 'IDLE', 'DINLEME': '1  LISTENING', 'SUPER': '2  SUPERPOSITION',
           'COKUS': '3  COLLAPSE', 'CEVAP': '4  ANSWER', 'DONUS': '5  RETURN'}

_D = {'faz': 'BEKLE', 't0': 0.0, 'kazanan': -1, 'kaynak': '-', 'tur': 0,
      'n': AJAN_SAYISI, 'sure': _TABAN, 'olcek': 1.0}

PAR  = '/project1/Pop_glsl_sort/ajan_par'
LOG  = '/project1/Pop_glsl_sort/kume_log'
EXEC = '/project1/Pop_glsl_sort/STAGE_KUME_exec'
CTRL = '/project1/CONTROL/actions'


def _son_tur():
    """Round numbers continue from the log, also after this module reloads."""
    try:
        t = op(LOG)
        return int(t[t.numRows - 1, 'tur'].val) if t.numRows > 1 else 0
    except Exception:
        return 0


_D['tur'] = _son_tur()


# -- settings -----------------------------------------------------------------
def _ayar():
    """The CONTROL panel's settings; safe defaults if the panel is missing."""
    try:
        return op(CTRL).module.settings()
    except Exception:
        return dict(agents=AJAN_SAYISI, mode=1, tmin=12.0, tmax=35.0, tfix=21.0)


def _sure_cek():
    """This round's length (LISTENING + SUPERPOSITION + COLLAPSE)."""
    a = _ayar()
    if int(a['mode']) == 2:
        T = float(a['tfix'])
    else:
        lo, hi = sorted((float(a['tmin']), float(a['tmax'])))
        T = random.uniform(lo, hi)
    T = max(3.0, T)
    _D['sure'] = round(T, 2)
    _D['olcek'] = T / _TABAN


def _n_cek():
    """How many agents this round (set by hand on the panel)."""
    N = int(_ayar()['agents'])
    N = max(2, min(AJAN_SAYISI, N))
    _D['n'] = N
    _yaz('n_active', N)


def _o():
    return _D.get('olcek', 1.0)


# -- ajan_par -----------------------------------------------------------------
def _yaz(ad, deger):
    p = op(PAR)
    for i in range(16):
        nm = 'name%d' % i
        if not hasattr(p.par, nm):
            break
        if p.par[nm].eval() == ad:
            p.par['value%d' % i].expr = ''
            p.par['value%d' % i] = float(deger)
            return True
    return False


# -- the quantum draw -----------------------------------------------------------
def _cek(n):
    """Draw 0..n-1 with just enough qubits (5 agents = 3, 10 = 4, 20 = 5).
    Qiskit Aer (a simulator) if present, else Python random.
    Out-of-range results are drawn again."""
    q = max(1, int(math.ceil(math.log2(max(n, 2)))))
    try:
        from qiskit import QuantumCircuit
        from qiskit_aer import AerSimulator
        qc = QuantumCircuit(q, q)
        qc.h(range(q))
        qc.measure(range(q), range(q))
        sim = AerSimulator()
        for _ in range(40):
            r = sim.run(qc, shots=1).result()
            v = int(list(r.get_counts().keys())[0], 2)
            if v < n:
                return v, 'aer-%dq' % q
        return v % n, 'aer-%dq-mod' % q
    except Exception:
        return random.randrange(n), 'python'


def _logla():
    """One row per draw in kume_log (shown on the panel under WINNERS)."""
    t = op(LOG)
    t.appendRow([_D['tur'], time.strftime('%H:%M:%S'), _D['n'],
                 _D['sure'], _D['kazanan'], _D['kaynak']])
    print('[STAGE] round %d  winner AGENT %d  (%s, %d agents, %.1f s)' % (
        _D['tur'], _D['kazanan'], _D['kaynak'], _D['n'], _D['sure']))


# -- phases ---------------------------------------------------------------------
def _yumusak(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _git(faz):
    _D['faz'] = faz
    _D['t0'] = time.time()


def _faz_suresi(f):
    return {'DINLEME': DINLEME_SN * _o(), 'SUPER': SUPER_SN * _o(),
            'COKUS': COKUS_SN * _o(), 'CEVAP': CEVAP_SN, 'DONUS': DONUS_SN}.get(f, 0.0)


def _yeni_tur():
    _D['tur'] += 1
    _sure_cek()
    _n_cek()
    _git('DINLEME')


# -- public ---------------------------------------------------------------------
def basla():
    _yaz('tension', 0.0); _yaz('chaos', 0.0)
    _yaz('winner', -1);   _yaz('collapse', 0.0)
    _D['kazanan'] = -1
    _D.pop('bitir', None)
    _yeni_tur()
    op(EXEC).par.active = True


def yeniden():
    """The brief's 'restart the listening window'."""
    if _D['faz'] in ('COKUS', 'CEVAP'):
        _git('DONUS')
    else:
        basla()


def bitir():
    """Stop. Whatever is happening relaxes home, then the stage idles."""
    if _D['faz'] in ('COKUS', 'CEVAP'):
        _D['bitir'] = True
        _git('DONUS')
    elif _D['faz'] == 'DONUS':
        _D['bitir'] = True          # already going home: just do not start again
    else:
        _yaz('tension', 0.0); _yaz('chaos', 0.0)
        _yaz('winner', -1);   _yaz('collapse', 0.0)
        _git('BEKLE')


def durum():
    return dict(_D, gecen=round(time.time() - _D['t0'], 2))


def bilgi():
    """For the panel: phase name, 0..1 progress, seconds left, round facts."""
    f = _D['faz']
    L = _faz_suresi(f)
    g = time.time() - _D['t0']
    frac = min(1.0, g / L) if L > 0 else 0.0
    return dict(faz=f, ad=FAZ_ADI.get(f, f), frac=frac,
                kalan=max(0.0, L - g) if L > 0 else 0.0,
                tur=_D['tur'], n=_D['n'], sure=_D['sure'],
                kazanan=_D['kazanan'], kaynak=_D['kaynak'],
                durduruluyor=bool(_D.get('bitir')))


def adim():
    """Called every frame by STAGE_KUME_exec while not IDLE."""
    f = _D['faz']
    if f == 'BEKLE':
        return
    g = time.time() - _D['t0']
    L = _faz_suresi(f)

    if f == 'DINLEME':
        # the whole window IS the leaning-in
        _yaz('tension', _yumusak(g / L))
        if g >= L:
            _git('SUPER')

    elif f == 'SUPER':
        _yaz('tension', 1.0)
        _yaz('chaos', math.sin(math.pi * min(1.0, g / L)))
        if g >= L:
            _yaz('chaos', 0.0)
            k, kaynak = _cek(_D['n'])
            _D['kazanan'], _D['kaynak'] = k, kaynak
            _yaz('winner', k)
            _logla()
            _git('COKUS')

    elif f == 'COKUS':
        u = _yumusak(g / L)
        _yaz('collapse', u)
        _yaz('tension', 1.0 - u)
        if g >= L:
            _git('CEVAP')

    elif f == 'CEVAP':
        _yaz('collapse', 1.0)
        if g >= L:
            _git('DONUS')

    elif f == 'DONUS':
        _yaz('collapse', 1.0 - _yumusak(g / L))
        if g >= L:
            _yaz('winner', -1)
            _yaz('collapse', 0.0)
            if _D.pop('bitir', False):
                _git('BEKLE')
            else:
                _yeni_tur()

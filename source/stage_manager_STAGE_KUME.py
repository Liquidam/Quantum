# =============================================================================
# SADA ALQUANTUM - STAGE MANAGER (one round of the piece)
# first built 2026-10-26, rewritten 2026-11-11 for the CONTROL panel,
# 2026-11-24: MANUAL mode - every stage has its own button (Eduardo performs
# the stages by hand, in sync with the music, from a MIDI controller).
#
#   IDLE -> 1 LISTENING -> 2 SUPERPOSITION -> 3 COLLAPSE -> 4 ANSWER -> 5 RETURN
#
# Two run modes (CONTROL.par.Runmode):
#   1 AUTO    the round runs by itself on the TIME settings and loops.
#   2 MANUAL  each stage plays its movement and then HOLDS until the next
#             stage button is pressed. After RETURN the stage waits (IDLE).
# The stage buttons work in both modes: pressing one jumps to that stage
# (in AUTO the timing then carries on from there).
#
# Every stage starts from wherever the dials are at that moment, so pressing
# the buttons early, late or out of order never makes the image jump.
#
# The draw (the qubits choose the winner) happens:
#   AUTO    at the end of SUPERPOSITION (as before)
#   MANUAL  the moment COLLAPSE (or ANSWER) is pressed - if not drawn yet.
#
# Writes ONLY these channels of ajan_par (the stage's dials):
#   tension    listening: lean to the middle, breaths fall into sync
#   chaos      superposition: radius flicker and random kicks
#   winner     the agent drawn by the qubits, -1 = none
#   collapse   0..1 the winner inflates, the others flow into it
#   n_active   how many agents are on stage (2..20)
# 'form' (A territory -> B body) is NOT touched here: the CONTROL panel owns it.
#
# Settings come from the CONTROL panel (/project1/CONTROL/actions.settings()):
#   agents     how many agents (set by hand). Applied while IDLE or LISTENING,
#              and at RETURN (so: change it during ANSWER, it lands at RETURN).
#   auto       True = AUTO, False = MANUAL
#   time mode  1 = RANDOM RANGE (a length between shortest and longest)
#              2 = FIXED
#   "time" = from the start of LISTENING to the end of COLLAPSE. The three
#   phases keep their proportions (15 : 2.5 : 3.5). ANSWER and RETURN are fixed.
#   In MANUAL the same lengths set how fast each movement plays.
#
# Real elapsed time, never frame counts. Public calls:
#   basla()   start a round (LISTENING)   git(stage)  jump to a stage
#   bitir()   stop, everyone home         yeniden()   restart listening
#   durum()   raw state                   bilgi()     what the panel shows
# Editing this text reloads the module: a running round stops (state -> IDLE).
# =============================================================================
import time
import math
import random

AJAN_SAYISI = 20      # slots. The agents on stage are the first N of them.
DINLEME_SN  = 15.0    # LISTENING      base length
SUPER_SN    = 2.5     # SUPERPOSITION  base length, short and chaotic
COKUS_SN    = 3.5     # COLLAPSE       base length, one comes forward
CEVAP_SN    = 8.0     # ANSWER         fixed (AUTO only; MANUAL holds)
DONUS_SN    = 5.0     # RETURN         fixed, everyone home - same particles
_TABAN      = DINLEME_SN + SUPER_SN + COKUS_SN    # 21 s = scale 1.0

FAZ_ADI = {'BEKLE': 'IDLE', 'DINLEME': '1  LISTENING', 'SUPER': '2  SUPERPOSITION',
           'COKUS': '3  COLLAPSE', 'CEVAP': '4  ANSWER', 'DONUS': '5  RETURN'}
SIRA = ('DINLEME', 'SUPER', 'COKUS', 'CEVAP', 'DONUS')

_D = {'faz': 'BEKLE', 't0': 0.0, 'kazanan': -1, 'kaynak': '-', 'tur': 0,
      'n': AJAN_SAYISI, 'sure': _TABAN, 'olcek': 1.0,
      'v0': {}, 'v': {'tension': 0.0, 'chaos': 0.0, 'collapse': 0.0}}

PAR  = '/project1/Pop_glsl_sort/ajan_par'
LOG  = '/project1/Pop_glsl_sort/kume_log'
EXEC = '/project1/Pop_glsl_sort/STAGE_KUME_exec'
CTRL = '/project1/CONTROL/actions'
MIDI = '/project1/CONTROL/midi'


def _son_tur():
    """Round numbers continue from the log, also after this module reloads."""
    try:
        t = op(LOG)
        return int(t[t.numRows - 1, 'tur'].val) if t.numRows > 1 else 0
    except Exception:
        return 0


# Read lazily, NOT at import time: reading kume_log here made this module
# depend on the log, so every new winner row reloaded it -> stage fell to IDLE
# right after the draw (bug reported by Eduardo, 2026-11-17).
_D['tur'] = -1


# -- settings -----------------------------------------------------------------
def _ayar():
    """The CONTROL panel's settings; safe defaults if the panel is missing."""
    try:
        a = op(CTRL).module.settings()
    except Exception:
        a = dict(agents=AJAN_SAYISI, mode=1, tmin=12.0, tmax=35.0, tfix=21.0)
    a.setdefault('auto', True)
    return a


def _oto():
    return bool(_ayar()['auto'])


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
    """How many agents (set by hand on the panel)."""
    N = int(_ayar()['agents'])
    N = max(2, min(AJAN_SAYISI, N))
    _D['n'] = N
    _yaz('n_active', N)


def n_degisti():
    """The AGENTS knob moved. Lands now while IDLE, LISTENING or RETURN
    (unless that would take the winner off stage); otherwise at RETURN."""
    f = _D['faz']
    if f in ('BEKLE', 'DINLEME'):
        _n_cek()
    elif f == 'DONUS':
        k = _D['kazanan']
        if k < 0 or k < int(_ayar()['agents']):
            _n_cek()


def _o():
    return _D.get('olcek', 1.0)


# -- ajan_par -----------------------------------------------------------------
def _yaz(ad, deger):
    if ad in _D['v']:
        _D['v'][ad] = float(deger)
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


def _oku(ad):
    try:
        return float(op(PAR)[ad].eval())
    except Exception:
        return _D['v'].get(ad, 0.0)


# -- the quantum draw -----------------------------------------------------------
# Circuit: q qubits, a Hadamard on each (equal superposition), then measure all.
# The outcome is the winner. q is just enough for the agents on stage
# (5 agents = 3 qubits, 10 = 4, 20 = 5); outcomes >= n are drawn again.
#
# Two engines, same circuit, same probabilities:
#   1. Qiskit Aer, if it is installed where TouchDesigner's Python can find it
#      (a 'pylibs' folder next to the .toe, or TD's own site-packages).
#   2. Otherwise a state-vector simulation in NumPy (built into TouchDesigner):
#      |0..0> -> H x q -> Born rule. Nothing has to be installed, so the file
#      opens on any Mac without security prompts (2026-11-19: the bundled
#      compiled Qiskit libraries were what macOS kept blocking).
_AER = {}


def _aer():
    """AerSimulator class, or None. Tried once per session."""
    if 'sim' not in _AER:
        try:
            import sys, os
            kok = project.folder
            for aday in (os.path.join(kok, 'pylibs'), os.path.join(os.path.dirname(kok), 'pylibs')):
                if os.path.isdir(aday) and aday not in sys.path:
                    sys.path.insert(0, aday)
            from qiskit import QuantumCircuit
            from qiskit_aer import AerSimulator
            _AER['QC'], _AER['sim'] = QuantumCircuit, AerSimulator()
        except Exception:
            _AER['sim'] = None
    return _AER['sim']


def _cek_aer(n, q):
    sim = _aer()
    qc = _AER['QC'](q, q)
    qc.h(range(q))
    qc.measure(range(q), range(q))
    for _ in range(40):
        r = sim.run(qc, shots=1).result()
        v = int(list(r.get_counts().keys())[0], 2)
        if v < n:
            return v, 'aer-%dq' % q
    return v % n, 'aer-%dq-mod' % q


def _cek_sv(n, q):
    import numpy as np
    H = np.array([[1.0, 1.0], [1.0, -1.0]]) / np.sqrt(2.0)
    U = H
    for _ in range(q - 1):
        U = np.kron(U, H)                    # H on every qubit
    psi = np.zeros(1 << q)                   # amplitudes are real for this circuit
    psi[0] = 1.0                             # |0...0>
    psi = U.dot(psi)
    p = np.abs(psi) ** 2                     # Born rule
    p = p / p.sum()
    rng = np.random.default_rng()            # seeded from the OS entropy pool
    for _ in range(40):
        v = int(rng.choice(1 << q, p=p))
        if v < n:
            return v, 'sv-%dq' % q
    return v % n, 'sv-%dq-mod' % q


def _cek(n):
    """Draw 0..n-1 with just enough qubits. Aer if present, else NumPy."""
    q = max(1, int(math.ceil(math.log2(max(n, 2)))))
    if _aer() is not None:
        try:
            return _cek_aer(n, q)
        except Exception as e:
            print('[STAGE] Aer failed, NumPy state vector instead:', e)
    try:
        return _cek_sv(n, q)
    except Exception:
        return random.randrange(n), 'python'


def _logla():
    """One row per draw in kume_log (shown on the panel under WINNERS)."""
    t = op(LOG)
    t.appendRow([_D['tur'], time.strftime('%H:%M:%S'), _D['n'],
                 _D['sure'], _D['kazanan'], _D['kaynak']])
    print('[STAGE] round %d  winner AGENT %d  (%s, %d agents, %.1f s)' % (
        _D['tur'], _D['kazanan'], _D['kaynak'], _D['n'], _D['sure']))


def _cekilis():
    """The qubits choose the winner: log it, send it out (MIDI OUT), show it."""
    k, kaynak = _cek(_D['n'])
    _D['kazanan'], _D['kaynak'] = k, kaynak
    _yaz('winner', k)
    _logla()
    try:                    # MIDI OUT: the agent's number 1..20 (CONTROL panel)
        op(MIDI).module.send_winner(k)
    except Exception as e:
        print('[STAGE] MIDI OUT failed:', e)


# -- phases ---------------------------------------------------------------------
def _yumusak(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _mix(a, b, t):
    return a + (b - a) * t


def _git(faz):
    """Enter a stage. Remember where the dials are: the stage moves on from there."""
    _D['faz'] = faz
    _D['t0'] = time.time()
    _D['v0'] = {k: _oku(k) for k in ('tension', 'chaos', 'collapse')}
    if faz != 'BEKLE':
        op(EXEC).par.active = True


def _faz_suresi(f):
    L = {'DINLEME': DINLEME_SN * _o(), 'SUPER': SUPER_SN * _o(),
         'COKUS': COKUS_SN * _o(), 'CEVAP': CEVAP_SN, 'DONUS': DONUS_SN}.get(f, 0.0)
    if f == 'CEVAP':        # ANSWER pressed before the collapse finished
        L = max(L, _cevap_yukselis()) if _oto() else _cevap_yukselis()
    return L


def _cevap_yukselis():
    """How long ANSWER takes to finish an unfinished collapse."""
    c0 = _D['v0'].get('collapse', 1.0) if _D['faz'] == 'CEVAP' else 1.0
    return 0.6 if c0 > 0.9 else COKUS_SN * _o()


def _yeni_tur():
    """A new round: number, length, agent count. The winner is cleared."""
    if _D['tur'] < 0:
        _D['tur'] = _son_tur()
    _D['tur'] += 1
    _D['kazanan'] = -1
    _D['kaynak'] = '-'
    _yaz('winner', -1)
    _sure_cek()
    _n_cek()


# -- public ---------------------------------------------------------------------
_ENG = {'LISTENING': 'DINLEME', 'LISTEN': 'DINLEME', 'START': 'DINLEME',
        'SUPERPOSITION': 'SUPER', 'COLLAPSE': 'COKUS', 'ANSWER': 'CEVAP',
        'RETURN': 'DONUS'}


def basla():
    """Start a round: LISTENING. Only called when no winner is on stage."""
    _D.pop('bitir', None)
    _D.pop('sonra', None)
    _yeni_tur()
    _git('DINLEME')


def git(faz):
    """A stage button. Jumps to that stage from wherever the round is.
    A new round (LISTENING / SUPERPOSITION) while a winner is on stage first
    sends everyone home (RETURN) and then starts it."""
    f = _ENG.get(str(faz).upper(), faz)
    if f not in SIRA:
        return
    cur = _D['faz']
    _D.pop('bitir', None)
    winner_on = _D['kazanan'] >= 0 and cur in ('COKUS', 'CEVAP', 'DONUS')

    if f in ('DINLEME', 'SUPER'):
        if winner_on:
            _D['sonra'] = f                 # after RETURN
            if cur != 'DONUS':
                _donus()
            return
        if f == 'DINLEME':
            basla()
            return
        if cur == 'BEKLE':
            _yeni_tur()
        _D.pop('sonra', None)
        _git('SUPER')
        return

    if f in ('COKUS', 'CEVAP'):
        _D.pop('sonra', None)
        if cur == 'BEKLE':
            _yeni_tur()
        if _D['kazanan'] < 0:
            _cekilis()
        _git(f)
        return

    if f == 'DONUS':
        _D.pop('sonra', None)
        if cur != 'BEKLE':
            _donus()


def _donus():
    _git('DONUS')
    # a new agent count lands now, unless it would take the winner off stage
    k = _D['kazanan']
    if k < 0 or k < int(_ayar()['agents']):
        _n_cek()


def yeniden():
    """The brief's 'restart the listening window'."""
    git('DINLEME')


def bitir():
    """Stop. Whatever is happening relaxes home, then the stage idles."""
    _D.pop('sonra', None)
    if _D['faz'] in ('COKUS', 'CEVAP'):
        _D['bitir'] = True
        _donus()
    elif _D['faz'] == 'DONUS':
        _D['bitir'] = True          # already going home: just do not start again
    else:
        _yaz('tension', 0.0); _yaz('chaos', 0.0)
        _yaz('winner', -1);   _yaz('collapse', 0.0)
        _D['kazanan'] = -1
        _git('BEKLE')


def durum():
    return dict(_D, gecen=round(time.time() - _D['t0'], 2))


SONRAKI = {'BEKLE': '1  LISTENING', 'DINLEME': '2  SUPERPOSITION', 'SUPER': '3  COLLAPSE',
           'COKUS': '4  ANSWER', 'CEVAP': '5  RETURN', 'DONUS': '1  LISTENING'}


def bilgi():
    """For the panel: phase name, 0..1 progress, seconds left, round facts."""
    f = _D['faz']
    L = _faz_suresi(f)
    g = time.time() - _D['t0']
    frac = min(1.0, g / L) if L > 0 else 0.0
    oto = _oto()
    return dict(faz=f, ad=FAZ_ADI.get(f, f), frac=frac,
                kalan=max(0.0, L - g) if L > 0 else 0.0,
                tur=_D['tur'], n=_D['n'], sure=_D['sure'],
                kazanan=_D['kazanan'], kaynak=_D['kaynak'],
                durduruluyor=bool(_D.get('bitir')),
                oto=oto, tutuyor=(not oto and f not in ('BEKLE', 'DONUS') and g >= L),
                sonraki=SONRAKI.get(f, ''), sonra=FAZ_ADI.get(_D.get('sonra', ''), ''))


def adim():
    """Called every frame by STAGE_KUME_exec while not IDLE.
    Every stage moves the dials from where they were (v0) to its own target."""
    f = _D['faz']
    if f == 'BEKLE':
        return
    g = time.time() - _D['t0']
    L = _faz_suresi(f)
    v0 = _D['v0']
    oto = _oto()

    if f == 'DINLEME':
        # the whole window IS the leaning-in
        u = _yumusak(g / L)
        _yaz('tension', _mix(v0['tension'], 1.0, u))
        _yaz('chaos', _mix(v0['chaos'], 0.0, _yumusak(g / 1.5)))
        _yaz('collapse', _mix(v0['collapse'], 0.0, u))
        if oto and g >= L:
            _git('SUPER')

    elif f == 'SUPER':
        _yaz('tension', _mix(v0['tension'], 1.0, _yumusak(g / max(0.3, 0.3 * L))))
        _yaz('collapse', _mix(v0['collapse'], 0.0, _yumusak(g / 1.0)))
        if oto:
            # one swell of chaos, then the draw
            _yaz('chaos', _mix(v0['chaos'], 0.0, _yumusak(g / L)) +
                 math.sin(math.pi * min(1.0, g / L)))
            if g >= L:
                _yaz('chaos', 0.0)
                if _D['kazanan'] < 0:
                    _cekilis()
                _git('COKUS')
        else:
            # MANUAL: the chaos rises and stays until COLLAPSE is pressed
            _yaz('chaos', _mix(v0['chaos'], 0.7, _yumusak(g / max(0.5, 0.4 * L))))

    elif f == 'COKUS':
        u = _yumusak(g / L)
        _yaz('collapse', _mix(v0['collapse'], 1.0, u))
        _yaz('tension', _mix(v0['tension'], 0.0, u))
        _yaz('chaos', _mix(v0['chaos'], 0.0, _yumusak(g / max(0.3, 0.3 * L))))
        if oto and g >= L:
            _git('CEVAP')

    elif f == 'CEVAP':
        u = _yumusak(g / _cevap_yukselis())
        _yaz('collapse', _mix(v0['collapse'], 1.0, u))
        _yaz('tension', _mix(v0['tension'], 0.0, u))
        _yaz('chaos', _mix(v0['chaos'], 0.0, u))
        if oto and g >= L:
            _donus()

    elif f == 'DONUS':
        u = _yumusak(g / L)
        _yaz('collapse', _mix(v0['collapse'], 0.0, u))
        _yaz('tension', _mix(v0['tension'], 0.0, u))
        _yaz('chaos', _mix(v0['chaos'], 0.0, u))
        if g >= L:
            _yaz('winner', -1)
            _yaz('collapse', 0.0)
            _D['kazanan'] = -1
            _n_cek()
            sonra = _D.pop('sonra', None)
            if _D.pop('bitir', False):
                _git('BEKLE')
            elif sonra:
                git(sonra)
            elif oto:
                basla()
            else:
                _git('BEKLE')       # MANUAL: wait for LISTENING

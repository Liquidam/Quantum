# qsim - MOCK quantum state source (no Qiskit yet)
#
# Outputs the statevector of a chosen circuit as two channels, 're' and 'im',
# each with 2^NQ samples. These feed q_re / q_im -> u_qre[] / u_qim[].
#
# THE POINT OF THIS FILE: the visual variety does NOT come from our knobs.
# It comes from the CIRCUIT. Each circuit is a different set of amplitudes,
# and a different set of amplitudes is a different image. Swap the circuit,
# swap the world.
#
# When Qiskit is wired in, only the CIRCUITS dict gets replaced by
# QuantumCircuit.from_qasm / Statevector.from_instruction. Everything
# downstream (channels, arrays, shader) stays identical.
#
# ASCII only - the TD script executor cannot encode unicode.

import numpy as np

NQ = 4
K  = 1 << NQ

# --- gate helpers ------------------------------------------------------------

def _H(q, nq=None):
    nq = nq or NQ
    s = 1.0/np.sqrt(2.0)
    M = np.zeros((1 << nq, 1 << nq), dtype=complex)
    for k in range(1 << nq):
        b = (k >> q) & 1
        k0 = k & ~(1 << q); k1 = k | (1 << q)
        M[k0, k] += s
        M[k1, k] += s if b == 0 else -s
    return M

def _CX(c, t, nq=None):
    nq = nq or NQ
    M = np.zeros((1 << nq, 1 << nq), dtype=complex)
    for k in range(1 << nq):
        kk = k ^ (1 << t) if (k >> c) & 1 else k
        M[kk, k] = 1.0
    return M

def _RY(q, th, nq=None):
    nq = nq or NQ
    M = np.zeros((1 << nq, 1 << nq), dtype=complex)
    c = np.cos(th/2.0); s = np.sin(th/2.0)
    for k in range(1 << nq):
        b = (k >> q) & 1
        k0 = k & ~(1 << q); k1 = k | (1 << q)
        if b == 0: M[k0, k] += c;  M[k1, k] += s
        else:      M[k0, k] += -s; M[k1, k] += c
    return M

def _RZ(q, th, nq=None):
    nq = nq or NQ
    M = np.zeros((1 << nq, 1 << nq), dtype=complex)
    for k in range(1 << nq):
        M[k, k] = np.exp(1j*th/2.0) if (k >> q) & 1 else np.exp(-1j*th/2.0)
    return M

def _CP(c, t, th, nq=None):
    """controlled phase - QFT's building block"""
    nq = nq or NQ
    M = np.zeros((1 << nq, 1 << nq), dtype=complex)
    for k in range(1 << nq):
        both = ((k >> c) & 1) and ((k >> t) & 1)
        M[k, k] = np.exp(1j*th) if both else 1.0
    return M

def _zero():
    v = np.zeros(K, dtype=complex); v[0] = 1.0
    return v

def _norm(v):
    n = np.linalg.norm(v)
    return v/n if n > 0 else v


# --- the circuit library -----------------------------------------------------
# Every entry: (short name, description, function(theta, phi) -> statevector)

def c_carpim(th, ph):
    """CARPIM - no entanglement at all. Each qubit rotated on its own.
       QASM:  ry(th) q0 ; ry(ph) q1 ; ry(th) q2 ; ry(ph) q3"""
    v = _zero()
    v = _RY(0, th) @ v
    v = _RY(1, ph) @ v
    v = _RY(2, th*0.7) @ v
    v = _RY(3, ph*1.3) @ v
    return _norm(v)

def c_bell2(th, ph):
    """IKI BELL CIFTI - q0-q1 dolanik, q2-q3 dolanik, ciftler birbirinden bagimsiz.
       QASM:  ry(th) q0 ; h q0 ; cx q0,q1 ; ry(ph) q2 ; h q2 ; cx q2,q3"""
    v = _zero()
    v = _RY(0, th) @ v
    v = _H(0) @ v
    v = _CX(0, 1) @ v
    v = _RY(2, ph) @ v
    v = _H(2) @ v
    v = _CX(2, 3) @ v
    return _norm(v)

def c_ghz(th, ph):
    """GHZ - dort kubit birden dolanik. Hepsi ya 0 ya 1.
       QASM:  ry(th) q0 ; h q0 ; cx q0,q1 ; cx q1,q2 ; cx q2,q3 ; rz(ph) q0"""
    v = _zero()
    v = _RY(0, th) @ v
    v = _H(0) @ v
    v = _CX(0, 1) @ v
    v = _CX(1, 2) @ v
    v = _CX(2, 3) @ v
    v = _RZ(0, ph) @ v
    return _norm(v)

def c_w(th, ph):
    """W DURUMU - tek bir uyarilma dort kubite yayilmis. GHZ'den bambaska
       bir dolaniklik cinsi: bir kubit olculse bile digerleri hala dolanik."""
    v = np.zeros(K, dtype=complex)
    for j in range(NQ):
        v[1 << j] = np.exp(1j*ph*j)
    v = _RZ(0, th) @ v
    return _norm(v)

def c_qft(th, ph):
    """QFT - kuantum Fourier donusumu. Butun fazlar duzenli bir merdiven.
       Belgenin kendi ornek devrelerinden biri (Phase 3 Test - QFT)."""
    v = _zero()
    v = _RY(0, th) @ v
    v = _RY(2, ph) @ v
    v = _H(0) @ v
    v = _CP(1, 0, np.pi/2) @ v
    v = _CP(2, 0, np.pi/4) @ v
    v = _CP(3, 0, np.pi/8) @ v
    v = _H(1) @ v
    v = _CP(2, 1, np.pi/2) @ v
    v = _CP(3, 1, np.pi/4) @ v
    v = _H(2) @ v
    v = _CP(3, 2, np.pi/2) @ v
    v = _H(3) @ v
    return _norm(v)

def c_zincir(th, ph):
    """ZINCIR - Miranda'nin kendi ornegi (GHZ with Parameters), 4 kubite tasindi.
       QASM:  rx(a) q0 ; ry(b) q1 ; rz(g) q2 ; h q0 ; cx q0,q1 ; cx q1,q2"""
    v = _zero()
    v = _RY(0, th) @ v
    v = _RY(1, ph) @ v
    v = _RZ(2, th*1.4) @ v
    v = _H(0) @ v
    v = _CX(0, 1) @ v
    v = _CX(1, 2) @ v
    v = _RY(3, ph*0.6) @ v
    return _norm(v)


def c_dolaniklik(th, ph):
    """DOLANIKLIK KNOBU - theta dolanikligi sifirdan maksimuma goturur.
       Fizik olarak anlamli tek eksen; hocanin MIDI knobu icin dogal aday.
         th = 0     -> |0000>          carpim, dolaniklik YOK   (entropi 0)
         th = pi/2  -> iki Bell cifti  MAKSIMUM dolanik          (entropi 1)
         th = pi    -> |1111>          yine carpim               (entropi 0)
       QASM:  ry(th) q0 ; cx q0,q1 ; ry(th) q2 ; cx q2,q3 ; rz(ph) q1"""
    v = _zero()
    v = _RY(0, th) @ v
    v = _CX(0, 1) @ v
    v = _RY(2, th) @ v
    v = _CX(2, 3) @ v
    v = _RZ(1, ph) @ v
    return _norm(v)


CIRCUITS = [
    ('CARPIM',   'dolanik DEGIL - dort bagimsiz kubit',   c_carpim),
    ('BELL x2',  'iki ayri dolanik cift',                 c_bell2),
    ('GHZ',      'dordu birden dolanik',                  c_ghz),
    ('W',        'tek uyarilma dorde yayilmis',           c_w),
    ('QFT',      'Fourier - duzenli faz merdiveni',       c_qft),
    ('ZINCIR',   "Miranda'nin ornegi, 4 kubit",           c_zincir),
    ('DOLANIK',  'theta dolanikligi 0 -> max -> 0 surer',  c_dolaniklik),
]


def state(idx, theta, phi):
    """Devrenin statevector'u. MOTOR'e gore Qiskit ya da numpy yolu."""
    idx = int(idx) % len(CIRCUITS)
    if MOTOR == 'qasm' and _qiskit_yukle():
        dat = op('qasm_input')
        metin = dat.text if dat is not None else QASM_METNI
        if metin.strip():
            return _qasm_state(metin)
    if MOTOR == 'qiskit' and _qiskit_yukle():
        try:
            return _qk_state(idx, theta, phi)
        except Exception as e:
            print('[qsim] Qiskit hatasi, numpy yoluna dusuldu:', e)
    return CIRCUITS[idx][2](theta, phi)


# --- field range (KULLANILMIYOR) --------------------------------------------
# 2026-08-28'de key'i normalize etmek icin yazildi, sonra geri alindi:
# key'e monoton bir donusum uygulamak siralamayi degistirmiyor, dolayisiyla
# ekranda hicbir sey degistirmiyor. Olcum araci olarak duruyor.

def field_range(v, spread, kscale, fieldScale, bx, by, G=56):
    x = np.linspace(-bx, bx, G); y = np.linspace(-by, by, G)
    X, Y = np.meshgrid(x, y, indexing='ij')
    px, py = X*fieldScale, Y*fieldScale
    th = [px*np.cos(j*spread)*kscale + py*np.sin(j*spread)*kscale for j in range(NQ)]
    F = np.zeros_like(px, dtype=complex)
    for k in range(K):
        ph = np.zeros_like(px)
        for j in range(NQ):
            if (k >> j) & 1: ph = ph + th[j]
        F += v[k]*np.exp(1j*ph)
    I = np.abs(F)**2
    return float(I.min()), float(I.max())




# =============================================================================
# QISKIT MOTORU  (kurulum: QUANTUM/pylibs, TD'nin kendi python3.11'i ile)
# =============================================================================
# Yukaridaki numpy kapilari OGRETICI ve YEDEK olarak duruyor. Gercek is artik
# Qiskit'te: ayni devreler QuantumCircuit olarak kuruluyor, Statevector ile
# cozuluyor. Ikisinin AYNI sonucu verdigi dogrulandi (bkz. qiskit_dogrula()).
#
# Miranda bir .qasm dosyasi verdiginde tek yapilacak: MOTOR='qasm' ve
# QASM_METNI'ni doldurmak. Alt tarafin hicbiri degismez.

MOTOR = 'qiskit'          # 'qiskit' | 'numpy' | 'qasm'
QASM_METNI = ''
# Qiskit lives next to the project file, not at a fixed path, so the project
# can be opened on another machine. Three locations are tried in order: beside
# the .toe, one level up, and finally the machine's own site-packages. If none
# of them has Qiskit the NumPy gate set takes over and the image is unaffected.
def _pylib_adaylari():
    import td as _td, os
    kok = _td.project.folder
    return [os.path.join(kok, 'pylibs'),
            os.path.join(os.path.dirname(kok), 'pylibs'),
            os.path.join(kok, 'QUANTUM', 'pylibs')]

PYLIBS = ''   # ilk basarili aday buraya yazilir

_QK = {'hazir': False}

def _qiskit_yukle():
    global PYLIBS
    if _QK['hazir']: return True
    if _QK.get('yok'): return False      # tried once already: NumPy from now on
    import sys, os
    for aday in _pylib_adaylari():
        if os.path.isdir(aday) and aday not in sys.path:
            sys.path.insert(0, aday)
            PYLIBS = aday
            break
    try:
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Statevector
        _QK['QC'] = QuantumCircuit
        _QK['SV'] = Statevector
        _QK['hazir'] = True
        return True
    except Exception as e:
        _QK['yok'] = True
        print('[qsim] Qiskit not found - the NumPy gate set (identical result) draws the field:', e)
        return False


def _qk_devre(idx, th, ph):
    """Ayni alti devre, bu kez Qiskit ile."""
    QC = _QK['QC']
    qc = QC(NQ)
    if   idx == 0:   # CARPIM
        qc.ry(th,0); qc.ry(ph,1); qc.ry(th*0.7,2); qc.ry(ph*1.3,3)
    elif idx == 1:   # BELL x2
        qc.ry(th,0); qc.h(0); qc.cx(0,1); qc.ry(ph,2); qc.h(2); qc.cx(2,3)
    elif idx == 2:   # GHZ
        qc.ry(th,0); qc.h(0); qc.cx(0,1); qc.cx(1,2); qc.cx(2,3); qc.rz(ph,0)
    elif idx == 3:   # W  (Qiskit'te dogrudan hazirlanir)
        import numpy as _np
        v = _np.zeros(K, dtype=complex)
        for j in range(NQ): v[1 << j] = _np.exp(1j*ph*j)
        v = v/_np.linalg.norm(v)
        qc.initialize(v, range(NQ)); qc.rz(th,0)
    elif idx == 4:   # QFT
        qc.ry(th,0); qc.ry(ph,2)
        qc.h(0); qc.cp(np.pi/2,1,0); qc.cp(np.pi/4,2,0); qc.cp(np.pi/8,3,0)
        qc.h(1); qc.cp(np.pi/2,2,1); qc.cp(np.pi/4,3,1)
        qc.h(2); qc.cp(np.pi/2,3,2)
        qc.h(3)
    elif idx == 5:   # ZINCIR
        qc.ry(th,0); qc.ry(ph,1); qc.rz(th*1.4,2)
        qc.h(0); qc.cx(0,1); qc.cx(1,2); qc.ry(ph*0.6,3)
    else:            # DOLANIK
        qc.ry(th,0); qc.cx(0,1); qc.ry(th,2); qc.cx(2,3); qc.rz(ph,1)
    return qc


def _qk_state(idx, th, ph):
    sv = _QK['SV'].from_instruction(_qk_devre(idx, th, ph))
    return np.array(sv.data, dtype=complex)


def _qasm_state(metin):
    QC = _QK['QC']
    qc = QC.from_qasm_str(metin)
    return np.array(_QK['SV'].from_instruction(qc).data, dtype=complex)


def qiskit_dogrula():
    """numpy kapilari ile Qiskit AYNI sonucu veriyor mu? Sayiyla kanit."""
    if not _qiskit_yukle():
        print('Qiskit yok'); return
    print(' devre     en buyuk fark      ayni mi')
    for i,(ad,_,_) in enumerate(CIRCUITS):
        a = CIRCUITS[i][2](1.1, 0.7)
        b = _qk_state(i, 1.1, 0.7)
        # global faz farkini kaldir
        j = int(np.argmax(np.abs(a)))
        if abs(b[j]) > 1e-12: b = b * (a[j]/abs(a[j])) / (b[j]/abs(b[j]))
        d = float(np.max(np.abs(a-b)))
        print(' %-9s %.3e          %s' % (ad, d, 'EVET' if d < 1e-9 else 'HAYIR'))


# =============================================================================
# OLCUM VE COKUS  (Miranda'nin belgesindeki "Adim 2")
# =============================================================================
# Born kurali: |k> sonucu |alpha_k|^2 olasilikla secilir. Secildikten sonra
# durum artik bir SUPERPOZISYON degil, tek bir temel durumdur.
#
# Gorselde ne olur (bunu OLCEREK biliyoruz, tahmin degil):
#   cok genlik -> girisim var          -> desen var
#   iki genlik -> alan 1 boyutlu       -> paralel seritler
#   tek genlik -> alan TAMAMEN DUZ     -> desen YOK, yapisiz toz
# Yani cokus, deseni yavasca eritip tozu birakiyor. Ve erirken kisa bir an
# icin iki-genlikli olup SERITLERDEN geciyor; o seritlerin ACISI secilen
# sonucun kimligini tasiyor.

_MEAS = {'faz': 'yok', 'k': -1, 'p': 0.0, 't': 0.0, 'sure': 2.5,
         'pre': None, 'son_t': None}


def _simdi():
    try:
        import td
        return td.absTime.seconds
    except Exception:
        return 0.0


def olc(sure=2.5):
    """OLCUM. Born kuralina gore bir sonuc secer, cokusu baslatir."""
    import td
    par = op('qpar')
    th = par['theta'].eval(); ph = par['phi'].eval()
    try:    idx = par['circuit'].eval()
    except Exception: idx = 0

    v = state(idx, th, ph)
    p = np.abs(v)**2
    p = p / p.sum()
    k = int(np.random.choice(K, p=p))

    _MEAS.update({'faz': 'cokuyor', 'k': k, 'p': float(p[k]),
                  't': 0.0, 'sure': float(sure), 'pre': v.copy(),
                  'son_t': _simdi()})

    bits = format(k, '0%db' % NQ)
    print('[OLCUM] sonuc |%s>   olasilik %.4f   cokus %.1f s' % (bits, p[k], sure))
    td.op('/project1/Pop_glsl_sort').store('olcum_sonuc', bits)
    return bits, float(p[k])


def sifirla():
    """Olcumden once ki hale don - superpozisyon geri gelir."""
    _MEAS.update({'faz': 'yok', 'k': -1, 'p': 0.0, 't': 0.0, 'pre': None, 'son_t': None})
    print('[OLCUM] sifirlandi - superpozisyon geri geldi')


def durum():
    return dict(_MEAS)


def _cokus_uygula(v):
    """Cokus aktifse genlik vektorunu hedefe dogru tasi."""
    faz = _MEAS['faz']
    if faz == 'yok':
        return v

    hedef = np.zeros(K, dtype=complex)
    hedef[_MEAS['k']] = 1.0

    if faz == 'coktu':
        return hedef

    # gercek gecen zaman (kare hizina bagli olmasin)
    simdi = _simdi()
    onceki = _MEAS['son_t'] if _MEAS['son_t'] is not None else simdi
    dt = min(0.1, max(0.0, simdi - onceki))
    _MEAS['son_t'] = simdi
    _MEAS['t'] += dt

    u = _MEAS['t'] / max(_MEAS['sure'], 1e-6)
    if u >= 1.0:
        _MEAS['faz'] = 'coktu'
        return hedef

    # yumusak gecis (S egrisi) - ani kesme yok
    u = u*u*(3.0 - 2.0*u)
    w = (1.0 - u)*_MEAS['pre'] + u*hedef
    n = np.linalg.norm(w)
    return w/n if n > 0 else hedef


# --- TouchDesigner interface -------------------------------------------------

def onCook(scriptOp):
    par = op('qpar')
    theta = par['theta'].eval() if par else 1.1
    phi   = par['phi'].eval()   if par else 0.7
    try:
        idx = par['circuit'].eval()
    except Exception:
        idx = 0

    v = state(idx, theta, phi)
    v = _cokus_uygula(v)          # olcum aktifse genlikleri hedefe tasir

    scriptOp.clear()                       # ALWAYS - else channels duplicate
    scriptOp.numSamples = K

    cre = scriptOp.appendChan('re')
    cim = scriptOp.appendChan('im')
    for i in range(K):
        cre[i] = float(v[i].real)
        cim[i] = float(v[i].imag)
    return


# --- olcum araci: kubit basina von Neumann entropisi -------------------------
# 0 = o kubit digerlerinden bagimsiz, 1 = tamamen dolanik.
# Miranda'nin belgesi de ayni olcutu kullaniyor (partial_trace + ozdegerler).

def entropy(v, qubit=0):
    M = np.asarray(v).reshape([2]*NQ)
    M = np.moveaxis(M, NQ-1-qubit, 0).reshape(2, -1)
    rho = M @ M.conj().T
    w = np.clip(np.linalg.eigvalsh(rho).real, 1e-15, 1.0)
    return float(-np.sum(w*np.log2(w)))

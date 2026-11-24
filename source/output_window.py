# =============================================================================
# cntrl / output  -  the output window for the projector (2026-11-24, Eduardo:
# "Ctrl+9 does not go to the extended screen ... it would be good to be able to
# define the dimensions ... and tell where I want it to be displayed").
#
# CONTROL panel, OUTPUT card:
#   SCREEN   which display the window opens on (click: next display).
#            AUTO = the last display that is not the main one, else the main one.
#   SIZE     FULL SCREEN (fills the display) or a fixed size, centred on it.
#   OPEN / CLOSE   (also Ctrl + 9 / Ctrl + 0)
# The window has no border. The picture keeps its shape: if the window has
# another shape, black bars fill the rest (out_fit).
#
# NOTE: `monitors` may only be read on TouchDesigner's main thread (panel
# clicks, keys, frame callbacks). Reading it from a web/bridge thread crashes TD.
# =============================================================================
import td

CTRL = '/project1/CONTROL'
WIN = '/project1/cntrl/perform'
FIT = '/project1/cntrl/out_fit'
PREVIEW = '/project1/cntrl/preview_window'

SIZES = (('FULL SCREEN', None), ('1920 x 1080', (1920, 1080)), ('1600 x 900', (1600, 900)),
         ('1280 x 720', (1280, 720)), ('1280 x 800', (1280, 800)), ('1024 x 768', (1024, 768)),
         ('800 x 600', (800, 600)))


def _C():
    return op(CTRL)


def _mons():
    try:
        return list(td.monitors)
    except Exception:
        return []


def screen_index():
    """The chosen display's index; -1 = AUTO."""
    try:
        return int(_C().par.Outscreen.eval())
    except Exception:
        return -1


def screen():
    """The monitor the window goes to."""
    ms = _mons()
    if not ms:
        return None
    i = screen_index()
    for m in ms:
        if m.index == i:
            return m
    others = [m for m in ms if not m.isPrimary]
    return others[-1] if others else ms[0]


def screen_text():
    ms = _mons()
    m = screen()
    if m is None:
        return 'SCREEN   none found'
    auto = 'AUTO  ' if screen_index() < 0 or all(x.index != screen_index() for x in ms) else ''
    main = '  (main)' if m.isPrimary else ''
    return 'SCREEN   %s%d  %s  %d x %d%s' % (auto, m.index + 1, m.displayName, m.width, m.height, main)


def next_screen():
    """AUTO -> 1 -> 2 -> ... -> AUTO"""
    ms = sorted(m.index for m in _mons())
    cur = screen_index()
    seq = [-1] + ms
    k = seq.index(cur) if cur in seq else 0
    _C().par.Outscreen = seq[(k + 1) % len(seq)]
    if is_open() or _P.get('pending'):
        open_window()


def size_index():
    try:
        return int(_C().par.Outsize.eval()) % len(SIZES)
    except Exception:
        return 0


def size_text():
    return 'SIZE   %s' % SIZES[size_index()][0]


def next_size():
    _C().par.Outsize = (size_index() + 1) % len(SIZES)
    if is_open() or _P.get('pending'):
        open_window()


def window_pixels():
    """(w, h) of the window on the chosen screen."""
    s = SIZES[size_index()][1]
    if s is not None:
        return s
    m = screen()
    if m is None:
        return (1920, 1080)
    return (int(m.width), int(m.height))


def is_open():
    try:
        return bool(op(WIN).isOpen) or bool(_P.get('pending'))
    except Exception:
        return False


def open_window():
    w = op(WIN)
    m = screen()
    pw, ph = window_pixels()
    f = op(FIT)
    if f is not None:
        f.par.resolutionw, f.par.resolutionh = pw, ph
        w.par.winop = f.path
    w.par.borders = False
    w.par.justifyoffsetto = 'specifydisplay'
    w.par.display = m.index if m is not None else 0
    w.par.justifyh = 'center'
    w.par.justifyv = 'center'
    w.par.winoffsetx = 0
    w.par.winoffsety = 0
    w.par.dpiscaling = 'native'
    if SIZES[size_index()][1] is None:
        w.par.size = 'fill'
    else:
        w.par.size = 'custom'
        w.par.winw, w.par.winh = pw, ph
    if w.isOpen:
        # close, then open again a few frames later WITH THE SETTINGS OF THAT
        # MOMENT (several quick clicks must end with the last choice)
        w.par.winclose.pulse()
        _P['pending'] = True
        run("op('/project1/cntrl/output').module._reopen()", delayFrames=3)
    else:
        w.par.winopen.pulse()


_P = {}


def _reopen():
    _P.pop('pending', None)
    if not op(WIN).isOpen:
        open_window()


def close_window():
    _P.pop('pending', None)
    op(WIN).par.winclose.pulse()


def status_text():
    if not is_open():
        return 'window closed   -   OPEN or Ctrl + 9'
    m = screen()
    pw, ph = window_pixels()
    where = ('%d  %s' % (m.index + 1, m.displayName)) if m is not None else '?'
    return 'OPEN on screen %s   %d x %d   no border   (CLOSE or Ctrl + 0)' % (where, pw, ph)


# -- the preview window (on the main screen, with a border) --------------------
# TouchDesigner keeps a window's shape equal to the picture's shape while it is
# dragged (tested 2026-11-24: a TOP or a panel inside, same result). So the
# preview takes the picture's shape, and Ctrl+3 switches NORMAL <-> LARGE
# (LARGE = as big as the main screen allows).
_PV = {'large': False}


def preview_fit(large=None):
    """Give the preview window the picture's shape (NORMAL or LARGE)."""
    if large is not None:
        _PV['large'] = bool(large)
    w = op(PREVIEW)
    a = op('/project1/cntrl/image_format').module.aspect()
    ms = _mons()
    main = [m for m in ms if m.isPrimary]
    if main:
        s = max(main[0].dpiScale, 1.0)
        sw, sh = main[0].width / s, main[0].height / s
    else:
        sw, sh = 1440, 900
    if _PV['large']:
        maxw, maxh = sw - 40, sh - 90
    else:
        maxw, maxh = min(960, sw * 0.6), min(800, sh - 140)
    pw = maxw
    ph = pw / a
    if ph > maxh:
        ph = maxh
        pw = ph * a
    w.par.winw, w.par.winh = int(pw), int(ph)
    if _PV['large']:
        w.par.justifyh, w.par.justifyv = 'center', 'center'
        w.par.winoffsetx, w.par.winoffsety = 0, 0
    else:
        w.par.justifyh, w.par.justifyv = 'right', 'top'
        w.par.winoffsetx, w.par.winoffsety = -20, -40


def preview_toggle():
    """Ctrl+3: open the preview; pressed again: NORMAL <-> LARGE."""
    w = op(PREVIEW)
    if w.isOpen:
        preview_fit(not _PV['large'])
        w.par.winclose.pulse()
        run("op(%r).par.winopen.pulse()" % PREVIEW, delayFrames=3)
    else:
        preview_fit(False)
        w.par.winopen.pulse()

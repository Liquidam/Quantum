# =============================================================================
# CONTROL / actions  -  everything the CONTROL panel does.
#
# Settings live in the widgets themselves:
#   agents, t_shortest, t_longest, t_fixed   knobs     par.Value
#   form                                    A/B bar   par.Value  (ajan_par.form follows it)
#   CONTROL.par.Timemode                    1 = random range, 2 = fixed time
# The stage manager (/project1/Pop_glsl_sort/STAGE_KUME) reads settings() at the
# start of every round.
#
# Called by:
#   mouse  (Panel Execute DAT)  clicks, drags, mouse wheel on the panel
#   tick   (Execute DAT)        every frame: A->B ramp + status display
#   midi   (CONTROL/midi)       MIDI LEARN: a mapped controller calls start/stop/
#                               reset, _knob_set and the A/B bar like the mouse does
# =============================================================================
import time

POP     = '/project1/Pop_glsl_sort'
STAGE   = POP + '/STAGE_KUME'
LOG     = POP + '/kume_log'
CURTAIN = POP + '/feedback1'

RAMP_S     = 10.0     # START from A: territory -> body takes this long
KNOB_DRAG  = 1.6      # a full-height drag moves a knob this many times its range

_R = {}               # running A->B ramp: t0, from
_DRAG = {}            # knob path -> (v at press, value at press)


def _C():
    return parent()


def _w(name):
    return parent().op(name)


def _stage():
    return op(STAGE).module


def _midi():
    return parent().op('midi').module


# -- read by the stage manager ---------------------------------------------------
def settings():
    return dict(agents=int(round(_w('agents').par.Value.eval())),
                auto=int(_C().par.Runmode.eval()) == 1,
                mode=int(_C().par.Timemode.eval()),
                tmin=float(_w('t_shortest').par.Value.eval()),
                tmax=float(_w('t_longest').par.Value.eval()),
                tfix=float(_w('t_fixed').par.Value.eval()))


# -- buttons ---------------------------------------------------------------------
def start():
    """1 START / LISTENING. From A the board first becomes bodies (10 s),
    then LISTENING begins. From B: LISTENING now (a winner still on stage
    goes home first)."""
    form = float(_w('form').par.Value.eval())
    if form < 0.99:
        _R['t0'] = time.time()
        _R['from'] = form
    else:
        _stage().git('DINLEME')


# stage buttons 2..5 (1 is START). They work in AUTO and in MANUAL.
STAGE_BUTTONS = {'btn_super': 'SUPER', 'btn_collapse': 'COKUS',
                 'btn_answer': 'CEVAP', 'btn_return': 'DONUS'}


def stage(name):
    if _R:                          # START's A->B ramp keeps going, but it will
        _R['no_listen'] = True      # not start LISTENING at its end any more
    _stage().git(name)


def set_run(m):
    """1 AUTO (rounds loop by themselves), 2 MANUAL (every stage by hand)."""
    _C().par.Runmode = m


def stop():
    """STOP. Whatever is happening relaxes home, then the stage idles."""
    _R.clear()
    _stage().bitir()


def reset():
    """RESET. Stop, back to A (territory), clear the curtain's memory.
    The curtain is the feedback loop that builds the image: after a reset the
    look needs a while to grow back."""
    _R.clear()
    _stage().bitir()
    _w('form').par.Value = 0.0
    op(CURTAIN).par.resetpulse.pulse()


# -- knobs --------------------------------------------------------------------------
def _knob_set(k, value):
    lo, hi = k.par.Lo.eval(), k.par.Hi.eval()
    value = max(lo, min(hi, value))
    if k.par.Integer.eval():
        value = round(value)
    if value != k.par.Value.eval():
        k.par.Value = value
        _knob_changed(k)


def _knob_changed(k):
    if k.name == 'agents':
        # now while idle, listening or returning; during the draw, collapse
        # and answer it waits for RETURN (the winner must stay on stage)
        _stage().n_degisti()


# -- mouse ------------------------------------------------------------------------------
def mouse(event, pv, prev):
    o = pv.owner
    n = o.name
    md = _midi()
    # MIDI card
    if event == 'press' and pv.name == 'lselect':
        if n == 'btn_guide':                # the HOW TO window
            op('/project1/cntrl/shortcuts').module.guide_open()
            return
        if n == 'midi_device':
            md.next_device()
            return
        if n == 'btn_learn':
            md.toggle_learn()
            return
        if n == 'btn_forget':
            md.forget()
            return
        if n == 'out_device':               # MIDI OUT: the winner's number
            md.next_out_device()
            return
        if n in ('out_cc', 'out_ch'):       # right half +1, left half -1
            md.nudge_out(n, 1 if o.panel.u.val >= 0.5 else -1)
            return
        # OUTPUT card: image shape + the projector window
        if n == 'out_format':
            op('/project1/cntrl/image_format').module.next_format()
            return
        if n == 'out_res':
            op('/project1/cntrl/image_format').module.next_res()
            return
        if n == 'out_screen':
            op('/project1/cntrl/output').module.next_screen()
            return
        if n == 'out_size':
            op('/project1/cntrl/output').module.next_size()
            return
        if n == 'btn_win_open':
            op('/project1/cntrl/output').module.open_window()
            return
        if n == 'btn_win_close':
            op('/project1/cntrl/output').module.close_window()
            return
        if md.learning():                   # LEARN: a click selects, never triggers
            target = o.parent().name if n == 'dial' else n
            if target in md.BUTTONS + md.KNOBS + md.BARS:
                md.arm(target)
            return
    if md.learning():
        return
    # buttons and radio: act on press
    if event == 'press' and pv.name == 'lselect':
        if n == 'btn_start':
            start()
        elif n == 'btn_stop':
            stop()
        elif n == 'btn_reset':
            reset()
        elif n in STAGE_BUTTONS:
            stage(STAGE_BUTTONS[n])
        elif n == 'run1':
            set_run(1)
        elif n == 'run2':
            set_run(2)
        elif n == 'mode1':
            _C().par.Timemode = 1
        elif n == 'mode2':
            _C().par.Timemode = 2
        elif n == 'dial':
            k = o.parent()
            _DRAG[k.path] = (o.panel.v.val, k.par.Value.eval())
        elif n == 'form':
            _R.clear()                      # a hand on the bar cancels a ramp
            o.par.Value = o.panel.u.val
        return
    if event == 'release' and pv.name == 'lselect':
        if n == 'dial':
            _DRAG.pop(o.parent().path, None)
        return
    if event != 'change':
        return
    if n in ('out_cc', 'out_ch') and pv.name == 'wheel' and pv.val != 0:
        md.nudge_out(n, 1 if pv.val > 0 else -1)
        return
    if n == 'dial':
        k = o.parent()
        if pv.name == 'v' and k.path in _DRAG:
            v0, val0 = _DRAG[k.path]
            rng = k.par.Hi.eval() - k.par.Lo.eval()
            _knob_set(k, val0 + (pv.val - v0) * rng * KNOB_DRAG)
        elif pv.name == 'wheel' and pv.val != 0:
            step = 1.0 if k.par.Integer.eval() else 0.5
            _knob_set(k, k.par.Value.eval() + (step if pv.val > 0 else -step))
    elif n == 'form' and pv.name == 'u' and o.panel.lselect.val:
        o.par.Value = max(0.0, min(1.0, pv.val))


# -- every frame -----------------------------------------------------------------------
_BOOT = {}            # once per session: pick the MIDI device if the saved one is absent


def tick(frame):
    if not _BOOT and parent().op('midi') is not None:
        _BOOT['done'] = True
        _midi().auto_device()
        _midi().auto_out_device()
    if _R:
        u = (time.time() - _R['t0']) / RAMP_S
        f = _R['from'] + (1.0 - _R['from']) * min(1.0, u)
        _w('form').par.Value = f
        if u >= 1.0:
            listen = not _R.get('no_listen')
            _R.clear()
            if listen:
                _stage().git('DINLEME')
    if frame % 4 == 0:
        _show()


def _show():
    s = _stage().bilgi()
    if _R:
        left = max(0.0, RAMP_S - (time.time() - _R['t0']))
        phase, frac = 'A  ->  B     becoming bodies', 1.0 - left / RAMP_S
        line = 'round 1 starts in %.0f s' % left
    else:
        phase, frac = s['ad'], s['frac']
        if s['faz'] == 'BEKLE':
            line = 'press  1  START'
        elif s['durduruluyor']:
            line = 'stopping  -  everyone goes home'
        elif s['sonra']:
            line = 'going home first, then  %s' % s['sonra']
        elif s['oto']:
            line = 'AUTO     round %d     %d agents     %.1f s     next phase in %.0f s' % (
                s['tur'], s['n'], s['sure'], s['kalan'])
        elif s['tutuyor']:
            line = 'MANUAL     round %d     %d agents     holding  -  next:  %s' % (
                s['tur'], s['n'], s['sonraki'])
        else:
            line = 'MANUAL     round %d     %d agents     moving  (%.0f s)  -  next:  %s' % (
                s['tur'], s['n'], s['kalan'], s['sonraki'])
    _w('st_phase').par.text = phase
    _w('st_progress').par.Value = frac
    _w('st_line').par.text = line
    k = s['kazanan']
    _w('st_winner').par.text = ('WINNER    AGENT  %d' % (k + 1)) if k >= 0 else _last_winner()
    rows = _winners_rows()
    for i in range(8):
        _w('win%d' % i).par.text = rows[i] if i < len(rows) else ''
    if parent().op('midi') is not None:
        _midi().show()
    if parent().op('out_format') is not None and frame_ok():
        _show_output()


_SO = {'n': 0}


def frame_ok():
    # the OUTPUT card changes rarely: refresh it every 16th display update
    _SO['n'] += 1
    return _SO['n'] % 4 == 1


def _show_output():
    fm = op('/project1/cntrl/image_format').module
    om = op('/project1/cntrl/output').module
    (rw, rh), _, _ = fm.sizes()
    _w('out_format').par.text = 'IMAGE   %s' % fm.name()
    if _w('out_res') is not None:
        _w('out_res').par.text = 'RESOLUTION   %s   %d x %d' % (
            fm.RESOLUTIONS[fm.res_index()][0].split()[0], rw, rh)
    _w('out_screen').par.text = om.screen_text()
    _w('out_size').par.text = om.size_text()
    _w('out_win_status').par.text = om.status_text()


def _last_winner():
    t = op(LOG)
    if t.numRows > 1:
        return 'last winner    AGENT  %d' % (int(t[t.numRows - 1, 'kazanan'].val) + 1)
    return '-'


def _winners_rows(n=8):
    t = op(LOG)
    rows = []
    for r in range(max(1, t.numRows - n), t.numRows)[::-1]:
        # agents are shown 1..20 (the number MIDI OUT sends); the log keeps slots 0..19
        rows.append('round %-4s %s   %2s agents  %5.1f s    AGENT %d' % (
            t[r, 'tur'].val, t[r, 'saat'].val, t[r, 'ajan_sayisi'].val,
            float(t[r, 'sure_sn'].val), int(t[r, 'kazanan'].val) + 1))
    return rows or ['no rounds yet']


def clear_winners():
    t = op(LOG)
    t.setSize(1, t.numCols)

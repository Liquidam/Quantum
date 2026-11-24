# =============================================================================
# CONTROL / midi  -  map any panel control to a MIDI controller (MIDI LEARN)
#
# HOW TO MAP (on the panel, MIDI card):
#   1. DEVICE   click until your controller's name shows (plug it in BEFORE
#               opening TouchDesigner - the list is read at start).
#   2. LEARN    turns learn mode on (button lights up).
#   3. Click a control on the panel: START, STOP, RESET, 1 RANDOM RANGE,
#      2 FIXED TIME, the AGENTS / shortest / longest / fixed knobs, or the
#      A <-> B bar. In learn mode a click does NOT trigger it, it only selects.
#   4. Press a pad / button or move a knob / fader on the controller.
#      The panel shows the binding next to the control (e.g. "cc 21").
#   5. Repeat 3-4 for the next control. LEARN again to finish.
#   FORGET (in learn mode) removes the binding of the selected control.
#
# WHAT A BINDING DOES
#   buttons (START STOP RESET, time modes):  note on, or CC crossing 64 upward
#   knobs and the A/B bar:  CC 0..127 -> the control's full range
#   One physical control drives one panel control (re-learning moves it).
#
# Bindings live in the table `midi_map` (saved with the .toe).
# Messages arrive through `midi_in` (MIDI In DAT, device ID 1 in /local/midi/device).
#
# MIDI OUT - the winner's number (requested by Eduardo, 2026-11-17)
#   Every time the qubits draw a winner, the agent's number 1..20 is sent as a
#   Control Change to the chosen output (e.g. the macOS IAC Driver -> Max/MSP).
#   OUT       click to choose the output device (or OFF)
#   CC  CH    click the right half for +1, the left half for -1 (or mouse wheel)
#   Sent by `midi_out` (MIDI Out CHOP, device ID 2 in /local/midi/device).
#   CC number and channel are the CONTROL parameters Outcc / Outch.
# =============================================================================

MAP = 'midi_map'
INPUTS = '/local/midi/midi_inputs'
DEVICES = '/local/midi/device'

BUTTONS = ('btn_start', 'btn_super', 'btn_collapse', 'btn_answer', 'btn_return',
           'btn_stop', 'btn_reset', 'run1', 'run2', 'mode1', 'mode2')
KNOBS = ('agents', 't_shortest', 't_longest', 't_fixed')
BARS = ('form',)
LABEL = {'btn_start': '1 START / LISTENING', 'btn_super': '2 SUPERPOSITION',
         'btn_collapse': '3 COLLAPSE', 'btn_answer': '4 ANSWER', 'btn_return': '5 RETURN',
         'run1': 'AUTO', 'run2': 'MANUAL',
         'btn_stop': 'STOP', 'btn_reset': 'RESET',
         'mode1': 'TIME MODE 1', 'mode2': 'TIME MODE 2', 'agents': 'AGENTS',
         't_shortest': 'SHORTEST', 't_longest': 'LONGEST', 't_fixed': 'FIXED',
         'form': 'A <-> B'}

_S = {'learn': False, 'armed': '', 'last': '', 'msg': ''}
_CC_LAST = {}          # (channel, index) -> last CC value (button edge detection)


def _C():
    return parent()


def _act():
    return _C().op('actions').module


# -- table ------------------------------------------------------------------------
def _table():
    t = _C().op(MAP)
    if t.numRows == 0 or t[0, 0].val != 'control':
        t.clear()
        t.appendRow(['control', 'type', 'channel', 'index'])
    return t


def bindings():
    t = _table()
    return [(t[r, 'control'].val, t[r, 'type'].val, int(t[r, 'channel'].val), int(t[r, 'index'].val))
            for r in range(1, t.numRows)]


def binding_text(control):
    for c, ty, ch, ix in bindings():
        if c == control:
            # TD counts from 1; controllers print CC / note numbers from 0
            return ('%s %d' % ('cc' if ty == 'cc' else 'note', ix - 1)) + ('' if ch == 1 else ' ch%d' % ch)
    return ''


def _bind(control, ty, ch, ix):
    t = _table()
    for r in range(t.numRows - 1, 0, -1):
        same_src = (t[r, 'type'].val == ty and int(t[r, 'channel'].val) == ch and int(t[r, 'index'].val) == ix)
        if t[r, 'control'].val == control or same_src:
            t.deleteRow(r)
    t.appendRow([control, ty, ch, ix])


def forget():
    c = _S['armed']
    if not c:
        _S['msg'] = 'FORGET: first click the control to forget (in LEARN)'
        return
    t = _table()
    for r in range(t.numRows - 1, 0, -1):
        if t[r, 'control'].val == c:
            t.deleteRow(r)
    _S['msg'] = '%s: binding removed' % LABEL.get(c, c)
    _S['armed'] = ''


# -- learn ------------------------------------------------------------------------------
def learning():
    return _S['learn']


def toggle_learn():
    _S['learn'] = not _S['learn']
    _S['armed'] = ''
    _S['msg'] = ('LEARN: click a control on the panel' if _S['learn'] else '')


def arm(control):
    """Called by actions.mouse while learning: select, do not trigger."""
    _S['armed'] = control
    _S['msg'] = '%s: now press or move a control on the MIDI device' % LABEL.get(control, control)


# -- device --------------------------------------------------------------------------------
def inputs():
    t = op(INPUTS)
    return [t[r, 0].val for r in range(t.numRows) if t[r, 0].val.strip()] if t else []


def device():
    t = op(DEVICES)
    for r in range(1, t.numRows):
        if t[r, 'id'].val == '1':
            return t[r, 'indevice'].val
    return ''


def set_device(name):
    t = op(DEVICES)
    if t.numRows == 0:
        t.appendRow(['id', 'indevice', 'outdevice', 'definition', 'channel'])
    for r in range(t.numRows - 1, 0, -1):
        if t[r, 'id'].val == '1':
            t.deleteRow(r)
    if name:
        t.appendRow(['1', name, '', '', '1'])
    m = _C().op('midi_in')            # re-open the port
    m.par.active = False
    run("op('%s').par.active = True" % m.path, delayFrames=2)


def next_device():
    ins = inputs()
    if not ins:
        _S['msg'] = 'no MIDI input found - plug it in, then restart TouchDesigner'
        return
    cur = device()
    i = ins.index(cur) + 1 if cur in ins else 0
    set_device(ins[i % len(ins)])
    _S['msg'] = 'device: %s' % device()


def auto_device():
    """At start: keep the chosen device if present, else take the first input,
    else clear it (a remembered device that is not plugged in is not shown)."""
    ins = inputs()
    if device() in ins:
        return
    set_device(ins[0] if ins else '')


# -- incoming --------------------------------------------------------------------------------
def receive(event):
    m = event.message
    ch, ix, val = int(event.channel), int(event.index), int(event.value)
    if m == 'Control Change':
        ty = 'cc'
    elif m in ('Note On', 'Note Off'):
        ty = 'note'
        if m == 'Note Off':
            val = 0
    else:
        return
    _S['last'] = '%s %d%s = %d' % ('cc' if ty == 'cc' else 'note', ix - 1, '' if ch == 1 else ' ch%d' % ch, val)
    prev = _CC_LAST.get((ch, ix), 0)       # CC history is kept in every mode,
    if ty == 'cc':                         # so a button never sticks "held"
        _CC_LAST[(ch, ix)] = val

    if _S['learn']:
        c = _S['armed']
        if c and val > 0:
            if (c in KNOBS or c in BARS) and ty != 'cc':
                _S['msg'] = '%s needs a knob or fader (CC), not a pad' % LABEL[c]
                return
            _bind(c, ty, ch, ix)
            _S['msg'] = '%s = %s   -   click the next control, or LEARN to finish' % (LABEL[c], binding_text(c))
            _S['armed'] = ''
        return

    for c, bty, bch, bix in bindings():
        if bty != ty or bch != ch or bix != ix:
            continue
        if c in BUTTONS:
            if ty == 'note':
                fire = val > 0
            else:
                fire = prev < 64 <= val
            if fire:
                _press(c)
        elif c in KNOBS:
            k = _C().op(c)
            lo, hi = k.par.Lo.eval(), k.par.Hi.eval()
            _act()._knob_set(k, lo + (hi - lo) * val / 127.0)
        elif c in BARS:
            _act()._R.clear()                # a hand on the bar cancels a ramp
            _C().op(c).par.Value = val / 127.0


def _press(c):
    a = _act()
    if c == 'btn_start':
        a.start()
    elif c == 'btn_stop':
        a.stop()
    elif c == 'btn_reset':
        a.reset()
    elif c in a.STAGE_BUTTONS:
        a.stage(a.STAGE_BUTTONS[c])
    elif c == 'run1':
        a.set_run(1)
    elif c == 'run2':
        a.set_run(2)
    elif c == 'mode1':
        _C().par.Timemode = 1
    elif c == 'mode2':
        _C().par.Timemode = 2


# -- display (called from actions._show) ------------------------------------------------------
def show():
    C = _C()
    dev = device()
    if dev and dev in inputs():
        C.op('midi_device').par.text = 'DEVICE   %s' % dev
    elif inputs():
        C.op('midi_device').par.text = 'DEVICE   -  click to choose'
    else:
        C.op('midi_device').par.text = 'DEVICE   none connected'
    if _S['msg']:
        line = _S['msg']
    else:
        n = len(bindings())
        line = ('%d controls mapped' % n) if n else 'nothing mapped yet - press LEARN'
        if _S['last']:
            line += '        last in:  %s' % _S['last']
    C.op('midi_status').par.text = line
    for c in BUTTONS + KNOBS + BARS:
        t = C.op('tag_' + c)
        if t is None:
            continue
        if _S['learn'] and _S['armed'] == c:
            t.par.text = '> MIDI ?'
        else:
            t.par.text = binding_text(c) or ('-' if _S['learn'] else '')
    if C.op('out_device') is not None:
        show_out()


# -- MIDI OUT: the winner's number ------------------------------------------------------------
OUT_ID = '2'
OUTPUTS = '/local/midi/midi_outputs'
_OUT = {'last': ''}


def outputs():
    t = op(OUTPUTS)
    return [t[r, 0].val for r in range(t.numRows) if t[r, 0].val.strip()] if t else []


def out_device():
    t = op(DEVICES)
    for r in range(1, t.numRows):
        if t[r, 'id'].val == OUT_ID:
            return t[r, 'outdevice'].val
    return ''


def set_out_device(name):
    t = op(DEVICES)
    if t.numRows == 0:
        t.appendRow(['id', 'indevice', 'outdevice', 'definition', 'channel'])
    for r in range(t.numRows - 1, 0, -1):
        if t[r, 'id'].val == OUT_ID:
            t.deleteRow(r)
    if name:
        t.appendRow([OUT_ID, '', name, '', '1'])
    m = _C().op('midi_out')            # re-open the port
    if m is not None:
        m.par.active = False
        run("op('%s').par.active = True" % m.path, delayFrames=2)


def next_out_device():
    """Click on OUT: OFF -> first output -> next ... -> OFF."""
    outs = outputs()
    if not outs:
        _S['msg'] = 'no MIDI output found - on a Mac switch on the IAC Driver, then restart TouchDesigner'
        return
    cycle = [''] + outs
    cur = out_device()
    i = cycle.index(cur) + 1 if cur in cycle else 1
    set_out_device(cycle[i % len(cycle)])
    _S['msg'] = ('MIDI OUT: %s' % out_device()) if out_device() else 'MIDI OUT: off'


def auto_out_device():
    """At start: a remembered output that is not present is cleared (no guessing)."""
    if out_device() and out_device() not in outputs():
        set_out_device('')


def out_cc():
    return int(_C().par.Outcc.eval())


def out_ch():
    return int(_C().par.Outch.eval())


def nudge_out(which, d):
    C = _C()
    if which == 'out_cc':
        C.par.Outcc = max(0, min(127, out_cc() + d))
    elif which == 'out_ch':
        C.par.Outch = max(1, min(16, out_ch() + d))


def send_winner(k):
    """Called by the stage manager when the qubits have drawn agent k (0-based).
    Sends k + 1 (agents are numbered 1..20) as CC Outcc on channel Outch."""
    n = int(k) + 1
    dev = out_device()
    if not dev or dev not in outputs():
        _OUT['last'] = 'AGENT %d  (not sent: no MIDI OUT device)' % n
        return False
    m = _C().op('midi_out')
    # TD counts controllers from 1 (CC 0 is index 1) and takes the value as 0..1
    # (x 127 on the wire), so n / 127 arrives as exactly n.
    m.sendControl(out_ch(), out_cc() + 1, n / 127.0)
    _OUT['last'] = 'AGENT %d  sent as CC %d = %d' % (n, out_cc(), n)
    print('[MIDI OUT] %s  ch %d  ->  %s' % (_OUT['last'], out_ch(), dev))
    return True


def show_out():
    C = _C()
    dev = out_device()
    if dev and dev in outputs():
        C.op('out_device').par.text = 'OUT   %s' % dev
    elif outputs():
        C.op('out_device').par.text = 'OUT   off  -  click to choose'
    else:
        C.op('out_device').par.text = 'OUT   no MIDI output found'
    C.op('out_cc').par.text = '-      CC %d      +' % out_cc()
    C.op('out_ch').par.text = '-      CH %d      +' % out_ch()
    line = 'at every answer the winning agent 1-20 is sent as CC %d, channel %d' % (out_cc(), out_ch())
    if _OUT['last']:
        line = 'last:  %s' % _OUT['last']
    C.op('out_status').par.text = line

# =============================================================================
# cntrl / shortcuts  -  keyboard shortcuts, Ctrl + key  (keys CHOP)
#
#   Ctrl + 1   open the CONTROL panel (it also opens by itself when the file opens)
#   Ctrl + 2   open the HOW TO window (also opens with the file)
#   Ctrl + 3   open the FINAL IMAGE preview window (also opens with the file)
#   Ctrl + `   particle REBIRTH (feedback2 start pulse). Takes minutes to look
#              right again - never during a show.
#   Ctrl + 7   still image   -> OUT_<project>/<project>.N.jpg   (moviefileout2)
#   Ctrl + 8   video on/off  -> OUT_<project>/V_<project>.N.mov (moviefileout1)
#   Ctrl + 9   open the output window  (perform, 1080 x 1350) on the SECOND screen;
#              with only one screen it opens on that one
#   Ctrl + 0   close the output window
#
# Recording state lives in `signals` (video = 1 while recording, shot = one
# frame pulse). The panel /project1/CONTROL can call the same functions.
# =============================================================================

def rebirth():
    op('/project1/Pop_glsl_sort/feedback2').par.startpulse.pulse()

def still():
    s = op('signals')
    s.par.const1value = 1
    run("op('/project1/cntrl/signals').par.const1value = 0", delayFrames=2)

def video_toggle():
    s = op('signals')
    s.par.const0value = 0 if s.par.const0value.eval() > 0.5 else 1

def panel_open():
    op('/project1/CONTROL').openViewer(unique=True, borders=True)
    op('/project1/cntrl').store('panel_opened_frame', absTime.frame)

def guide_open():
    op('guide_window').par.winopen.pulse()

def preview_open():
    # 4:5 like the final image, as tall as this screen allows (max 800)
    m = monitors[0] if len(monitors) else None
    h = 800 if m is None else int(max(400, min(800, m.height - 140)))
    w = op('preview_window')
    w.par.winw, w.par.winh = int(h * 0.8), h
    w.par.winoffsetx, w.par.winoffsety = -20, -40
    w.par.winopen.pulse()

def window_open():
    w = op('perform')
    if len(monitors) > 1:              # projector / second screen: as set up
        w.par.display = 1
        w.par.winoffsetx = 514
    else:                              # one screen only
        w.par.display = 0
        w.par.winoffsetx = 0
    w.par.winopen.pulse()

def window_close():
    op('perform').par.winclose.pulse()

ACTIONS = {'1': panel_open, '2': guide_open, '3': preview_open, '`': rebirth, '7': still, '8': video_toggle, '9': window_open, '0': window_close}

def onOffToOn(channel, sampleIndex, val, prev):
    key = channel.owner.par.keys.eval().split()[channel.index]
    f = ACTIONS.get(key)
    if f:
        f()
    return

# =============================================================================
# cntrl / image_format  -  the shape of the final image (2026-11-24, Eduardo:
# "the image should be landscape, not portrait").
#
# One choice on the CONTROL panel (OUTPUT card, IMAGE): 16:9, 16:10, 4:3,
# SCREEN (the shape of the chosen output screen) or 4:5 (the old portrait).
#
# Changing the shape keeps the LOOK: the same number of rendered pixels
# (2160 x 2700 worth) and the same world AREA (so the same particle density,
# the same agent sizes and the same pixels per world unit). Only the shape of
# the box changes. Everything that depends on it is set here:
#   constant10        nominal image size (render1 = 2 x this, via math8 -> RES)
#   world_box         half-size of the world (hx, hy) - agent centres read it
#   glsl1 u_world     the particles' box          alan_top u_box
#   cam1.tz           camera distance: the visible area = the box exactly
#   ajan_* TOPs       agent mask chain, same pixel count as before (1024 x 1280)
# =============================================================================
import math

P = '/project1/Pop_glsl_sort'
CTRL = '/project1/CONTROL'

FORMATS = (('16:9', 16.0 / 9.0), ('16:10', 1.6), ('4:3', 4.0 / 3.0),
           ('SCREEN', None), ('4:5  portrait', 0.8))
DEFAULT = 0

RENDER_PIX = 2160 * 2700           # pixels rendered (before 2026-11-24: 2160 x 2700)
MASK_PIX = 1024 * 1280             # the agent-mask chain
HALF_AREA = 51.8 * 62.59           # world half-width x half-height (the old box)
MASKS = ('ajan_fb', 'ajan_lvl', 'ajan_out', 'ajan_blur', 'ajan_comp', 'ajan_cross')


# RESOLUTION (2026-11-24, user: "put a resolution setting on the panel, just in
# case"): AUTO keeps the detail of before (2160 x 2700 worth of pixels); the
# others fix the picture's HEIGHT (width follows the shape). Lower = lighter
# for the graphics card; the texture gets coarser with it (fewer pixels per
# world unit).
RESOLUTIONS = (('AUTO', None), ('2160  (4K)', 2160), ('1440', 1440), ('1080  (HD)', 1080), ('720', 720))


def res_index():
    try:
        return int(op(CTRL).par.Imageres.eval()) % len(RESOLUTIONS)
    except Exception:
        return 0


def next_res():
    op(CTRL).par.Imageres = (res_index() + 1) % len(RESOLUTIONS)
    return apply()


def index():
    try:
        return int(op(CTRL).par.Imageformat.eval()) % len(FORMATS)
    except Exception:
        return DEFAULT


def name():
    n, a = FORMATS[index()]
    if a is None:
        return 'SCREEN  %s' % _fmt(aspect())
    return n


def _fmt(a):
    for n, v in FORMATS:
        if v is not None and abs(v - a) < 0.01:
            return '(' + n.split()[0] + ')'
    return '(%.2f : 1)' % a


def aspect():
    n, a = FORMATS[index()]
    if a is not None:
        return a
    try:
        m = op('/project1/cntrl/output').module.screen()
        if m is not None and m.height > 0:
            return float(m.width) / float(m.height)
    except Exception:
        pass
    return 16.0 / 9.0


def sizes(a=None):
    """render (w, h), mask (w, h), world half-size (hx, hy) for aspect a"""
    a = aspect() if a is None else a
    fixed = RESOLUTIONS[res_index()][1]
    if fixed is None:
        rh = int(round(math.sqrt(RENDER_PIX / a) / 4.0)) * 4
    else:
        rh = int(fixed)
    rw = int(round(rh * a / 4.0)) * 4
    mh = int(round(math.sqrt(MASK_PIX / a) / 2.0)) * 2
    mw = int(round(mh * a / 2.0)) * 2
    hy = math.sqrt(HALF_AREA / a)
    hx = hy * a
    return (rw, rh), (mw, mh), (hx, hy)


def apply():
    """Set the whole chain to the chosen shape. Safe to call any time."""
    (rw, rh), (mw, mh), (hx, hy) = sizes()
    p = op(P)
    c = p.op('constant10')                      # x 2 in math8 -> RES -> render1
    c.par.const0value = rw // 2
    c.par.const1value = rh // 2
    wb = p.op('world_box')
    wb.par.const0value = hx
    wb.par.const1value = hy
    g = p.op('glsl1')
    g.par.vec9valuex.expr = ''
    g.par.vec9valuey.expr = ''
    g.par.vec9valuex = hx
    g.par.vec9valuey = hy
    at = p.op('alan_top')
    at.par.vec6valuex = hx
    at.par.vec6valuey = hy
    cam = p.op('cam1')
    cam.par.tz = hx / math.tan(math.radians(cam.par.fov.eval() / 2.0))
    for n in MASKS:
        t = p.op(n)
        if t is not None:
            t.par.resolutionw = mw
            t.par.resolutionh = mh
    # the preview window takes the new shape (on the main thread: it reads monitors)
    run("op('/project1/cntrl/output').module.preview_fit()", delayFrames=1)
    return dict(render=(rw, rh), mask=(mw, mh), world=(round(hx, 2), round(hy, 2)),
                tz=round(cam.par.tz.eval(), 3))


def next_format():
    C = op(CTRL)
    C.par.Imageformat = (index() + 1) % len(FORMATS)
    return apply()

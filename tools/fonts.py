"""herdr-fold Mono, both clients' monospace font, from JetBrainsMono Nerd Font: renamed (the OFL asks it of a Modified
Version), its lines 10% taller, split above and below, and the symbols the terminals' programs print drawn from its own
glyphs. A developer's tool (CONTRIBUTING.md); the fonts are committed. python3 tools/fonts.py [--source …] [--check]"""
import argparse
import hashlib
import io
import math
import os
import sys
import tarfile
import urllib.request

try:
    from fontTools.misc.timeTools import timestampFromString
    from fontTools.misc.transform import Transform
    from fontTools.pens.areaPen import AreaPen
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
    from fontTools.pens.reverseContourPen import ReverseContourPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._g_l_y_f import flagOverlapSimple
except ImportError:
    sys.exit("tools/fonts.py needs fontTools: python3 -m pip install --user fonttools (CONTRIBUTING.md)")

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PACKAGE, "app", "mods", "herdr-fold", "fonts")
FAMILY, POSTSCRIPT, FILE = "herdr-fold Mono", "herdrfoldMono", "herdr-fold-Mono-{}.ttf"
VERSION = "1.000"
BUILT = "Fri Nov 13 00:00:00 2026"                 # head.modified, fixed: the same sources build the same bytes
NERD_FONTS = "3.5.1"
ARCHIVE = f"https://github.com/ryanoasis/nerd-fonts/releases/download/v{NERD_FONTS}/JetBrainsMono.tar.xz"
ARCHIVE_SHA256 = "04d5e8f903693f9dd13e16f867e994834e681eb3c72c0d337a770dcda09010cf"
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "herdr-fold", "fonts")
# every file the build reads, the release's own, by its SHA-256
SOURCES = {
    "Regular": "1c680e8cde9fcf8b88a5605ce8d1fb94dd3fb15841f7ca7bf4c55664855e5611",
    "Bold": "e490660ad75e0b152c93b1604c2ea1a4ea675f1b8a3fe0d005b1998568f99f1f",
    "Italic": "71d5466cc3ab31bee38b4e2c5cc99c2b41a749c4973ed4579b814ec992b0738e",
    "BoldItalic": "19a2e3af8ccf99954941ea07e0a29df27574500f12016d86d6c4c059b825ffe1",
    "ExtraBold": "8af99acce860533a64926ebff131aa9f37806ffef9636798f36c3a4a526f9e32",
}
# each style: its name, its source, the heavier upright one its ✔ ✘ ✖ ℹ come from, and its upright one (the font's
# symbols stand upright in its italics too)
STYLES = {"Regular": ("Regular", "Regular", "Bold", "Regular"), "Bold": ("Bold", "Bold", "ExtraBold", "Bold"),
          "Italic": ("Italic", "Italic", "Bold", "Regular"),
          "BoldItalic": ("Bold Italic", "BoldItalic", "ExtraBold", "Bold")}
TALLER = 1.10
# herdr's folds of its machines in the Spaces list (▾ open, ▸ shut, built into herdr) drawn as the sidebar's
# chevrons, Nerd Fonts' own, so every fold on the screen looks alike (the owner, 2026-11-20)
SAME_AS = {0x25BE: 0xEAB4, 0x25B8: 0xEAB6}
WIDTH = 600
CENTRE = (300, 360)                                # where ● and ✶ sit: the middle of the caps
REACH = 300                                        # ✶'s radius, which the spinner's stars keep to


def source_file(source, name):
    """The bytes of JetBrainsMonoNerdFont-NAME.ttf from SOURCE (a folder or the release's tar.xz), checked."""
    file = f"JetBrainsMonoNerdFont-{name}.ttf"
    if os.path.isdir(source):
        with open(os.path.join(source, file), "rb") as f:
            data = f.read()
    else:
        with tarfile.open(source, "r:xz") as tar:
            data = tar.extractfile(file).read()
    if hashlib.sha256(data).hexdigest() != SOURCES[name]:
        sys.exit(f"{file} in {source} is not Nerd Fonts {NERD_FONTS}'s")
    return data


def fetch():
    """The release's archive, downloaded into CACHE once, checked."""
    path = os.path.join(CACHE, f"JetBrainsMono-{NERD_FONTS}.tar.xz")
    if not os.path.isfile(path):
        os.makedirs(CACHE, exist_ok=True)
        with urllib.request.urlopen(ARCHIVE) as answer:
            data = answer.read()
        if hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
            sys.exit(f"{ARCHIVE} is not the archive it was")
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
    return path


# --- the outlines: drawn into a recording, each contour turned the TrueType way (clockwise filled, a hole the other)

class Shape:
    def __init__(self):
        self.contours = []          # (recording, is_hole)

    def add(self, draw, hole=False):
        """DRAW(pen) draws one or more closed contours: filled, or a HOLE; a glyph's own outline keeps its turns."""
        keep = getattr(draw, "own", False)
        pen = RecordingPen()
        draw(pen)
        contour = []
        for op, args in pen.value:
            contour.append((op, args))
            if op in ("closePath", "endPath"):
                self.contours.append((contour, None if keep else hole))
                contour = []
        return self

    def glyph(self, glyph_set, transform=None):
        tt = TTGlyphPen(glyph_set)
        out = Cu2QuPen(tt, max_err=0.5, reverse_direction=False)
        if transform:
            out = TransformPen(out, transform)
        for contour, hole in self.contours:
            area = AreaPen()
            replay(contour, area)
            # AreaPen counts a clockwise contour negative
            turn = hole is not None and (area.value > 0) != hole
            replay(contour, ReverseContourPen(out) if turn else out)
        glyph = tt.glyph()
        if glyph.numberOfContours > 0:
            glyph.flags[0] |= flagOverlapSimple
        return glyph


def replay(contour, pen):
    for op, args in contour:
        getattr(pen, op)(*args)


def outline(font, char, transform=None):
    """A drawer of CHAR's outline in FONT (decomposed), moved by TRANSFORM."""
    glyph_set = font.getGlyphSet()
    name = font.getBestCmap()[ord(char)]

    def draw(pen):
        rec = DecomposingRecordingPen(glyph_set)
        glyph_set[name].draw(rec)
        rec.replay(TransformPen(pen, transform) if transform else pen)
    draw.own = True
    return draw


def contours_of(font, char):
    """CHAR's contours in FONT as lists of (op, args)."""
    rec = DecomposingRecordingPen(font.getGlyphSet())
    font.getGlyphSet()[font.getBestCmap()[ord(char)]].draw(rec)
    found, one = [], []
    for op, args in rec.value:
        one.append((op, args))
        if op in ("closePath", "endPath"):
            found.append(one)
            one = []
    return found


def bounds(font, char):
    glyph = font["glyf"][font.getBestCmap()[ord(char)]]
    glyph.recalcBounds(font["glyf"])
    return glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax


def cut(font, char, right=False):
    """The end CHAR's leftmost (RIGHT: rightmost) point is on (→'s shaft, ✕'s arm): its width, cut square across, and
    its middle."""
    (contour,) = contours_of(font, char)
    points = [p for op, args in contour for p in args]
    at = (max if right else min)(range(len(points)), key=lambda i: points[i])
    p, other = points[at], min((points[at - 1], points[(at + 1) % len(points)]),
                               key=lambda q: math.hypot(q[0] - points[at][0], q[1] - points[at][1]))
    return math.hypot(other[0] - p[0], other[1] - p[1]), ((p[0] + other[0]) / 2, (p[1] + other[1]) / 2)


def rect(x0, y0, x1, y1):
    def draw(pen):
        pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0)); pen.closePath()
    return draw


def bar(a, b, width):
    """A straight stroke WIDTH thick from A to B, its ends cut square."""
    (ax, ay), (bx, by) = a, b
    length = math.hypot(bx - ax, by - ay)
    nx, ny = -(by - ay) / length * width / 2, (bx - ax) / length * width / 2

    def draw(pen):
        pen.moveTo((ax + nx, ay + ny)); pen.lineTo((bx + nx, by + ny)); pen.lineTo((bx - nx, by - ny))
        pen.lineTo((ax - nx, ay - ny)); pen.closePath()
    return draw


KAPPA = 0.5523


def disc(cx, cy, r):
    def draw(pen):
        k = KAPPA * r
        pen.moveTo((cx, cy - r))
        pen.curveTo((cx - k, cy - r), (cx - r, cy - k), (cx - r, cy))
        pen.curveTo((cx - r, cy + k), (cx - k, cy + r), (cx, cy + r))
        pen.curveTo((cx + k, cy + r), (cx + r, cy + k), (cx + r, cy))
        pen.curveTo((cx + r, cy - k), (cx + k, cy - r), (cx, cy - r))
        pen.closePath()
    return draw


def teardrop(angle, tip, head, radius, centre=CENTRE):
    """A drop pointing out from CENTRE at ANGLE (degrees, 90 up): its point TIP from the centre, its round end a circle
    of RADIUS whose middle is HEAD from the centre; its sides pinch in toward the point, as a drop of ink does."""
    t, d, r, k = tip, head, radius, KAPPA * radius
    reach = d - t
    local = [("moveTo", ((0, t),)),
             ("curveTo", ((0.14 * r, t + 0.32 * reach), (r, d - 0.5 * reach), (r, d))),
             ("curveTo", ((r, d + k), (k, d + r), (0, d + r))),
             ("curveTo", ((-k, d + r), (-r, d + k), (-r, d))),
             ("curveTo", ((-r, d - 0.5 * reach), (-0.14 * r, t + 0.32 * reach), (0, t))),
             ("closePath", ())]
    turn = Transform().translate(*centre).rotate(math.radians(angle - 90))

    def draw(pen):
        replay(local, TransformPen(pen, turn))
    return draw


def polygon(points):
    def draw(pen):
        pen.moveTo(points[0])
        for p in points[1:]:
            pen.lineTo(p)
        pen.closePath()
    return draw


def meet(a, b, c, d):
    """Where line AB meets line CD."""
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = a, b, c, d
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return x1 + t * (x2 - x1), y1 + t * (y2 - y1)


def inset(points, d):
    """POINTS (a closed polygon, either turn) with every edge moved D inward, its corners mitred."""
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))
    turn = 1 if area > 0 else -1                       # counterclockwise: the inside is on the left
    edges = []
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        length = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / length * d * turn, (x1 - x0) / length * d * turn
        edges.append(((x0 + nx, y0 + ny), (x1 + nx, y1 + ny)))
    return [meet(*edges[i - 1], *edges[i]) for i in range(len(edges))]


def band(points, width):
    """A stroke WIDTH thick along the polyline POINTS, its corners mitred, its ends cut square."""
    left, right, n = [], [], len(points)
    normals = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        normals.append((-(y1 - y0) / length * width / 2, (x1 - x0) / length * width / 2))
    for i, (x, y) in enumerate(points):
        if i in (0, n - 1):
            nx, ny = normals[min(i, n - 2)]
            left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
            continue
        (ax, ay), (bx, by) = normals[i - 1], normals[i]
        for side, sign in ((left, 1), (right, -1)):
            p0, p1 = points[i - 1], points[i + 1]
            side.append(meet((p0[0] + sign * ax, p0[1] + sign * ay), (x + sign * ax, y + sign * ay),
                             (x + sign * bx, y + sign * by), (p1[0] + sign * bx, p1[1] + sign * by)))
    return polygon(left + right[::-1])


def chevron(tip, direction, length, width, half=52):
    """An arrowhead as the font draws →'s: two legs WIDTH thick and LENGTH long meeting at TIP, HALF degrees off the
    way back; the shaft comes in at its inner corner, width / sin(HALF) behind the tip."""
    dx, dy = direction
    norm = math.hypot(dx, dy)
    dx, dy = dx / norm, dy / norm
    a = math.radians(half)
    legs = [(-dx * math.cos(a) - sign * dy * math.sin(a), -dy * math.cos(a) + sign * dx * math.sin(a))
            for sign in (1, -1)]
    tx, ty = tip
    ends = [(tx + length * ux, ty + length * uy) for ux, uy in legs]
    inner = []
    for (ux, uy), (vx, vy), (ex, ey) in zip(legs, legs[::-1], ends):
        dot = ux * vx + uy * vy
        px, py = vx - dot * ux, vy - dot * uy
        pl = math.hypot(px, py)
        inner.append((ex + px / pl * width, ey + py / pl * width))
    v = (tx - dx * width / math.sin(a), ty - dy * width / math.sin(a))
    return polygon([tip, ends[0], inner[0], v, inner[1], ends[1]])


def arc(pen, cx, cy, r, a0, a1, start=True):
    """Circle arc from A0 to A1 degrees (either way) as cubic pieces of at most 90°."""
    steps = max(1, math.ceil(abs(a1 - a0) / 90))
    step = math.radians(a1 - a0) / steps
    k = 4 / 3 * math.tan(step / 4) * r
    at = math.radians(a0)
    if start:
        pen.moveTo((cx + r * math.cos(at), cy + r * math.sin(at)))
    for _ in range(steps):
        nxt = at + step
        pen.curveTo((cx + r * math.cos(at) - k * math.sin(at), cy + r * math.sin(at) + k * math.cos(at)),
                    (cx + r * math.cos(nxt) + k * math.sin(nxt), cy + r * math.sin(nxt) - k * math.cos(nxt)),
                    (cx + r * math.cos(nxt), cy + r * math.sin(nxt)))
        at = nxt


def ring_arc(cx, cy, r, width, a0, a1):
    """A stroke WIDTH thick along the circle of R from A0 to A1 degrees, its ends cut along the radius."""
    def draw(pen):
        arc(pen, cx, cy, r + width / 2, a0, a1)
        a = math.radians(a1)
        pen.lineTo((cx + (r - width / 2) * math.cos(a), cy + (r - width / 2) * math.sin(a)))
        arc(pen, cx, cy, r - width / 2, a1, a0, start=False)
        pen.closePath()
    return draw


def ellipse_half(pen, cx, cy, rx, ry, upper, leftward, start=False):
    """Half an ellipse, its upper or lower half, from its right end to its left (LEFTWARD) or back."""
    k, sign = KAPPA, 1 if upper else -1
    ends = [(cx + rx, cy), (cx, cy + sign * ry), (cx - rx, cy)]
    controls = [((cx + rx, cy + sign * k * ry), (cx + k * rx, cy + sign * ry)),
                ((cx - k * rx, cy + sign * ry), (cx - rx, cy + sign * k * ry))]
    if not leftward:
        ends, controls = ends[::-1], [(b, a) for a, b in controls[::-1]]
    if start:
        pen.moveTo(ends[0])
    else:
        pen.lineTo(ends[0])
    for (c1, c2), end in zip(controls, ends[1:]):
        pen.curveTo(c1, c2, end)


# --- the symbols Claude Code and Codex print that JetBrainsMono Nerd Font lacks, each drawn from the font's own

def symbols(font, heavy, upright):
    """{codepoint: Shape} for FONT, HEAVY its heavier upright weight, UPRIGHT its upright one."""
    made = {}
    # ⏺ Claude Code's bullet on a Mac (● elsewhere), ⎿ its result's corner: the font's own ● and └
    made[0x23FA] = Shape().add(outline(font, "●"))
    made[0x23BF] = Shape().add(outline(font, "└"))

    # the spinner, · ✢ ✳ ✶ ✻ ✽ (✶ and · are the font's): each as wide as ✶, round CENTRE
    made[0x2722] = Shape()                                            # ✢ four drops, joined
    for angle in (90, 0, 270, 180):
        made[0x2722].add(teardrop(angle, -14, 224, 76))
    x0, y0, x1, y1 = bounds(font, "✕")                                # ✳ ✕ and ✕ turned 45°, its own strokes
    middle = ((x0 + x1) / 2, (y0 + y1) / 2)
    there = Transform().translate(CENTRE[0] - middle[0], CENTRE[1] - middle[1])
    turned = there.translate(*middle).rotate(math.pi / 4).translate(-middle[0], -middle[1])
    made[0x2733] = Shape().add(outline(font, "✕", there)).add(outline(font, "✕", turned))
    made[0x273B] = Shape().add(disc(*CENTRE, 60))                     # ✻ six light drops round a dot
    made[0x273D] = Shape()                                            # ✽ six heavy drops, joined
    for n in range(6):
        made[0x273B].add(teardrop(90 + 60 * n, 98, 244, 56))
        made[0x273D].add(teardrop(90 + 60 * n, -10, 210, 90))

    # ⏵⏵ accept edits, ⏸ plan mode: ▶ at a medium size, and two bars as tall
    small, (cx, cy) = 0.72, CENTRE
    made[0x23F5] = Shape().add(outline(font, "▶", Transform().translate(cx, cy).scale(small).translate(-cx, -cy)))
    _, b0, _, b1 = bounds(font, "▶")
    low, high = cy + (b0 - cy) * small, cy + (b1 - cy) * small
    side = round((high - low) * 0.27)
    made[0x23F8] = Shape().add(rect(cx - side * 1.5, low, cx - side * 0.5, high)) \
        .add(rect(cx + side * 0.5, low, cx + side * 1.5, high))

    # the task list's ✔ ◼ ◻, a question's ☐ ☒, a diagnostic's ✘ ℹ: the heavier weight's ✓ ✗ i; □'s line
    made[0x2714] = Shape().add(outline(heavy, "✓"))
    made[0x2718] = Shape().add(outline(heavy, "✗"))
    made[0x2139] = Shape().add(outline(heavy, "i"))
    x0, y0, x1, y1 = bounds(font, "□")
    line = min(abs(p[0] - x0) for c in contours_of(font, "□")[1:] for op, args in c for p in args)
    half = (x1 - x0) * 0.375                                          # a medium square: between ▪ and □
    made[0x25FC] = Shape().add(rect(cx - half, cy - half, cx + half, cy + half))
    made[0x25FB] = Shape().add(rect(cx - half, cy - half, cx + half, cy + half)) \
        .add(rect(cx - half + line, cy - half + line, cx + half - line, cy + half - line), hole=True)
    made[0x2610] = Shape().add(outline(font, "□"))
    inset = line + 90
    made[0x2612] = Shape().add(outline(font, "□")) \
        .add(bar((x0 + inset, y0 + inset), (x1 - inset, y1 - inset), line)) \
        .add(bar((x0 + inset, y1 - inset), (x1 - inset, y0 + inset), line))
    # ⧉ an editor's selection: two medium squares in □'s line, the one behind up and left
    edge, shift = 400, 140
    for left, bottom in ((cx - edge / 2 - shift / 2, cy - edge / 2 + shift / 2),
                         (cx - edge / 2 + shift / 2, cy - edge / 2 - shift / 2)):
        made.setdefault(0x29C9, Shape()).add(rect(left, bottom, left + edge, bottom + edge)) \
            .add(rect(left + line, bottom + line, left + edge - line, bottom + edge - line), hole=True)

    # ◐ the effort's middle step: ● with the right half of ◔'s hole, as the font makes ◔ and ◕
    hole = contours_of(font, "◔")[1]
    quarter = next(args for op, args in hole if op == "qCurveTo" and args[-1][1] == cy)
    start = hole[0][1][0]
    mirrored = [(x, 2 * cy - y) for x, y in reversed((start,) + quarter[:-1])]

    def right_half(pen):
        pen.moveTo(start); pen.qCurveTo(*quarter); pen.qCurveTo(*mirrored); pen.closePath()
    made[0x25D0] = Shape().add(outline(font, "●")).add(right_half, hole=True)

    # ↳ Claude Code's and Codex's turn: → with a stem up from its shaft's end, the shaft's width, to the caps' height
    shaft, (x0, axis) = cut(font, "→")
    made[0x21B3] = Shape().add(outline(font, "→")) \
        .add(rect(x0, axis - shaft / 2, x0 + shaft, font["OS/2"].sCapHeight))
    # ※ ✕ with a dot in each of its four gaps
    arm, _ = cut(font, "✕")
    dot, gap = arm / 2, 205
    made[0x203B] = Shape().add(outline(font, "✕", there))
    for dx, dy in ((0, gap), (gap, 0), (0, -gap), (-gap, 0)):
        made[0x203B].add(disc(cx + dx, cy + dy, dot))
    more(font, heavy, upright, made)
    return made


def mapped(font, base, target):
    """The transform that takes BASE's box onto TARGET's (0 onto ⁰): the font's own size and place for them."""
    b, t = bounds(font, base), bounds(font, target)
    scale = (t[3] - t[1]) / (b[3] - b[1])
    return Transform().translate((t[0] + t[2]) / 2, (t[1] + t[3]) / 2).scale(scale) \
        .translate(-(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2)


def dashed(font, char):
    """↑ or ↓ with its shaft in three pieces: its far end moved up to the head, two dashes in the gap."""
    (contour,) = contours_of(font, char)
    ys = [p[1] for op, args in contour for p in args]
    far = min(ys) if char == "↑" else max(ys)          # the shaft's end away from the head
    ends = sorted(p for op, args in contour for p in args if p[1] == far)
    near = [p for op, args in contour for p in args if p[0] in (ends[0][0], ends[-1][0]) and p[1] != far]
    head = max(q[1] for q in near) if char == "↑" else min(q[1] for q in near)
    length = abs(head - far)
    dash, gap = 0.2 * length, 0.16 * length
    sign = 1 if char == "↑" else -1
    stub = far + sign * (2 * dash + 2 * gap)
    moved = [(op, tuple((x, stub) if y == far else (x, y) for x, y in args)) for op, args in contour]
    x0, x1 = ends[0][0], ends[-1][0]
    shape = Shape().add(lambda pen: replay(moved, pen))
    for n in range(2):
        a = far + sign * n * (dash + gap)
        shape.add(rect(x0, min(a, a + sign * dash), x1, max(a, a + sign * dash)))
    return shape


def quarters(font):
    """◔'s hole as the inner circle's four quarters (lower right, upper right, upper left, lower left), each a point
    list from one end through its off-curve points to the other."""
    cy = CENTRE[1]
    hole = contours_of(font, "◔")[1]
    lower_right = (hole[0][1][0],) + next(args for op, args in hole if op == "qCurveTo" and args[-1][1] == cy)
    upper_right = [(x, 2 * cy - y) for x, y in reversed(lower_right)]
    upper_left = [(2 * CENTRE[0] - x, y) for x, y in reversed(upper_right)]
    lower_left = [(2 * CENTRE[0] - x, y) for x, y in reversed(lower_right)]
    return [list(lower_right), upper_right, upper_left, lower_left]


def half_hole(parts):
    def draw(pen):
        pen.moveTo(parts[0][0])
        for part in parts:
            pen.qCurveTo(*part[1:])
        pen.closePath()
    return draw


def drum(layers, rx=230, ry=95, height=160, line=50, centre=CENTRE):
    """A draughts piece seen from the side, LAYERS discs high, in □'s line: its outline, its top face, a band each."""
    cx, cy = centre
    bottom = cy - (2 * ry + layers * height) / 2 + ry
    top = bottom + layers * height
    shape = Shape()

    def outside(pen):
        pen.moveTo((cx - rx, top)); pen.lineTo((cx - rx, bottom))
        ellipse_half(pen, cx, bottom, rx, ry, upper=False, leftward=False)
        pen.lineTo((cx + rx, top))
        ellipse_half(pen, cx, top, rx, ry, upper=True, leftward=True)
        pen.closePath()
    shape.add(outside)

    def face(pen):
        ellipse_half(pen, cx, top, rx - line, ry - line, upper=True, leftward=True, start=True)
        ellipse_half(pen, cx, top, rx - line, ry - line, upper=False, leftward=False)
        pen.closePath()
    shape.add(face, hole=True)
    for n in range(layers):
        above, below = top - n * height, top - (n + 1) * height

        def side(pen, above=above, below=below):
            pen.moveTo((cx - rx + line, above)); pen.lineTo((cx - rx + line, below))
            ellipse_half(pen, cx, below, rx - line, ry - line, upper=False, leftward=False)
            pen.lineTo((cx + rx - line, above))
            ellipse_half(pen, cx, above, rx - line, ry, upper=False, leftward=True)
            pen.closePath()
        shape.add(side, hole=True)
    return shape


def more(font, heavy, upright, made):
    """The rest of what reaches these terminals (tools/fonts.py's ledger lines name where each comes from)."""
    cx, cy = CENTRE
    shaft, _ = cut(font, "→")
    line = min(abs(p[0] - bounds(font, "□")[0]) for c in contours_of(font, "□")[1:] for op, args in c for p in args)
    half = (bounds(font, "□")[2] - bounds(font, "□")[0]) * 0.375
    lean = math.sin(math.radians(52))

    # ↻ herdr's and Claude Code's: a circle in the arrows' stroke, open at the top, the font's arrowhead at its end
    r, middle_y = 205, 345
    end = math.radians(120)
    way = (math.sin(end), -math.cos(end))
    at = (cx + r * math.cos(end), middle_y + r * math.sin(end))
    turn = [ring_arc(cx, middle_y, r, shaft, 62, -240),
            chevron((at[0] + way[0] * shaft / lean, at[1] + way[1] * shaft / lean), way, 2 * shaft, shaft)]
    made[0x21BB], made[0x21BA] = Shape(), Shape()                    # ↺ herdr-fold's plain discard mark: ↻'s mirror
    for draw in turn:
        made[0x21BB].add(draw)
        made[0x21BA].add(lambda pen, draw=draw: draw(TransformPen(pen, (-1, 0, 0, 1, 2 * cx, 0))))
    # ↯ Claude Code's: a zigzag in the same stroke, the arrowhead at its foot; ⌁ (Codex's) the same, lying
    for code, points in ((0x21AF, [(165, 690), (390, 425), (215, 325), (395, 110)]),
                         (0x2301, [(36, 252), (248, 432), (328, 292), (500, 436)])):
        (x0, y0), (x1, y1) = points[-2], points[-1]
        length = math.hypot(x1 - x0, y1 - y0)
        way = ((x1 - x0) / length, (y1 - y0) / length)
        made[code] = Shape().add(band(points, shaft)) \
            .add(chevron((x1 + way[0] * shaft / lean, y1 + way[1] * shaft / lean), way, 2 * shaft, shaft))
    # ⑂ Claude Code's fork: two prongs and a stem in the arrows' stroke, baseline to caps
    cap, w = font["OS/2"].sCapHeight, shaft
    made[0x2442] = Shape().add(rect(150 - w / 2, 380, 150 + w / 2, cap)).add(rect(450 - w / 2, 380, 450 + w / 2, cap)) \
        .add(rect(150 - w / 2, 380 - w / 2, 450 + w / 2, 380 + w / 2)).add(rect(cx - w / 2, 0, cx + w / 2, 380))
    # ↵ herdr's Enter, Claude Code's and Codex's line break: ↳'s mirror, ← with a stem up from its shaft's end
    width, (x1, axis) = cut(font, "←", right=True)
    made[0x21B5] = Shape().add(outline(font, "←")).add(rect(x1 - width, axis - width / 2, x1, cap))
    # ⇆ an agent's "⇆ tab": the font's ⇉ taken apart, its upper arrow turned to the left
    (pair,) = contours_of(font, "⇉")
    points = [p for op, args in pair for p in args]
    if len(points) != 18 or points[5][1] != points[14][1]:
        raise SystemExit("⇉ is drawn otherwise: tools/fonts.py needs another way to take it apart")
    made[0x21C6] = Shape().add(polygon(points[0:6] + points[14:18])) \
        .add(polygon([(2 * cx - x, y) for x, y in points[5:15]]))
    # ⇡ ⇣ starship's ahead and behind: ↑ and ↓ with dashed shafts; ⇕ its diverged: the font's ⇔ stood up
    made[0x21E1], made[0x21E3] = dashed(font, "↑"), dashed(font, "↓")
    x0, y0, x1, y1 = bounds(font, "⇔")
    made[0x21D5] = Shape().add(outline(font, "⇔", Transform().translate(cx, cy).rotate(math.pi / 2)
                                       .translate(-(x0 + x1) / 2, -(y0 + y1) / 2)))
    # ⏹ Claude Code's stopped task: a square as tall as ⏸
    small_low, small_high = bounds_of(made[0x23F8], font)[1::2]
    side = (small_high - small_low) / 2
    made[0x23F9] = Shape().add(rect(cx - side, small_low, cx + side, small_high))
    # ◑ ◒ ◓ Claude Code's spinner with ◐: ● with the other halves of ◔'s hole
    lr, ur, ul, ll = quarters(font)
    for code, parts in ((0x25D1, [ul, ll]), (0x25D2, [ur, ul]), (0x25D3, [ll, lr])):
        made[code] = Shape().add(outline(font, "●")).add(half_hole(parts), hole=True)
    # ▰ ▱ Claude Code's progress bar: parallelograms as tall as ◼, ▱ in □'s line
    lean_box = [(40, cy - half), (420, cy - half), (560, cy + half), (180, cy + half)]
    made[0x25B0] = Shape().add(polygon(lean_box))
    made[0x25B1] = Shape().add(polygon(lean_box)).add(polygon(inset(lean_box, line)), hole=True)
    # /context's grid: ⛁ a stack, ⛀ one piece, ⛶ free room, ⛝ the reserve, in □'s line round CENTRE
    made[0x26C0], made[0x26C1] = drum(1, line=line), drum(2, line=line)
    ring = lambda shape, h=half: shape.add(rect(cx - h, cy - h, cx + h, cy + h)) \
        .add(rect(cx - h + line, cy - h + line, cx + h - line, cy + h - line), hole=True)       # noqa: E731
    inner = half - line
    made[0x26DD] = ring(Shape()).add(bar((cx - inner, cy - inner), (cx + inner, cy + inner), line)) \
        .add(bar((cx - inner, cy + inner), (cx + inner, cy - inner), line))
    made[0x26F6] = Shape()
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = cx + sx * half, cy + sy * half
            made[0x26F6].add(rect(min(x, x - sx * 150), min(y, y - sy * line), max(x, x - sx * 150),
                                  max(y, y - sy * line)))
            made[0x26F6].add(rect(min(x, x - sx * line), min(y, y - sy * 150), max(x, x - sx * line),
                                  max(y, y - sy * 150)))
    # ⧈ Claude Code's sandbox count: ◻ with a small square in it
    made[0x29C8] = ring(ring(Shape()), 105)
    # ⬢ ⬡ an agent's spinner (Devin), starship's Node.js: hexagons as tall as ✶; ⬝ pi's progress: a very small square
    hexagon = [(cx + REACH * math.cos(math.radians(a)), cy + REACH * math.sin(math.radians(a)))
               for a in (90, 150, 210, 270, 330, 30)]
    made[0x2B22] = Shape().add(polygon(hexagon))
    made[0x2B21] = Shape().add(polygon(hexagon)).add(polygon(inset(hexagon, line)), hole=True)
    made[0x2B1D] = Shape().add(rect(cx - 80, cy - 80, cx + 80, cy + 80))
    # ✖ zod's errors in Claude Code: the heavier weight's ✕
    made[0x2716] = Shape().add(outline(heavy, "✕"))
    # ✂ Claude Code's "lines hidden": two rings in □'s line and two blades crossing at the middle
    made[0x2702] = Shape()
    for ring_at, tip in (((125, 470), (585, 235)), ((125, 250), (585, 485))):
        (ax, ay), (tx, ty) = ring_at, tip
        length = math.hypot(tx - ax, ty - ay)
        ux, uy = (tx - ax) / length, (ty - ay) / length
        base = (ax + ux * 80, ay + uy * 80)
        made[0x2702].add(polygon([(base[0] - uy * 40, base[1] + ux * 40), tip, (base[0] + uy * 40, base[1] - ux * 40)]))
        made[0x2702].add(disc(ax, ay, 92)).add(disc(ax, ay, 92 - line), hole=True)
    # ➤ yarn's lines: an arrowhead as wide as ▶, notched at its back
    made[0x27A4] = Shape().add(polygon([(575, cy), (45, cy + 255), (195, cy), (45, cy - 255)]))
    # ★ ☆ npm's star and Claude Code's figures.star: five points as far out as ✶'s, ☆ in a line a little finer than □'s
    star = [(cx + (REACH if n % 2 == 0 else REACH * 0.382) * math.cos(math.radians(90 + 36 * n)),
             332 + (REACH if n % 2 == 0 else REACH * 0.382) * math.sin(math.radians(90 + 36 * n))) for n in range(10)]
    made[0x2605] = Shape().add(polygon(star))
    made[0x2606] = Shape().add(polygon(star)).add(polygon(inset(star, line * 0.7)), hole=True)
    # ☑ Codex's done task in Markdown: □ with a check in its line
    x0, y0, x1, y1 = bounds(font, "□")
    made[0x2611] = Shape().add(outline(font, "□")).add(band([(x0 + 150, cy + 10), (cx - 35, y0 + 160),
                                                              (x1 - 140, y1 - 130)], line))
    # ⓘ Codex's notice: ○ with the upright i at the size its line is ○'s
    x0, y0, x1, y1 = bounds(upright, "i")
    made[0x24D8] = Shape().add(outline(font, "○")).add(outline(upright, "i", Transform().translate(cx, cy).scale(0.55)
                                                               .translate(-(x0 + x1) / 2, -(y0 + y1) / 2)))
    # spaces (pnpm's, Codex's) blank and a cell wide; ‑ Codex's non-breaking hyphen as ‐
    cmap = font.getBestCmap()
    for code in [*range(0x2000, 0x200B), 0x202F, 0x205F]:
        if code not in cmap:
            made[code] = Shape()
    made[0x2011] = Shape().add(outline(font, "‐"))
    # Codex's math: ⁻ ⁽ ⁾ and ₊ ₋ ₌ ₍ ₎, made from − ( ) + = as the font makes ⁼ from = and ⁰ ₀ from 0 (its ⁺ sits
    # lower than its digits)
    sign_up, digit_up, digit_down = mapped(font, "=", "⁼"), mapped(font, "0", "⁰"), mapped(font, "0", "₀")
    drop = (bounds(font, "₀")[1] + bounds(font, "₀")[3] - bounds(font, "⁰")[1] - bounds(font, "⁰")[3]) / 2
    sign_down = Transform().translate(0, drop).transform(sign_up)
    for code, char, how in ((0x207B, "−", sign_up), (0x207D, "(", digit_up), (0x207E, ")", digit_up),
                            (0x208A, "+", sign_down), (0x208B, "−", sign_down), (0x208C, "=", sign_down),
                            (0x208D, "(", digit_down), (0x208E, ")", digit_down)):
        made[code] = Shape().add(outline(font, char, how))


def bounds_of(shape, font):
    """SHAPE's box as drawn."""
    glyph = shape.glyph(font.getGlyphSet())
    glyph.recalcBounds(font["glyf"])
    return glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax


# --- the font

def rename(font, style):
    """Every name of the source's replaced: the OFL keeps a Modified Version from the Original's names."""
    name, old = font["name"], {r.nameID: r.toUnicode() for r in font["name"].names if r.platformID == 3}
    words = STYLES[style][0]
    names = {
        0: f"{old[0]}; herdr-fold Mono's changes: Copyright 2026 princesshu (https://github.com/princesshu)",
        1: FAMILY, 2: words, 3: f"{VERSION};NONE;{POSTSCRIPT}-{style}", 4: f"{FAMILY} {words}",
        5: f"Version {VERSION}; JetBrains Mono 2.304 with Nerd Fonts {NERD_FONTS}",
        6: f"{POSTSCRIPT}-{style}", 8: "herdr-fold", 9: old[9],
        10: (f"JetBrains Mono with the glyphs of Nerd Fonts {NERD_FONTS} (their authors: "
             "https://github.com/ryanoasis/nerd-fonts/blob/-/src/glyphs/README.md), lines 10% taller and the symbols "
             "Claude Code, Codex, herdr and starship print. A Modified Version under the SIL Open Font License 1.1."),
        11: "https://github.com/princesshu/herdr-fold", 12: old[12], 13: old[13], 14: old[14],
    }
    names.update({n: text for n, text in old.items() if n >= 256})       # the stylistic sets' names, GSUB's own
    name.names = []
    for n, text in sorted(names.items()):
        name.setName(text, n, 3, 1, 0x409)
        name.setName(text, n, 1, 0, 0)
    font["OS/2"].achVendID = "NONE"


def taller(font):
    """The line TALLER times as tall, the room split evenly above and below: the text keeps the middle of its line."""
    hhea, os2 = font["hhea"], font["OS/2"]
    line = hhea.ascent - hhea.descent + hhea.lineGap
    more = round(line * (TALLER - 1) / 2)
    hhea.ascent, hhea.descent, hhea.lineGap = hhea.ascent + more, hhea.descent - more, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = hhea.ascent, hhea.descent, 0
    os2.usWinAscent, os2.usWinDescent = hhea.ascent, -hhea.descent
    os2.fsSelection |= 1 << 7                                             # USE_TYPO_METRICS


def add_symbols(font, heavy, upright):
    cmap, glyf, hmtx = font.getBestCmap(), font["glyf"], font["hmtx"]
    order = list(font.getGlyphOrder())
    glyph_set = font.getGlyphSet()
    for code, shape in sorted(symbols(font, heavy, upright).items()):
        if code in cmap:
            raise SystemExit(f"U+{code:04X} is in the font already: take it out of tools/fonts.py")
        name = f"uni{code:04X}"
        glyph = shape.glyph(glyph_set)
        glyph.recalcBounds(glyf)
        order.append(name)
        glyf.glyphs[name] = glyph
        hmtx.metrics[name] = (WIDTH, glyph.xMin if glyph.numberOfContours else 0)
        for table in font["cmap"].tables:
            if table.isUnicode() and table.format in (4, 12):
                table.cmap[code] = name
    font.setGlyphOrder(order)
    glyf.glyphOrder = order


def same_as(font):
    """Each character of SAME_AS drawn as its other one: its cmap entries pointed at that one's glyph."""
    cmap = font.getBestCmap()
    for code, other in SAME_AS.items():
        for table in font["cmap"].tables:
            if table.isUnicode() and code in table.cmap:
                table.cmap[code] = cmap[other]


def build(source, style):
    words, own, heavier, straight = STYLES[style]
    font = TTFont(io.BytesIO(source_file(source, own)), recalcTimestamp=False)
    heavy = TTFont(io.BytesIO(source_file(source, heavier)))
    upright = font if straight == own else TTFont(io.BytesIO(source_file(source, straight)))
    rename(font, style)
    taller(font)
    add_symbols(font, heavy, upright)
    same_as(font)
    font["head"].modified = timestampFromString(BUILT)
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


def main(argv):
    parser = argparse.ArgumentParser(prog="tools/fonts.py", description="Builds herdr-fold Mono.")
    parser.add_argument("--source", help="a folder with the JetBrainsMonoNerdFont-*.ttf files, or the release's tar.xz")
    parser.add_argument("--out", default=OUT)
    parser.add_argument("--check", action="store_true", help="build in memory and say whether OUT holds the same")
    args = parser.parse_args(argv)
    source = os.path.expanduser(args.source) if args.source else fetch()
    stale = []
    for style in STYLES:
        data, path = build(source, style), os.path.join(args.out, FILE.format(style))
        if args.check:
            with open(path, "rb") as f:
                stale += [] if f.read() == data else [path]
            continue
        os.makedirs(args.out, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        print(f"{path}: {len(data)} bytes")
    for path in stale:
        print(f"{path}: not what tools/fonts.py builds")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

import AppKit
// herdr-fold's logo and app icon: its sheep as a Halloween ghost on a theme-colored Mac app icon. Plain SVG, colors
// written in (no CSS or filter), so CoreSVG shows it too; apply.py recolors the parts icon-bottom/-middle/-top/-ears.
// Run: swiftc -O tools/logo.swift -o logo && ./logo FACE BOTTOM MIDDLE TOP EARS > logo.svg (e.g. 0_0, colors bottom up)
func fail(_ why: String) -> Never {
    FileHandle.standardError.write(Data((why + "\n").utf8))
    exit(1)
}
let args = CommandLine.arguments
guard args.count == 6 else { fail("usage: logo FACE BOTTOM MIDDLE TOP EARS") }
let face = args[1], colors = Array(args[2...5])
guard face.count == 3 else { fail("a face is three characters: eye, nose, eye") }
guard colors.allSatisfy({ $0.range(of: "^#[0-9a-fA-F]{6}$", options: .regularExpression) != nil })
else { fail("a color is #rrggbb") }

// THE GRID: Apple's 824-pixel square in the middle of 1024, its edges bending round each corner in one smooth curve
// (CORNER, HANDLE: 62 pixels in on the diagonal, as macOS 27's); below it the system's shadow (SHADOW*), over it the
// glass: a sheen from the top gone by the middle, and a thin rim, brightest at the top
let BODY = CGRect(x: 100, y: 100, width: 824, height: 824)
let CORNER: CGFloat = 245, HANDLE: CGFloat = 84
let SHADOW: CGFloat = 0.13, SHADOW_DOWN: CGFloat = 8, SHADOW_SOFT: CGFloat = 30
let SHEEN: CGFloat = 0.13, RIM: CGFloat = 5, RIM_TOP: CGFloat = 0.40, RIM_BOTTOM: CGFloat = 0.05
// the sheet's gray from its top to its hem, and its size (300 = the units below), in the middle of the icon
let SHEET = ["#f2f2f2", "#dadada", "#d8d8d8"], SHEET_AT: [CGFloat] = [0, 0.5, 1]
let SIZE: CGFloat = 470, MIDDLE = CGPoint(x: 512, y: 512)
// the face: its openings (OPENING units thick), each in an even white rim (EDGE: the rim's outer width)
let OPENING: CGFloat = 14, EDGE: CGFloat = 21
// LIQUID GLASS (macOS 26 on, light from above): the sheep's shadow is its own outline LIFT_DOWN lower; a light edge
// runs inside the fleece's arcs (FLEECE_*, gone by the eyes) and the ears (EAR_*), never along a lower edge, where it
// would run beside the top edge of what is below
let LIFT: CGFloat = 0.3, LIFT_DOWN: CGFloat = 8, LIFT_SOFT: CGFloat = 10
let FLEECE_EDGE: CGFloat = 2.5, FLEECE_FADE: [(at: CGFloat, light: CGFloat)] = [(0, 1), (0.35, 0.35), (0.6, 0)]
let EAR_EDGE: CGFloat = 1.5, EAR_LIGHT: CGFloat = 0.5, EAR_FADE: [(at: CGFloat, light: CGFloat)] = [(0, 1), (0.7, 0)]
// a soft edge: SOFT_STEPS outlines, each wider than the last, each a share of the whole darkness
let SOFT_STEPS = 10

// a string's outline in JetBrains Mono Bold, centered on (0, 0)
func codeChars(_ s: String, size: CGFloat) -> CGPath {
    let base = CTFontCreateWithName("JetBrainsMono Nerd Font" as CFString, size, nil)
    let font = CTFontCreateCopyWithSymbolicTraits(base, size, nil, .boldTrait, .boldTrait) ?? base
    let line = CTLineCreateWithAttributedString(NSAttributedString(string: s, attributes: [.font: font]))
    let path = CGMutablePath()
    for run in CTLineGetGlyphRuns(line) as! [CTRun] {
        let n = CTRunGetGlyphCount(run)
        var glyphs = [CGGlyph](repeating: 0, count: n), positions = [CGPoint](repeating: .zero, count: n)
        CTRunGetGlyphs(run, CFRange(location: 0, length: n), &glyphs)
        CTRunGetPositions(run, CFRange(location: 0, length: n), &positions)
        for i in 0..<n {
            if let g = CTFontCreatePathForGlyph(font, glyphs[i], nil) {
                path.addPath(g, transform: CGAffineTransform(translationX: positions[i].x, y: positions[i].y))
            }
        }
    }
    let box = path.boundingBoxOfPath
    var center = CGAffineTransform(translationX: -box.midX, y: -box.midY)
    return path.copy(using: &center)!
}

// a glyph's outer outlines only: its counters (the hole of a 0, the dot in it) filled, so a thick eye has no specks
func outer(_ path: CGPath) -> CGPath {
    var parts: [CGMutablePath] = []
    path.applyWithBlock { e in
        let p = e.pointee.points
        switch e.pointee.type {
        case .moveToPoint: parts.append(CGMutablePath()); parts[parts.count - 1].move(to: p[0])
        case .addLineToPoint: parts[parts.count - 1].addLine(to: p[0])
        case .addQuadCurveToPoint: parts[parts.count - 1].addQuadCurve(to: p[1], control: p[0])
        case .addCurveToPoint: parts[parts.count - 1].addCurve(to: p[2], control1: p[0], control2: p[1])
        case .closeSubpath: parts[parts.count - 1].closeSubpath()
        @unknown default: break
        }
    }
    let boxes = parts.map { $0.boundingBoxOfPath }, kept = CGMutablePath()
    for (i, part) in parts.enumerated()
    where !boxes.indices.contains(where: { $0 != i && boxes[$0].contains(boxes[i]) }) {
        kept.addPath(part)
    }
    return kept
}

// THE SHEEP AS A HALLOWEEN GHOST: a white sheet with a fleece over its dome, drooping ears and a three-scallop hem; its
// face (FACE: eye, nose, eye, such as ^_^) cut in as characters thickened by a round stroke, with a white rim. Centered
// on MIDDLE; the sheet is one outline (curls and dome together), so its light edge follows what shows.
struct Sheep {
    let u: CGFloat                                       // pixels per unit
    let ears: CGPath, body: CGPath, face: CGPath         // the face's characters before they are thickened
    let openings: CGPath                                 // the face's characters thickened: the holes
}
func sheep(face: String) -> Sheep {
    let u = SIZE / 300
    var place = CGAffineTransform(scaleX: u, y: u)
    // the sheet runs counterclockwise, as the curls do, so where they overlap it stays filled
    let sheet = CGMutablePath()                          // the sides, three scallops, the dome
    sheet.move(to: CGPoint(x: -102, y: 40))
    sheet.addLine(to: CGPoint(x: -104, y: -98))
    for k in 0..<3 {
        let x0 = -104 + CGFloat(k) * 208 / 3, x1 = x0 + 208 / 3
        sheet.addCurve(to: CGPoint(x: x1, y: -98), control1: CGPoint(x: x0 + 4, y: -140),
                       control2: CGPoint(x: x1 - 4, y: -140))
    }
    sheet.addLine(to: CGPoint(x: 102, y: 40))
    sheet.addArc(center: CGPoint(x: 0, y: 40), radius: 102, startAngle: 0, endAngle: .pi, clockwise: false)
    sheet.closeSubpath()
    for k in 0...8 {                                     // the fleece: curls round the dome, down to the ears
        let a = -0.18 + CGFloat(k) * (.pi + 0.36) / 8
        sheet.addEllipse(in: CGRect(x: 98 * cos(a) - 27, y: 40 + 98 * sin(a) - 27, width: 54, height: 54))
    }
    let ears = CGMutablePath()
    for side: CGFloat in [1, -1] {                       // a leaf from under the curls, drooping
        let ear = CGMutablePath()
        ear.move(to: CGPoint(x: 80, y: 60))
        ear.addCurve(to: CGPoint(x: 158, y: -8), control1: CGPoint(x: 130, y: 62), control2: CGPoint(x: 166, y: 18))
        ear.addCurve(to: CGPoint(x: 90, y: 16), control1: CGPoint(x: 148, y: -26), control2: CGPoint(x: 114, y: 4))
        ear.closeSubpath()
        ears.addPath(ear, transform: CGAffineTransform(scaleX: side, y: 1))
    }
    // the face: each character fitted into its box (the nose stretched to it)
    func glyph(_ s: String, box: CGSize, at: CGPoint, stretch: Bool = false) -> CGPath {
        let outline = outer(codeChars(s, size: 100)), b = outline.boundingBoxOfPath
        let k = min(box.width / b.width, box.height / b.height)
        let fit = CGAffineTransform(scaleX: stretch ? box.width / b.width : k, y: stretch ? box.height / b.height : k)
            .concatenating(CGAffineTransform(translationX: at.x, y: at.y))
        return outline.copy(using: [fit])!
    }
    let chars = Array(face).map(String.init), marks = CGMutablePath()
    marks.addPath(glyph(chars[0], box: CGSize(width: 52, height: 56), at: CGPoint(x: -46, y: 36)))
    marks.addPath(glyph(chars[2], box: CGSize(width: 52, height: 56), at: CGPoint(x: 46, y: 36)))
    marks.addPath(glyph(chars[1], box: CGSize(width: 62, height: 8), at: CGPoint(x: 0, y: -32), stretch: true))
    // where it really ends (a curve's own box: the box of a path takes in its control points, which lie beyond it)
    let reach = sheet.boundingBoxOfPath.union(ears.boundingBoxOfPath).applying(place)
    place = place.concatenating(CGAffineTransform(translationX: MIDDLE.x - reach.midX, y: MIDDLE.y - reach.midY))
    let placedFace = marks.copy(using: &place)!
    let openings = placedFace.union(placedFace.copy(strokingWithWidth: OPENING * u, lineCap: .round, lineJoin: .round,
                                                    miterLimit: 4))
    return Sheep(u: u, ears: ears.copy(using: &place)!, body: sheet.normalized().copy(using: &place)!,
                 face: placedFace, openings: openings)
}

// THE ICON'S SHAPE: a rounded square on Apple's grid
func shape() -> CGPath {
    let path = CGMutablePath(), (l, b, r, t) = (BODY.minX, BODY.minY, BODY.maxX, BODY.maxY)
    path.move(to: CGPoint(x: l + CORNER, y: b))
    path.addLine(to: CGPoint(x: r - CORNER, y: b))
    path.addCurve(to: CGPoint(x: r, y: b + CORNER), control1: CGPoint(x: r - HANDLE, y: b),
                  control2: CGPoint(x: r, y: b + HANDLE))
    path.addLine(to: CGPoint(x: r, y: t - CORNER))
    path.addCurve(to: CGPoint(x: r - CORNER, y: t), control1: CGPoint(x: r, y: t - HANDLE),
                  control2: CGPoint(x: r - HANDLE, y: t))
    path.addLine(to: CGPoint(x: l + CORNER, y: t))
    path.addCurve(to: CGPoint(x: l, y: t - CORNER), control1: CGPoint(x: l + HANDLE, y: t),
                  control2: CGPoint(x: l, y: t - HANDLE))
    path.addLine(to: CGPoint(x: l, y: b + CORNER))
    path.addCurve(to: CGPoint(x: l + CORNER, y: b), control1: CGPoint(x: l, y: b + HANDLE),
                  control2: CGPoint(x: l + HANDLE, y: b))
    path.closeSubpath()
    return path
}

// THE SVG, top down (y from the top, as SVG has it)
func number(_ v: CGFloat) -> String {
    var s = String(format: "%.2f", Double(v))
    while s.hasSuffix("0") { s.removeLast() }
    if s.hasSuffix(".") { s.removeLast() }
    return s == "-0" ? "0" : s
}
func svgPath(_ path: CGPath) -> String {
    var d = ""
    func at(_ p: CGPoint) -> String { number(p.x) + " " + number(1024 - p.y) }
    path.applyWithBlock { e in
        let p = e.pointee.points
        switch e.pointee.type {
        case .moveToPoint: d += "M" + at(p[0])
        case .addLineToPoint: d += "L" + at(p[0])
        case .addQuadCurveToPoint: d += "Q" + at(p[0]) + " " + at(p[1])
        case .addCurveToPoint: d += "C" + at(p[0]) + " " + at(p[1]) + " " + at(p[2])
        case .closeSubpath: d += "Z"
        @unknown default: break
        }
    }
    return d
}

// lines of at most WIDTH characters (the repository's limit, with room for the quotes round each in the preview's
// data), broken where a space is: between the attributes, and between the numbers of a path; its attributes in single
// quotes, which the preview's data carries as they are
let WIDTH = 112
func wrapped(_ text: String) -> String {
    text.split(separator: "\n", omittingEmptySubsequences: false).map { line -> String in
        var rest = Substring(line), lines: [Substring] = []
        while rest.count > WIDTH, let space = rest.prefix(WIDTH + 1).lastIndex(of: " ") {
            lines.append(rest[..<space])
            rest = rest[rest.index(after: space)...]
        }
        return (lines + [rest]).joined(separator: "\n")
    }.joined(separator: "\n")
}

func svg(_ s: Sheep, colors: [String]) -> String {
    let (bottom, middle, top, ears) = (colors[0], colors[1], colors[2], colors[3])
    let whole = s.body.boundingBoxOfPath, earBox = s.ears.boundingBoxOfPath
    let body = svgPath(s.body), earsPath = svgPath(s.ears), square = svgPath(shape())
    let everywhere = "maskUnits='userSpaceOnUse' x='0' y='0' width='1024' height='1024'"
    // a gradient's stops: where, its color, how opaque (fully: not written), and the part's name where one is given
    func stops(_ list: [(CGFloat, String, CGFloat)], names: [String] = []) -> String {
        list.enumerated().map { k, stop in
            "<stop" + (k < names.count ? " id='\(names[k])'" : "") + " offset='\(number(stop.0))'"
                + " stop-color='\(stop.1)'" + (stop.2 < 1 ? " stop-opacity='\(number(stop.2))'" : "") + "/>"
        }.joined()
    }
    func light(_ at: CGFloat, _ alpha: CGFloat) -> (CGFloat, String, CGFloat) { (at, "#fff", alpha) }
    // a gradient from the top of BOX to its bottom
    func down(_ id: String, _ box: CGRect, _ list: [(CGFloat, String, CGFloat)]) -> String {
        "<linearGradient id='\(id)' gradientUnits='userSpaceOnUse' x1='0' y1='\(number(1024 - box.maxY))' x2='0' "
            + "y2='\(number(1024 - box.minY))'>\(stops(list))</linearGradient>"
    }
    // a soft dark below a shape (the part named ID, already moved down): SOFT_STEPS copies of it, each grown wider
    // (filled and outlined in black, see-through only as a whole, so no part of one is darkened twice), every one a
    // share of DARK: the dark is whole inside it and fades out over SOFT pixels round it
    func soft(_ id: String, dark: CGFloat, soft: CGFloat) -> String {
        let share = 1 - pow(1 - dark, 1 / CGFloat(SOFT_STEPS))
        return (1...SOFT_STEPS).map { k in
            let width = 2 * soft * CGFloat(k) / CGFloat(SOFT_STEPS)
            return "<use href='#\(id)' fill='#000' stroke='#000' stroke-width='\(number(width))' "
                + "stroke-linejoin='round' opacity='\(number(share))'/>"
        }.joined(separator: "\n")
    }
    func rimWidth(_ width: CGFloat) -> String {
        "stroke-width='\(number(width * s.u))' stroke-linecap='round' stroke-linejoin='round'"
    }
    let drop = svgPath(shape().copy(using: [CGAffineTransform(translationX: 0, y: -SHADOW_DOWN)])!)
    let lifted = svgPath(s.body.union(s.ears).subtracting(s.openings)
        .copy(using: [CGAffineTransform(translationX: 0, y: -LIFT_DOWN)])!)
    return wrapped("""
    <svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1024 1024' width='1024' height='1024'>
    <!-- herdr-fold's logo, its app icon: written by tools/logo.swift, do not edit -->
    <defs>
    <linearGradient id='icon-screen' gradientUnits='userSpaceOnUse' x1='512' y1='\(number(1024 - BODY.minY))' \
    x2='512' y2='\(number(1024 - BODY.maxY))'>\
    \(stops([(0, bottom, 1), (0.5, middle, 1), (1, top, 1)], names: ["icon-bottom", "icon-middle", "icon-top"]))\
    </linearGradient>
    \(down("icon-sheet", whole, zip(SHEET_AT, SHEET).map { ($0, $1, 1) }))
    \(down("icon-sheen", CGRect(x: 0, y: BODY.midY, width: 1, height: BODY.height / 2), [light(0, SHEEN), light(1, 0)]))
    \(down("icon-rim", BODY, [light(0, RIM_TOP), light(1, RIM_BOTTOM)]))
    <path id='icon-drop' d='\(drop)'/>
    <clipPath id='icon-shape'><path d='\(square)'/></clipPath>
    <mask id='icon-face' \(everywhere)><rect width='1024' height='1024' fill='#fff'/>\
    <path d='\(svgPath(s.openings))' fill='#000'/></mask>
    <path id='icon-glass-lift' d='\(lifted)'/>
    \(down("icon-glass-fleece-fade", whole, FLEECE_FADE.map { light($0.at, $0.light) }))
    <mask id='icon-glass-fleece' \(everywhere)>\
    <rect width='1024' height='1024' fill='url(#icon-glass-fleece-fade)'/></mask>
    <clipPath id='icon-glass-body'><path d='\(body)'/></clipPath>
    \(down("icon-glass-ear-fade", earBox, EAR_FADE.map { light($0.at, $0.light) }))
    <mask id='icon-glass-ear' \(everywhere)><rect width='1024' height='1024' fill='url(#icon-glass-ear-fade)'/></mask>
    <clipPath id='icon-glass-ears'><path d='\(earsPath)'/></clipPath>
    </defs>
    \(soft("icon-drop", dark: SHADOW, soft: SHADOW_SOFT))
    <path d='\(square)' fill='url(#icon-screen)'/>
    <g id='icon-glass-shadow' clip-path='url(#icon-shape)'>
    \(soft("icon-glass-lift", dark: LIFT, soft: LIFT_SOFT))
    </g>
    <g mask='url(#icon-face)'>
    <path id='icon-ears' d='\(earsPath)' fill='\(ears)'/>
    <path id='icon-glass-ear-light' d='\(earsPath)' fill='none' stroke='#fff' stroke-opacity='\(number(EAR_LIGHT))' \
    stroke-width='\(number(2 * EAR_EDGE * s.u))' clip-path='url(#icon-glass-ears)' mask='url(#icon-glass-ear)'/>
    <path d='\(body)' fill='url(#icon-sheet)'/>
    <path id='icon-glass-fleece-light' d='\(body)' fill='none' stroke='#fff' \
    stroke-width='\(number(2 * FLEECE_EDGE * s.u))' clip-path='url(#icon-glass-body)' mask='url(#icon-glass-fleece)'/>
    <path d='\(svgPath(s.face))' fill='#fff' stroke='#fff' \(rimWidth(EDGE))/>
    </g>
    <path d='\(square)' fill='url(#icon-sheen)'/>
    <path d='\(square)' fill='none' stroke='url(#icon-rim)' stroke-width='\(number(2 * RIM))' \
    clip-path='url(#icon-shape)'/>
    </svg>

    """)
}

print(svg(sheep(face: face), colors: colors), terminator: "")

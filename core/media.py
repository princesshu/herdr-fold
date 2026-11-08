"""What the preview draws as a picture: an image (as a PNG, through macOS's sips), a PDF's page (PDFKit) or an SVG or
a page (WebKit, offline), through small Swift helpers compiled once into the cache; and the browser that opens them.
Usage (the Herdr app mod's, in JSON): media.py picture PATH PAGE WIDTH [HEIGHT] (its kind, pages, PNG), open PATH."""
import contextlib
import glob
import hashlib
import json
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import time

KINDS = {**{ext: "image" for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tif", ".tiff", ".bmp")},
         ".pdf": "pdf", ".html": "html", ".htm": "html", ".svg": "svg"}
SAFARI = "com.apple.Safari"
APP_PICTURES = "herdr-fold-pictures"     # in the Herdr app's home: its image() takes a path from there
TIMEOUT = 120                 # seconds a compile or a page may take
DENSITY = 2                   # a drawn SVG's or page's pixels to a point: a Mac's screen
# the Swift helpers, each compiled once: pdf-pages `sizes PDF` prints each page's size in points, `render PDF N WIDTH
# OUT` writes page N (from 0) WIDTH pixels wide; page-shot `PATH WIDTH OUT RULES [HEIGHT]` draws a page or an SVG
HELPERS = {"pdf-pages": """import AppKit
import PDFKit
let a = CommandLine.arguments
guard a.count >= 3, let doc = PDFDocument(url: URL(fileURLWithPath: a[2])) else { exit(2) }
func shown(_ page: PDFPage) -> CGSize {                  // as it is shown: a turned page turned
  let box = page.bounds(for: .cropBox)
  return page.rotation % 180 == 0 ? box.size : CGSize(width: box.height, height: box.width)
}
if a[1] == "sizes" {
  for n in 0..<doc.pageCount { let s = shown(doc.page(at: n)!); print(Int(s.width.rounded()), Int(s.height.rounded())) }
  exit(0)
}
guard a[1] == "render", a.count == 6, let n = Int(a[3]), let width = Double(a[4]), n >= 0, n < doc.pageCount,
      let page = doc.page(at: n) else { exit(2) }
let box = shown(page)
let size = NSSize(width: width, height: (box.height * width / box.width).rounded())
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size.width), pixelsHigh: Int(size.height),
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
rep.size = size
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
NSColor.white.setFill()
NSRect(origin: .zero, size: size).fill()
page.thumbnail(of: size, for: .cropBox).draw(in: NSRect(origin: .zero, size: size))
NSGraphicsContext.restoreGraphicsState()
guard let png = rep.representation(using: .png, properties: [:]) else { exit(3) }
do { try png.write(to: URL(fileURLWithPath: a[5])) } catch { exit(3) }
""", "page-shot": r"""import AppKit
import WebKit
let a = CommandLine.arguments
guard a.count == 5 || a.count == 6, let width = Double(a[2]), width > 0 else { exit(2) }
let room = a.count == 6 ? Double(a[5]) ?? 0 : 0                  // the room's height, else 5/4 of its width
let file = URL(fileURLWithPath: a[1]), svg = file.pathExtension.lowercased() == "svg"
let points = width / 2, box = room > 0 ? room / 2 : points * 5 / 4      // twice as sharp as laid out (DENSITY)
NSApplication.shared.setActivationPolicy(.prohibited)
var done = false, failed = false

final class Shot: NSObject, WKNavigationDelegate {
  let width: Double, points: Double, out: URL, measure: String
  init(width: Double, points: Double, out: URL, measure: String) {
    self.width = width; self.points = points; self.out = out; self.measure = measure
  }
  func end(_ ok: Bool) { failed = !ok; done = true }
  func webView(_ view: WKWebView, didFinish _: WKNavigation!) {
    view.evaluateJavaScript(measure) { rect, _ in
      guard let r = rect as? [NSNumber], r.count == 2, r[0].doubleValue >= 1, r[1].doubleValue >= 1 else {
        return self.end(false)
      }
      let config = WKSnapshotConfiguration()
      config.rect = CGRect(x: 0, y: 0, width: r[0].doubleValue, height: r[1].doubleValue)
      view.takeSnapshot(with: config) { image, _ in
        guard let cg = image?.cgImage(forProposedRect: nil, context: nil, hints: nil) else { return self.end(false) }
        let wide = max(1, Int((self.width * r[0].doubleValue / self.points).rounded()))
        let high = max(1, Int((Double(wide) * r[1].doubleValue / r[0].doubleValue).rounded()))
        let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: wide, pixelsHigh: high, bitsPerSample: 8,
                                   samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                                   bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
        NSGraphicsContext.current?.imageInterpolation = .high
        NSGraphicsContext.current?.cgContext.draw(cg, in: CGRect(x: 0, y: 0, width: wide, height: high))
        NSGraphicsContext.restoreGraphicsState()
        self.end((try? rep.representation(using: .png, properties: [:])?.write(to: self.out)) != nil)
      }
    }
  }
  func webView(_: WKWebView, didFail _: WKNavigation!, withError _: Error) { end(false) }
  func webView(_: WKWebView, didFailProvisionalNavigation _: WKNavigation!, withError _: Error) { end(false) }
}

// a page's first screen; an SVG whole at its own size, never larger, smaller where it does not fit that
let measure = svg ? "(() => { const i = document.images[0], w = i.naturalWidth || 300, h = i.naturalHeight || 150, " +
  "k = Math.min(1, \(points) / w, \(box) / h); i.style.width = w * k + 'px'; i.style.height = h * k + 'px'; " +
  "return [w * k, h * k]; })()"
  : "[\(points), Math.min(document.documentElement.scrollHeight, \(box))]"
let shot = Shot(width: width, points: points, out: URL(fileURLWithPath: a[3]), measure: measure)
let rules = "[" + #"{"trigger":{"url-filter":".*"},"action":{"type":"block"}}"# + ["file", "data", "about"].map {
  #",{"trigger":{"url-filter":"^\#($0):"},"action":{"type":"ignore-previous-rules"}}"# }.joined() + "]"
var kept: [AnyObject] = []                                   // the view and its window, alive while it loads
WKContentRuleListStore(url: URL(fileURLWithPath: a[4]))!
  .compileContentRuleList(forIdentifier: "offline", encodedContentRuleList: rules) { list, _ in
  guard let list else { return shot.end(false) }
  let config = WKWebViewConfiguration()
  config.defaultWebpagePreferences.allowsContentJavaScript = false
  config.preferences.isFraudulentWebsiteWarningEnabled = false
  config.userContentController.add(list)
  config.websiteDataStore = .nonPersistent()
  let view = WKWebView(frame: NSRect(x: 0, y: 0, width: points, height: box), configuration: config)
  let window = NSWindow(contentRect: view.frame, styleMask: [.borderless], backing: .buffered, defer: false)
  view.navigationDelegate = shot
  window.contentView = view
  kept = [view, window]
  if svg {                                       // as an image, from its bytes: it runs nothing and reads nothing
    guard let data = try? Data(contentsOf: file) else { return shot.end(false) }
    view.loadHTMLString("<body style='margin:0'><img src='data:image/svg+xml;base64,\(data.base64EncodedString())'"
                        + " style='display:block'>", baseURL: nil)
    view.setValue(false, forKey: "drawsBackground")       // what it leaves empty stays clear, not white
  } else {
    view.loadFileURL(file, allowingReadAccessTo: file.deletingLastPathComponent())
  }
}
let end = Date(timeIntervalSinceNow: 60)
while !done && Date() < end { RunLoop.main.run(until: Date(timeIntervalSinceNow: 0.05)) }
exit(done && !failed ? 0 : 3)
"""}


def kind_of(path):
    """image, pdf, html or svg (a picture that is code too) by PATH's extension, else None."""
    return KINDS.get(os.path.splitext(path)[1].lower())


def size(path):
    """A PNG's (width, height) in pixels, or None for anything else."""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", head[16:24])


def run(argv, timeout, **switches):
    """ARGV run within TIMEOUT seconds: its finished process, or None where it hung or could not start."""
    try:
        return subprocess.run(argv, capture_output=True, timeout=timeout, **switches)
    except (subprocess.TimeoutExpired, OSError):
        return None


def named(path):
    """The name of PATH's pictures, from its path and its version: a changed file's are new ones, never kept ones."""
    try:
        stat = os.stat(path)
        version = f"{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        version = ""
    return hashlib.sha256(f"{path}\0{version}".encode()).hexdigest()[:12]


def as_png(path, folder, side):
    """IMAGE as a PNG at most SIDE pixels on its longer side: itself when it is one already, else made in FOLDER by
    sips; None when it cannot be."""
    shape = size(path)
    if shape and max(shape) <= side:
        return path
    if not shutil.which("sips"):
        return None
    made = os.path.join(folder, f"{named(path)}-{side}.png")
    done = run(["sips", "-s", "format", "png", path, "--out", made], TIMEOUT)
    if not done or done.returncode != 0 or not size(made):
        return None
    if max(size(made)) > side:                        # only then: -Z makes a smaller one larger too
        run(["sips", "-Z", str(side), made], TIMEOUT)
    return made if size(made) else None


def drawn_png(path, width, folder, height=None):
    """An SVG or a page as WebKit draws it, offline and none of its scripts run, WIDTH pixels wide and HEIGHT high at
    most (a page's first screen that high, else 5/4 of WIDTH), made in FOLDER (kept for its version); an SVG through
    sips without it; None where it cannot be."""
    made = os.path.join(folder, f"{named(path)}-drawn-{width}x{height or 0}-{revision('page-shot')}.png")
    if size(made):
        return made
    tool = helper("page-shot")
    if tool:
        with tempfile.TemporaryDirectory(dir=folder) as work:            # its rules, gone even when it hung
            done = run([tool, path, str(width), made, os.path.join(work, "rules"), *([str(height)] if height else [])],
                       TIMEOUT)
            if done and done.returncode == 0 and size(made):
                return made
    return as_png(path, folder, width) if kind_of(path) == "svg" else None


def drawable(path):
    """Whether PATH, an SVG or a page, can be drawn here: WebKit (macOS, its helper compiled by swiftc), or sips for an
    SVG."""
    return sys.platform == "darwin" and bool(shutil.which("swiftc") or kind_of(path) == "svg" and shutil.which("sips"))


def cache():
    return os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
                        "herdr-fold")


def revision(kind):
    """The KIND helper's source, by its hash: a newer herdr-fold's is another."""
    return hashlib.sha256(HELPERS[kind].encode()).hexdigest()[:12]


def helper(kind):
    """The KIND helper (macOS), compiled by swiftc into the cache once for its source (an earlier one removed), or
    None."""
    name = f"{kind}-{revision(kind)}"
    folder, made = cache(), os.path.join(cache(), name)
    if os.access(made, os.X_OK):
        return made
    swiftc = shutil.which("swiftc")
    if not swiftc or sys.platform != "darwin":
        return None
    os.makedirs(folder, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder) as work:
        source, built = os.path.join(work, "main.swift"), os.path.join(work, name)
        with open(source, "w", encoding="utf-8") as f:
            f.write(HELPERS[kind])
        done = run([swiftc, "-O", source, "-o", built], TIMEOUT * 3, env={**os.environ, "TMPDIR": work + os.sep})
        if not done or done.returncode != 0 or not os.access(built, os.X_OK):
            return None
        for old in glob.glob(os.path.join(folder, f"{kind}-*")):
            with contextlib.suppress(FileNotFoundError):         # another first picture's took it away first
                os.remove(old)
        os.replace(built, made)
    return made


def pages(path):
    """A PDF's pages, each [width, height] in points as it is shown, or None (no helper, or no PDF)."""
    tool = helper("pdf-pages")
    done = run([tool, "sizes", path], TIMEOUT, text=True) if tool else None
    if not done or done.returncode != 0:
        return None
    sizes = [line.split() for line in done.stdout.splitlines()]
    if not sizes or not all(len(size) == 2 and all(n.isdigit() and int(n) > 0 for n in size) for size in sizes):
        return None
    return [[int(n) for n in size] for size in sizes]


def page_png(path, page, width, folder):
    """A PDF's PAGE (from 0) as a PNG WIDTH pixels wide, made in FOLDER (kept for its version); None past its last
    page. Without the helper, the first page alone, through sips."""
    made = os.path.join(folder, f"{named(path)}-{page}-{width}.png")
    if size(made):
        return made
    tool = helper("pdf-pages")
    if tool:
        argv = [tool, "render", path, str(page), str(width), made]
    elif page == 0 and shutil.which("sips"):
        argv = ["sips", "-s", "format", "png", "--resampleWidth", str(width), path, "--out", made]
    else:
        return None
    done = run(argv, TIMEOUT)
    return made if done and done.returncode == 0 and size(made) else None


def browser():
    """The bundle of the browser macOS opens web pages with (LaunchServices' https handler), Safari when none is set."""
    plist = os.path.join(os.path.expanduser("~"), "Library", "Preferences", "com.apple.LaunchServices",
                         "com.apple.launchservices.secure.plist")
    try:
        with open(plist, "rb") as f:
            rows = plistlib.load(f).get("LSHandlers", [])
    except (OSError, ValueError, plistlib.InvalidFileException):
        rows = []
    return next((row.get("LSHandlerRoleAll") for row in rows if isinstance(row, dict)
                 and row.get("LSHandlerURLScheme") == "https" and row.get("LSHandlerRoleAll")), SAFARI)


def open_argv(path, platform=sys.platform):
    """The command that opens PATH in the default browser: macOS's open, Windows' Explorer (the app for its kind), else
    the desktop's opener; None without one."""
    if platform == "darwin":
        return ["open", "-b", browser(), path]
    if platform == "win32":
        return ["explorer", path]
    return ["xdg-open", path] if shutil.which("xdg-open") else None


def browsable():
    """Whether a browser opened here is in front of its person: not over SSH (a remote machine's), and one there."""
    return not (os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_CLIENT")) and open_argv("") is not None


def app_pictures():
    """Where the Herdr app's pictures are made, in its home (HERDR_APP_HOME, else ~/.config/herdr-app, as
    lib/herdr_app.py has it): those older than a day removed first."""
    home = os.environ.get("HERDR_APP_HOME") or os.path.join(os.path.expanduser("~"), ".config", "herdr-app")
    made = os.path.join(home, APP_PICTURES)
    os.makedirs(made, exist_ok=True)
    for old in glob.glob(os.path.join(made, "*.png")):
        try:
            if os.path.getmtime(old) < time.time() - 86400:
                os.remove(old)
        except OSError:
            pass
    return made


def picture(path, page, width, height=None):
    """PATH as the app's preview draws it: its kind, a PDF's pages (each one's size in points), and the PNG of the image
    or of PAGE, WIDTH wide (an SVG or a page, HEIGHT high at most), made in the app's home (its path from there) with
    its size (in points, a drawn one's), or None."""
    kind = kind_of(path)
    if kind not in ("image", "pdf", "svg", "html"):
        return {"kind": kind, "pages": None, "png": None, "size": None}
    folder = app_pictures()
    made = page_png(path, page, width, folder) if kind == "pdf" else drawn_png(path, width, folder, height) \
        if kind in ("svg", "html") else as_png(path, folder, width)
    if made and os.path.dirname(made) != folder:          # an image already small enough: a copy in the app's home
        made = shutil.copyfile(made, os.path.join(folder, f"{named(path)}.png"))
    density = DENSITY if made and "-drawn-" in os.path.basename(made) else 1     # WebKit's: drawn twice as sharp
    return {"kind": kind, "pages": pages(path) if kind == "pdf" else None,
            "png": made and f"{APP_PICTURES}/{os.path.basename(made)}",
            "size": made and [n // density for n in size(made)]}


def open_in_browser(path):
    """PATH opened in the default browser, not waited for; whether there was a way to."""
    argv = open_argv(path)
    if argv:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    return bool(argv)


def main(argv):
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if command == "picture" and len(args) in (3, 4) and all(arg.isdigit() for arg in args[1:]):
        answer = picture(args[0], *(int(arg) for arg in args[1:]))
    elif command == "open" and len(args) == 1:
        answer = {"opened": open_in_browser(args[0])}
    else:
        print("usage: media.py picture PATH PAGE WIDTH [HEIGHT] | open PATH", file=sys.stderr)
        return 2
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

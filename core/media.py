"""What the preview draws as a picture: an image (as a PNG, through macOS's sips) or a PDF's page (through PDFKit, a
small Swift helper compiled once into the cache); and the default browser that opens an image, a PDF or a page.
Usage (the Herdr app mod's, in JSON): media.py picture PATH PAGE WIDTH (its kind, pages, PNG), open PATH."""
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
         ".pdf": "pdf", ".html": "html", ".htm": "html"}
SAFARI = "com.apple.Safari"
APP_PICTURES = "herdr-fold-pictures"     # in the Herdr app's home: its image() takes a path from there
TIMEOUT = 120                 # seconds a compile or a page may take
# the helper: `count PDF` prints its pages, `render PDF N WIDTH OUT` writes page N (from 0) WIDTH pixels wide as a PNG
SWIFT = """import AppKit
import PDFKit
let a = CommandLine.arguments
guard a.count >= 3, let doc = PDFDocument(url: URL(fileURLWithPath: a[2])) else { exit(2) }
if a[1] == "count" { print(doc.pageCount); exit(0) }
guard a[1] == "render", a.count == 6, let n = Int(a[3]), let width = Double(a[4]), n >= 0, n < doc.pageCount,
      let page = doc.page(at: n) else { exit(2) }
let box = page.bounds(for: .cropBox)
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
"""


def kind_of(path):
    """image, pdf or html by PATH's extension, else None."""
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


def as_png(path, folder, side):
    """IMAGE as a PNG at most SIDE pixels on its longer side: itself when it is one already, else made in FOLDER by
    sips; None when it cannot be."""
    shape = size(path)
    if shape and max(shape) <= side:
        return path
    if not shutil.which("sips"):
        return None
    made = os.path.join(folder, f"{hashlib.sha256(path.encode()).hexdigest()[:12]}-{side}.png")
    if subprocess.run(["sips", "-s", "format", "png", path, "--out", made], capture_output=True,
                      timeout=TIMEOUT).returncode != 0 or not size(made):
        return None
    if max(size(made)) > side:                        # only then: -Z makes a smaller one larger too
        subprocess.run(["sips", "-Z", str(side), made], capture_output=True, timeout=TIMEOUT)
    return made if size(made) else None


def cache():
    return os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
                        "herdr-fold")


def helper():
    """The PDF helper, compiled by swiftc into the cache once for this source (an earlier one removed), or None."""
    name = f"pdf-pages-{hashlib.sha256(SWIFT.encode()).hexdigest()[:12]}"
    folder, made = cache(), os.path.join(cache(), name)
    if os.access(made, os.X_OK):
        return made
    swiftc = shutil.which("swiftc")
    if not swiftc:
        return None
    os.makedirs(folder, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder) as work:
        source, built = os.path.join(work, "pdf_pages.swift"), os.path.join(work, name)
        with open(source, "w", encoding="utf-8") as f:
            f.write(SWIFT)
        done = subprocess.run([swiftc, "-O", source, "-o", built], capture_output=True, timeout=TIMEOUT * 3,
                              env={**os.environ, "TMPDIR": work + os.sep})
        if done.returncode != 0 or not os.access(built, os.X_OK):
            return None
        for old in glob.glob(os.path.join(folder, "pdf-pages-*")):
            os.remove(old)
        os.replace(built, made)
    return made


def pages(path):
    """A PDF's page count, or None (no helper, or no PDF)."""
    tool = helper()
    done = subprocess.run([tool, "count", path], capture_output=True, text=True, timeout=TIMEOUT) if tool else None
    return int(done.stdout) if done and done.returncode == 0 and done.stdout.strip().isdigit() else None


def page_png(path, page, width, folder):
    """A PDF's PAGE (from 0) as a PNG WIDTH pixels wide, made in FOLDER; None past its last page. Without the helper,
    the first page alone, through sips."""
    made = os.path.join(folder, f"{hashlib.sha256(path.encode()).hexdigest()[:12]}-{page}-{width}.png")
    tool = helper()
    if tool:
        argv = [tool, "render", path, str(page), str(width), made]
    elif page == 0 and shutil.which("sips"):
        argv = ["sips", "-s", "format", "png", "--resampleWidth", str(width), path, "--out", made]
    else:
        return None
    done = subprocess.run(argv, capture_output=True, timeout=TIMEOUT)
    return made if done.returncode == 0 and size(made) else None


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
    """The command that opens PATH in the default browser: macOS's open, else the desktop's opener; None without one."""
    if platform == "darwin":
        return ["open", "-b", browser(), path]
    return ["xdg-open", path] if shutil.which("xdg-open") else None


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


def picture(path, page, width):
    """PATH as the app's preview draws it: its kind, a PDF's pages, and the PNG of the image or of PAGE, WIDTH wide,
    made in the app's home (its path from there), or None."""
    kind = kind_of(path)
    if kind not in ("image", "pdf"):
        return {"kind": kind, "pages": None, "png": None}
    folder = app_pictures()
    made = page_png(path, page, width, folder) if kind == "pdf" else as_png(path, folder, width)
    if made and os.path.dirname(made) != folder:          # an image already small enough: a copy in the app's home
        made = shutil.copyfile(made, os.path.join(folder, f"{hashlib.sha256(path.encode()).hexdigest()[:12]}.png"))
    return {"kind": kind, "pages": pages(path) if kind == "pdf" else None,
            "png": made and f"{APP_PICTURES}/{os.path.basename(made)}"}


def open_in_browser(path):
    """PATH opened in the default browser, not waited for; whether there was a way to."""
    argv = open_argv(path)
    if argv:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    return bool(argv)


def main(argv):
    command, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if command == "picture" and len(args) == 3 and args[1].isdigit() and args[2].isdigit():
        answer = picture(args[0], int(args[1]), int(args[2]))
    elif command == "open" and len(args) == 1:
        answer = {"opened": open_in_browser(args[0])}
    else:
        print("usage: media.py picture PATH PAGE WIDTH | open PATH", file=sys.stderr)
        return 2
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

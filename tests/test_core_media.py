"""Tests for core/media.py: which files the preview draws as pictures, an image as a PNG (sips), a PDF's pages as PNGs
(PDFKit, through a Swift helper compiled once), and the browser that opens them (LaunchServices' https handler)."""
import http.server
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zlib
from unittest import mock

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import media  # noqa: E402

MAC = sys.platform == "darwin"


def png(path, width, height):
    """A PNG of WIDTH x HEIGHT, a gradient, at PATH."""
    rows = b"".join(b"\x00" + b"".join(bytes((x * 255 // width, 90, y * 255 // height)) for x in range(width))
                    for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    return path


def first_pixel(path):
    """The top left pixel of the PNG at PATH, RGBA: a first row's first pixel is kept as it is, whatever its filter."""
    with open(path, "rb") as f:
        data = f.read()
    chunks, at = [], 8
    while at < len(data):
        length, kind = struct.unpack(">I4s", data[at:at + 8])
        if kind == b"IDAT":
            chunks.append(data[at + 8:at + 8 + length])
        at += 12 + length
    return tuple(zlib.decompress(b"".join(chunks))[1:5])


def pdf(path, pages, turned=()):
    """A PDF of PAGES letter pages, each a gray box, at PATH; those numbered in TURNED (from 0) turned a quarter."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Kids [{' '.join(f'{3 + 2 * n} 0 R' for n in range(pages))}] /Count {pages} >>"]
    for n in range(pages):
        box = b"0.5 g 72 72 300 400 re f"
        turn = " /Rotate 90" if n in turned else ""
        objects += [f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]{turn} /Contents {4 + 2 * n} 0 R >>",
                    f"<< /Length {len(box)} >>\nstream\n{box.decode()}\nendstream"]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    with open(path, "wb") as f:
        f.write(out)
    return path


class Kinds(unittest.TestCase):
    def test_pictures_pdfs_and_pages(self):
        for name, kind in [("a.PNG", "image"), ("b.jpeg", "image"), ("c.webp", "image"), ("d.heic", "image"),
                           ("e.pdf", "pdf"), ("f.html", "html"), ("g.HTM", "html"), ("h.svg", "svg"), ("i.py", None),
                           ("Makefile", None)]:
            with self.subTest(name=name):
                self.assertEqual(media.kind_of(name), kind)

    def test_a_png_knows_its_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(media.size(png(os.path.join(tmp, "a.png"), 30, 20)), (30, 20))
            with open(os.path.join(tmp, "b.png"), "wb") as f:
                f.write(b"not a png")
            self.assertIsNone(media.size(os.path.join(tmp, "b.png")))


class Browser(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)

    def handlers(self, rows):
        folder = os.path.join(self.home, "Library", "Preferences", "com.apple.LaunchServices")
        os.makedirs(folder)
        with open(os.path.join(folder, "com.apple.launchservices.secure.plist"), "wb") as f:
            plistlib.dump({"LSHandlers": rows}, f, fmt=plistlib.FMT_BINARY)

    def test_the_default_browser_opens_it(self):
        self.handlers([{"LSHandlerURLScheme": "mailto", "LSHandlerRoleAll": "com.apple.mail"},
                       {"LSHandlerURLScheme": "https", "LSHandlerRoleAll": "com.google.chrome"}])
        self.assertEqual(media.open_argv("/w/a.pdf", "darwin"), ["open", "-b", "com.google.chrome", "/w/a.pdf"])

    def test_with_none_chosen_safari(self):
        self.assertEqual(media.open_argv("/w/a.html", "darwin"), ["open", "-b", "com.apple.Safari", "/w/a.html"])

    def test_elsewhere_the_desktops_own(self):
        with mock.patch.object(media.shutil, "which", lambda name: "/usr/bin/xdg-open" if name == "xdg-open" else None):
            self.assertEqual(media.open_argv("/w/a.png", "linux"), ["xdg-open", "/w/a.png"])
        with mock.patch.object(media.shutil, "which", lambda name: None):
            self.assertIsNone(media.open_argv("/w/a.png", "linux"))
        self.assertEqual(media.open_argv(r"C:\w\a.png", "win32"), ["explorer", r"C:\w\a.png"])

    def test_over_ssh_no_browser_is_offered(self):
        """A browser opened on a machine reached over SSH is one nobody in front of the Mac sees."""
        set_env(self, SSH_CONNECTION=None, SSH_CLIENT=None)
        self.assertEqual(media.browsable(), media.open_argv("x") is not None)
        set_env(self, SSH_CONNECTION="the client and this machine")
        self.assertFalse(media.browsable())


class Hangs(unittest.TestCase):
    """A tool that hangs or is gone (sips, swiftc, the helper) makes no picture, and never ends the preview."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, XDG_CACHE_HOME=os.path.join(self.tmp, "cache"))

    def test_a_hanging_tool_makes_no_picture(self):
        big = png(os.path.join(self.tmp, "big.png"), 300, 200)
        hang = mock.patch.object(media.subprocess, "run", side_effect=subprocess.TimeoutExpired("sips", 1))
        found = mock.patch.object(media.shutil, "which", lambda name: f"/usr/bin/{name}")
        with hang, found:
            self.assertIsNone(media.as_png(big, self.tmp, 100))
            self.assertIsNone(media.page_png(big, 0, 100, self.tmp))
            self.assertIsNone(media.pages(big))

    @unittest.skipUnless(MAC, "the helpers: macOS")
    def test_an_earlier_helper_already_gone_is_no_failure(self):
        """Two first PDFs at once (the TUI's and the app's): the other took the old helper away first."""
        def built(argv, **_):                                              # swiftc's output: a runnable file
            with open(argv[-1], "w"):
                pass
            os.chmod(argv[-1], 0o755)
            return subprocess.CompletedProcess(argv, 0)
        gone = os.path.join(media.cache(), "pdf-pages-000000000000")
        with mock.patch.object(media.subprocess, "run", side_effect=built), \
                mock.patch.object(media.shutil, "which", lambda name: "/usr/bin/swiftc"), \
                mock.patch.object(media.glob, "glob", lambda pattern: [gone]):
            self.assertTrue(media.helper("pdf-pages").startswith(media.cache()))


@unittest.skipUnless(MAC, "sips: macOS")
class Images(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_a_small_png_is_shown_as_it_is(self):
        small = png(os.path.join(self.tmp, "a.png"), 40, 30)
        self.assertEqual(media.as_png(small, self.tmp, 100), small)

    def test_another_kind_or_a_big_one_becomes_a_smaller_png(self):
        big = png(os.path.join(self.tmp, "big.png"), 300, 200)
        made = media.as_png(big, self.tmp, 100)
        self.assertNotEqual(made, big)
        self.assertEqual(media.size(made), (100, 66))           # sips cuts the 0.67 off
        jpeg = os.path.join(self.tmp, "c.jpg")
        subprocess.run(["sips", "-s", "format", "jpeg", big, "--out", jpeg], capture_output=True, check=True)
        self.assertEqual(media.size(media.as_png(jpeg, self.tmp, 1000)), (300, 200))


@unittest.skipUnless(MAC, "sips: macOS")
class ForTheApp(unittest.TestCase):
    """The Herdr app draws a picture from its own folder (image() takes a path in it): media.py picture makes it in
    the app's home, herdr-fold-pictures/, an old one gone after a day."""

    @classmethod
    def setUpClass(cls):
        cls.cache = tempfile.mkdtemp()               # the helpers compiled once for all of them, never in ~/.cache

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.cache)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HERDR_APP_HOME=os.path.join(self.tmp, "app"), XDG_CACHE_HOME=self.cache)

    def test_an_image_made_in_the_apps_home(self):
        shot = png(os.path.join(self.tmp, "shot.webp.png"), 300, 200)
        answer = media.picture(shot, 0, 100)
        self.assertEqual((answer["kind"], answer["pages"]), ("image", None))
        self.assertTrue(answer["png"].startswith("herdr-fold-pictures/"))
        self.assertEqual(media.size(os.path.join(self.tmp, "app", answer["png"])), (100, 66))
        self.assertEqual(answer["size"], [100, 66])

    def test_a_small_image_keeps_its_own_size(self):
        """The app draws it no larger than that, as the TUI does."""
        icon = png(os.path.join(self.tmp, "icon.png"), 40, 30)
        self.assertEqual(media.picture(icon, 0, 100)["size"], [40, 30])

    def test_a_changed_image_is_a_new_picture(self):
        """The app keeps a picture by its path: a file changed since is made under a new name, never the one it has."""
        shot = png(os.path.join(self.tmp, "shot.png"), 30, 20)
        first = media.picture(shot, 0, 100)["png"]
        png(shot, 40, 20)
        self.assertNotEqual(media.picture(shot, 0, 100)["png"], first)

    def test_an_svg_drawn_as_a_picture(self):
        """An SVG is code and a picture: the app draws it as the picture (WebKit, else sips)."""
        svg = os.path.join(self.tmp, "logo.svg")
        with open(svg, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40"><rect width="60" height="40"'
                    ' fill="#7c6cd8"/></svg>\n')
        answer = media.picture(svg, 0, 100)
        self.assertEqual(answer["kind"], "svg")                                # drawn sharp, no wider than asked
        self.assertEqual(max(media.size(os.path.join(self.tmp, "app", answer["png"]))), 100)

    @unittest.skipUnless(MAC and shutil.which("swiftc"), "WebKit and swiftc: macOS")
    def test_an_svg_is_drawn_at_its_own_size_on_nothing(self):
        """As a design tool shows it: never stretched to the room, its own size in points (a PNG twice that, sharp on a
        Mac's screen), what it leaves empty clear, not white."""
        svg = os.path.join(self.tmp, "mark.svg")
        with open(svg, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40"><rect x="20" y="10" width="20"'
                    ' height="20" fill="#7c6cd8"/></svg>\n')
        answer = media.picture(svg, 0, 1600)
        made = os.path.join(self.tmp, "app", answer["png"])
        self.assertEqual((media.size(made), answer["size"]), ((120, 80), [60, 40]))
        self.assertEqual(first_pixel(made)[3], 0)                              # its corner: nothing drawn there

    @unittest.skipUnless(MAC and shutil.which("swiftc"), "WebKit and swiftc: macOS")
    def test_a_tall_svg_is_drawn_whole_and_narrower(self):
        """An SVG too large is drawn whole and smaller, at most WIDTH wide and 5/4 of it high: a tall one narrower."""
        svg = os.path.join(self.tmp, "tall.svg")
        with open(svg, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="1000"><rect width="400" height="1000"'
                    ' fill="#7c6cd8"/></svg>\n')
        self.assertEqual(media.size(media.drawn_png(svg, 200, self.tmp)), (100, 250))

    @unittest.skipUnless(MAC and shutil.which("swiftc"), "WebKit and swiftc: macOS")
    def test_a_drawn_page_is_kept_for_its_version(self):
        """The TUI draws again at every resize: a page already drawn as wide is taken as it is, not drawn again."""
        page = os.path.join(self.tmp, "index.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write("<html><body><h1>Pagination</h1></body></html>\n")
        first = media.drawn_png(page, 300, self.tmp)
        with mock.patch.object(media, "run", return_value=None):              # no drawing would work now
            self.assertEqual(media.drawn_png(page, 300, self.tmp), first)

    def test_a_picture_an_earlier_helper_drew_is_drawn_again(self):
        """A newer herdr-fold may draw it otherwise (an SVG at its own size): the one it drew before is not taken."""
        page = os.path.join(self.tmp, "index.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write("<h1>Pagination</h1>\n")

        def drew(argv, timeout, **_):
            png(argv[3], 10, 10)
            return subprocess.CompletedProcess(argv, 0)
        with mock.patch.object(media, "helper", return_value="/usr/bin/true"), \
                mock.patch.object(media, "run", side_effect=drew):
            first = media.drawn_png(page, 300, self.tmp)
            with mock.patch.dict(media.HELPERS, {"page-shot": media.HELPERS["page-shot"] + "\n"}):
                self.assertNotEqual(media.drawn_png(page, 300, self.tmp), first)

    @unittest.skipUnless(MAC and shutil.which("swiftc"), "WebKit and swiftc: macOS")
    def test_drawing_a_page_reaches_nothing_on_the_network(self):
        """A page in a repository may name a picture, a style, a font or a frame far away, to learn who opened it:
        drawing it opens no connection at all, not even an early one, and runs none of its scripts."""
        reached = []

        class Server(http.server.HTTPServer):
            def verify_request(self, request, address):
                reached.append(address)
                return True

        class Seen(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(204)
                self.end_headers()

            def log_message(self, *_):
                pass
        server = Server(("127.0.0.1", 0), Seen)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        far = f"http://127.0.0.1:{server.server_port}"
        page = os.path.join(self.tmp, "index.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(f'<html><head><link rel="preconnect" href="{far}"><link rel="dns-prefetch" href="{far}">'
                    f'<link rel="prefetch" href="{far}/next"><link rel="stylesheet" href="{far}/style.css">'
                    f'<style>@font-face {{font-family: x; src: url({far}/font.woff)}} body {{font-family: x; '
                    f'background: url({far}/back.png)}}</style></head><body><h1>Pagination</h1>'
                    f'<img src="{far}/beacon.png"><iframe src="{far}/frame"></iframe><video poster="{far}/poster.png">'
                    f'</video><script>fetch("{far}/script")</script></body></html>\n')
        self.assertIsNotNone(media.drawn_png(page, 400, self.tmp))
        time.sleep(1)
        self.assertEqual(reached, [])

    @unittest.skipUnless(MAC and shutil.which("swiftc"), "WebKit and swiftc: macOS")
    def test_a_page_is_drawn_as_a_browser_shows_it(self):
        """An HTML page drawn by macOS's own WebKit, WIDTH pixels wide, beside its code."""
        page = os.path.join(self.tmp, "index.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write("<html><body><h1>Pagination</h1><p>Every list route answers a page.</p></body></html>\n")
        answer = media.picture(page, 0, 600)
        self.assertEqual(answer["kind"], "html")
        self.assertEqual(media.size(os.path.join(self.tmp, "app", answer["png"]))[0], 600)

    @unittest.skipUnless(MAC and shutil.which("swiftc"), "WebKit and swiftc: macOS")
    def test_a_page_is_drawn_as_a_browser_as_large_as_its_room(self):
        """Beside its code, a page is laid out as a browser of the room's size shows it, the room's height too."""
        page = os.path.join(self.tmp, "index.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write("<html><body><h1>Pagination</h1><p>Every list route answers a page.</p></body></html>\n")
        self.assertEqual(media.size(media.drawn_png(page, 400, self.tmp, 900)), (400, 900))
        answer = media.picture(page, 0, 400, 200)
        self.assertEqual(answer["size"], [200, 100])                          # in points: the room's

    def test_an_old_picture_goes(self):
        old = png(os.path.join(media.app_pictures(), "old.png"), 4, 4)
        os.utime(old, (1, 1))
        media.app_pictures()
        self.assertFalse(os.path.exists(old))

    def test_no_picture_for_anything_else(self):
        self.assertEqual(media.picture("/w/notes.md", 0, 100), {"kind": None, "pages": None, "png": None,
                                                                 "size": None})


@unittest.skipUnless(MAC and shutil.which("swiftc"), "PDFKit and swiftc: macOS")
class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = tempfile.mkdtemp()               # one compile for all of them

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.cache)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, XDG_CACHE_HOME=self.cache)
        self.pdf = pdf(os.path.join(self.tmp, "two.pdf"), 2)

    def test_a_pdf_has_its_pages_each_as_large_as_it_is_shown(self):
        """Each page's size in points, a turned one's turned: the preview lays the pages out before it draws them."""
        self.assertEqual(media.pages(pdf(os.path.join(self.tmp, "turned.pdf"), 2, turned=(1,))),
                         [[612, 792], [792, 612]])

    def test_a_page_as_a_png_as_wide_as_asked(self):
        made = media.page_png(self.pdf, 1, 400, self.tmp)
        self.assertEqual(media.size(made), (400, 518))
        self.assertIsNone(media.page_png(self.pdf, 2, 400, self.tmp))       # no third page
        turned = pdf(os.path.join(self.tmp, "turned.pdf"), 2, turned=(1,))
        self.assertEqual(media.size(media.page_png(turned, 1, 400, self.tmp)), (400, 309))

    def test_a_page_made_is_kept_for_its_version(self):
        """The preview draws a page again as it scrolls: one already made as wide is taken as it is."""
        first = media.page_png(self.pdf, 0, 300, self.tmp)
        with mock.patch.object(media, "run", return_value=None):              # no drawing would work now
            self.assertEqual(media.page_png(self.pdf, 0, 300, self.tmp), first)

    def test_the_helper_is_compiled_once_and_alone(self):
        first = media.helper("pdf-pages")
        self.assertEqual(media.helper("pdf-pages"), first)
        left = [name for name in os.listdir(os.path.dirname(first)) if name.startswith("pdf-pages")]
        self.assertEqual(left, [os.path.basename(first)])

    def test_without_the_helper_the_first_page(self):
        with mock.patch.object(media, "helper", return_value=None):
            self.assertIsNone(media.pages(self.pdf))
            self.assertIsNotNone(media.size(media.page_png(self.pdf, 0, 300, self.tmp)))
            self.assertIsNone(media.page_png(self.pdf, 1, 300, self.tmp))


if __name__ == "__main__":
    unittest.main()

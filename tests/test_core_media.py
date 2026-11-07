"""Tests for core/media.py: which files the preview draws as pictures, an image as a PNG (sips), a PDF's pages as PNGs
(PDFKit, through a Swift helper compiled once), and the browser that opens them (LaunchServices' https handler)."""
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
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


def pdf(path, pages):
    """A PDF of PAGES letter pages, each a gray box, at PATH."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Kids [{' '.join(f'{3 + 2 * n} 0 R' for n in range(pages))}] /Count {pages} >>"]
    for n in range(pages):
        box = b"0.5 g 72 72 300 400 re f"
        objects += [f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * n} 0 R >>",
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
                           ("e.pdf", "pdf"), ("f.html", "html"), ("g.HTM", "html"), ("h.svg", None), ("i.py", None),
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

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HERDR_APP_HOME=os.path.join(self.tmp, "app"))

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

    def test_a_pdf_has_its_pages(self):
        self.assertEqual(media.pages(self.pdf), 2)

    def test_a_page_as_a_png_as_wide_as_asked(self):
        made = media.page_png(self.pdf, 1, 400, self.tmp)
        self.assertEqual(media.size(made)[0], 400)
        self.assertIsNone(media.page_png(self.pdf, 2, 400, self.tmp))       # no third page

    def test_the_helper_is_compiled_once_and_alone(self):
        first = media.helper()
        self.assertEqual(media.helper(), first)
        left = [name for name in os.listdir(os.path.dirname(first)) if name.startswith("pdf-pages")]
        self.assertEqual(left, [os.path.basename(first)])

    def test_without_the_helper_the_first_page(self):
        with mock.patch.object(media, "helper", return_value=None):
            self.assertIsNone(media.pages(self.pdf))
            self.assertIsNotNone(media.size(media.page_png(self.pdf, 0, 300, self.tmp)))
            self.assertIsNone(media.page_png(self.pdf, 1, 300, self.tmp))


if __name__ == "__main__":
    unittest.main()

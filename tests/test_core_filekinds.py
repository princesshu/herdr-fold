"""Tests for core/filekinds.py: what a file is by its extension, one table for the preview and Runs: an image, a PDF,
a page, an SVG, audio or video, and what Runs counts each as."""
import os
import sys
import unittest

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import filekinds  # noqa: E402


class Kinds(unittest.TestCase):
    def test_pictures_pdfs_pages_audio_and_video(self):
        for name, kind in [("a.PNG", "image"), ("b.jpeg", "image"), ("c.webp", "image"), ("d.heic", "image"),
                           ("e.pdf", "pdf"), ("f.html", "html"), ("g.HTM", "html"), ("h.svg", "svg"),
                           ("voice-over.mp3", "audio"), ("take.WAV", "audio"), ("note.m4a", "audio"),
                           ("hero-shot.mp4", "video"), ("clip.MOV", "video"), ("loop.webm", "video"), ("i.py", None),
                           ("Makefile", None), (".mp3", None)]:
            with self.subTest(name=name):
                self.assertEqual(filekinds.kind_of(name), kind)

    def test_every_picture_macos_reads(self):
        """Whatever macOS's ImageIO reads is a picture: the web's, Apple's, Adobe's, the GPU's, a camera's raw file."""
        for ext in (".avif", ".heif", ".jxl", ".jp2", ".ico", ".icns", ".psd", ".tga", ".exr", ".hdr", ".dds", ".ktx",
                    ".astc", ".pbm", ".pgm", ".ppm", ".dng", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".orf", ".rw2"):
            with self.subTest(ext=ext):
                self.assertEqual(filekinds.kind_of("a" + ext.upper()), "image")

    def test_runs_counts_an_svg_as_an_image_and_a_pdf_or_page_as_no_media(self):
        kinds = ("image", "svg", "audio", "video", "pdf", "html")
        self.assertEqual({kind: filekinds.MEDIA.get(kind) for kind in kinds},
                         {"image": "image", "svg": "image", "audio": "audio", "video": "video", "pdf": None,
                          "html": None})


if __name__ == "__main__":
    unittest.main()

# Generated from core/filekinds.py by tools/build.py: change it there, then run /usr/bin/python3 tools/build.py
"""What a file is by its extension, one table for the preview (media.py draws it) and Runs (runs.py counts what a run
made): an image, a PDF, a page, an SVG, audio or video. Kept small: each helper that reads either carries it whole."""
import os

IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".ico")     # the web's: a browser shows them
# the rest macOS's ImageIO reads (sips makes a PNG of each): Apple's, Adobe's, the GPU's, a camera's raw file
PICTURES = (".heic", ".heics", ".heif", ".hif", ".tif", ".tiff", ".jxl", ".jp2", ".j2k", ".jpf", ".jpe", ".mpo", ".cur",
            ".icns", ".psd", ".tga", ".exr", ".hdr", ".sgi", ".pict", ".pct", ".pbm", ".pgm", ".ppm", ".pnm", ".dds",
            ".ktx", ".ktx2", ".astc", ".pvr", ".dcm", ".dng", ".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf",
            ".sr2", ".raf", ".orf", ".rw2", ".pef", ".srw", ".erf", ".3fr", ".fff", ".iiq", ".mos", ".mrw", ".dcr",
            ".rwl")
AUDIO = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".aiff", ".aif", ".caf", ".ogg", ".opus")
VIDEO = (".mp4", ".mov", ".m4v", ".webm")
KINDS = {**{ext: "image" for ext in IMAGES + PICTURES}, ".pdf": "pdf", ".html": "html", ".htm": "html", ".svg": "svg",
         **{ext: "audio" for ext in AUDIO}, **{ext: "video" for ext in VIDEO}}
MEDIA = {"image": "image", "svg": "image", "audio": "audio", "video": "video"}     # what Runs counts a kind as


def kind_of(path):
    """image, pdf, html, svg (a picture that is code too), audio or video by PATH's extension, else None."""
    return KINDS.get(os.path.splitext(path)[1].lower())

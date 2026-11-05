"""Tests for remote/fetch-tool.sh: a pinned release lands in ~/.local/bin only if its SHA-256 matches the release's
checksum; a tampered or broken download never does. curl is a fake that writes the given bytes.
"""
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest

from support import stubs

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "remote", "fetch-tool.sh")
FAKE_CURL = """#!/bin/sh
echo "$*" >> "$CURL_LOG"
while [ $# -gt 0 ]; do case "$1" in -o) out=$2; shift 2 ;; *) shift ;; esac; done
if [ -n "${CURL_ASSET:-}" ]; then cp "$CURL_ASSET" "$out"; else printf 'not the real program' > "$out"; fi
"""


class FetchTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self.fakes = fakes = stubs(os.path.join(self.tmp, "stubs"), {"curl": FAKE_CURL})
        self.log = os.path.join(self.tmp, "curl-calls")
        self.env = {"PATH": f"{fakes}:/usr/bin:/bin", "CURL_LOG": self.log, "TMPDIR": self.tmp + "/"}

    def fetch(self, tool, target):
        return subprocess.run(["bash", SCRIPT, tool, target, self.bin], env=self.env, capture_output=True, text=True,
                              timeout=30)

    def test_the_program_appears_whole_by_a_rename_in_its_folder(self):
        # the checksum passes here (a fake sha256sum): this is about where the file is put, not about checking it
        asset = os.path.join(self.tmp, "starship.tar.gz")
        with tarfile.open(asset, "w:gz") as tar:
            program = tarfile.TarInfo("starship")
            program.size = len(b"#!/bin/sh\n")
            tar.addfile(program, io.BytesIO(b"#!/bin/sh\n"))
        self.env["CURL_ASSET"] = asset
        mv_log = os.path.join(self.tmp, "mv-calls")
        stubs(self.fakes, {"sha256sum": "#!/bin/sh\n"
                                        "echo 10c8eb4cb3b761d9bf59ea828444c2dab36c900b7d69a69e08814b286969df89\n",
                           "mv": '#!/bin/sh\nfor a; do from=$to; to=$a; done\n'
                                 'printf "%s|%s\\n" "$from" "$to" >> "$MV_LOG"\n'
                                 'exec /bin/mv "$@"\n'})                    # the last two: from, to
        self.env["MV_LOG"] = mv_log
        done = self.fetch("starship", "x86_64-unknown-linux-musl")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(os.access(os.path.join(self.bin, "starship"), os.X_OK))
        with open(mv_log) as f:
            source, target = f.read().splitlines()[-1].split("|")
        self.assertEqual((os.path.dirname(source), target), (self.bin, os.path.join(self.bin, "starship")))
        self.assertEqual(os.listdir(self.bin), ["starship"])                # nothing left beside it

    def test_a_download_with_the_wrong_checksum_is_not_installed(self):
        done = self.fetch("starship", "x86_64-unknown-linux-musl")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(os.listdir(self.bin), [])

    def test_it_downloads_the_pinned_release_not_latest(self):
        self.fetch("starship", "x86_64-unknown-linux-musl")
        with open(self.log) as f:
            call = f.read()
        self.assertIn("/releases/download/v1.27.0/starship-x86_64-unknown-linux-musl.tar.gz", call)
        self.assertNotIn("latest", call)

    def test_an_unknown_platform_downloads_nothing(self):
        done = self.fetch("starship", "plan9-mips")
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse(os.path.exists(self.log))

    def test_only_starship_is_fetched(self):
        # jq was for the status line, a Python script now: no download of it is pinned any more
        done = self.fetch("jq", "linux-amd64")
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse(os.path.exists(self.log))


if __name__ == "__main__":
    unittest.main()

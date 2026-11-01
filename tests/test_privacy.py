"""Privacy guard: no published file, commit, tag, branch, staged file, image (metadata, OCR text) or GitHub About holds
e-mails, IPs, MACs, home paths, secrets, AI attribution, private words, or names of this Mac, its SSH hosts or tailnet.
Test data uses placeholders only: example.com, RFC 5737 addresses, tail0000 and 100.115.92.0/23 for Tailscale."""
import hashlib
import ipaddress
import json
import os
import re
import struct
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest

from support import PACKAGE, PNG_SIGNATURE, is_webp, publishable_files, set_env

PRIVATE_WORDS = os.path.join(os.path.expanduser("~"), ".config", "herdr-fold", "private-words.txt")

EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b")
EMAIL_DOMAINS_OK = ("example.com", "example.org", "example.net", "tail0000.ts.net")
IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w.])")
# documentation ranges, loopback, and a small placeholder range for Tailscale; every other Tailscale address (the
# 100.64/10 block) and home network address is caught
IPV4_OK = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "100.115.92.0/23",
                                             "127.0.0.0/8", "0.0.0.0/32")]
TAILSCALE = shutil.which("tailscale") or "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
TAILNET_ID = re.compile(r"\btail[0-9a-f]{4,}\b")
TS_NET = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.ts\.net\b")
# a home folder: under /Users, /home or C:\\Users, in the name of Claude's project folder, and the tilde-user form
HOME_PATH = re.compile(r"/Us" r"ers/([^/\s'\"`<>]+)|/ho" r"me/([^/\s'\"`<>]+)"
                       r"|[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/)([^\\/\s'\"`<>]+)"
                       r"|(?<![A-Za-z0-9])-Us" r"ers-([A-Za-z0-9_.]+)|(?<![\w~])~([A-Za-z_][\w.-]*)(?=/)")
# a user's own temporary folder on a Mac: its path is the same for no one else
TEMP_PATH = re.compile(r"/var/fol" r"ders/[^/\s]+/[^/\s]+")
IPV6 = re.compile(r"(?<![\w:.])([0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7})(?![\w:])")
# the documentation range, loopback and unspecified
IPV6_OK = [ipaddress.ip_network(n) for n in ("2001:db8::/32", "::1/128", "::/128")]
MAC = re.compile(r"(?<![0-9A-Fa-f:-])((?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})(?![0-9A-Fa-f:-])")
MAC_OK = re.compile(r"00:00:5e:00:53:[0-9a-f]{2}|00:00:00:00:00:00")         # RFC 7042's documentation addresses
HOME_NAMES_OK = {"dev", "a", "a_b", "you", "x", "Shared", "Test"}
SECRET = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}"
                    r"|AKIA[0-9A-Z]{16}|xox[abpr]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}"
                    r"|-----BEGIN [A-Z ]*PRIVATE KEY")
SESSION = re.compile(r"/private/tmp/cla" r"ude|claude-\d{3}/|/scratch" r"pad/")
# AI attribution of any kind: a co-author or assisted-by trailer, a "generated with" or "created by" line, an AI session
# link or mark (the commit messages Claude or Codex writes for the sidebar are a feature, not a credit)
AI_TOOL = r"(?:Claude|Codex|ChatGPT|Copilot|Gemini|Cursor)"
ATTRIBUTION = re.compile(r"Co-Authored" r"-By:|Assisted" r"-By:|Generated" r" with |(?:Generated|Created)"
                         r" (?:by|with) " + AI_TOOL + r"|Claude-" r"Session|claude\.ai/(?:code|chat|share)/"
                         r"|chatgpt\.com/|noreply@anthropic\.com|noreply@openai\.com|\U0001F916", re.IGNORECASE)
# letters English has not (Latin Extended-A, the accents of other languages' alphabets): every text here is English
NOT_ENGLISH = re.compile("[\u0100-\u017f]")
PNG_TEXT_CHUNKS = {b"tEXt", b"iTXt", b"zTXt", b"eXIf"}
WEBP_META_CHUNKS = {b"EXIF", b"XMP ", b"ICCP"}


def fold(text):
    """TEXT in lowercase without its accents, whichever Unicode form it is in (macOS keeps file names decomposed)."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)).lower()


def private_words():
    """The private word list's words, this Mac's own names and the machines its SSH settings name."""
    try:
        with open(PRIVATE_WORDS, encoding="utf-8") as f:
            words = [w.strip() for w in f if w.strip() and not w.lstrip().startswith("#")]
    except OSError:
        words = []
    return [fold(w) for w in words + machine_names() + sorted(ssh_names())]


# a machine's name that says nothing about anyone (macOS calls an unnamed Mac so)
GENERIC_NAMES = {"", "localhost", "mac", "macbook", "macbook pro", "macbook air", "imac", "mac mini", "mac studio"}
# public services an SSH setting names: no one's own
SSH_PUBLIC = {"github.com", "ssh.github.com", "gitlab.com", "bitbucket.org", "ssh.dev.azure.com"}


def ssh_names(home=None):
    """The machines HOME's SSH settings name (the home folder's by default): ~/.ssh/config's hosts (no pattern) and
    their HostName, and the names in ~/.ssh/known_hosts (a hashed one says nothing); no address, no public service."""
    ssh, names = os.path.join(home or os.path.expanduser("~"), ".ssh"), set()
    try:
        with open(os.path.join(ssh, "config"), encoding="utf-8", errors="replace") as f:
            for line in f:
                key, _, value = line.strip().partition(" ")
                if key.lower() in ("host", "hostname"):
                    names.update(name for name in value.split() if not set("*?!") & set(name))
    except OSError:
        pass
    try:
        with open(os.path.join(ssh, "known_hosts"), encoding="utf-8", errors="replace") as f:
            for line in f:
                hosts = line.split(" ", 1)[0]
                if hosts and not hosts.startswith(("|", "#", "@")):
                    names.update(re.sub(r"^\[(.*)\]:\d+$", r"\1", host) for host in hosts.split(","))
    except OSError:
        pass
    def address(name):
        try:
            ipaddress.ip_address(name)
            return True
        except ValueError:
            return False
    return {name for name in names if name.lower() not in SSH_PUBLIC and not address(name)}


def machine_names():
    """This Mac's own names: its network name, its computer name and its host name, and the owner's full name where it
    is more than the account's name (nothing where there is no scutil)."""
    def ask(*argv):
        try:
            return subprocess.run(argv, capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return ""
    names = [ask("scutil", "--get", "LocalHostName"), ask("scutil", "--get", "ComputerName"), ask("hostname", "-s")]
    full = ask("id", "-F")
    if full.lower() != ask("id", "-un").lower():
        names.append(full)
    return [name for name in names if fold(name) not in GENERIC_NAMES]


def identity_ok(name, email):
    """A commit's author, committer or tagger: a GitHub noreply address, under the login it names (no real name)."""
    login = re.fullmatch(r"(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com", email)
    return bool(login) and name == login.group(1)


def tailnet_from(status):
    """(names, addresses) of a `tailscale status --json` answer, names in lowercase. A device name that is only its
    OS ("windows") or "localhost" says nothing about anyone and is left out."""
    names, addresses = set(), set()
    for device in [status.get("Self") or {}] + list((status.get("Peer") or {}).values()):
        generic = {"", "localhost", str(device.get("OS", "")).lower()}
        names.update(n for n in (str(device.get("HostName", "")).lower(),
                                 str(device.get("DNSName", "")).split(".")[0].lower()) if n not in generic)
        addresses.update(device.get("TailscaleIPs") or [])
    tailnet = status.get("CurrentTailnet") or {}
    suffix = tailnet.get("MagicDNSSuffix") or status.get("MagicDNSSuffix") or ""
    names.update(str(n).lower() for n in (tailnet.get("Name"), suffix, suffix.split(".")[0]) if n)
    for user in (status.get("User") or {}).values():
        names.update(str(n).lower() for n in (user.get("LoginName"), user.get("DisplayName")) if n)
    return sorted(names), addresses


def tailnet():
    """This machine's tailnet (nothing where Tailscale is not installed or not answering)."""
    try:
        done = subprocess.run([TAILSCALE, "status", "--json"], capture_output=True, text=True, timeout=15)
        return tailnet_from(json.loads(done.stdout))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return tailnet_from({})


def allowed_email(local, domain):
    domain = domain.lower()
    if (local, domain) == ("git", "github.com"):           # ssh remote syntax, not a mailbox
        return True
    if domain == "users.noreply.github.com":                # no mailbox: a GitHub login, public on every commit
        return True
    return domain.endswith(".example") or any(domain == ok or domain.endswith("." + ok) for ok in EMAIL_DOMAINS_OK)


def findings(text, words=(), names=(), addresses=()):
    """(line number, category) for everything personal in TEXT; a private word or a tailnet name is named by its place
    in its list, never by itself."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        found += [(n, "e-mail address") for m in EMAIL.finditer(line) if not allowed_email(m.group(1), m.group(2))]
        for m in IPV4.finditer(line):
            try:
                ip = ipaddress.ip_address(m.group(1))
            except ValueError:
                continue
            if m.group(1) in addresses:
                found.append((n, "tailnet address"))
            elif not any(ip in net for net in IPV4_OK):
                found.append((n, "IP address"))
        for m in IPV6.finditer(line):
            if sum(1 for group in m.group(1).split(":") if group) < 3:      # ::1, a slice [::2], a::b
                continue
            try:
                ip = ipaddress.IPv6Address(m.group(1))
            except ValueError:
                continue
            if not any(ip in net for net in IPV6_OK) and m.group(1).lower() not in addresses:
                found.append((n, "IP address"))
        found += [(n, "MAC address") for m in MAC.finditer(line)
                  if not MAC_OK.fullmatch(m.group(1).lower().replace("-", ":"))]
        found += [(n, "temporary folder path") for _ in TEMP_PATH.finditer(line)]
        found += [(n, "Tailscale name") for m in TAILNET_ID.finditer(line) if m.group(0) != "tail0000"]
        found += [(n, "Tailscale name") for m in TS_NET.finditer(line) if not m.group(0).endswith("tail0000.ts.net")]
        for m in HOME_PATH.finditer(line):
            if next(g for g in m.groups() if g is not None) not in HOME_NAMES_OK:
                found.append((n, "home folder path"))
        if SECRET.search(line):
            found.append((n, "secret"))
        if SESSION.search(line):
            found.append((n, "temporary session path"))
        if ATTRIBUTION.search(line):
            found.append((n, "AI attribution"))
        if NOT_ENGLISH.search(unicodedata.normalize("NFC", line)):
            found.append((n, "non-English letters"))
        low = fold(line)
        # a private word counts inside compounds too (word-archive, my_word, word2): only letters around it hide it
        found += [(n, f"private word #{i}") for i, word in enumerate(words, 1) if inside(fold(word), low)]
        found += [(n, f"tailnet name #{i}") for i, name in enumerate(names, 1) if inside(fold(name), low)]
        found += [(n, "tailnet address") for a in addresses
                  if ":" in a and re.search(r"(?<![\w:])" + re.escape(a.lower()) + r"(?![\w:])", low)]
    return found


def inside(word, low):
    """WORD in LOW with no letter right before or after it, or with an "s-" after it, as in a Mac's
    name (Names-MacBook)."""
    return bool(re.search(r"(?<![^\W\d_])" + re.escape(word) + r"(?:(?![^\W\d_])|(?=s-))", low))


def staged_blobs(root=PACKAGE):
    """{path: content} of what is staged for the next commit (it may differ from the folder: both are read)."""
    try:
        done = subprocess.run(["git", "-C", root, "diff", "--cached", "--name-only", "--diff-filter=AMR", "-z"],
                              capture_output=True)
    except OSError:                                                # no git: nothing can be staged
        return {}
    return {rel: subprocess.run(["git", "-C", root, "show", f":{rel}"], capture_output=True).stdout
            for rel in filter(None, done.stdout.decode("utf-8").split("\0") if done.returncode == 0 else [])}


def ref_names(root=PACKAGE):
    """Every branch and tag name of ROOT's repository, a lightweight tag's too: each goes public with it."""
    try:
        done = subprocess.run(["git", "-C", root, "for-each-ref", "--format=%(refname)"], capture_output=True)
    except OSError:
        return []
    return done.stdout.decode("utf-8", "replace").split() if done.returncode == 0 else []


def git(*args):
    """git's output in the package (None without git or outside a repository)."""
    try:
        done = subprocess.run(["git", "-C", PACKAGE, *args], capture_output=True)
    except OSError:
        return None
    return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None


def png_metadata(data):
    """The text and EXIF chunks of a PNG image: metadata that can hold names, paths or places."""
    chunks, at = [], len(PNG_SIGNATURE)
    while at + 8 <= len(data):
        size, kind = struct.unpack(">I4s", data[at:at + 8])
        if kind in PNG_TEXT_CHUNKS:
            chunks.append(kind.decode("ascii"))
        at += 12 + size
    return chunks


def webp_metadata(data):
    """The EXIF, XMP and color profile chunks of a WebP image: metadata that can hold names, paths, places
    or devices."""
    chunks, at = [], 12
    while at + 8 <= len(data):
        kind, size = data[at:at + 4], struct.unpack("<I", data[at + 4:at + 8])[0]
        if kind in WEBP_META_CHUNKS:
            chunks.append(kind.decode("ascii"))
        at += 8 + size + size % 2
    return chunks


OCR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr.swift")
IMAGES = (".png", ".webp", ".jpg", ".jpeg", ".gif")
# what was read off an image before, by its content: a run reads only what changed (macOS empties the folder itself)
OCR_CACHE = os.path.join(tempfile.gettempdir(), "herdr-fold-ocr")


def ocr_program():
    """ocr.swift compiled, once for each version of it."""
    with open(OCR, "rb") as f:
        program = os.path.join(OCR_CACHE, "ocr-" + hashlib.sha256(f.read()).hexdigest()[:16])
    if not os.path.exists(program):
        os.makedirs(OCR_CACHE, exist_ok=True)
        subprocess.run(["swiftc", "-O", OCR, "-o", program + ".new"], check=True, capture_output=True)
        os.replace(program + ".new", program)
    return program


def image_texts(paths):
    """{(path, frame): text} of every frame of the images at PATHS (relative to the package, or full), as macOS's
    text recognition reads them."""
    program, texts = ocr_program(), {}
    for rel in paths:
        with open(os.path.join(PACKAGE, rel), "rb") as f:
            cached = os.path.join(OCR_CACHE, hashlib.sha256(f.read()).hexdigest() + ".json")
        if not os.path.exists(cached):
            done = subprocess.run([program, os.path.join(PACKAGE, rel)], capture_output=True, text=True, check=True)
            with open(cached + ".new", "w", encoding="utf-8") as f:
                json.dump([json.loads(line)["text"] for line in done.stdout.splitlines()], f)
            os.replace(cached + ".new", cached)
        with open(cached, encoding="utf-8") as f:
            texts.update({(rel, frame): text for frame, text in enumerate(json.load(f))})
    return texts


def image_problems(where, data):
    """What is wrong with DATA as an image of the repository (None: it is no image)."""
    if data.startswith(PNG_SIGNATURE):
        return [f"{where}: PNG metadata chunk {chunk}" for chunk in png_metadata(data)]
    if is_webp(data):
        return [f"{where}: WebP metadata chunk {chunk}" for chunk in webp_metadata(data)]
    return None


class Privacy(unittest.TestCase):
    def test_the_private_word_list_lives_outside_the_repo(self):
        if not os.path.exists(PRIVATE_WORDS):
            self.skipTest(f"no private word list at {PRIVATE_WORDS} (the pattern checks still run)")
        self.assertFalse(os.path.realpath(PRIVATE_WORDS).startswith(os.path.realpath(PACKAGE) + os.sep))

    def test_no_file_holds_personal_data(self):
        words, (names, addresses), problems = private_words(), tailnet(), []
        for rel in publishable_files():
            problems += [f"{rel} (its path): {what}" for _, what in findings(rel, words, names, addresses)]
            with open(os.path.join(PACKAGE, rel), "rb") as f:
                data = f.read()
            image = image_problems(rel, data)
            if image is not None:
                problems += image
                continue
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                problems.append(f"{rel}: binary file (only PNG and WebP images without metadata are allowed)")
                continue
            problems += [f"{rel}:{n}: {what}" for n, what in findings(text, words, names, addresses)]
        self.assertEqual(problems, [], "\n" + "\n".join(problems))

    def test_no_commit_holds_personal_data(self):
        """Every commit and tag can be read once the repository is public: its author, committer and tagger (a GitHub
        login alone, at its noreply address) and everything it holds."""
        commits = git("rev-list", "--all")
        if commits is None:
            self.skipTest("not a git repository")
        words, (names, addresses), problems = private_words(), tailnet(), []
        for sha in commits.split():
            name, email, committer, address = git("show", "-s", "--format=%an%x00%ae%x00%cn%x00%ce", sha).split("\0")
            if not (identity_ok(name, email) and identity_ok(committer, address.strip())):
                problems.append(f"{sha[:7]}: an author or committer that is not a GitHub login at its noreply address")
            problems += [f"{sha[:7]}:{n}: {what}"
                         for n, what in findings(git("show", "--format=%B", sha), words, names, addresses)]
        for ref in ref_names():
            problems += [f"{ref}: {what}" for _, what in findings(ref, words, names, addresses)]
        for tag in (git("tag", "--list") or "").split():
            if (git("cat-file", "-t", tag) or "").strip() != "tag":
                continue                                          # a lightweight tag: only its commit, read above
            text = git("cat-file", "-p", tag)
            tagger = re.search(r"^tagger (.*) <([^>]*)>", text, re.MULTILINE)
            if tagger and not identity_ok(*tagger.groups()):
                problems.append(f"tag {tag}: a tagger that is not a GitHub login at its noreply address")
            problems += [f"tag {tag}:{n}: {what}" for n, what in findings(text, words, names, addresses)]
        self.assertEqual(problems, [], "\n" + "\n".join(problems))

    def test_no_file_in_the_history_is_an_image_with_metadata(self):
        """A file deleted since is still in the history: every binary file ever committed is a PNG or WebP image without
        metadata."""
        objects = git("rev-list", "--all", "--objects")
        if objects is None:
            self.skipTest("not a git repository")
        shas = "".join(line.split(" ", 1)[0] + "\n" for line in objects.splitlines())
        kinds = subprocess.run(["git", "-C", PACKAGE, "cat-file", "--batch-check=%(objectname) %(objecttype)"],
                               input=shas.encode(), capture_output=True, check=True).stdout.decode().split("\n")
        blobs = "".join(line.split()[0] + "\n" for line in kinds if line.endswith(" blob"))
        out = subprocess.run(["git", "-C", PACKAGE, "cat-file", "--batch"], input=blobs.encode(), capture_output=True,
                             check=True).stdout
        problems, at = [], 0
        while at < len(out):
            header, _, rest = out[at:].partition(b"\n")
            sha, _, size = header.decode().split()
            data = rest[:int(size)]
            at += len(header) + 1 + int(size) + 1
            image = image_problems(sha[:7], data)
            if image is not None:
                problems += image
                continue
            try:
                data.decode("utf-8-sig")
            except UnicodeDecodeError:
                problems.append(f"{sha[:7]}: binary file (only PNG and WebP images without metadata are allowed)")
        self.assertEqual(problems, [], "\n" + "\n".join(problems))

    def test_nothing_staged_holds_personal_data(self):
        words, (names, addresses), problems = private_words(), tailnet(), []
        for rel, blob in staged_blobs().items():
            image = image_problems(f"{rel} (staged)", blob)
            if image is not None:
                problems += image
                continue
            try:
                text = blob.decode("utf-8-sig")
            except UnicodeDecodeError:
                problems.append(f"{rel} (staged): neither text nor an image it can read")
                continue
            problems += [f"{rel}:{n} (staged): {what}" for n, what in findings(text, words, names, addresses)]
        self.assertEqual(problems, [], "\n" + "\n".join(problems))


@unittest.skipUnless(sys.platform == "darwin" and shutil.which("swiftc"),
                     "reading the text an image shows needs macOS's text recognition and swiftc")
class Images(unittest.TestCase):
    """What an image shows, every frame of an animation: a screen recording once showed a whole command line, with
    the account's name in a path."""

    def test_no_image_shows_personal_data(self):
        texts = image_texts([rel for rel in publishable_files() if rel.lower().endswith(IMAGES)])
        self.assertTrue(any(texts.values()), "no text read off any image: the check would pass for nothing")
        words, (names, addresses) = private_words(), tailnet()
        problems = [f"{rel} frame {frame}: {what}" for (rel, frame), text in texts.items()
                    for _, what in findings(text, words, names, addresses)]
        self.assertEqual(problems, [], "\n" + "\n".join(problems))

    def test_the_text_an_image_shows_is_read(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        shot = os.path.join(tmp, "shot.png")
        subprocess.run([ocr_program(), "--draw", "cd /Us" + "ers/someone/app", shot], check=True)
        texts = image_texts([shot])                                   # a full path: outside the package
        self.assertEqual([what for text in texts.values() for _, what in findings(text)], ["home folder path"])


def github_about(root=PACKAGE):
    """(OWNER/NAME, its About as GitHub shows it: the description, the homepage, the topics), or (None, the reason
    it cannot be read: no remote on GitHub, no gh, no answer)."""
    remote = git("remote", "get-url", "origin") if root == PACKAGE else None
    match = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$", (remote or "").strip())
    if not match:
        return None, "the repository is on no GitHub remote"
    if not shutil.which("gh"):
        return None, "no gh to ask GitHub"
    try:
        done = subprocess.run(["gh", "repo", "view", match.group(1), "--json",
                               "description,homepageUrl,repositoryTopics"], capture_output=True, text=True, timeout=30)
        about = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        about = None
    if not isinstance(about, dict):
        return None, "GitHub did not answer (offline, signed out, or no such repository)"
    topics = " ".join(str(t.get("name", "")) for t in about.get("repositoryTopics") or [] if isinstance(t, dict))
    return match.group(1), "\n".join([str(about.get("description") or ""), str(about.get("homepageUrl") or ""), topics])


class Hooks(unittest.TestCase):
    """With core.hooksPath on .githooks, nothing personal gets into a commit: its files before it, its message after."""

    def message_hook(self, message):
        with tempfile.NamedTemporaryFile("w", suffix=".msg", delete=False) as f:
            f.write(message)
        self.addCleanup(os.remove, f.name)
        return subprocess.run([os.path.join(PACKAGE, ".githooks", "commit-msg"), f.name], cwd=PACKAGE,
                              capture_output=True, text=True, timeout=120)

    def test_a_personal_commit_message_is_stopped(self):
        done = self.message_hook("fix: mail me at someone" + "@gmail.com\n")
        self.assertEqual(done.returncode, 1)
        self.assertIn("e-mail address", done.stdout + done.stderr)

    def test_a_plain_commit_message_goes_through(self):
        self.assertEqual(self.message_hook("fix: name the leftover files\n").returncode, 0)

    def test_before_a_commit_the_privacy_check_runs(self):
        # not run here: the privacy check would start itself again
        hook = os.path.join(PACKAGE, ".githooks", "pre-commit")
        self.assertTrue(os.access(hook, os.X_OK))
        with open(hook, encoding="utf-8") as f:
            self.assertIn("-p test_privacy.py", f.read())


class GitHub(unittest.TestCase):
    """What GitHub shows beside the code, set on its page, not in a file: the About (description, homepage, topics)."""

    def test_the_about_holds_nothing_personal(self):
        repo, about = github_about()
        if repo is None:
            self.skipTest(about)
        words, (names, addresses) = private_words(), tailnet()
        problems = [f"{repo} About:{n}: {what}" for n, what in findings(about, words, names, addresses)]
        self.assertEqual(problems, [], "\n" + "\n".join(problems))


class Sources(unittest.TestCase):
    """What the guard reads: the files that would be published — also without git — and what is staged for a commit."""

    def test_without_git_it_walks_the_folder(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty)
        set_env(self, PATH=empty)                                      # no git anywhere on PATH
        files = publishable_files()
        self.assertIn("install.sh", files)
        self.assertFalse([rel for rel in files if rel.startswith(".git" + os.sep)])

    def test_staged_content_is_read_too(self):
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        git = ["git", "-C", repo, "-c", "user.name=dev", "-c", "user.email=dev@example.com"]
        subprocess.run(git + ["init", "-q"], check=True)
        with open(os.path.join(repo, "notes.txt"), "w") as f:
            f.write("token ghp" + "_" + "a" * 30 + "\n")
        subprocess.run(git + ["add", "notes.txt"], check=True)
        with open(os.path.join(repo, "notes.txt"), "w") as f:
            f.write("nothing here\n")                                 # fixed in the folder, not in what is staged
        self.assertEqual({rel: [what for _, what in findings(blob.decode(), [])]
                          for rel, blob in staged_blobs(repo).items()}, {"notes.txt": ["secret"]})

    def test_a_staged_image_is_read_too(self):
        # its metadata as staged: the folder's copy may already be clean
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
        chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + b"\0\0\0\0"      # noqa: E731
        png = PNG_SIGNATURE + chunk(b"IHDR", b"\0" * 13) + chunk(b"tEXt", b"Author\0someone") + chunk(b"IEND", b"")
        with open(os.path.join(repo, "shot.png"), "wb") as f:
            f.write(png)
        subprocess.run(["git", "-C", repo, "add", "shot.png"], check=True)
        with open(os.path.join(repo, "shot.png"), "wb") as f:
            f.write(PNG_SIGNATURE + chunk(b"IHDR", b"\0" * 13) + chunk(b"IEND", b""))
        blobs = staged_blobs(repo)
        self.assertEqual(image_problems("shot.png", blobs["shot.png"]), ["shot.png: PNG metadata chunk tEXt"])

    def test_branch_and_tag_names_are_read(self):
        # a name goes public with its branch or tag, a lightweight tag's too
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        git = ["git", "-C", repo, "-c", "user.name=dev", "-c", "user.email=dev@example.com"]
        for args in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "start"],
                     ["branch", "fix-for-sample-word"], ["tag", "v1-sample-word"]):
            subprocess.run(git + args, check=True)
        found = {ref: [what for _, what in findings(ref, ["sample-word"])] for ref in ref_names(repo)}
        self.assertEqual(found, {"refs/heads/fix-for-sample-word": ["private word #1"], "refs/heads/main": [],
                                 "refs/tags/v1-sample-word": ["private word #1"]})


class Patterns(unittest.TestCase):
    """The guard itself: what it catches and what it lets through."""

    def categories(self, text, words=(), **tailnet):
        return sorted({what for _, what in findings(text, words, **tailnet)})

    def test_catches_real_looking_data(self):
        # the samples are put together from pieces: this file goes through the same scan, with no exceptions
        self.assertEqual(self.categories("mail me: someone" + "@gmail.com"), ["e-mail address"])
        self.assertEqual(self.categories("ssh 8.8." + "8.8"), ["IP address"])
        self.assertEqual(self.categories("HostName box.tail" + "ab12cd.ts" + ".net"), ["Tailscale name"])
        self.assertEqual(self.categories("cd /Us" + "ers/someone/project"), ["home folder path"])
        self.assertEqual(self.categories("C:\\\\Us" + "ers\\\\someone\\\\app"), ["home folder path"])
        self.assertEqual(self.categories("token ghp" + "_" + "a" * 30), ["secret"])
        self.assertEqual(self.categories("see /private/tmp/cla" + "ude-501/x"), ["temporary session path"])
        self.assertEqual(self.categories("Co-Authored" + "-By: Bot <bot@example.com>"), ["AI attribution"])
        self.assertEqual(self.categories("the Sample-Word repo", ["sample-word"]), ["private word #1"])

    def test_catches_a_home_folder_written_otherwise(self):
        # Claude's project folders named after a home folder, a user's own temporary folder, the tilde-user form
        self.assertEqual(self.categories("~/.claude/projects/-Us" + "ers-someone-app"), ["home folder path"])
        self.assertEqual(self.categories("/var/fol" + "ders/_r/5yb3xbps/T/tmp1"), ["temporary folder path"])
        self.assertEqual(self.categories("cd ~some" + "one/app"), ["home folder path"])

    def test_catches_an_ipv6_or_a_mac_address(self):
        self.assertEqual(self.categories("ssh fd7a:115c:a1e0:" + "ab12::1"), ["IP address"])
        self.assertEqual(self.categories("addr fe80::1c2b:" + "3aff:fe4d:5e6f"), ["IP address"])
        self.assertEqual(self.categories("ether 3c:22:fb:" + "12:34:56"), ["MAC address"])

    def test_lets_placeholders_through(self):
        self.assertEqual(self.categories("root@alpha.example own@example.com git@github.com:org/repo"), [])
        self.assertEqual(self.categories("HostName 192.0.2.10 100.115.92.5 127.0.0.1 version 1.141.2"), [])
        self.assertEqual(self.categories("dev@mac-mini.tail0000.ts.net"), [])
        self.assertEqual(self.categories(r"C:\\Users\\dev\\app /home/dev/project /Users/a_b"), [])
        self.assertEqual(self.categories("1234567+dev" + "@users.noreply.github.com"), [])   # a login, no mailbox
        self.assertEqual(self.categories("-Users-dev-app -Users-a-b-my-repo ~dev/app ~/x ~~gone~~"), [])
        self.assertEqual(self.categories("2001:db8::1 ::1 x[::2] 12:30:45 std::vector 00:00:5e:00:53:01"), [])

    def test_a_private_word_inside_a_compound_is_caught(self):
        for text in ("sample-word-archive", "my-sample-word", "sample-word_v2", "sample-word2", "Sample-Word.md"):
            self.assertEqual(self.categories(text, ["sample-word"]), ["private word #1"], text)
        self.assertEqual(self.categories("unsample-wordy", ["sample-word"]), [])

    def test_an_sk_inside_a_word_is_no_secret(self):
        self.assertEqual(self.categories("the task" + "-runner-config-for-every-project"), [])
        self.assertEqual(self.categories("key s" + "k-" + "a" * 24), ["secret"])

    def test_a_tailnet_name_is_caught(self):
        self.assertEqual(self.categories("ssh dev@box-one", names=["box-one"]), ["tailnet name #1"])

    def test_a_tailnet_address_is_caught_even_where_placeholders_are_allowed(self):
        self.assertEqual(self.categories("HostName 100.115.92.6", addresses={"100.115.92.6"}), ["tailnet address"])
        self.assertEqual(self.categories("HostName 100.115.92.60", addresses={"100.115.92.6"}), [])
        v6 = "2001:db8::a1"                                       # a placeholder: caught as the tailnet's own
        self.assertEqual(self.categories("ping " + v6, addresses={v6}), ["tailnet address"])

    def test_a_real_tailscale_address_is_caught(self):
        self.assertEqual(self.categories("HostName 100.101." + "7.42"), ["IP address"])

    def test_a_home_network_address_is_caught(self):
        self.assertEqual(self.categories("ssh dev@10.0." + "0.12"), ["IP address"])

    def test_any_ai_tool_attribution_is_caught(self):
        for tool in ("ChatGPT", "Copilot", "Gemini", "Cursor", "Claude Code"):
            self.assertEqual(self.categories("Generated" + " with " + tool), ["AI attribution"], tool)
        self.assertEqual(self.categories("Co-authored" + "-by: Copilot <x@example.com>"), ["AI attribution"])
        for line in ("Generated" + " by Claude Code", "Created" + " with Codex", "Assisted" + "-by: Claude",
                     "https://claude" + ".ai/code/session_01abc", "https://claude" + ".ai/chat/5e1f",
                     "https://chatgpt" + ".com/codex/tasks/task_e_1"):
            self.assertEqual(self.categories(line), ["AI attribution"], line)

    def test_the_product_names_alone_are_no_attribution(self):
        self.assertEqual(self.categories("a message written by Claude or Codex from the staged changes"), [])

    def test_a_private_word_is_caught_in_either_unicode_form(self):
        # macOS keeps file names (and often pasted text) decomposed: the accent as a letter of its own
        composed, decomposed = "s\u00e1mple", "sa\u0301mple"
        self.assertEqual(self.categories("the " + decomposed + " repo", [composed]), ["private word #1"])
        self.assertEqual(self.categories("the " + composed + " repo", [decomposed]), ["private word #1"])
        self.assertEqual(self.categories("o" + "\u030b"), ["non-English letters"])

    def test_the_ssh_settings_name_the_machines_this_mac_reaches(self):
        # its config's hosts and their addresses, the machines it has a key of: names that are someone's own
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        os.makedirs(os.path.join(home, ".ssh"))
        with open(os.path.join(home, ".ssh", "config"), "w") as f:
            f.write("Host *\n  AddKeysToAgent yes\nHost nas-box web-?\n  HostName nas.home.lan\n"
                    "Host github.com\n  HostName github.com\n")
        with open(os.path.join(home, ".ssh", "known_hosts"), "w") as f:
            f.write("build-01,192.0.2.10 ssh-ed25519 AAAA\n[vault.lan]:2222 ssh-ed25519 AAAA\n"
                    "|1|hashed= ssh-ed25519 AAAA\ngithub.com ssh-ed25519 AAAA\n")
        self.assertEqual(sorted(ssh_names(home)), ["build-01", "nas-box", "nas.home.lan", "vault.lan"])

    def test_a_private_word_in_a_macs_name_is_caught(self):
        # the Mac's default name: the owner's name with 's, as Sample-Words-MacBook-Pro
        self.assertEqual(self.categories("Sample-Words-MacBook-Pro.local", ["sample-word"]), ["private word #1"])

    def test_a_commit_identity_is_a_github_login_alone(self):
        login = "60492654+princesshu" + "@users.noreply.github.com"
        self.assertTrue(identity_ok("princesshu", login))
        self.assertFalse(identity_ok("Jane Roe", login))                # a real name beside the noreply address
        self.assertFalse(identity_ok("princesshu", "someone" + "@gmail.com"))
        self.assertFalse(identity_ok("dev", "dev@example.com"))

    def test_letters_english_has_not_are_caught(self):
        # any of the Latin Extended-A block, in either case, is enough; an e with an acute (Rosé Pine) is not in it
        for letter in ("\u0100", "\u0141", "\u0151", "\u0171", "\u017f"):
            self.assertEqual(self.categories("the key: x" + letter + "y"), ["non-English letters"], letter)
        self.assertEqual(self.categories("Ros\u00e9 Pine"), [])

    def test_webp_metadata_is_found(self):
        def chunk(kind, body):
            return kind + struct.pack("<I", len(body)) + body + (b"\0" if len(body) % 2 else b"")
        def webp(*chunks):
            body = b"WEBP" + b"".join(chunks)
            return b"RIFF" + struct.pack("<I", len(body)) + body
        self.assertEqual(webp_metadata(webp(chunk(b"VP8X", b"\0" * 10), chunk(b"VP8L", b"x" * 5),
                                            chunk(b"EXIF", b"Author someone"), chunk(b"XMP ", b"<x/>"))),
                         ["EXIF", "XMP "])
        self.assertEqual(webp_metadata(webp(chunk(b"VP8L", b"x" * 5))), [])

    def test_png_metadata_is_found(self):
        def chunk(kind, body):
            return struct.pack(">I4s", len(body), kind) + body + b"\0\0\0\0"
        image = PNG_SIGNATURE + chunk(b"IHDR", b"\0" * 13) + chunk(b"tEXt", b"Author\0someone") + chunk(b"IEND", b"")
        self.assertEqual(png_metadata(image), ["tEXt"])


class Tailnet(unittest.TestCase):
    """The machine's own tailnet: every device's names and addresses, the tailnet's name and DNS suffix, its users'
    names are private, with no word list to keep up."""
    STATUS = {"MagicDNSSuffix": "tail0000.ts.net",
              "CurrentTailnet": {"Name": "dev@example.com", "MagicDNSSuffix": "tail0000.ts.net"},
              "User": {"1": {"LoginName": "dev@example.com", "DisplayName": "Dev Example"}},
              "Self": {"HostName": "Dev's Laptop", "DNSName": "dev-laptop.tail0000.ts.net.", "OS": "macOS",
                       "TailscaleIPs": ["100.115.92.5"]},
              "Peer": {"a": {"HostName": "windows", "DNSName": "windows.tail0000.ts.net.", "OS": "windows",
                             "TailscaleIPs": ["100.115.92.6"]},
                       "b": {"HostName": "localhost", "DNSName": "dev-phone.tail0000.ts.net.", "OS": "iOS",
                             "TailscaleIPs": ["100.115.92.7"]}}}

    def test_names_and_addresses_come_from_every_device(self):
        names, addresses = tailnet_from(self.STATUS)
        self.assertEqual(names, ["dev example", "dev's laptop", "dev-laptop", "dev-phone", "dev@example.com",
                                 "tail0000", "tail0000.ts.net"])
        self.assertEqual(addresses, {"100.115.92.5", "100.115.92.6", "100.115.92.7"})

    def test_a_name_that_is_only_the_os_or_localhost_says_nothing(self):
        names, _ = tailnet_from(self.STATUS)
        self.assertNotIn("windows", names)
        self.assertNotIn("localhost", names)

    def test_without_tailscale_there_is_nothing_to_add(self):
        self.assertEqual(tailnet_from({}), ([], set()))


if __name__ == "__main__":
    unittest.main()

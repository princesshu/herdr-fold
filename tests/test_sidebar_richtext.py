"""Tests for the sidebar plugin's richtext.py: Markdown as HTML (only web and mail links kept) and the clipboard writer
that puts it beside the plain text, on a named pasteboard, never the general one."""
import os
import re
import subprocess
import sys
import time
import unittest
import uuid

from support import SRC, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import richtext as rt  # noqa: E402


class MarkdownToHtml(unittest.TestCase):
    def test_table(self):
        html = rt.markdown_to_html("| A | B |\n|---|---|\n| **x** | y |")
        self.assertIn("<table", html)
        self.assertIn("<th>A</th>", html)
        self.assertIn("<td><strong>x</strong></td>", html)

    def test_list_bold_code_and_link(self):
        html = rt.markdown_to_html("- **a** `b` [c](https://d.example/)")
        self.assertIn("<ul>", html)
        self.assertIn("<strong>a</strong>", html)
        self.assertIn("<code>b</code>", html)
        self.assertIn('<a href="https://d.example/">c</a>', html)

    def test_link_with_an_ampersand_is_escaped_once(self):
        html = rt.markdown_to_html("[t](https://a.example/?x=1&y=2)")
        self.assertIn('href="https://a.example/?x=1&amp;y=2"', html)

    def test_a_bare_address_cannot_add_an_attribute(self):
        # a reply's text: the address ends at a quote, which would otherwise close href and start an attribute
        html = rt.markdown_to_html('see https://a.example/"onmouseover="alert(1) and https://b.example/?x=1&y=2')
        self.assertIn('<a href="https://a.example/">https://a.example/</a>"onmouseover="alert(1)', html)
        self.assertIn('href="https://b.example/?x=1&amp;y=2"', html)

    def test_no_pass_writes_into_an_address_another_one_made(self):
        # an address inside a link's target, a code span inside an address: each would end up inside href
        for md in ("[t](https://a.example/?u=https://b.example/onmouseover=alert(1)//)",
                   'https://x.example/`a" onmouseover="alert(1)`', "https://y.example/a_b_c and _d_"):
            html = rt.markdown_to_html(md)
            hrefs = re.findall(r'href="([^"]*)"', html)
            self.assertTrue(hrefs, md)
            self.assertFalse([h for h in hrefs if "<" in h or "onmouseover" in h.split("?")[0]], (md, html))
            self.assertEqual(html.count("<a "), html.count("</a>"), html)
            self.assertNotIn('onmouseover="', html.replace('onmouseover=&quot;', ""), md)

    def test_a_long_line_of_unclosed_marks_is_quick(self):
        # each * or _ looked for its closing one to the end of the line: a long reply took minutes
        for mark in ("*a ", "_a "):
            started = time.perf_counter()
            rt.markdown_to_html(mark * 20000)
            self.assertLess(time.perf_counter() - started, 1.0, mark)
        self.assertIn("<em>b</em> and <strong>c</strong>", rt.markdown_to_html("*b* and **c**"))

    def test_only_web_and_mail_links_stay_links(self):
        html = rt.markdown_to_html("[a](javascript:alert(1)) [b](mailto:dev@example.com) [c](data:text/html,x) "
                                   "[d](JavaScript&#58;void) [e](https://e.example/)")
        for scheme in ("javascript", "data", "JavaScript"):
            self.assertNotIn('href="' + scheme, html)
        self.assertIn('<a href="mailto:dev@example.com">b</a>', html)
        self.assertIn('<a href="https://e.example/">e</a>', html)
        self.assertIn("a", html.split("<a ")[0])                         # the text of a dropped link stays

    def test_code_block(self):
        self.assertIn("<pre><code>x = 1</code></pre>", rt.markdown_to_html("```python\nx = 1\n```"))


def pasteboard(name, action, text=""):
    """Test helper: set / read a named pasteboard (its string, or the list of its types)."""
    script = """
ObjC.import('AppKit');
function run(argv) {
  const pb = $.NSPasteboard.pasteboardWithName(argv[0]);
  if (argv[1] === 'set') { pb.clearContents; pb.setStringForType($(argv[2]), $.NSPasteboardTypeString); return ''; }
  if (argv[1] === 'types') { return ObjC.deepUnwrap(pb.types).join(','); }
  if (argv[1] === 'release') { pb.releaseGlobally; return ''; }
  return ObjC.unwrap(pb.stringForType($.NSPasteboardTypeString)) || '';
}"""
    return subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", script, name, action, text],
                          capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(sys.platform == "darwin", "the clipboard exists on macOS only")
class CopyRich(unittest.TestCase):
    def setUp(self):
        self.name = "herdr-test-" + uuid.uuid4().hex
        set_env(self, HERDR_COPY_PASTEBOARD=self.name)
        self.addCleanup(pasteboard, self.name, "release")

    def test_upgrades_when_the_clipboard_still_holds_the_selection(self):
        pasteboard(self.name, "set", "Done.")
        self.assertTrue(rt.copy_rich("**Done.**", "Done."))
        self.assertIn("public.html", pasteboard(self.name, "types"))
        self.assertEqual(pasteboard(self.name, "get"), "Done.")

    def test_leaves_a_newer_copy_alone(self):
        pasteboard(self.name, "set", "something else")
        self.assertFalse(rt.copy_rich("**Done.**", "Done."))
        self.assertNotIn("public.html", pasteboard(self.name, "types"))
        self.assertEqual(pasteboard(self.name, "get"), "something else")


if __name__ == "__main__":
    unittest.main()

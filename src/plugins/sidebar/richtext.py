"""Markdown on the clipboard as HTML and RTF beside the plain text, so Docs, Mail, Word or Slack paste it formatted;
macOS only (osascript). For Copy conversation and herdr-fold's formatted copy; HERDR_COPY_PASTEBOARD=<name> (tests)
writes to a named pasteboard."""
import html
import json
import os
import re
import subprocess
import urllib.parse

# Only web and mail links stay links: a javascript:, data: or file: target in a reply would reach the pasted document
LINK_SCHEMES = ("http", "https", "mailto")


def link(m):
    """A Markdown link [text](target) in escaped text: its target is unescaped first, so its & becomes &amp; once, not
    &amp;amp;; a target of another kind leaves only the text."""
    target = html.unescape(m.group(2))
    if urllib.parse.urlsplit(target).scheme.lower() not in LINK_SCHEMES:
        return m.group(1)
    return f'<a href="{html.escape(target)}">{m.group(1)}</a>'


def inline(text):
    """One line's Markdown as HTML. What each pass makes (a code span, a link, a bare address's link) is set aside as a
    placeholder and put back at the end, so no later pass writes into it: an address inside a link's target, a code
    span or an underscore inside an address would otherwise land inside href."""
    made = []

    def aside(part):
        made.append(part)
        return f"\x00{len(made) - 1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: aside(f"<code>{html.escape(m.group(1))}</code>"), text.replace("\x00", ""))
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^\s\x00]+?)\)", lambda m: aside(link(m)), text)
    # a bare address ends at a quote too: one would close href and open an attribute of the reply's choosing
    text = re.sub(r'\b(https?://[^\s<)"\x00]+[^\s<).,;:!?"\x00])',
                  lambda m: aside(f'<a href="{m.group(1)}">{m.group(1)}</a>'), text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # emphasis holds no mark of its own kind: each mark would look for its closing one to the end of the line, and a
    # long reply with many took minutes
    text = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(?!\s)([^_]+?)(?<!\s)_(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)
    while "\x00" in text:                       # a link's text may hold a code span: put back in turn
        text = re.sub("\x00(\\d+)\x00", lambda m: made[int(m.group(1))], text)
    return text


def table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows
             if not re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", r)]
    head, body = cells[0], cells[1:]
    out = ['<table border="1" cellpadding="4" style="border-collapse:collapse">',
           "<tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"]
    out += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body]
    return "\n".join(out + ["</table>"])


def markdown_to_html(md):
    lines, out, i = md.splitlines(), [], 0
    para, lists = [], []            # lists: stack of open lists (tag, indent); a sublist goes into its parent <li>

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    def close_lists(indent=-1):
        while lists and lists[-1][1] > indent:
            tag, _ = lists.pop()
            out.append(f"</{tag}>" + ("</li>" if lists else ""))

    while i < len(lines):
        line = lines[i]
        fence = re.match(r"\s*(```|~~~)", line)
        heading = re.match(r"(#{1,6})\s+(.*)", line)
        item = re.match(r"(\s*)([-*+]|\d+[.)])\s+(.*)", line)
        if fence:
            flush(); close_lists()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence.group(1)):
                code.append(lines[i]); i += 1
            out.append("<pre><code>" + html.escape("\n".join(code), quote=False) + "</code></pre>")
        elif not line.strip():
            flush()
        elif heading:
            flush(); close_lists()
            out.append(f"<h{len(heading.group(1))}>{inline(heading.group(2))}</h{len(heading.group(1))}>")
        elif re.fullmatch(r"\s*([-*_])(\s*\1){2,}\s*", line):
            flush(); close_lists(); out.append("<hr>")
        elif (line.lstrip().startswith("|") and i + 1 < len(lines)
              and re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", lines[i + 1])):
            flush(); close_lists()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i]); i += 1
            out.append(table(rows)); continue
        elif line.lstrip().startswith(">"):
            flush(); close_lists()
            quote = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quote.append(lines[i].lstrip()[1:].lstrip()); i += 1
            out.append("<blockquote>" + markdown_to_html("\n".join(quote)) + "</blockquote>"); continue
        elif item:
            flush()
            indent, tag = len(item.group(1)), "ol" if item.group(2)[0].isdigit() else "ul"
            close_lists(indent)
            if lists and lists[-1][1] == indent and lists[-1][0] != tag:   # bullets turn into numbers (or vice versa)
                old, _ = lists.pop()
                out.append(f"</{old}>" + ("</li>" if lists else ""))
            if not lists or lists[-1][1] < indent:
                if lists:                   # sublist: the parent <li> stays open and closes with the list
                    out[-1] = out[-1][:-5] if out[-1].endswith("</li>") else out[-1]
                out.append(f"<{tag}>"); lists.append((tag, indent))
            out.append(f"<li>{inline(item.group(3))}</li>")
        elif lists and line.startswith(" "):
            out[-1] = out[-1][:-5] + " " + inline(line.strip()) + "</li>"   # continuation line in the list item
        else:
            close_lists(); para.append(line.strip())
        i += 1
    flush(); close_lists()
    return "\n".join(out)


# --- the clipboard: HTML + RTF + plain text at once

JXA = r"""
ObjC.import('AppKit');
function run() {
  const input = $.NSString.alloc.initWithDataEncoding($.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile,
    $.NSUTF8StringEncoding);
  const o = JSON.parse(ObjC.unwrap(input));
  const pb = o.name ? $.NSPasteboard.pasteboardWithName(o.name) : $.NSPasteboard.generalPasteboard;
  if (ObjC.unwrap(pb.stringForType($.NSPasteboardTypeString)) !== o.text) return 'skip';
  const data = $(o.html).dataUsingEncoding($.NSUTF8StringEncoding);
  const attr = $.NSAttributedString.alloc.initWithHTMLDocumentAttributes(data, null);
  pb.clearContents;
  pb.setStringForType($(o.html), $.NSPasteboardTypeHTML);
  if (attr && !attr.isNil()) pb.setDataForType(attr.RTFFromRangeDocumentAttributes($.NSMakeRange(0, attr.length), $()),
    $.NSPasteboardTypeRTF);
  pb.setStringForType($(o.text), $.NSPasteboardTypeString);
  return 'ok';
}
"""


def copy_rich(markdown, plain):
    """To the clipboard: the Markdown as HTML and RTF, plus `plain` (the selected text) as plain text — but only if the
    clipboard still holds exactly `plain` (you have not copied anything else meanwhile). True if it wrote."""
    body = markdown_to_html(markdown)
    document = ('<html><head><meta charset="utf-8"></head>'
                f'<body style="font-family:-apple-system,Helvetica,Arial,sans-serif">{body}</body></html>')
    payload = json.dumps({"html": document, "text": plain, "name": os.environ.get("HERDR_COPY_PASTEBOARD", "")})
    out = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", JXA], input=payload, capture_output=True,
                         text=True)
    return out.returncode == 0 and out.stdout.strip() == "ok"

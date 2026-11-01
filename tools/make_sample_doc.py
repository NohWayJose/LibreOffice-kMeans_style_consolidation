#!/usr/bin/env python3
"""Regenerate hitchhikers_ch1_styles.odt: ~80% of paragraphs use named styles,
~20% carry hand-crafted direct formatting.  Usage: make_sample_doc.py out.odt"""
import re
import sys
import zipfile
from xml.sax.saxutils import escape

OUT = sys.argv[1]

# ---------------------------------------------------------------------------
# Content. Each entry: (kind, style, text)
#   kind "S" = styled only (named paragraph style, named char styles only)
#   kind "M" = manual (automatic paragraph style and/or automatic text spans)
#   kind "L" = list item (named list + named paragraph style)
# Inline markup: {c:StyleName|text} named char style, {t:T1|text} direct span.
# ---------------------------------------------------------------------------
DOC = [
    ("S", "Title", "The Hitchhiker’s Guide to the Galaxy"),
    ("S", "Subtitle", "Chapter One, Retold: The Morning the Bulldozers Came"),
    ("M", "P1", "In which a perfectly ordinary Thursday turns out to be anything but."),
    ("S", "Source_20_Note",
     "Source material: Douglas Adams, The Hitchhiker’s Guide to the Galaxy (1979), Chapter 1. "
     "This is a summary retelling written for a styles-versus-direct-formatting exercise; "
     "it is not the original text, and quotations are kept to a few words."),

    ("S", "Heading_20_1", "Prologue: An Unfashionable Corner of the Galaxy"),
    ("S", "Text_20_body",
     "The story opens far out in the unmapped backwaters of the Western Spiral Arm, where a "
     "small and thoroughly unremarkable yellow sun keeps company with a small blue-green planet. "
     "Nobody of any galactic importance has ever paid it much attention."),
    ("S", "Text_20_body",
     "The planet’s dominant life forms are descended from apes and are, the narrator notes, so "
     "astonishingly primitive that they still think {c:Emphasis|digital watches} are a pretty "
     "neat idea. They also have a problem: most of them are unhappy most of the time, and none "
     "of their many proposed solutions has helped, largely because the solutions were mostly "
     "about the movement of small green pieces of paper."),
    ("S", "Text_20_body",
     "Then, one Thursday, a young woman sitting alone in a café in Rickmansworth suddenly "
     "understands what has been going wrong all this time, and how the world could be made a "
     "good and happy place. Before she can tell anyone, a terrible and stupid catastrophe "
     "intervenes, and the idea is lost forever."),
    ("S", "Guide_20_Entry",
     "This is not her story. It is the story of that catastrophe and some of its consequences, "
     "and of a book: {c:Guide_20_Term|The Hitchhiker’s Guide to the Galaxy}, which has displaced "
     "the great Encyclopaedia Galactica as the standard repository of all knowledge and wisdom. "
     "It is slightly cheaper, and it has two words printed on its cover."),
    ("M", "P2",
     "Those two words, the narrator explains, are {t:T1|DON’T PANIC}, inscribed in large, "
     "friendly letters, which goes a long way towards explaining the book’s success."),

    ("S", "Heading_20_1", "The House"),
    ("S", "Text_20_body",
     "The house in question stands on a slight rise at the edge of a village. It is not "
     "remarkable: about thirty years old, squattish, squarish, made of brick, with four windows "
     "facing the front whose size and proportion are more or less guaranteed to displease the eye."),
    ("S", "Text_20_body",
     "The only person for whom the house is in any way special is {c:Character_20_Name|Arthur "
     "Dent}, and only because it happens to be the one he lives in. He has lived there for about "
     "three years, ever since moving out of London because it made him nervous and irritable."),
    ("S", "Text_20_body",
     "At eight o’clock on Thursday morning Arthur does not feel very good. He wakes blearily, "
     "wanders around his room, opens a window, sees a bulldozer, finds his slippers, and stomps "
     "off to the bathroom to wash. The word {c:Emphasis|bulldozer} wanders through his mind for a "
     "while in search of something to connect with."),
    ("M", "P3",
     "It connects with nothing until he is halfway through brushing his teeth. Then, slowly, he "
     "remembers. The council wants to knock his house down and build a "
     "{t:T2|bypass} in its place, and his house is about to be {t:T2|demolished}."),
    ("S", "Text_20_body",
     "The plans, it turns out, have been available to anyone who cared to look for them. They "
     "were on display in the planning office, at the bottom of a locked filing cabinet, in a "
     "disused lavatory, in a cellar with no stairs and no light, behind a door bearing a sign "
     "warning of a leopard. Arthur did not, at the time, think this was adequate public notice."),

    ("S", "Heading_20_2", "Mr L. Prosser"),
    ("S", "Text_20_body",
     "{c:Character_20_Name|Mr L. Prosser} is, in the narrator’s terms, only human: a carbon-based "
     "bipedal life form descended from an ape. He is forty, fat and shabby, works for the local "
     "council, and is—unknown even to himself—a direct male-line descendant of Genghis Khan. "
     "Centuries of intermediate generations have diluted the genes so thoroughly that the only "
     "traces left are a pronounced stomach and a weakness for little fur hats."),
    ("S", "Quotations",
     "Prosser points out that the bulldozer driver is a busy man and that Arthur cannot lie in "
     "front of it indefinitely. Arthur replies that he is game; he will see who rusts first."),
    ("M", "P4",
     "Arthur, meanwhile, is lying in the mud in front of the yellow machine, and he is "
     "discovering that the mud is wet, the morning is cold, and the moral high ground is a "
     "remarkably uncomfortable place to stand—or, in this case, to lie."),
    ("S", "Text_20_body",
     "Prosser finds himself oddly gripped by a vision of Arthur’s house in flames and Arthur "
     "running screaming from the blazing ruin with at least three hefty spears protruding from "
     "his back. Visions of this sort trouble him often and make him feel very nervous. He "
     "stammers for a moment, then pulls himself together."),

    ("S", "Heading_20_1", "Enter Ford Prefect"),
    ("S", "Text_20_body",
     "Arthur’s friend {c:Character_20_Name|Ford Prefect} arrives on the scene at this point. Ford "
     "is not, despite appearances, from Guildford. He is from a small planet somewhere in the "
     "vicinity of Betelgeuse, and he has been stranded on Earth for fifteen years while "
     "researching a new edition of the Guide."),
    ("S", "Text_20_body",
     "In all that time he has never quite managed to blend in. He chose the name Ford Prefect "
     "because he believed it to be nicely inconspicuous, having mistaken the dominant life form "
     "of the planet for the motor car. He smiles slightly too broadly and does not blink often "
     "enough, which unsettles people without their knowing why."),
    ("M", "P5", "A Matter of Some Urgency"),
    ("S", "Text_20_body",
     "Ford needs to talk to Arthur, urgently, and he needs a drink, and he needs Arthur to have "
     "a drink too, ideally several. He is maddeningly unwilling to explain why. Arthur, flat on "
     "his back in the mud, points out that he is rather busy saving his house."),
    ("S", "Text_20_body",
     "Ford solves the problem with a piece of bewildering logic. He persuades Mr Prosser that, "
     "since the bulldozers cannot proceed while Arthur is lying in front of them anyway, Prosser "
     "might just as well lie down in Arthur’s place. That way Arthur can go to the pub for a "
     "short while, and nothing at all will have changed."),
    ("M", "P6",
     "And so, with a growing sense that the morning has slipped somewhere beyond his control, "
     "Mr Prosser lowers himself into the mud, and Arthur and Ford set off across the field to "
     "the {t:T3|Horse and Groom}."),
    ("S", "Guide_20_Entry",
     "Ford’s satchel contains, among other things, an electronic Sub-Etha Sens-O-Matic, a towel, "
     "and a battered copy of the Guide itself. The towel, the Guide insists, is about the most "
     "massively useful thing an interstellar hitchhiker can have."),

    ("S", "Heading_20_2", "Key Events of the Chapter"),
    ("L", "Event_20_List", "Arthur Dent wakes on Thursday morning to find bulldozers outside his house."),
    ("L", "Event_20_List", "He lies down in the mud to stop the council demolishing it for a bypass."),
    ("L", "Event_20_List", "Ford Prefect, secretly an alien researcher, insists Arthur come to the pub."),
    ("L", "Event_20_List", "Unknown to all of them, a far larger demolition is already on its way."),

    ("S", "Heading_20_2", "Who’s Who"),
    ("S", "Character_20_Note",
     "{c:Character_20_Name|Arthur Dent} — works in local radio; anxious, decent, and about to "
     "have a very bad day."),
    ("S", "Character_20_Note",
     "{c:Character_20_Name|Ford Prefect} — field researcher for the Guide, stranded on Earth for "
     "fifteen years."),
    ("S", "Character_20_Note",
     "{c:Character_20_Name|Mr L. Prosser} — local council official with distant and unsuspected "
     "imperial ancestry."),
    ("M", "P7",
     "What none of the three men in the field knows is that, high above them, a fleet of "
     "enormous yellow ships is already sliding silently through the atmosphere. The council’s "
     "bypass is about to become the least of anybody’s worries."),
    ("M", "P8", "The Vogons were already on their way."),
]

# ---------------------------------------------------------------------------
# Direct (manual) formatting: automatic styles, each one hand-crafted.
# ---------------------------------------------------------------------------
AUTO_STYLES = """
  <style:style style:name="P1" style:family="paragraph" style:parent-style-name="Text_20_body">
    <style:paragraph-properties fo:text-align="center" fo:margin-top="0.1cm" fo:margin-bottom="0.6cm"/>
    <style:text-properties style:font-name="Liberation Serif" fo:font-size="12pt" fo:font-style="italic" fo:color="#666666"/>
  </style:style>
  <style:style style:name="P2" style:family="paragraph" style:parent-style-name="Text_20_body"/>
  <style:style style:name="P3" style:family="paragraph" style:parent-style-name="Text_20_body"/>
  <style:style style:name="P4" style:family="paragraph" style:parent-style-name="Text_20_body">
    <style:paragraph-properties fo:margin-left="2cm" fo:margin-right="1cm" fo:text-align="justify" fo:margin-top="0.2cm" fo:margin-bottom="0.4cm"/>
    <style:text-properties fo:font-size="10pt"/>
  </style:style>
  <style:style style:name="P5" style:family="paragraph" style:parent-style-name="Text_20_body">
    <style:paragraph-properties fo:margin-top="0.5cm" fo:margin-bottom="0.2cm" fo:keep-with-next="always"/>
    <style:text-properties style:font-name="Liberation Sans" fo:font-size="15pt" fo:font-weight="bold" fo:color="#1f3a5f"/>
  </style:style>
  <style:style style:name="P6" style:family="paragraph" style:parent-style-name="Text_20_body"/>
  <style:style style:name="P7" style:family="paragraph" style:parent-style-name="Text_20_body">
    <style:paragraph-properties fo:line-height="150%" fo:text-indent="1.25cm" fo:margin-top="0.4cm"/>
    <style:text-properties style:font-name="Liberation Serif" fo:font-size="13pt"/>
  </style:style>
  <style:style style:name="P8" style:family="paragraph" style:parent-style-name="Text_20_body">
    <style:paragraph-properties fo:text-align="end" fo:margin-top="0.5cm" fo:padding="0.15cm" fo:border-top="0.06pt solid #2a5db0" fo:border-bottom="0.06pt solid #2a5db0" fo:border-left="none" fo:border-right="none"/>
    <style:text-properties fo:font-weight="bold" fo:font-style="italic" fo:color="#2a5db0" fo:font-size="12pt"/>
  </style:style>
  <style:style style:name="T1" style:family="text">
    <style:text-properties fo:font-size="16pt" fo:font-weight="bold" fo:color="#c9211e" fo:letter-spacing="0.08cm" style:font-name="Liberation Sans"/>
  </style:style>
  <style:style style:name="T2" style:family="text">
    <style:text-properties fo:background-color="#ffff00"/>
  </style:style>
  <style:style style:name="T3" style:family="text">
    <style:text-properties fo:font-variant="small-caps" style:text-underline-style="solid" style:text-underline-width="auto" style:text-underline-color="font-color"/>
  </style:style>
"""

STYLES = """
  <style:default-style style:family="paragraph">
    <style:paragraph-properties fo:hyphenation-ladder-count="no-limit" style:writing-mode="page"/>
    <style:text-properties style:font-name="Liberation Serif" fo:font-size="11pt" fo:language="en" fo:country="GB" fo:hyphenate="false"/>
  </style:default-style>
  <style:style style:name="Standard" style:family="paragraph" style:class="text"/>
  <style:style style:name="Text_20_body" style:display-name="Text Body" style:family="paragraph" style:parent-style-name="Standard" style:class="text">
    <style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.25cm" fo:line-height="115%" fo:text-align="justify"/>
  </style:style>
  <style:style style:name="Heading" style:family="paragraph" style:parent-style-name="Standard" style:next-style-name="Text_20_body" style:class="text">
    <style:paragraph-properties fo:margin-top="0.42cm" fo:margin-bottom="0.21cm" fo:keep-with-next="always"/>
    <style:text-properties style:font-name="Liberation Sans" fo:font-size="14pt"/>
  </style:style>
  <style:style style:name="Title" style:family="paragraph" style:parent-style-name="Heading" style:next-style-name="Subtitle" style:class="chapter">
    <style:paragraph-properties fo:text-align="center" fo:margin-top="0cm" fo:margin-bottom="0.2cm"/>
    <style:text-properties fo:font-size="26pt" fo:font-weight="bold" fo:color="#1f3a5f"/>
  </style:style>
  <style:style style:name="Subtitle" style:family="paragraph" style:parent-style-name="Heading" style:next-style-name="Text_20_body" style:class="chapter">
    <style:paragraph-properties fo:text-align="center" fo:margin-top="0.1cm" fo:margin-bottom="0.2cm"/>
    <style:text-properties fo:font-size="16pt" fo:color="#4a6a8a"/>
  </style:style>
  <style:style style:name="Heading_20_1" style:display-name="Heading 1" style:family="paragraph" style:parent-style-name="Heading" style:next-style-name="Text_20_body" style:default-outline-level="1" style:class="text">
    <style:paragraph-properties fo:margin-top="0.6cm" fo:margin-bottom="0.25cm" fo:border-bottom="0.5pt solid #1f3a5f" fo:padding-bottom="0.08cm" fo:border-top="none" fo:border-left="none" fo:border-right="none"/>
    <style:text-properties fo:font-size="18pt" fo:font-weight="bold" fo:color="#1f3a5f"/>
  </style:style>
  <style:style style:name="Heading_20_2" style:display-name="Heading 2" style:family="paragraph" style:parent-style-name="Heading" style:next-style-name="Text_20_body" style:default-outline-level="2" style:class="text">
    <style:paragraph-properties fo:margin-top="0.45cm" fo:margin-bottom="0.2cm"/>
    <style:text-properties fo:font-size="14pt" fo:font-weight="bold" fo:font-style="italic" fo:color="#2e5a88"/>
  </style:style>
  <style:style style:name="Quotations" style:family="paragraph" style:parent-style-name="Standard" style:class="html">
    <style:paragraph-properties fo:margin-left="1cm" fo:margin-right="1cm" fo:margin-top="0.1cm" fo:margin-bottom="0.35cm" fo:text-align="start"/>
    <style:text-properties fo:font-style="italic" fo:color="#444444"/>
  </style:style>
  <style:style style:name="Source_20_Note" style:display-name="Source Note" style:family="paragraph" style:parent-style-name="Standard" style:class="extra">
    <style:paragraph-properties fo:text-align="center" fo:margin-left="1.5cm" fo:margin-right="1.5cm" fo:margin-top="0.1cm" fo:margin-bottom="0.5cm"/>
    <style:text-properties fo:font-size="8.5pt" fo:color="#777777"/>
  </style:style>
  <style:style style:name="Guide_20_Entry" style:display-name="Guide Entry" style:family="paragraph" style:parent-style-name="Standard" style:class="extra">
    <style:paragraph-properties fo:margin-left="0.5cm" fo:margin-right="0.5cm" fo:margin-top="0.25cm" fo:margin-bottom="0.35cm" fo:padding="0.25cm" fo:background-color="#e8f3e8" fo:border-left="3pt solid #3a8a3a" fo:border-right="none" fo:border-top="none" fo:border-bottom="none" fo:line-height="115%"/>
    <style:text-properties style:font-name="Liberation Sans" fo:font-size="10pt" fo:color="#1e4a1e"/>
  </style:style>
  <style:style style:name="Event_20_List" style:display-name="Event List" style:family="paragraph" style:parent-style-name="Standard" style:list-style-name="Event_20_Bullets" style:class="list">
    <style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.12cm"/>
  </style:style>
  <style:style style:name="Character_20_Note" style:display-name="Character Note" style:family="paragraph" style:parent-style-name="Standard" style:class="extra">
    <style:paragraph-properties fo:margin-left="1cm" fo:text-indent="-0.5cm" fo:margin-top="0cm" fo:margin-bottom="0.15cm"/>
    <style:text-properties fo:font-size="10.5pt"/>
  </style:style>

  <style:style style:name="Emphasis" style:family="text">
    <style:text-properties fo:font-style="italic"/>
  </style:style>
  <style:style style:name="Character_20_Name" style:display-name="Character Name" style:family="text">
    <style:text-properties fo:font-weight="bold" fo:color="#5a2e88"/>
  </style:style>
  <style:style style:name="Guide_20_Term" style:display-name="Guide Term" style:family="text">
    <style:text-properties fo:font-weight="bold" fo:font-style="italic"/>
  </style:style>

  <text:list-style style:name="Event_20_Bullets" style:display-name="Event Bullets">
    <text:list-level-style-bullet text:level="1" text:bullet-char="➤">
      <style:list-level-properties text:list-level-position-and-space-mode="label-alignment">
        <style:list-level-label-alignment text:label-followed-by="listtab" text:list-tab-stop-position="1.27cm" fo:text-indent="-0.635cm" fo:margin-left="1.27cm"/>
      </style:list-level-properties>
      <style:text-properties fo:color="#3a8a3a"/>
    </text:list-level-style-bullet>
  </text:list-style>
"""

NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
      'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
      'xmlns:dc="http://purl.org/dc/elements/1.1/" '
      'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
      'office:version="1.3"')

FONTS = """<office:font-face-decls>
  <style:font-face style:name="Liberation Serif" svg:font-family="'Liberation Serif'" style:font-family-generic="roman" style:font-pitch="variable"/>
  <style:font-face style:name="Liberation Sans" svg:font-family="'Liberation Sans'" style:font-family-generic="swiss" style:font-pitch="variable"/>
</office:font-face-decls>"""


def inline(text):
    out, pos = [], 0
    for m in re.finditer(r"\{([ct]):([^|]+)\|([^}]*)\}", text):
        out.append(escape(text[pos:m.start()]))
        out.append(f'<text:span text:style-name="{m.group(2)}">{escape(m.group(3))}</text:span>')
        pos = m.end()
    out.append(escape(text[pos:]))
    return "".join(out)


def body():
    parts, in_list = [], False
    for kind, style, text in DOC:
        if kind == "L" and not in_list:
            parts.append('<text:list text:style-name="Event_20_Bullets">')
            in_list = True
        if kind != "L" and in_list:
            parts.append("</text:list>")
            in_list = False
        tag = "text:h" if style.startswith("Heading_20_") else "text:p"
        lvl = f' text:outline-level="{style[-1]}"' if tag == "text:h" else ""
        p = f'<{tag} text:style-name="{style}"{lvl}>{inline(text)}</{tag}>'
        parts.append(f"<text:list-item>{p}</text:list-item>" if kind == "L" else p)
    if in_list:
        parts.append("</text:list>")
    return "\n".join(parts)


content = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content {NS}>
{FONTS}
<office:automatic-styles>{AUTO_STYLES}</office:automatic-styles>
<office:body><office:text>
{body()}
</office:text></office:body>
</office:document-content>"""

styles = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles {NS}>
{FONTS}
<office:styles>{STYLES}</office:styles>
<office:automatic-styles>
  <style:page-layout style:name="pm1">
    <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" style:print-orientation="portrait" fo:margin-top="2cm" fo:margin-bottom="2cm" fo:margin-left="2.2cm" fo:margin-right="2.2cm"/>
  </style:page-layout>
</office:automatic-styles>
<office:master-styles>
  <style:master-page style:name="Standard" style:page-layout-name="pm1"/>
</office:master-styles>
</office:document-styles>"""

meta = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta {NS}>
<office:meta>
  <dc:title>The Hitchhiker’s Guide to the Galaxy — Chapter One, Retold</dc:title>
  <dc:description>Styles vs direct formatting test document: ~80% named styles, ~20% manual formatting.</dc:description>
  <meta:generator>build_odt.py</meta:generator>
</office:meta>
</office:document-meta>"""

manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""

with zipfile.ZipFile(OUT, "w") as z:
    z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text",
               compress_type=zipfile.ZIP_STORED)
    for name, data in (("content.xml", content), ("styles.xml", styles),
                       ("meta.xml", meta), ("META-INF/manifest.xml", manifest)):
        z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)

# Report the split.
manual = [d for d in DOC if d[0] == "M"]
chars = lambda ds: sum(len(re.sub(r"\{[ct]:[^|]+\|([^}]*)\}", r"\1", t)) for _, _, t in ds)
print(f"paragraphs: {len(DOC)}  styled: {len(DOC) - len(manual)}  manual: {len(manual)} "
      f"({100 * len(manual) / len(DOC):.0f}%)")
print(f"characters: manual {chars(manual)} / {chars(DOC)} ({100 * chars(manual) / chars(DOC):.0f}%)")

"""Native text layers for the legacy kit's incorrect app-name captions.

The screenshot pixels and scientific content stay intact. Corrections are matched
by the exact source-image hash so they do not affect future, different captures.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIXES=json.loads((ROOT/'src/data/presentations/petrography-name-fixes.json').read_text(encoding='utf8'))
CSS="""@font-face{font-family:PetrographyBrand;src:url('/presentations/petrography/brand-font.woff2') format('woff2');font-weight:100 900;font-style:normal;font-display:block}
.petrography-name-fix{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}
"""


def overlay_svg(image_id, source_digest=None):
 fix=FIXES.get(image_id)
 if not fix or source_digest is not None and fix['sourceSha256']!=source_digest:return ''
 return f'''<svg class="petrography-name-fix" viewBox="0 0 720 1600" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false"><rect x="{fix['x']}" y="{fix['y']}" width="{fix['width']}" height="{fix['height']}" fill="{fix['background']}"/><text x="{fix['textX']}" y="{fix['baseline']}" font-family="PetrographyBrand" font-size="{fix['fontSize']}" font-weight="650" fill="{fix['foreground']}" textLength="{fix['textWidth']}" lengthAdjust="spacingAndGlyphs">RockSurv</text></svg>'''

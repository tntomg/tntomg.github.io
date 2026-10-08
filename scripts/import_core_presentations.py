"""Import the supplied Core HTML decks into the site's presentation routes.

Usage: python scripts/import_core_presentations.py --source <presentation-directory>
Requires Pillow. Original source files are kept in ignored materials/Rocksurv-Core.
"""
import argparse
import base64
import io
import re
import shutil
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('--source', type=Path, required=True)
    source = args.parse_args().source.resolve()
    output = ROOT / 'public/presentations/core'
    originals = ROOT / 'materials/Rocksurv-Core'
    output.mkdir(parents=True, exist_ok=True)
    originals.mkdir(parents=True, exist_ok=True)
    for lang in ('ru', 'en'):
        member = f'Rocksurv_Core_Presentation_{lang.upper()}.html'
        shutil.copy2(source / member, originals / member)
        raw = (source / member).read_text(encoding='utf-8-sig')
        image_index = 0

        def replace_image(match):
            nonlocal image_index
            tag = match[0]
            embedded = re.search(r'src="data:image/[^;]+;base64,([^"]+)"', tag)
            if not embedded:
                raise ValueError('Unexpected non-embedded image')
            image_index += 1
            with Image.open(io.BytesIO(base64.b64decode(embedded[1]))) as original:
                image = original.convert('RGB')
            widths = sorted({min(width, image.width) for width in (640, 1280)})
            prefix = f'/presentations/core/{lang}-{image_index:02d}'
            for width in widths:
                resized = image.resize((width, round(width * image.height / image.width)), Image.Resampling.LANCZOS)
                resized.save(output / f'{lang}-{image_index:02d}-{width}.webp', 'WEBP', quality=90, method=6)
            tag = re.sub(r'src="[^"]+"', lambda _: f'src="{prefix}-{max(widths)}.webp"', tag)
            srcset = ', '.join(f'{prefix}-{width}.webp {width}w' for width in widths)
            return tag[:-1] + f' srcset="{srcset}" sizes="(max-width: 900px) 90vw, 1000px" width="{image.width}" height="{image.height}" loading="eager" decoding="async">'

        raw = re.sub(r'<img\b[^>]*>', replace_image, raw)
        raw = raw.replace('<style>', '<style is:global>').replace('<script>', '<script is:inline>')
        raw = raw.replace('Rocksurv_Core_Presentation_' + ('EN' if lang == 'ru' else 'RU') + '.html', f'/{"en" if lang == "ru" else "ru"}/presentations/core/')
        raw = raw.replace('<div id="slide-counter" class="nav-counter">', '<div id="slide-counter" class="nav-counter" aria-live="polite">')
        back = 'Назад к приложениям' if lang == 'ru' else 'Back to apps'
        count = '14 слайдов' if lang == 'ru' else '14 slides'
        header = f'<header class="core-topbar"><a class="core-back" href="/{lang}/#apps">{back}</a><span class="core-title">Rocksurv Core</span><span>{count}</span></header>'
        raw = raw.replace('<body>', '<body>\n' + header)
        css = '''
.core-topbar { position:fixed; inset:0 0 auto; height:52px; padding:8px 16px; display:flex; align-items:center; justify-content:space-between; gap:16px; color:#f5f7f2; background:#0e1714; border-bottom:1px solid #244139; z-index:1001; font-size:13px; }
.core-back { color:inherit; padding:8px 10px; text-decoration:none; border:1px solid #38584b; border-radius:6px; }
.core-back:hover, .core-back:focus-visible { background:#244139; outline:2px solid #69d4ad; outline-offset:2px; }
.core-title { font-weight:700; }
#stage { top:calc(50% - 15px); }
#nav-bar { max-width:calc(100vw - 16px); white-space:nowrap; }
#nav-dots .dot { padding:0; cursor:pointer; }
#nav-dots .dot:focus-visible { outline:2px solid #69d4ad; outline-offset:3px; }
@media (max-width:900px) { #nav-dots, .nav-divider { display:none; } }
@media (max-width:640px) { #btn-fs, #btn-print, .core-title { display:none; } #nav-bar { gap:6px; padding:4px 8px; } .nav-btn { min-height:44px; padding:6px 8px; } .core-topbar { padding-inline:8px; gap:8px; } }
@media print { .core-topbar { display:none; } }
'''
        raw = raw.replace('</style>', css + '</style>', 1)
        raw = raw.replace('var currentSlide = 0;', "var currentSlide = Math.min(slides.length - 1, Math.max(0, (parseInt(location.hash.slice(1), 10) || 1) - 1));")
        raw = raw.replace("document.createElement('div')", "document.createElement('button')")
        raw = raw.replace("dot.title = (idx + 1).toString();", "dot.type = 'button';\n    dot.title = (idx + 1).toString();\n    dot.setAttribute('aria-label', '" + ('Слайд ' if lang == 'ru' else 'Slide ') + "' + (idx + 1));")
        raw = raw.replace("s.classList.toggle('active', idx === currentSlide);", "s.classList.toggle('active', idx === currentSlide);\n      s.setAttribute('aria-hidden', idx !== currentSlide);")
        raw = raw.replace("counter.textContent = num + ' / ' + total;", "counter.textContent = num + ' / ' + total;\n      history.replaceState(null, '', '#' + (currentSlide + 1));\n      document.querySelector('a.lang-toggle').href = '/" + ('en' if lang == 'ru' else 'ru') + "/presentations/core/#' + (currentSlide + 1);")
        raw = raw.replace("window.addEventListener('keydown', function(e) {", "window.addEventListener('keydown', function(e) {\n    if (e.altKey || e.ctrlKey || e.metaKey) return;\n    if (['ArrowRight','ArrowLeft','PageDown','PageUp',' ','Home','End'].includes(e.key)) e.preventDefault();")
        raw = raw.replace('var scale = Math.min(window.innerWidth / 1600, window.innerHeight / 900);', 'var scale = Math.min((window.innerWidth - 32) / 1600, (window.innerHeight - 134) / 900);')
        raw = raw.replace('  resizeStage();\n})();', '  updateSlide();\n  resizeStage();\n})();')
        titles = re.findall(r'<h[12]\b[^>]*>(.*?)</h[12]>', raw, re.S)
        slide_index = 0
        def label_slide(match):
            nonlocal slide_index
            title = re.sub(r'<[^>]+>', ' ', titles[slide_index])
            title = re.sub(r'\s+', ' ', title).strip().replace('"', '&quot;')
            slide_index += 1
            return match[0][:-1] + f' aria-label="{slide_index}. {title}">'
        raw = re.sub(r'<section\b[^>]*class="[^"]*\bslide\b[^"]*"[^>]*>', label_slide, raw)
        if slide_index != 14 or 'data:image' in raw:
            raise ValueError('Unexpected Core deck structure')
        raw = raw.replace('</head>', '<link rel="icon" type="image/svg+xml" href="/favicon.svg">\n</head>')
        page = ROOT / f'src/pages/{lang}/presentations/core.astro'
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text('---\n// Supplied Core presentation, with optimized assets and site navigation.\n---\n' + raw, encoding='utf8')
        print(f'Core {lang}: {slide_index} slides, {image_index} optimized images')


if __name__ == '__main__':
    main()

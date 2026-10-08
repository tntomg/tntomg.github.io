"""Import the bilingual Petrography kit, screenshots and original PDFs.

Usage: python scripts/import_petrography_presentations.py --kit <presentation-kit.zip>
Requires Pillow. Source kit stays in the ignored materials directory.
"""
import argparse,base64,hashlib,html,io,json,re,shutil,subprocess,zipfile
from pathlib import Path
from PIL import Image
from petrography_branding import overlay_svg, CSS as BRANDING_CSS
ROOT=Path(__file__).resolve().parents[1]
MEMBERS='RockSurf_Petrography_Presentation_Kit'


def main():
 args=argparse.ArgumentParser(description=__doc__)
 args.add_argument('--kit',type=Path,required=True)
 kit_path=args.parse_args().kit.resolve()
 originals=ROOT/'materials'/kit_path.name
 if kit_path!=originals:shutil.copy2(kit_path,originals)
 output=ROOT/'public/presentations/petrography';output.mkdir(parents=True,exist_ok=True)
 data=ROOT/'src/data/presentations'
 known={};images={}
 with zipfile.ZipFile(kit_path) as kit:
  for lang in ('ru','en'):
   stem=f'RockSurf_Petrography_Presentation_{lang.upper()}'
   raw=kit.read(f'{MEMBERS}/{stem}.html').decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
   def replace_image(match):
    tag=match[0]
    embedded=re.search(r'src="data:image/[^;]+;base64,([^"]+)"',tag)
    if not embedded:raise ValueError('Unexpected non-embedded image')
    content=base64.b64decode(embedded[1]);digest=hashlib.sha256(content).hexdigest()
    if digest not in known:
     image_id=f'{len(known)+1:02d}';known[digest]=image_id
     with Image.open(io.BytesIO(content)) as source:image=source.convert('RGB')
     widths=sorted({min(w,image.width) for w in (360,720)})
     for width in widths:
      image.resize((width,round(width*image.height/image.width)),Image.Resampling.LANCZOS).save(output/f'{image_id}-{width}.webp','WEBP',quality=90,method=6)
     images[image_id]={'width':image.width,'height':image.height,'variants':widths}
    image_id=known[digest];info=images[image_id]
    prefix=f'/presentations/petrography/{image_id}'
    tag=re.sub(r'src="[^"]+"',lambda _:f'src="{prefix}-{max(info["variants"])}.webp"',tag)
    srcset=', '.join(f'{prefix}-{w}.webp {w}w' for w in info['variants'])
    return tag[:-1]+f' srcset="{srcset}" sizes="(max-width: 900px) 46vw, 430px" width="{info["width"]}" height="{info["height"]}" loading="eager" decoding="async">'+overlay_svg(image_id,digest)
   raw=re.sub(r'<img\b[^>]*>',replace_image,raw)
   raw=raw.replace('RockSurf','RockSurv')
   raw=raw.replace('<style>','<style is:global>').replace('<script>','<script is:inline>')
   slides=re.findall(r'<section\b[^>]*class="[^"]*\bslide\b[^"]*"[^>]*>(.*?)</section>',raw,re.S)
   titles=[html.unescape(re.sub(r'<[^>]+>',' ',re.search(r'<h[12][^>]*>(.*?)</h[12]>',slide,re.S)[1])).strip() for slide in slides]
   if len(slides)!=12 or 'data:image' in raw:raise ValueError('Unexpected Petrography structure')
   (data/f'petrography.{lang}.json').write_text(json.dumps({'source':f'materials/{originals.name}: {stem}.html','lang':lang,'slides':[{'title':re.sub(r'\s+',' ',title)} for title in titles]},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
   pdf=f'/presentations/petrography/petrography-{lang}.pdf'
   # PDFs are rendered below from the corrected HTML, rather than copied from the legacy kit.
   other='en' if lang=='ru' else 'ru'
   back='Назад к приложениям' if lang=='ru' else 'Back to apps'
   header=f'<header class="petrography-topbar"><a href="/{lang}/#apps">{back}</a><span class="petrography-title">RockSurv Petrography</span><div class="petrography-actions"><a class="petrography-language" href="/{other}/presentations/petrography/">{other.upper()}</a><a href="{pdf}" download aria-label="'+('Скачать презентацию PDF' if lang=='ru' else 'Download presentation PDF')+'">PDF</a></div></header>'
   raw=raw.replace('<body>','<body>\n'+header,1)
   css='''
.petrography-topbar{position:fixed;inset:0 0 auto;height:52px;padding:8px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px;background:#0e1714;color:#f5f7f2;z-index:101;font-size:13px}
.petrography-topbar a{color:inherit;text-decoration:none;padding:8px 10px;border:1px solid #38584b;border-radius:6px}
.petrography-topbar a:hover,.petrography-topbar a:focus-visible{background:#244139;outline:2px solid #69d4ad;outline-offset:2px}
.petrography-actions{display:flex;gap:8px}.petrography-title{font-weight:700}
#stage{top:calc(50% - 15px)}.controls{max-width:calc(100vw - 16px);white-space:nowrap}
@media(max-width:640px){.petrography-title,#fsBtn,#printBtn{display:none}.petrography-topbar{padding-inline:8px}.controls{padding:4px 8px;gap:6px}.controls button{min-height:44px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
@media print{.petrography-topbar{display:none}}
'''
   raw=raw.replace('</style>',css+BRANDING_CSS+'</style>',1)
   raw=raw.replace('window.innerWidth / 1600, window.innerHeight / 900','(window.innerWidth - 32) / 1600, (window.innerHeight - 134) / 900')
   raw=raw.replace('let currentSlide = 0;',"let currentSlide = Math.min(slides.length-1, Math.max(0, (parseInt(location.hash.slice(1),10)||1)-1));")
   raw=raw.replace("s.classList.toggle('active', i === currentSlide);","s.classList.toggle('active', i === currentSlide);\n        s.setAttribute('aria-hidden', i !== currentSlide);")
   raw=raw.replace("slideOut.textContent = (currentSlide + 1) + ' / ' + slides.length;", "slideOut.textContent = String(currentSlide + 1).padStart(2,'0') + ' / ' + slides.length;\n      history.replaceState(null,'','#'+(currentSlide+1));\n      document.querySelector('.petrography-language').href='/"+other+"/presentations/petrography/#'+(currentSlide+1);")
   raw=raw.replace('    // Modern Carousel Engine','    showSlide(currentSlide);\n\n    // Modern Carousel Engine',1)
   raw=raw.replace("window.addEventListener('keydown', (e) => {", "window.addEventListener('keydown', (e) => {\n      if(e.altKey || e.ctrlKey || e.metaKey) return;",1)
   raw=re.sub(r'(function startCycle\(\)\s*\{)',r"\1\n        if(window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;",raw)
   raw=raw.replace('<output id="slideOut">','<output id="slideOut" aria-live="polite">')
   raw=raw.replace('</head>','<link rel="icon" type="image/svg+xml" href="/favicon.svg">\n</head>',1)
   raw=raw.replace('      let timer = null;', '')
   if lang=='ru':
    for before,after in [('Previous Slide (Left Arrow)','Предыдущий слайд'),('Next Slide (Right Arrow)','Следующий слайд'),('Toggle Fullscreen (F)','На весь экран (F)'),('Print to 16:9 PDF (P)','Печать в PDF (P)'),('Slide navigation','Управление слайдами'),('Previous image','Предыдущий снимок'),('Next image','Следующий снимок'),('Go to state','Показать экран')]:raw=raw.replace(before,after)
   page=ROOT/f'src/pages/{lang}/presentations/petrography.astro'
   page.write_text('---\n// Supplied Petrography deck, optimized media and site navigation.\n---\n'+raw,encoding='utf8')
   print(f'Imported Petrography {lang}: {len(slides)} slides, original PDF and optimized media')
 (data/'petrography-images.json').write_text(json.dumps(images,indent=2)+'\n',encoding='utf8')
 print(f'{len(images)} shared images')
 subprocess.run(['node',str(ROOT/'scripts/export_petrography_pdf.mjs')],cwd=ROOT,check=True)


if __name__=='__main__':main()

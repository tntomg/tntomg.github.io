"""Import a bilingual Field kit into the existing Astro presentation pages.

Keeps the site's navigation, keyboard controls, print styles and language defaults.
Screenshots are exported as responsive WebP using build_presentations.py's crop.
Usage: python scripts/update_field_presentation.py --kit materials/<kit>.zip
Requires Pillow. Original kits remain in the ignored materials directory.
"""

import argparse
import base64
import hashlib
import html
import json
import re
import zipfile
from pathlib import Path

from field_geochemistry import normalize_field_copy
from build_presentations import DATA_DIR, PUBLIC_DIR, ROOT, DeckParser, export_image, finish_slide


ASSETS = {
    "android_rs.svg": "android.svg",
    "apple_rs.svg": "apple.svg",
    "flag_gb.svg": "flag_gb.svg",
    "flag_ru.svg": "flag_ru.svg",
    "flag_sa.svg": "flag_sa.svg",
}


class FieldDeckParser(DeckParser):
    """Collect source text as well as the embedded screenshot media."""

    def handle_data(self, data):
        if self.text is not None:
            self.text[2] += data


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def update_page(template, stages, total, lang):
    pattern = r'(<div\b[^>]*\bid="deck-(ru|en)"[^>]*>)(.*?)(\n      </div>)'
    page, count = re.subn(pattern, lambda m: m[1] + "\n        " + stages[m[2]] + m[4], template, flags=re.S)
    if count != 2:
        raise ValueError(f"Expected both language decks in {lang} page, found {count}")
    page = re.sub(r'(<span class="pres-chip">)\d+', lambda m: m[1] + str(total), page)
    page = re.sub(r'(<output id="counter"[^>]*>)01 / \d+', lambda m: m[1] + f"01 / {total:02d}", page)
    description = (
        "Интерактивная презентация Rocksurv Field: геология и геохимический сбор, офлайн-карты, высотные профили и передача проб."
        if lang == "ru" else
        "Interactive Rocksurv Field presentation: geology and geochemical sampling, offline maps, terrain profiles and sample handover."
    )
    page = re.sub(r'(<meta name="description" content=")[^"]*(">)', lambda m: m[1] + description + m[2], page)
    return page


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--kit", type=Path, default=ROOT / "materials/Rocksurv_Field_Presentation_Kit_EN_RU_v14.zip")
    kit_path = args.parse_args().kit.resolve()
    previous = read_json(DATA_DIR / "field.ru.json")
    previous_total = len(previous["slides"])
    previous_closing = previous["slides"][-1]["media"][0]["image"]
    pages = {lang: ROOT / f"src/pages/{lang}/presentations/field.astro" for lang in ("ru", "en")}
    templates = {lang: path.read_text(encoding="utf-8") for lang, path in pages.items()}
    images = read_json(DATA_DIR / "images.json")
    field_images = {}
    known = {}
    stages = {}
    payloads = {}
    assets = {}
    source = str(kit_path.relative_to(ROOT)).replace("\\", "/") if kit_path.is_relative_to(ROOT) else kit_path.name
    output = PUBLIC_DIR / "field"
    output.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(kit_path) as kit:
        for member, target in ASSETS.items():
            raw = kit.read(f"rocksurv_field/assets/{member}")
            assets[hashlib.sha1(raw).hexdigest()] = target
            (output / "assets" / target).write_bytes(raw)
        for lang in ("ru", "en"):
            member = f"rocksurv_field/Rocksurv_Field_Presentation_{lang.upper()}.html"
            raw_html = kit.read(member).decode("utf-8-sig")
            raw_html = normalize_field_copy(raw_html, lang)
            stage = re.search(r'<main id="stage">(.*?)</main>', raw_html, re.S)
            if not stage:
                raise ValueError(f"Missing stage in {member}")
            parser = FieldDeckParser()
            parser.feed(stage[1])
            slides = [finish_slide(slide) for slide in parser.slides]
            if not slides or slides[0]["kind"] != "cover" or slides[-1]["kind"] != "closing":
                raise ValueError(f"Incomplete presentation in {member}")
            slides[0].update(title="Rocksurv Field", brand=["Rocksurv", "Field"])
            for slide in slides:
                for media in slide["media"]:
                    raw = media.pop("raw")
                    digest = hashlib.sha1(raw).hexdigest()
                    if digest not in known:
                        image_id = f"{len(known) + 1:02d}"
                        known[digest] = image_id
                        field_images[image_id] = export_image(raw, "field", image_id)
                    media["image"] = known[digest]
            payloads[lang] = {"deck": "field", "lang": lang, "source": f"{source}: {member}", "slides": slides}
            first_image = True

            def replace_image(match):
                nonlocal first_image
                tag = match[0]
                embedded = re.search(r'src="data:image/([^;]+);base64,([^"]+)"', tag)
                if not embedded:
                    raise ValueError(f"Unexpected image source in {member}")
                digest = hashlib.sha1(base64.b64decode(embedded[2])).hexdigest()
                if embedded[1] == "svg+xml":
                    target = f"/presentations/field/assets/{assets[digest]}"
                    return re.sub(r'src="[^"]+"', lambda _: f'src="{target}"', tag)[:-1] + ' loading="lazy">'
                image_id = known[digest]
                info = field_images[image_id]
                variants = info["variants"]
                prefix = f"/presentations/field/{image_id}"
                srcset = ", ".join(f"{prefix}-{width}.webp {width}w" for width in variants)
                loading = ' fetchpriority="high" loading="eager"' if first_image else ' loading="lazy"'
                first_image = False
                tag = re.sub(r'src="[^"]+"', lambda _: f'src="{prefix}-{max(variants)}.webp"', tag)
                return tag[:-1] + f' srcset="{srcset}" sizes="(max-width: 900px) 90vw, 960px" width="{info["width"]}" height="{info["height"]}"{loading} decoding="async">'

            content = re.sub(r'<img\b[^>]+>', replace_image, stage[1])
            if "data:image" in content:
                raise ValueError("Unconverted embedded image")
            section_index = 0

            def label_slide(match):
                nonlocal section_index
                title = slides[section_index]["title"]
                section_index += 1
                opening = match[0]
                if "aria-label=" not in opening:
                    opening = opening[:-1] + f' aria-label="{section_index}. {html.escape(title, quote=True)}">'
                return opening

            content = re.sub(r'<section\b[^>]*class="[^"]*\bslide\b[^"]*"[^>]*>', label_slide, content)
            stages[lang] = re.sub(r'>\s+<', '><', content).strip()

    total = len(payloads["ru"]["slides"])
    if total != len(payloads["en"]["slides"]):
        raise ValueError("Russian and English slide counts differ")
    prepared = {path: update_page(templates[lang], stages, total, lang) for lang, path in pages.items()}
    closing_image = payloads["ru"]["slides"][-1]["media"][0]["image"]
    for lang in ("ru", "en"):
        for name in ("index.astro", "apps/[slug].astro"):
            path = ROOT / f"src/pages/{lang}/{name}"
            content = path.read_text(encoding="utf-8")
            content = content.replace(f"{previous_total} слайдов", f"{total} слайдов").replace(f"{previous_total} slides", f"{total} slides")
            content = content.replace(f"/presentations/field/{previous_closing}-640.webp", f"/presentations/field/{closing_image}-640.webp")
            prepared[path] = content
    for path, content in prepared.items():
        path.write_text(content, encoding="utf-8")
    for lang, payload in payloads.items():
        (DATA_DIR / f"field.{lang}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    images["field"] = field_images
    (DATA_DIR / "images.json").write_text(json.dumps(images, indent=2) + "\n", encoding="utf-8")
    generated = {f"{image_id}-{width}.webp" for image_id, info in field_images.items() for width in info["variants"]}
    for stale in output.glob("*.webp"):
        if stale.name not in generated:
            stale.unlink()
    print(f"Imported {kit_path.name}: {total} slides per language, {len(field_images)} shared images.")


if __name__ == "__main__":
    main()

import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { chromium } from 'playwright-core';

const dist = resolve('dist');
const types = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2'
};

const server = createServer(async (req, res) => {
  try {
    let pathname = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (pathname === '/favicon.ico') pathname = '/favicon.svg';
    let file = normalize(join(dist, pathname));
    if (!file.startsWith(dist)) throw new Error('outside dist');
    if ((await stat(file).catch(() => null))?.isDirectory()) file = join(file, 'index.html');
    const body = await readFile(file);
    res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    console.log('SERVER 404:', req.url);
    res.writeHead(404);
    res.end();
  }
});

await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const problems = [];

page.on('pageerror', (e) => problems.push(`PageError: ${e.message}`));
page.on('console', (m) => {
  if (m.type() === 'error') problems.push(`ConsoleError: ${m.text()}`);
});
page.on('response', (res) => {
  if (res.status() === 404) problems.push(`Missing asset or page: ${res.url()}`);
});

try {
  // 1. Verify main page
  console.log('Testing /ru/ main page...');
  await page.goto(`${origin}/ru/`, { waitUntil: 'load' });

  // All four published apps must have their own preview and presentation links.
  const appTitles = await page.locator('#apps .app h3').allTextContents();
  if (appTitles.join('|') !== 'Rocksurv Field|Rocksurv Classifier|Rocksurv Core|RockSurv Petrography') problems.push('Expected Field, Classifier, Core and Petrography in the apps section');
  if (await page.locator('a[href="/ru/presentations/core/"]').count() === 0) problems.push('Core presentation link missing on home page');

  // Verify presentation buttons on main page
  const fieldPresBtn = page.locator('a[href="/ru/presentations/field/"]');
  if (await fieldPresBtn.count() === 0) problems.push('Field presentation link missing on main page');

  const classPresBtn = page.locator('a[href="/ru/presentations/classifier/"]');
  if (await classPresBtn.count() === 0) problems.push('Classifier presentation link missing on main page');

  // 2. Test Field Presentation Mini-App
  console.log('Testing /ru/presentations/field/ ...');
  await page.goto(`${origin}/ru/presentations/field/`, { waitUntil: 'load' });

  let counter = await page.locator('#counter').innerText();
  if (counter.trim() !== '01 / 17') problems.push(`Initial counter expected "01 / 17", got "${counter}"`);

  // Click next slide
  await page.locator('#next').click();
  await page.waitForTimeout(300);
  counter = await page.locator('#counter').innerText();
  if (counter.trim() !== '02 / 17') problems.push(`After next, counter expected "02 / 17", got "${counter}"`);

  // Check language switcher
  const btnEn = page.locator('#btn-lang-en');
  await btnEn.click();
  await page.waitForTimeout(300);
  const activeDeckEn = await page.locator('#deck-en').evaluate(el => el.classList.contains('active-deck'));
  if (!activeDeckEn) problems.push('English deck was not activated on toggle click');

  const btnRu = page.locator('#btn-lang-ru');
  await btnRu.click();
  await page.waitForTimeout(300);
  const activeDeckRu = await page.locator('#deck-ru').evaluate(el => el.classList.contains('active-deck'));
  if (!activeDeckRu) problems.push('Russian deck was not reactivated on toggle click');

  // Test keyboard navigation
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(300);
  counter = await page.locator('#counter').innerText();
  if (counter.trim() !== '03 / 17') problems.push(`After ArrowRight, counter expected "03 / 17", got "${counter}"`);

  // Every v14 slide and asset must be available in both language decks.
  for (const lang of ['ru', 'en']) {
    const count = await page.locator('#deck-' + lang + ' .slide').count();
    if (count !== 17) problems.push('Expected 17 Field slides for ' + lang + ', got ' + count);
  }
  await page.keyboard.press('End');
  if ((await page.locator('#counter').innerText()).trim() !== '17 / 17') problems.push('End did not reach the last Field slide');
  const brokenImages = await page.locator('#stage img').evaluateAll(async images => {
    await Promise.all(images.map(async image => {
      image.loading = 'eager';
      await image.decode().catch(() => {});
    }));
    return images.filter(image => !image.naturalWidth).map(image => image.getAttribute('src'));
  });
  if (brokenImages.length) problems.push('Broken Field images: ' + brokenImages.join(', '));

  // 3. Test Classifier Presentation Mini-App
  console.log('Testing /ru/presentations/classifier/ ...');
  await page.goto(`${origin}/ru/presentations/classifier/`, { waitUntil: 'load' });

  counter = await page.locator('#counter').innerText();
  if (counter.trim() !== '01 / 10') problems.push(`Classifier initial counter expected "01 / 10", got "${counter}"`);

  // Slide 2 has carousel with 4 states
  await page.locator('#next').click();
  await page.waitForTimeout(400);
  counter = await page.locator('#counter').innerText();
  if (counter.trim() !== '02 / 10') problems.push(`Classifier slide 2 counter expected "02 / 10", got "${counter}"`);

  const carouselItemCount = await page.locator('.slide.active .carousel-item').count();
  if (carouselItemCount !== 4) problems.push(`Expected 4 carousel items on slide 2, found ${carouselItemCount}`);

  // Test carousel next button
  const carouselBtnNext = page.locator('.slide.active .carousel-btn.next');
  if (await carouselBtnNext.count() > 0) {
    await carouselBtnNext.click();
    await page.waitForTimeout(300);
  }

  // Core: the supplied bilingual deck, slide navigation and source images.
  for (const lang of ['ru', 'en']) {
    await page.goto(`${origin}/${lang}/presentations/core/`, { waitUntil: 'load' });
    if (await page.locator('#stage .slide').count() !== 14) problems.push(`Expected 14 Core slides for ${lang}`);
    if ((await page.locator('#slide-counter').innerText()).trim() !== '01 / 14') problems.push(`Wrong Core initial counter for ${lang}`);
    await page.locator('#btn-next').click();
    if ((await page.locator('#slide-counter').innerText()).trim() !== '02 / 14') problems.push(`Core next failed for ${lang}`);
    const otherLang = lang === 'ru' ? 'en' : 'ru';
    const languageHref = await page.locator('a.lang-toggle').getAttribute('href');
    if (languageHref !== `/${otherLang}/presentations/core/#2`) problems.push(`Core language switch loses slide for ${lang}`);
    await page.goto(`${origin}${languageHref}`, { waitUntil: 'load' });
    if ((await page.locator('#slide-counter').innerText()).trim() !== '02 / 14') problems.push('Core URL slide restore failed');
    await page.keyboard.press('End');
    if ((await page.locator('#slide-counter').innerText()).trim() !== '14 / 14') problems.push('Core End navigation failed');
    const broken = await page.locator('#stage img').evaluateAll(async images => {
      await Promise.all(images.map(image => image.decode().catch(() => {})));
      return images.filter(image => !image.naturalWidth).map(image => image.src);
    });
    if (broken.length) problems.push('Broken Core images: ' + broken.join(', '));
    await page.goto(`${origin}/${lang}/apps/rocksurv-core/`, { waitUntil: 'load' });
    if (await page.locator('a[href="/' + lang + '/presentations/core/"]').count() === 0) problems.push(`Core presentation missing on ${lang} case page`);
    if (!await page.locator('.case-facts').innerText().then(text => text.includes(lang === 'ru' ? 'MVP в разработке' : 'MVP in development'))) problems.push('Core development stage missing');
    if (await page.locator('.case-figure img[src*="/classifier/"]').count()) problems.push('Core case shows Classifier screenshots');
  }

  // Petrography is a separate optical application with its own deck and PDF.
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const lang of ['ru', 'en']) {
    await page.goto(`${origin}/${lang}/presentations/petrography/`, { waitUntil: 'load' });
    if (await page.locator('#stage .slide').count() !== 12) problems.push('Petrography must contain 12 slides');
    if ((await page.locator('#slideOut').innerText()).trim() !== '01 / 12') problems.push('Petrography initial slide is wrong');
    await page.locator('.slide.active .carousel-btn.next').click();
    const state = await page.locator('.slide.active .badge-count').innerText();
    if (!state.startsWith('2 ')) problems.push('Petrography carousel did not advance');
    await page.locator('#nextBtn').click();
    if ((await page.locator('#slideOut').innerText()).trim() !== '02 / 12') problems.push('Petrography next slide failed');
    const languageHref = await page.locator('.petrography-language').getAttribute('href');
    await page.goto(`${origin}${languageHref}`, { waitUntil: 'load' });
    if ((await page.locator('#slideOut').innerText()).trim() !== '02 / 12') problems.push('Petrography language switch lost slide');
    await page.keyboard.press('End');
    if ((await page.locator('#slideOut').innerText()).trim() !== '12 / 12') problems.push('Petrography End failed');
    const broken = await page.locator('#stage img').evaluateAll(async images => {
      await Promise.all(images.map(image => image.decode().catch(() => {})));
      return images.filter(image => !image.naturalWidth).map(image => image.src);
    });
    if (broken.length) problems.push('Broken Petrography images: ' + broken.join(', '));
    const pdf = await page.request.get(`${origin}/presentations/petrography/petrography-${lang}.pdf`);
    if (pdf.status() !== 200 || (await pdf.body()).subarray(0, 5).toString() !== '%PDF-') problems.push('Petrography PDF missing or invalid');
    await page.goto(`${origin}/${lang}/apps/rocksurv-petrography/`, { waitUntil: 'load' });
    if (!await page.locator('h1').innerText().then(text => text.includes('RockSurv Petrography'))) problems.push('Petrography case title missing');
    if (await page.locator('.case-figure img[src*="/classifier/"]').count()) problems.push('Petrography case shows Classifier screens');
  }

  // 4. Test case detail pages
  console.log('Testing /ru/apps/rocksurv-field/ ...');
  await page.goto(`${origin}/ru/apps/rocksurv-field/`, { waitUntil: 'load' });
  const caseFieldPres = page.locator('a[href="/ru/presentations/field/"]');
  if (await caseFieldPres.count() === 0) problems.push('Presentation link missing on /ru/apps/rocksurv-field/');

  console.log('Testing /ru/apps/classifier/ ...');
  await page.goto(`${origin}/ru/apps/classifier/`, { waitUntil: 'load' });
  const caseClassPres = page.locator('a[href="/ru/presentations/classifier/"]');
  if (await caseClassPres.count() === 0) problems.push('Presentation link missing on /ru/apps/classifier/');

  if (problems.length > 0) {
    console.error('FAILURES:\n' + problems.join('\n'));
  } else {
    console.log('ALL PRESENTATION MINI-APP TESTS PASSED SUCCESSFULLY!');
  }
} catch (err) {
  console.error(`Test threw: ${err.message}\n${err.stack}`);
  problems.push(err.message);
} finally {
  server.close();
  await Promise.race([browser.close(), new Promise((ok) => setTimeout(ok, 2000))]);
  process.exit(problems.length ? 1 : 0);
}

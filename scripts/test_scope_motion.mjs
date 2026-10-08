// Regression check against dist/, where CSS minification previously broke scroll animations.
// Usage: npm run build, then node scripts/test_scope_motion.mjs
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { extname, isAbsolute, join, relative, resolve } from 'node:path';
import { chromium } from 'playwright-core';

const dist = resolve('dist');
const types = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript',
  '.webp': 'image/webp', '.svg': 'image/svg+xml', '.woff2': 'font/woff2',
};
const server = createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    let file = resolve(dist, `.${pathname}`);
    const fromDist = relative(dist, file);
    if (fromDist.startsWith('..') || isAbsolute(fromDist)) throw new Error('outside dist');
    if ((await stat(file)).isDirectory()) file = join(file, 'index.html');
    const body = await readFile(file);
    res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404);
    res.end();
  }
});
await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
const origin = `http://127.0.0.1:${server.address().port}`;
const out = resolve('.analysis/scope-motion');
mkdirSync(out, { recursive: true });
let browser;
try {
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  for (const [name, viewport] of [
    ['desktop', { width: 1440, height: 900 }],
    ['mobile', { width: 390, height: 844 }],
  ]) {
    for (const locale of ['ru', 'en']) {
      const page = await browser.newPage({ viewport, reducedMotion: 'no-preference' });
      const errors = [];
      page.on('pageerror', (error) => errors.push(error.message));
      await page.goto(`${origin}/${locale}/`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(1800);
      const sample = () => page.locator('.scope .thin').evaluate((image) => {
        const css = getComputedStyle(image);
        return { angle: parseFloat(css.rotate) || 0, filter: css.filter, loaded: image.complete && image.naturalWidth > 0 };
      });
      const start = await sample();
      assert.ok(start.loaded, `${name}/${locale}: thin-section image loaded`);
      assert.ok(Math.abs(start.angle) < 1, `${name}/${locale}: starts at zero degrees`);
      if (locale === 'ru') await page.screenshot({ path: join(out, `${name}-fixed-start.png`) });

      await page.evaluate(() => window.scrollTo({ top: innerHeight * 0.3, behavior: 'instant' }));
      await page.waitForFunction(() => parseFloat(getComputedStyle(document.querySelector('.scope .thin')).rotate) > 20);
      const middle = await sample();
      assert.ok(middle.angle < 100, `${name}/${locale}: controlled rotation while scrolling`);
      assert.notEqual(middle.filter, start.filter, `${name}/${locale}: optical dimming follows rotation`);
      if (locale === 'ru') await page.screenshot({ path: join(out, `${name}-fixed-scrolled.png`) });

      await page.evaluate(() => window.scrollTo({ top: innerHeight * 1.2, behavior: 'instant' }));
      await page.waitForFunction(() => Math.abs(parseFloat(getComputedStyle(document.querySelector('.scope .thin')).rotate) - 180) < 1);
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
      await page.waitForFunction(() => Math.abs(parseFloat(getComputedStyle(document.querySelector('.scope .thin')).rotate)) < 1);
      assert.deepEqual(errors, [], `${name}/${locale}: no runtime errors`);
      console.log(`${name}/${locale}: scroll rotation, dimming, endpoint and reverse scrolling passed`);
      await page.close();
    }
  }
  for (const locale of ['ru', 'en']) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
    await page.goto(`${origin}/${locale}/`, { waitUntil: 'networkidle' });
    const style = () => page.locator('.scope .thin').evaluate((image) => {
      const css = getComputedStyle(image);
      return { rotate: css.rotate, filter: css.filter, animations: image.getAnimations().length };
    });
    const before = await style();
    await page.evaluate(() => window.scrollTo({ top: 450, behavior: 'instant' }));
    await page.waitForTimeout(150);
    assert.deepEqual(await style(), before, `${locale}: reduced motion keeps the image still`);
    assert.equal(before.animations, 0, `${locale}: no scroll animation under reduced motion`);
    console.log(`${locale}: reduced-motion preference respected`);
    await page.close();
  }
} finally {
  await browser?.close();
  await new Promise((ok) => server.close(ok));
}

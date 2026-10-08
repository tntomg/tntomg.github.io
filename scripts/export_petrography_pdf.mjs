// Render downloadable PDFs from the current, corrected presentation sources.
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const publicRoot = join(root, 'public');
const types = { '.webp': 'image/webp', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
const server = createServer(async (req, res) => {
  try {
    const pathname = new URL(req.url, 'http://local').pathname;
    const language = pathname.match(/^\/print\/(ru|en)\/$/);
    if (language) {
      const page = await readFile(join(root, `src/pages/${language[1]}/presentations/petrography.astro`), 'utf8');
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      res.end(page.replace(/^---[\s\S]*?---\s*/, ''));
      return;
    }
    const file = join(publicRoot, decodeURIComponent(pathname));
    if (!file.startsWith(publicRoot) || !(await stat(file)).isFile()) throw new Error('Invalid asset');
    res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' });
    res.end(await readFile(file));
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(ok => server.listen(0, '127.0.0.1', ok));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  for (const lang of ['ru', 'en']) {
    const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, reducedMotion: 'reduce' });
    await page.goto(`${origin}/print/${lang}/`, { waitUntil: 'networkidle' });
    await page.locator('#stage img').evaluateAll(images => Promise.all(images.map(image => image.decode())));
    await page.evaluate(() => document.fonts.ready);
    await page.pdf({ path: join(publicRoot, `presentations/petrography/petrography-${lang}.pdf`), preferCSSPageSize: true, printBackground: true });
    await page.close();
    console.log(`Exported RockSurv Petrography PDF (${lang})`);
  }
} finally {
  await browser.close();
  await new Promise(ok => server.close(ok));
}

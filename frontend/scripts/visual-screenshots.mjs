import { mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const output = join(root, '..', 'docs', 'design', 'screenshots');
const baseUrl = process.env.VISUAL_BASE_URL ?? 'http://127.0.0.1:4173';
const widths = [375, 768, 1440];

async function assertNoOverflow(page, width) {
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  if (overflows) {
    throw new Error(`horizontal overflow at ${width}px on ${page.url()}`);
  }
}

await mkdir(output, { recursive: true });
const browser = await chromium.launch();

for (const width of widths) {
  const context = await browser.newContext({ viewport: { width, height: 900 } });
  await context.route('**/api/health', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'UP', service: 'turnos-api', version: '0.1.0' }),
    }),
  );
  await context.route('**/api/auth/login', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'visual-access-token',
        refresh_token: 'visual-refresh-token',
        token_type: 'bearer',
      }),
    }),
  );

  const page = await context.newPage();
  await page.goto(`${baseUrl}/`);
  await page.evaluate(() => document.fonts.ready);
  await assertNoOverflow(page, width);
  await page.screenshot({ path: join(output, `home-${width}.png`), fullPage: true });

  await page.goto(`${baseUrl}/login`);
  await assertNoOverflow(page, width);
  await page.screenshot({ path: join(output, `login-${width}.png`), fullPage: true });

  await page.getByLabel('Consultorio').fill('demo');
  await page.getByLabel('Email').fill('admin@demo.test');
  await page.getByLabel('Contraseña').fill('demo-password');
  await page.getByRole('button', { name: 'Entrar al panel' }).click();
  await page.waitForURL('**/app');
  await assertNoOverflow(page, width);
  await page.screenshot({ path: join(output, `app-${width}.png`), fullPage: true });

  await page.goto(`${baseUrl}/ruta-inexistente`);
  await assertNoOverflow(page, width);
  await page.screenshot({ path: join(output, `404-${width}.png`), fullPage: true });

  await context.close();
  console.log(`captured ${width}px`);
}

await browser.close();
console.log(`screenshots written to ${output}`);

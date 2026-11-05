import { mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const output = join(root, '..', 'openspec', 'changes', 'f-02-reserva-publica-landing', 'mockups', 'previews');
const baseUrl = process.env.VISUAL_BASE_URL ?? 'http://127.0.0.1:4173';

const CATALOGO = {
  prestaciones: [
    { id: 'PREST-30', nombre: 'Consulta', duracion_min: 30 },
    { id: 'PREST-45', nombre: 'Limpieza', duracion_min: 45 },
  ],
  profesionales: [{ id: 'P1', nombre: 'Dra. Demo' }],
};

const HUECOS = [
  { inicio: '2026-10-06T09:00:00-03:00', fin: '2026-10-06T09:30:00-03:00', profesional_id: 'P1', sillon_id: 'S1' },
  { inicio: '2026-10-06T10:00:00-03:00', fin: '2026-10-06T10:30:00-03:00', profesional_id: 'P1', sillon_id: 'S2' },
];

const RESERVA = {
  turno_id: 'TURNO-DEMO',
  estado: 'PENDIENTE',
  inicio: '2026-10-06T09:00:00-03:00',
  fin: '2026-10-06T09:30:00-03:00',
  origen: 'PUBLICO',
  prestacion: 'PREST-30',
  sillon_id: 'S1',
  token_publico: 'TOK-DEMO',
};

async function esperarServidor() {
  for (let intento = 0; intento < 60; intento += 1) {
    try {
      const respuesta = await globalThis.fetch(baseUrl);
      if (respuesta.ok) return;
    } catch {
      // el preview todavía no está listo
    }
    await new Promise((resolve) => globalThis.setTimeout(resolve, 500));
  }
  throw new Error(`preview no disponible en ${baseUrl}`);
}

async function assertSinOverflow(page, etiqueta) {
  const desborda = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  if (desborda) {
    throw new Error(`overflow horizontal en ${etiqueta} (${page.url()})`);
  }
}

await esperarServidor();
await mkdir(output, { recursive: true });

const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});
const errores = [];

async function nuevaPagina(width, { estado409 = false } = {}) {
  const context = await browser.newContext({ viewport: { width, height: 900 } });
  await context.route('**/api/publico/T1/catalogo', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CATALOGO) }),
  );
  await context.route('**/api/publico/T1/disponibilidad*', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(HUECOS) }),
  );
  await context.route('**/api/publico/T1/verificacion', (route) =>
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        verificacion_id: 'VER-DEMO',
        expira_at: '2026-10-06T09:10:00-03:00',
        canal: 'captcha',
      }),
    }),
  );
  await context.route('**/api/publico/T1/reservas/TOK-DEMO', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(RESERVA) }),
  );
  await context.route('**/api/publico/T1/reservas', (route) =>
    route.fulfill(
      estado409
        ? {
            status: 409,
            contentType: 'application/json',
            body: JSON.stringify({
              detalle: 'El horario ya no está libre.',
              alternativas: [
                { inicio: '2026-10-06T10:00:00-03:00', fin: '2026-10-06T10:30:00-03:00' },
                { inicio: '2026-10-06T11:00:00-03:00', fin: '2026-10-06T11:30:00-03:00' },
                { inicio: '2026-10-06T12:00:00-03:00', fin: '2026-10-06T12:30:00-03:00' },
              ],
            }),
          }
        : {
            status: 201,
            contentType: 'application/json',
            body: JSON.stringify(RESERVA),
          },
    ),
  );

  const page = await context.newPage();
  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().includes('fonts.googleapis')) {
      errores.push(message.text());
    }
  });
  return { context, page };
}

async function completarReserva(page) {
  await page.getByRole('button', { name: /Consulta/ }).click();
  await page.getByRole('option', { name: /09:00/ }).click();
  await page.getByRole('button', { name: /Continuar con nombre y tel/ }).click();
  await page.getByRole('textbox', { name: 'Nombre' }).fill('Paciente Demo');
  await page.getByRole('textbox', { name: 'Teléfono' }).fill('+54 9 11 0000 0000');
  await page.getByRole('checkbox', { name: /No soy un robot/i }).click();
  await page.waitForFunction(() => {
    const botones = Array.from(document.querySelectorAll('button'));
    const reservar = botones.find((boton) => boton.textContent?.includes('Reservar turno'));
    return reservar !== undefined && !reservar.disabled;
  });
  await page.getByRole('button', { name: /Reservar turno/i }).click();
}

for (const width of [375, 768, 1440]) {
  const { context, page } = await nuevaPagina(width);
  await page.goto(`${baseUrl}/r/T1`);
  await page.getByRole('button', { name: /Consulta/ }).waitFor();
  await page.evaluate(() => document.fonts.ready);
  await assertSinOverflow(page, 'catálogo');
  await page.screenshot({ path: join(output, `reserva-catalogo-${width}.png`), fullPage: true });
  await context.close();
}

for (const width of [375, 1440]) {
  const { context, page } = await nuevaPagina(width);
  await page.goto(`${baseUrl}/r/T1`);
  await page.getByRole('button', { name: /Consulta/ }).click();
  await page.getByRole('option', { name: /09:00/ }).waitFor();
  await assertSinOverflow(page, 'huecos');
  await page.screenshot({ path: join(output, `reserva-huecos-${width}.png`), fullPage: true });

  await page.getByRole('option', { name: /09:00/ }).click();
  await page.getByRole('button', { name: /Continuar con nombre y tel/ }).click();
  await page.getByRole('textbox', { name: 'Nombre' }).waitFor();
  await assertSinOverflow(page, 'formulario');
  await page.screenshot({ path: join(output, `reserva-formulario-${width}.png`), fullPage: true });
  await context.close();
}

for (const width of [375, 1440]) {
  const { context, page } = await nuevaPagina(width);
  await page.goto(`${baseUrl}/r/T1`);
  await completarReserva(page);
  await page.getByRole('heading', { name: /Tu turno/i }).waitFor();
  await assertSinOverflow(page, 'confirmación');
  await page.screenshot({ path: join(output, `reserva-confirmacion-${width}.png`), fullPage: true });
  await context.close();
}

{
  const width = 375;
  const { context, page } = await nuevaPagina(width, { estado409: true });
  await page.goto(`${baseUrl}/r/T1`);
  await completarReserva(page);
  await page.getByRole('listbox', { name: /alternativos/i }).waitFor();
  await assertSinOverflow(page, '409 alternativas');
  await page.screenshot({ path: join(output, `reserva-409-${width}.png`), fullPage: true });
  await context.close();
}

await browser.close();
console.log(`capturas en ${output}`);
if (errores.length > 0) {
  console.log(`errores de consola: ${errores.length}`);
  for (const error of errores) console.log(`- ${error}`);
}

/**
 * Lot 4 et non-régression « arrêt du moteur à l'aperçu d'un PDF » :
 *  - aperçu d'un PDF de plusieurs pages, ouvert et refermé rapidement, le moteur doit rester disponible ;
 *  - historique d'activité (filtres, valeurs avant/après), connexions, diagnostic, intégrité.
 *   node tests/e2e/history.cjs [--shots dossier]
 */
const { chromium } = require("playwright");
const { spawn, execFileSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const ROOT = path.resolve(__dirname, "../..");
const PY = process.env.ARCHIPEL_PYTHON || path.join(ROOT, ".venv/bin/python");
const PORT = 24000 + Math.floor(Math.random() * 2000);
const BASE = `http://127.0.0.1:${PORT}/`;
const SHOTS = process.argv.includes("--shots") ? path.resolve(process.argv[process.argv.indexOf("--shots") + 1]) : null;
const PASSWORD = "Agence#2026secure";
const results = [];
let server;

function check(name, cond, detail = "") {
  results.push({ name, ok: !!cond });
  console.log(`${cond ? "✔" : "✘"} ${name}${detail ? " — " + detail : ""}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function shot(page, name, opts = {}) {
  if (!SHOTS) return;
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(SHOTS, name + ".png"), fullPage: !!opts.full });
}
async function go(page, route) {
  await page.goto("about:blank");
  await page.goto(BASE + "#" + route);
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(500);
}
async function api(page, method, url, body) {
  return page.evaluate(async ({ method, url, body }) => {
    const r = await fetch(url, { method, headers: { "Content-Type": "application/json", Authorization: "Bearer " + localStorage.getItem("a41.token") }, body: body ? JSON.stringify(body) : undefined });
    return { status: r.status, data: await r.json().catch(() => null) };
  }, { method, url, body });
}
async function healthy() {
  try { return (await fetch(BASE + "api/health")).ok; } catch { return false; }
}

async function main() {
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "a41hist_"));
  // PDF de 5 pages (fusion des PDF de démonstration) : reproduit l'aperçu multipage du rapport d'incident
  const pdf = path.join(tmp, "Devis_multipage.pdf");
  execFileSync(PY, ["-c", `
import sys
from pypdf import PdfWriter
w = PdfWriter()
for f in ["Devis_BatiOuest_Lot02_GrosOeuvre.pdf", "Devis_Durand_Lot02_GrosOeuvre.pdf", "CCTP_Lot02_GrosOeuvre.pdf", "Devis_LeGoff_Lot02_scan.pdf", "Reglement_PLU_FICTIF_Demo.pdf"]:
    w.append(sys.argv[1] + "/" + f)
w.write(sys.argv[2])`, path.join(ROOT, "database/seeds/demo_files"), pdf]);
  server = spawn(PY, ["-m", "app"], { cwd: path.join(ROOT, "web/backend"), env: { ...process.env, ARCHIPEL_MODE: "server", ARCHIPEL_DATA_DIR: tmp, ARCHIPEL_PORT: String(PORT), ARCHIPEL_DATABASE_URL: "" }, stdio: "ignore" });
  for (let i = 0; i < 100 && !(await healthy()); i++) await sleep(200);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SHOTS ? 2 : 1, locale: "fr-FR", timezoneId: "Europe/Paris" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto(BASE);
  await page.waitForSelector("text=Bienvenue dans Archipel41");
  await page.fill("input[placeholder='Atelier …']", "Atelier Historique");
  const inputs = page.locator("form input");
  await inputs.nth(3).fill("Joseph Martin");
  await inputs.nth(4).fill("joseph@atelier-historique.fr");
  await inputs.nth(5).fill(PASSWORD);
  await inputs.nth(6).fill(PASSWORD);
  await page.click("button:has-text(\"Créer l'agence et me connecter\")");
  await page.waitForSelector("text=Bonjour Joseph");
  const p = (await api(page, "POST", "/api/projects", { code: "26-030", name: "Concession automobile", budget_initial: 850000 })).data;
  await api(page, "PUT", `/api/projects/${p.id}`, { budget_initial: 910000, status: "consultation", version: p.version });

  // ---------------------------------------------------------- aperçu PDF multipage : le moteur doit tenir
  await go(page, "/documents");
  await page.setInputFiles("input[type=file]", [pdf]);
  await page.waitForSelector("text=Devis_multipage.pdf", { timeout: 60000 });
  for (let i = 0; i < 4; i++) {           // ouvertures/fermetures rapides, comme un utilisateur qui navigue
    await page.locator("tr:has-text('Devis_multipage.pdf') button[title='Ouvrir']").click();
    await page.waitForSelector("[role=dialog]");
    await page.waitForTimeout(i === 3 ? 4000 : 250);
    if (i < 3) await page.locator("[role=dialog] button[aria-label=Fermer]").click();
  }
  const imgs = await page.locator("[role=dialog] img[alt^='Page']").count();
  check("Aperçu PDF multipage : pages affichées", imgs >= 4, `${imgs} page(s)`);
  check("Aperçu PDF multipage : le moteur est toujours disponible", await healthy());
  // rafale de 30 rendus simultanés directement sur l'API (pire cas)
  const doc = (await api(page, "GET", "/api/documents")).data.find((d) => d.name === "Devis_multipage.pdf");
  const statuses = await page.evaluate(async (id) => {
    const t = localStorage.getItem("a41.token");
    return Promise.all(Array.from({ length: 30 }, (_, i) => fetch(`/api/documents/${id}/page/${(i % 5) + 1}?scale=1.6&r=${i}`, { headers: { Authorization: "Bearer " + t } }).then((r) => r.status).catch(() => 0)));
  }, doc.id);
  check("30 rendus de pages simultanés : tous servis, moteur toujours disponible", statuses.every((s) => s === 200) && (await healthy()), statuses.filter((s) => s !== 200).length + " échec(s)");
  await shot(page, "62_apercu_pdf");
  await page.locator("[role=dialog] button[aria-label=Fermer]").click();

  // ---------------------------------------------------------- historique d'activité
  await go(page, "/historique");
  await page.locator("select[aria-label=Projet]").selectOption({ label: "26-030 – Concession automobile" });
  await page.locator("select[aria-label=Opération]").selectOption("update");
  await page.waitForSelector("td:has-text('Modification')");
  await page.locator("tr:has-text('Modification')").first().click();
  await page.waitForSelector("text=Ancienne valeur");
  check("Historique : modification filtrée par projet, avec ancienne et nouvelle valeur", (await page.locator("td:has-text('850000')").count()) > 0 && (await page.locator("td:has-text('910000')").count()) > 0);
  await shot(page, "63_historique_activite");
  await page.click("button[role=tab]:has-text('Connexions')");
  await page.waitForSelector("td:has-text('Joseph Martin')");
  check("Historique : connexions listées avec l'appareil", (await page.locator("td:has-text('Chrome')").count() + await page.locator("td:has-text('Navigateur')").count()) > 0);
  // erreur JavaScript simulée → visible dans le diagnostic avec sa référence
  await page.evaluate(() => setTimeout(() => { throw new Error("Erreur de test e2e : composant indisponible"); }, 0));
  await page.waitForTimeout(800);
  errors.length = 0; // erreur volontaire
  await page.click("button[role=tab]:has-text('Erreurs et diagnostic')");
  await page.waitForSelector("text=Journal technique des erreurs");
  await page.waitForSelector("td:has-text('Interface (JavaScript)')", { timeout: 8000 }).catch(() => {});
  check("Diagnostic : l'erreur de l'interface est consignée avec une référence", (await page.locator("td.font-mono:has-text('E-')").count()) > 0);
  await page.locator("td.font-mono:has-text('E-')").first().click();
  await page.waitForSelector("text=En clair");
  check("Diagnostic : détail avec explication compréhensible et contexte", (await page.locator("text=Erreur de test e2e").count()) > 0);
  await shot(page, "64_diagnostic_erreur");
  await page.locator("[role=dialog] button[aria-label=Fermer]").click();
  await shot(page, "65_diagnostic", { full: true });
  await page.click("button[role=tab]:has-text('Intégrité et conservation')");
  await page.waitForSelector("text=Journal intègre");
  check("Intégrité : journal d'activité vérifié et intègre", true);
  const csv = await page.evaluate(async (pid) => (await fetch(`/api/history/activity/export?fmt=csv&project_id=${pid}`, { headers: { Authorization: "Bearer " + localStorage.getItem("a41.token") } })).text(), p.id);
  check("Export CSV de l'historique : valeurs avant → après", csv.includes("850000") && csv.includes("→"));

  check("Aucune erreur JavaScript inattendue", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
}

main().catch((e) => { console.error(e); results.push({ name: "exception", ok: false }); })
  .finally(() => {
    if (server) server.kill();
    const ok = results.filter((r) => r.ok).length;
    console.log(`\n${ok}/${results.length} vérifications réussies`);
    process.exit(ok === results.length ? 0 : 1);
  });

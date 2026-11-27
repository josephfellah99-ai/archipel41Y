/**
 * Lot 6 — Terrain et cartographie, dans le navigateur :
 *  - carte interactive, outils de mesure (distance, surface), repère annoté enregistré ;
 *  - import GeoJSON en Lambert-93 (conversion automatique), GPX et KML ; couches listées, masquées, supprimées ;
 *  - fiche terrain (nombre au format français) enregistrée et relue ; export GeoJSON ;
 *  - identification de parcelle sans accès au service IGN : message clair, pas de plantage.
 *   node tests/e2e/terrain.cjs [--shots dossier]
 */
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const ROOT = path.resolve(__dirname, "../..");
const PY = process.env.ARCHIPEL_PYTHON || path.join(ROOT, ".venv/bin/python");
const PORT = 26000 + Math.floor(Math.random() * 2000);
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
async function shot(page, name) {
  if (!SHOTS) return;
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(SHOTS, name + ".png") });
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
async function tab(page, label) {
  await page.click(`button[role=tab]:has-text('${label}')`);
  await page.waitForTimeout(400);
}
async function mapClick(page, fx, fy, opts = {}) {
  const box = await page.locator("[aria-label='Carte du terrain']").boundingBox();
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy, opts);
  await page.waitForTimeout(250);
}

async function main() {
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "a41terrain_"));
  // jeux de données géographiques fictifs (Normanville, Eure)
  const gj = path.join(tmp, "Releve_geometre_L93.geojson");
  fs.writeFileSync(gj, JSON.stringify({
    type: "FeatureCollection", crs: { type: "name", properties: { name: "urn:ogc:def:crs:EPSG::2154" } },
    features: [
      { type: "Feature", properties: { nom: "Limite parcellaire" }, geometry: { type: "Polygon", coordinates: [[[573000, 6885000], [573120, 6885000], [573120, 6885090], [573000, 6885090], [573000, 6885000]]] } },
      { type: "Feature", properties: { nom: "Borne B2" }, geometry: { type: "Point", coordinates: [573000, 6885000] } },
    ],
  }));
  const gpx = path.join(tmp, "Releve_terrain.gpx");
  fs.writeFileSync(gpx, `<?xml version="1.0"?><gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
<wpt lat="49.0801" lon="1.1502"><name>Regard EP</name></wpt><wpt lat="49.0805" lon="1.1510"><name>Poteau incendie</name></wpt>
<trk><name>Cheminement</name><trkseg><trkpt lat="49.0800" lon="1.1500"/><trkpt lat="49.0806" lon="1.1512"/></trkseg></trk></gpx>`);
  const kml = path.join(tmp, "Emprise_projet.kml");
  fs.writeFileSync(kml, `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>Emprise extension</name>
<Polygon><outerBoundaryIs><LinearRing><coordinates>1.1498,49.0798,0 1.1515,49.0798,0 1.1515,49.0808,0 1.1498,49.0808,0 1.1498,49.0798,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>`);

  server = spawn(PY, ["-m", "app"], { cwd: path.join(ROOT, "web/backend"), env: { ...process.env, ARCHIPEL_MODE: "server", ARCHIPEL_DATA_DIR: tmp, ARCHIPEL_PORT: String(PORT), ARCHIPEL_DATABASE_URL: "" }, stdio: "ignore" });
  for (let i = 0; i < 100 && !(await healthy()); i++) await sleep(200);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SHOTS ? 2 : 1, locale: "fr-FR", timezoneId: "Europe/Paris" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const prompts = [];
  page.on("dialog", async (d) => {
    if (d.type() === "prompt") { const v = prompts.shift() ?? ""; await d.accept(v); } else await d.accept();
  });

  await page.goto(BASE);
  await page.waitForSelector("text=Bienvenue dans Archipel41");
  await page.fill("input[placeholder='Atelier …']", "Atelier Terrain");
  const inputs = page.locator("form input");
  await inputs.nth(3).fill("Joseph Martin");
  await inputs.nth(4).fill("joseph@atelier-terrain.fr");
  await inputs.nth(5).fill(PASSWORD);
  await inputs.nth(6).fill(PASSWORD);
  await page.click("button:has-text(\"Créer l'agence et me connecter\")");
  await page.waitForSelector("text=Bonjour Joseph");
  const p = (await api(page, "POST", "/api/projects", { code: "26-041", name: "Extension concession (démo)", latitude: 49.0802, longitude: 1.1505, city: "Normanville" })).data;
  check("Projet de démonstration localisé créé", !!p?.id);
  await page.evaluate((id) => localStorage.setItem("a41.project", id), p.id);
  await page.goto(BASE + "#/terrain");
  await page.reload();
  await page.waitForSelector("[aria-label='Carte du terrain'].leaflet-container", { timeout: 15000 });
  check("Carte interactive affichée (Leaflet) avec échelle métrique", (await page.locator(".leaflet-control-scale").count()) === 1);

  // ---------------------------------------------------------- mesures
  await page.click("button[title='Mesurer une distance']");
  await mapClick(page, 0.35, 0.5); await mapClick(page, 0.65, 0.5);
  const dist = await page.locator("b:has-text('Longueur')").textContent().catch(() => "");
  const dm = parseFloat((dist.match(/([\d\s ,]+)\s*m\b/) || [])[1]?.replace(/[\s ]/g, "").replace(",", ".") || "0");
  check("Mesure de distance affichée", dm > 0, dist.trim());
  await page.click("button[title='Mesurer une surface']");
  await mapClick(page, 0.4, 0.4); await mapClick(page, 0.6, 0.4); await mapClick(page, 0.6, 0.6);
  const area = await page.locator("b:has-text('Surface')").textContent().catch(() => "");
  check("Mesure de surface et de périmètre affichée", /Surface : .*m².*périmètre/.test(area), area.trim());
  await shot(page, "70_terrain_mesure");

  // ---------------------------------------------------------- repère annoté
  await page.click("button[title='Ajouter un repère']");
  prompts.push("Borne B1 (test)", "Borne retrouvée, à confirmer par le géomètre");
  await mapClick(page, 0.5, 0.45);
  await page.waitForSelector("text=Annotation enregistrée.", { timeout: 8000 }).catch(() => {});
  const layers1 = (await api(page, "GET", `/api/projects/${p.id}/geo/layers`)).data || [];
  const ann = layers1.find((l) => l.kind === "annotations");
  const feat = ann?.data?.features?.[0];
  check("Repère enregistré avec son intitulé et son observation", feat?.properties?.label === "Borne B1 (test)" && /géomètre/.test(feat?.properties?.note || ""));
  check("Coordonnées du repère dans la zone du projet", feat && Math.abs(feat.geometry.coordinates[1] - 49.08) < 0.05 && Math.abs(feat.geometry.coordinates[0] - 1.15) < 0.05,
    feat ? feat.geometry.coordinates.map((x) => x.toFixed(5)).join(", ") : "");
  await page.click("button[title='Ajouter un repère']"); // désactive l'outil

  // ---------------------------------------------------------- identification de parcelle hors ligne
  await page.click("button[title='Identifier la parcelle']");
  await mapClick(page, 0.52, 0.52);
  await page.waitForSelector("text=Parcelle identifiée", { timeout: 20000 }).catch(() => {});
  const card = page.locator("text=Parcelle identifiée").locator("xpath=ancestor::*[contains(@class,'card')][1]");
  let parcelCard = "";
  for (let i = 0; i < 60; i++) {   // attendre la fin du chargement (le service IGN peut être injoignable)
    parcelCard = (await card.textContent().catch(() => "")) || "";
    if (parcelCard && !/Chargement/.test(parcelCard) && (await card.locator(".animate-spin").count()) === 0) break;
    await sleep(500);
  }
  check("Identification de parcelle : réponse claire même sans accès au service IGN",
    !/Chargement/.test(parcelCard) && parcelCard.replace("Parcelle identifiée", "").trim().length > 10 && (await healthy()), parcelCard.replace(/\s+/g, " ").slice(0, 160));
  await page.click("button[title='Identifier la parcelle']");

  // ---------------------------------------------------------- imports
  await tab(page, "Couches et imports");
  for (const [f, re] of [[gj, /Releve_geometre_L93/], [gpx, /Releve_terrain/], [kml, /Emprise_projet/]]) {
    await page.setInputFiles("input[aria-label='Fichiers géographiques']", f);
    await page.waitForSelector("text=importée", { timeout: 20000 }).catch(() => {});
    await page.waitForTimeout(600);
  }
  const layers2 = (await api(page, "GET", `/api/projects/${p.id}/geo/layers`)).data || [];
  const l93 = layers2.find((l) => /Releve_geometre_L93/.test(l.name));
  check("Import GeoJSON Lambert-93 : système reconnu", !!l93 && /2154|Lambert/.test(l93.crs_source || ""), l93?.crs_source || "absent");
  const b = l93?.bounds || [];
  // 573000 / 6885000 en Lambert-93 ≈ 1,26° E / 49,05° N (Eure) : contrôle d'ordre de grandeur
  check("Import Lambert-93 : coordonnées converties en WGS84 dans l'Eure", b.length === 4 && b[0] > 0.8 && b[2] < 1.4 && b[1] > 48.9 && b[3] < 49.2, b.map((x) => x.toFixed(4)).join(", "));
  check("Import GPX : points et trace", layers2.some((l) => /Releve_terrain/.test(l.name) && l.feature_count >= 3));
  check("Import KML : emprise", layers2.some((l) => /Emprise_projet/.test(l.name) && l.feature_count === 1));
  await page.waitForSelector("td:has-text('Releve_geometre_L93')");
  await shot(page, "71_terrain_couches");

  // ---------------------------------------------------------- carte : couches affichées, masquer
  await tab(page, "Carte");
  await page.waitForTimeout(800);
  const shapes = await page.locator(".leaflet-overlay-pane canvas, .leaflet-overlay-pane path").count();
  check("Couches importées dessinées sur la carte", shapes > 0);
  await shot(page, "72_terrain_carte");
  const hide = page.locator("li:has-text('Releve_terrain') button[aria-label='Masquer'], div:has-text('Releve_terrain') > button[aria-label='Masquer']").first();
  if (await hide.count()) await hide.click(); else await page.locator("button[aria-label='Masquer']").nth(1).click();
  await page.waitForTimeout(800);
  const vis = ((await api(page, "GET", `/api/projects/${p.id}/geo/layers`)).data || []).filter((l) => !l.visible).length;
  check("Couche masquée (état enregistré)", vis >= 1);

  // ---------------------------------------------------------- fiche terrain
  await tab(page, "Fiche terrain");
  await page.locator("label:has-text('Références cadastrales') input").fill("27438 ZB 112, ZB 113");
  await page.locator("label:has-text('Superficie du terrain') input").fill("4 250,5");
  await page.locator("label:has-text('Zone du PLU') input").fill("UZ");
  await page.click("button:has-text('Enregistrer')");
  await page.waitForTimeout(1200);
  const pp = (await api(page, "GET", `/api/projects/${p.id}`)).data;
  check("Fiche terrain : références et zone enregistrées", pp?.terrain?.parcelle === "27438 ZB 112, ZB 113" && pp?.terrain?.zone_plu === "UZ");
  check("Fiche terrain : « 4 250,5 » m² lu comme 4250,5", Math.abs((pp?.terrain?.superficie_m2 ?? 0) - 4250.5) < 1e-6, String(pp?.terrain?.superficie_m2));
  await page.reload(); await page.waitForTimeout(800); await tab(page, "Fiche terrain");
  const sup = await page.locator("label:has-text('Superficie du terrain') input").inputValue();
  check("Fiche terrain : valeur relue après rechargement", /4\s?250,5/.test(sup.replace(/ /g, " ")), sup);
  await shot(page, "73_terrain_fiche");

  // ---------------------------------------------------------- export
  const exp = await page.evaluate(async (pid) => {
    const r = await fetch(`/api/projects/${pid}/geo/export?fmt=geojson`, { headers: { Authorization: "Bearer " + localStorage.getItem("a41.token") } });
    return { status: r.status, text: await r.text() };
  }, p.id);
  let fc = null; try { fc = JSON.parse(exp.text); } catch { /* */ }
  check("Export GeoJSON : collection complète avec le repère annoté", exp.status === 200 && fc?.type === "FeatureCollection" && exp.text.includes("Borne B1 (test)"),
    fc ? `${fc.features.length} objet(s)` : exp.status);
  const kmlx = await page.evaluate(async (pid) => (await fetch(`/api/projects/${pid}/geo/export?fmt=kml`, { headers: { Authorization: "Bearer " + localStorage.getItem("a41.token") } })).text(), p.id);
  check("Export KML lisible par Google Earth", kmlx.includes("<kml") && kmlx.includes("Borne B1"));

  // ---------------------------------------------------------- suppression d'une couche
  await tab(page, "Couches et imports");
  const before = (await api(page, "GET", `/api/projects/${p.id}/geo/layers`)).data.length;
  await page.locator("tr:has-text('Emprise_projet') button[aria-label='Supprimer la couche']").click();
  await page.waitForTimeout(1000);
  const after = (await api(page, "GET", `/api/projects/${p.id}/geo/layers`)).data.length;
  check("Suppression d'une couche après confirmation", after === before - 1, `${before} → ${after}`);

  check("Moteur toujours disponible", await healthy());
  check("Aucune erreur JavaScript", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
}

main().catch((e) => { console.error(e); results.push({ name: "exception", ok: false }); })
  .finally(() => {
    server?.kill();
    const ok = results.filter((r) => r.ok).length;
    console.log(`\n${ok}/${results.length} vérifications réussies`);
    process.exit(ok === results.length ? 0 : 1);
  });

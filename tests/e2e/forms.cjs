/**
 * Tests de fiabilité des formulaires (Playwright / Chromium).
 *   node tests/e2e/forms.cjs
 * Pour chaque formulaire critique : saisie réaliste (virgules, espaces, champs vidés),
 * enregistrement, rechargement complet de la page, puis relecture EN BASE via l'API.
 * Vérifie aussi qu'une erreur ne fait jamais disparaître la saisie.
 */
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const ROOT = path.resolve(__dirname, "../..");
const PY = process.env.ARCHIPEL_PYTHON || path.join(ROOT, ".venv/bin/python");
const PORT = 20000 + Math.floor(Math.random() * 2000);
const BASE = `http://127.0.0.1:${PORT}/`;
const PASSWORD = "Agence#2026secure";
const results = [];
let server;

function check(name, cond, detail = "") {
  results.push({ name, ok: !!cond });
  console.log(`${cond ? "✔" : "✘"} ${name}${detail ? " — " + detail : ""}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function startServer() {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), "a41forms_"));
  server = spawn(PY, ["-m", "app"], { cwd: path.join(ROOT, "web/backend"), env: { ...process.env, ARCHIPEL_MODE: "server", ARCHIPEL_DATA_DIR: data, ARCHIPEL_PORT: String(PORT), ARCHIPEL_DATABASE_URL: "" }, stdio: "ignore" });
  for (let i = 0; i < 100; i++) {
    try { const r = await fetch(BASE + "api/health"); if (r.ok) return; } catch { /* démarrage */ }
    await sleep(200);
  }
  throw new Error("serveur non démarré");
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

const field = (scope, label) => scope.locator(`label:has(span.label:text-is("${label}"))`).locator("input, select, textarea").first();

async function main() {
  await startServer();
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 860 }, locale: "fr-FR", timezoneId: "Europe/Paris" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  // Agence
  await page.goto(BASE);
  await page.waitForSelector("text=Bienvenue dans Archipel41");
  await page.fill("input[placeholder='Atelier …']", "Atelier Formulaires");
  const inputs = page.locator("form input");
  await inputs.nth(3).fill("Alex Martin");
  await inputs.nth(4).fill("alex@atelier-formulaires.fr");
  await inputs.nth(5).fill(PASSWORD);
  await inputs.nth(6).fill(PASSWORD);
  await page.click("button:has-text(\"Créer l'agence et me connecter\")");
  await page.waitForSelector("text=Bonjour Alex");

  // ---------------------------------------------------------- entreprise : spécialités avec virgules
  await go(page, "/annuaire");
  await page.click("button[role=tab]:has-text('Entreprises')");
  await page.click("button:has-text('Nouvelle entreprise')");
  let dlg = page.locator("[role=dialog]");
  await field(dlg, "Nom / raison sociale").fill("Charpentes de l'Erdre");
  const spec = field(dlg, "Spécialités (séparées par des virgules)");
  await spec.click();
  await spec.pressSequentially("Charpente, Couverture, Zinguerie", { delay: 15 });
  check("Entreprise : la virgule reste saisissable dans « Spécialités »", (await spec.inputValue()) === "Charpente, Couverture, Zinguerie", await spec.inputValue());
  // un clic à l'extérieur ne ferme pas la fenêtre et ne perd rien
  await page.mouse.click(5, 5);
  check("Fenêtre de saisie : un clic extérieur ne fait pas perdre la saisie", (await page.locator("[role=dialog]").count()) === 1 && (await spec.inputValue()).includes("Zinguerie"));
  await dlg.locator("button:has-text('Créer')").click();
  await page.waitForSelector("text=Historique");
  let r = await api(page, "GET", "/api/companies");
  const comp = r.data.find((c) => c.name === "Charpentes de l'Erdre");
  check("Entreprise : spécialités enregistrées en base", comp && comp.specialties.join("|") === "Charpente|Couverture|Zinguerie", JSON.stringify(comp?.specialties));

  // ---------------------------------------------------------- projet : montants et surfaces à la française
  await go(page, "/projets");
  await page.click("button:has-text('Nouveau projet')");
  dlg = page.locator("[role=dialog]");
  await field(dlg, "Code projet").fill("26-101");
  await field(dlg, "Nom du projet").fill("École des Sablons");
  await field(dlg, "Surface (m²)").fill("1 152,5");
  await field(dlg, "Budget travaux initial (€ HT)").fill("1 250 000,50");
  await field(dlg, "Taux d'honoraires (%)").fill("11,5");
  await field(dlg, "Début").fill("2026-12-01");
  await dlg.locator("button:has-text('Créer le projet')").click();
  await page.waitForSelector("text=Fiche projet");
  const pid = page.url().split("/projets/")[1];
  await page.reload();
  await page.waitForSelector("text=Fiche projet");
  r = await api(page, "GET", `/api/projects/${pid}`);
  check("Projet : « 1 250 000,50 » € enregistré exactement", r.data.budget_initial === 1250000.5, String(r.data.budget_initial));
  check("Projet : surface « 1 152,5 » m² et honoraires « 11,5 » %", r.data.surface_m2 === 1152.5 && r.data.fee_rate === 11.5, `${r.data.surface_m2} / ${r.data.fee_rate}`);
  check("Projet : date de début enregistrée", r.data.start_date === "2026-12-01", r.data.start_date);
  check("Projet : valeurs réaffichées après rechargement", (await field(page, "Budget travaux initial (€ HT)").inputValue()).replace(/\s/g, "").startsWith("1250000"));

  // avancement : le champ peut être vidé puis ressaisi (plus de « 0 » imposé)
  const prog = field(page, "Avancement global (%)");
  await prog.fill("");
  check("Projet : le champ « Avancement » peut être vidé", (await prog.inputValue()) === "");
  await prog.fill("35");
  // saisie invalide : signalée, conservée, et rien n'est perdu à l'échec
  const bud = field(page, "Budget travaux initial (€ HT)");
  await bud.fill("douze mille");
  check("Projet : saisie invalide signalée sous le champ", (await page.locator("text=Nombre invalide").count()) > 0);
  await page.locator("button:has-text('Enregistrer')").first().click();
  await page.waitForTimeout(600);
  check("Projet : après un échec d'enregistrement, la saisie est conservée", (await bud.inputValue()) === "douze mille" && (await prog.inputValue()) === "35");
  await bud.fill("1 300 000");
  await page.locator("button:has-text('Enregistrer')").first().click();
  await page.waitForSelector("text=Projet enregistré.");
  r = await api(page, "GET", `/api/projects/${pid}`);
  check("Projet : modification enregistrée (1 300 000 € ; 35 %)", r.data.budget_initial === 1300000 && r.data.progress === 35, `${r.data.budget_initial} / ${r.data.progress}`);

  // double clic sur Enregistrer : un seul envoi, aucun faux conflit
  const before = r.data.version;
  const btn = page.locator("button:has-text('Enregistrer')").first();
  await Promise.all([btn.click(), btn.click({ force: true }).catch(() => {})]);
  await page.waitForTimeout(1200);
  r = await api(page, "GET", `/api/projects/${pid}`);
  check("Projet : double clic → un seul enregistrement, pas de conflit", (await page.locator("text=Conflit").count()) === 0 && r.data.version - before <= 1, `version ${before} → ${r.data.version}`);

  // terrain : coordonnées avec virgule
  await page.click("button[role=tab]:has-text('Terrain')");
  await field(page, "Latitude (WGS84)").fill("47,2184");
  await field(page, "Longitude (WGS84)").fill("-1,5536");
  await page.locator("button:has-text('Enregistrer')").first().click();
  await page.waitForSelector("text=Projet enregistré.");
  r = await api(page, "GET", `/api/projects/${pid}`);
  check("Terrain : coordonnées « 47,2184 / -1,5536 » enregistrées", r.data.latitude === 47.2184 && r.data.longitude === -1.5536, `${r.data.latitude}, ${r.data.longitude}`);

  // phases : avancement d'une phase
  await page.click("button[role=tab]:has-text('Phases')");
  const ph = page.locator("input[aria-label='Avancement ESQ']");
  await ph.fill("");
  await ph.fill("80");
  await page.locator("button:has-text('Enregistrer')").first().click();
  await page.waitForSelector("text=Projet enregistré.");
  r = await api(page, "GET", `/api/projects/${pid}`);
  check("Phases : avancement ESQ 80 % enregistré", r.data.phases.find((p) => p.code === "ESQ").progress === 80);

  // lot : budget « 36 000 » et marché « 34 783,50 »
  await page.click("button[role=tab]:has-text('Lots')");
  await page.click("button:has-text('Ajouter un lot')");
  dlg = page.locator("[role=dialog]");
  await field(dlg, "N° de lot").fill("02");
  await field(dlg, "Désignation").fill("Gros œuvre");
  await field(dlg, "Budget (€ HT)").fill("36 000");
  await field(dlg, "Montant du marché (€ HT)").fill("34 783,50");
  await dlg.locator("button:has-text('Enregistrer')").click();
  await page.waitForSelector("td:has-text('Gros œuvre')");
  r = await api(page, "GET", `/api/lots?project_id=${pid}`);
  check("Lot : « 36 000 » et « 34 783,50 » enregistrés", r.data[0].budget === 36000 && r.data[0].contract_amount === 34783.5, `${r.data[0].budget} / ${r.data[0].contract_amount}`);

  // ---------------------------------------------------------- finances : montant avec espaces et virgule
  await go(page, "/finances");
  await page.click("button[role=tab]:has-text('Écritures')");
  await page.click("button.btn-primary:has-text('Écriture')");
  dlg = page.locator("[role=dialog]");
  await field(dlg, "Libellé").fill("Situation n°1 gros œuvre");
  await field(dlg, "Montant HT (€)").fill("12 500,40");
  check("Finances : TTC estimé affiché pendant la saisie", (await dlg.locator("text=TTC estimé").count()) > 0);
  await dlg.locator("button:has-text('Enregistrer')").click();
  await page.waitForSelector("td:has-text('Situation n°1')");
  r = await api(page, "GET", `/api/finance-entries?project_id=${pid}`);
  check("Finances : 12 500,40 € HT → 15 000,48 € TTC en base", r.data[0].amount_ht === 12500.4 && r.data[0].amount_ttc === 15000.48, `${r.data[0].amount_ht} → ${r.data[0].amount_ttc}`);

  // ---------------------------------------------------------- planning : durée vidée puis ressaisie
  await go(page, "/planning");
  await page.click("button.btn-primary:has-text('Tâche')");
  dlg = page.locator("[role=dialog]");
  await field(dlg, "Intitulé").fill("Fondations");
  await field(dlg, "Début").fill("2027-01-04");
  const dur = field(dlg, "Durée (jours, 0 = jalon)");
  await dur.fill("");
  await dur.fill("12");
  await dlg.locator("button:has-text('Enregistrer')").click();
  await page.waitForTimeout(900);
  r = await api(page, "GET", `/api/tasks?project_id=${pid}`);
  const task = (r.data || []).find((t) => t.name === "Fondations");
  check("Planning : tâche de 12 jours enregistrée", task && task.duration_days === 12 && task.start_date === "2027-01-04", task ? `${task.start_date} / ${task.duration_days} j` : "absente");

  // ---------------------------------------------------------- agenda : fin avant début refusée sans perte
  await go(page, "/agenda");
  await page.click("button.btn-primary:has-text('Rendez-vous')");
  dlg = page.locator("[role=dialog]");
  await field(dlg, "Objet").fill("Réunion de chantier n°1");
  await field(dlg, "Début").fill("2027-01-11T09:00");
  await field(dlg, "Fin").fill("2027-01-11T08:00");
  check("Agenda : « fin avant début » signalé en français", (await dlg.locator("text=La fin doit être postérieure au début.").count()) > 0);
  check("Agenda : enregistrement bloqué tant que les dates sont incohérentes", await dlg.locator("button:has-text('Enregistrer')").isDisabled());
  await field(dlg, "Fin").fill("2027-01-11T10:30");
  await dlg.locator("button:has-text('Enregistrer')").click();
  await page.waitForTimeout(900);
  r = await api(page, "GET", "/api/events?start=2027-01-10T00:00:00Z&end=2027-01-12T00:00:00Z");
  const ev = (r.data || []).find((e) => e.title === "Réunion de chantier n°1");
  check("Agenda : rendez-vous enregistré à 9 h 00 – 10 h 30 (heure de Paris)", ev && new Date(ev.start).toISOString() === "2027-01-11T08:00:00.000Z" && new Date(ev.end).toISOString() === "2027-01-11T09:30:00.000Z", ev ? `${ev.start} → ${ev.end}` : "absent");

  // ---------------------------------------------------------- API : nombres français acceptés, nombre illisible refusé
  r = await api(page, "POST", "/api/finance-entries", { project_id: pid, kind: "facture", label: "Test API", amount_ht: "1 000,10", vat_rate: "20", entry_date: "2027-01-15", status: "prevu" });
  check("API : « 1 000,10 » accepté côté serveur", r.status === 201 && r.data.amount_ht === 1000.1, `${r.status} ${r.data?.amount_ht}`);
  r = await api(page, "POST", "/api/finance-entries", { project_id: pid, kind: "facture", label: "Test API", amount_ht: "mille", entry_date: "2027-01-15", status: "prevu" });
  check("API : « mille » refusé avec un message explicite", r.status === 422 && JSON.stringify(r.data).includes("mille"));

  check("Aucune erreur JavaScript dans le navigateur", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
}

main().catch((e) => { console.error(e); results.push({ name: "exception", ok: false }); })
  .finally(() => {
    if (server) server.kill();
    const ok = results.filter((r) => r.ok).length;
    console.log(`\n${ok}/${results.length} vérifications réussies`);
    process.exit(ok === results.length ? 0 : 1);
  });

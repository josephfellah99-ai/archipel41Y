/**
 * Lots 2 et 3 dans le navigateur : trois modes de connexion, gestion de l'équipe et des autorisations,
 * invitation à un projet, espace invité isolé, révocation, commentaires et notifications.
 *   node tests/e2e/access.cjs [--shots dossier]
 */
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const ROOT = path.resolve(__dirname, "../..");
const PY = process.env.ARCHIPEL_PYTHON || path.join(ROOT, ".venv/bin/python");
const PORT = 22000 + Math.floor(Math.random() * 2000);
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
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOTS, name + ".png"), fullPage: !!opts.full });
}
async function startServer() {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), "a41acc_"));
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

async function loginAs(page, mode, email, password) {
  await page.goto("about:blank");
  await page.goto(BASE);
  await page.waitForSelector("text=Connexion");
  await page.click(`button[role=tab]:has-text('${mode}')`);
  await page.fill("input[type=email]", email);
  await page.fill("input[type=password]", password);
  await page.click("form button.btn-primary");
}

async function main() {
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  await startServer();
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SHOTS ? 2 : 1, locale: "fr-FR", timezoneId: "Europe/Paris" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  // Agence + données
  await page.goto(BASE);
  await page.waitForSelector("text=Bienvenue dans Archipel41");
  await page.fill("input[placeholder='Atelier …']", "Atelier Accès");
  const inputs = page.locator("form input");
  await inputs.nth(3).fill("Camille Durand");
  await inputs.nth(4).fill("camille@atelier-acces.fr");
  await inputs.nth(5).fill(PASSWORD);
  await inputs.nth(6).fill(PASSWORD);
  await page.click("button:has-text(\"Créer l'agence et me connecter\")");
  await page.waitForSelector("text=Bonjour Camille");
  const p1 = (await api(page, "POST", "/api/projects", { code: "26-014", name: "Maison Martin", city: "Nantes", status: "chantier", description: "Extension bois de 45 m²." })).data;
  const p2 = (await api(page, "POST", "/api/projects", { code: "26-020", name: "Bureaux Erdre (confidentiel)", confidential: true })).data;
  await api(page, "POST", "/api/finance-entries", { project_id: p1.id, kind: "marche", label: "Marché GO", amount_ht: 34783, vat_rate: 20, entry_date: "2026-11-02", status: "valide" });

  // ---------------------------------------------------------- Équipe : collaborateur avec autorisations fines
  await go(page, "/equipe");
  check("Navigation : 12 entrées dont Équipe, Chantiers, Terrain, Historique", (await page.locator("aside nav >> text=Chantiers").count()) > 0 && (await page.locator("aside nav >> text=Historique et activité").count()) > 0);
  await page.click("button.btn-primary:has-text('Collaborateur')");
  let dlg = page.locator("[role=dialog]");
  await field(dlg, "Nom complet").fill("Léa Petit");
  await field(dlg, "E-mail (identifiant)").fill("lea@atelier-acces.fr");
  await field(dlg, "Fonction").fill("Architecte");
  await field(dlg, "Mot de passe initial").fill("LeaPetit#2026");
  await dlg.locator("button[role=tab]:has-text('Autorisations')").click();
  await dlg.locator("select[aria-label='Accès Finances']").selectOption("none");
  await dlg.locator("select[aria-label='Accès Agenda']").selectOption("read");
  await shot(page, "55_equipe_autorisations");
  await dlg.locator("button:has-text('Enregistrer')").click();
  await page.waitForSelector("text=Léa Petit");
  let r = await api(page, "GET", "/api/users");
  const lea = r.data.find((u) => u.email === "lea@atelier-acces.fr");
  check("Équipe : compte créé avec « Finances : aucun accès » et « Agenda : consultation »", lea && lea.permissions.modules.finances === "none" && lea.permissions.modules.agenda === "read");
  await api(page, "PUT", `/api/projects/${p1.id}`, { team: [{ user_id: lea.id, role: "Architecte" }], version: p1.version });
  await shot(page, "56_equipe", { full: true });

  // ---------------------------------------------------------- Invitation à un projet
  await page.click("button[role=tab]:has-text('Gestion des accès invités')");
  await page.click("button:has-text('Créer une invitation')");
  dlg = page.locator("[role=dialog]");
  await field(dlg, "Intitulé").fill("Présentation à M. et Mme Martin");
  await field(dlg, "Nom de l'invité").fill("M. Martin");
  await dlg.getByRole("checkbox", { name: "26-014 – Maison Martin", exact: true }).check();
  await dlg.getByRole("checkbox", { name: "Planning", exact: true }).check();
  await dlg.getByRole("checkbox", { name: "Autoriser les commentaires" }).check();
  await shot(page, "57_invitation_creation");
  await dlg.locator("button:has-text('Générer le code')").click();
  await page.waitForSelector("text=Invitation créée");
  const code = (await page.locator("[aria-label='Code d\\'invitation']").innerText()).trim();
  check("Invitation : code unique au format XXXX-XXXX-XXXX affiché une fois", /^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(code), code);
  await shot(page, "58_invitation_code");
  await page.click("button:has-text(\"J'ai noté le code\")");
  check("Invitation : le code n'est plus affiché ensuite (masqué)", (await page.locator(`text=${code}`).count()) === 0 && (await page.locator("text=••••-••••-").count()) > 0);

  // ---------------------------------------------------------- Connexion administrateur refusée à un collaborateur
  await page.evaluate(() => localStorage.removeItem("a41.token"));
  await loginAs(page, "Administrateur", "lea@atelier-acces.fr", "LeaPetit#2026");
  await page.waitForSelector("text=n'a pas les droits d'administration");
  check("Connexion : un collaborateur est refusé sur l'accès « Administrateur »", true);
  await shot(page, "59_connexion_modes");

  // ---------------------------------------------------------- Connexion collaborateur : modules masqués et refusés
  await page.click("button[role=tab]:has-text('Collaborateur')");
  await page.fill("input[type=password]", "LeaPetit#2026");
  await page.click("form button.btn-primary");
  await page.waitForSelector("text=Bonjour Léa");
  check("Collaborateur : « Finances » absent de la navigation", (await page.locator("aside nav >> text=Finances").count()) === 0);
  r = await api(page, "GET", "/api/finance-entries");
  check("Collaborateur : finances refusées par le serveur (pas seulement masquées)", r.status === 403, String(r.status));
  r = await api(page, "POST", "/api/events", { title: "Test", start: "2027-01-11T08:00:00Z", end: "2027-01-11T09:00:00Z" });
  check("Collaborateur : agenda en consultation seule (création refusée)", r.status === 403);
  // commentaire avec mention → notification de l'administratrice
  await api(page, "POST", "/api/comments", { entity: "projects", entity_id: p1.id, body: "@Camille Durand les plans PRO sont prêts pour validation." });
  r = await api(page, "GET", `/api/projects`);
  check("Collaborateur : projet confidentiel non visible", !r.data.some((p) => p.id === p2.id));

  // ---------------------------------------------------------- Espace invité
  await page.evaluate(() => localStorage.removeItem("a41.token"));
  await page.goto("about:blank");
  await page.goto(BASE);
  await page.waitForSelector("text=Connexion");
  await page.click("button[role=tab]:has-text('Invité')");
  await page.fill("input[aria-label=\"Code d'invitation\"]", code.toLowerCase().replace(/-/g, ""));
  check("Invité : saisie tolérante (minuscules, sans tirets) reformatée", (await page.inputValue("input[aria-label=\"Code d'invitation\"]")) === code);
  await page.click("form button.btn-primary");
  await page.waitForSelector("text=espace invité");
  await page.waitForSelector("text=26-014 – Maison Martin", { timeout: 8000 }).catch(() => {});
  check("Invité : espace dédié, limité au projet partagé", (await page.locator("text=26-014 – Maison Martin").count()) > 0 && (await page.locator("aside nav").count()) === 0);
  check("Invité : aucune donnée financière ni projet confidentiel affichés", (await page.locator("text=34").count()) === 0 && (await page.locator("text=Bureaux Erdre").count()) === 0);
  r = await api(page, "GET", "/api/projects");
  check("Invité : les routes standard refusent son jeton", r.status === 403, String(r.status));
  r = await api(page, "GET", `/api/guest/projects/${p2.id}`);
  check("Invité : projet non partagé refusé", r.status === 403);
  await shot(page, "60_espace_invite");
  await page.click("button[role=tab]:has-text('Échanges avec')");
  await page.fill("textarea[aria-label='Nouveau commentaire']", "Merci, la proposition d'extension nous convient.");
  await page.click("button:has-text('Publier')");
  await page.waitForSelector("text=la proposition d'extension nous convient");
  check("Invité : commentaire publié (autorisé par l'invitation)", true);
  await page.click("button:has-text('Quitter')");
  await page.waitForSelector("text=Connexion");

  // ---------------------------------------------------------- Administratrice : notifications, révocation
  await loginAs(page, "Administrateur", "camille@atelier-acces.fr", PASSWORD);
  await page.waitForSelector("text=Bonjour Camille");
  await page.click("button[aria-label^='Notifications']");
  await page.waitForSelector("text=vous a mentionné");
  check("Notifications : mention par Léa reçue", true);
  check("Notifications : commentaire de l'invité reçu", (await page.locator("text=Nouveau commentaire").count()) > 0);
  await shot(page, "61_notifications");
  r = await api(page, "GET", "/api/invitations");
  const inv = r.data[0];
  check("Invitation : 1 utilisation comptée, sessions tracées", inv.uses === 1 && inv.sessions === 1);
  await api(page, "POST", `/api/invitations/${inv.id}/revoke`);
  r = await page.evaluate(async (c) => (await fetch("/api/guest/redeem", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: c }) })).status, code);
  check("Invitation révoquée : le code est refusé", r === 401);

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

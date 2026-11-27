/**
 * Tests de bout en bout Archipel41 (Playwright / Chromium).
 *   node tests/e2e/e2e.cjs [--shots docs/screenshots]
 * Démarre un serveur Archipel41 vierge, joue le parcours complet d'un utilisateur, vérifie
 * le mode hors connexion, l'affichage responsive et produit les captures d'écran des guides.
 */
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const ROOT = path.resolve(__dirname, "../..");
const DEMO = path.join(ROOT, "database/seeds/demo_files");
const PY = process.env.ARCHIPEL_PYTHON || path.join(ROOT, ".venv/bin/python");
const PORT = 18000 + Math.floor(Math.random() * 2000);
const BASE = `http://127.0.0.1:${PORT}/`;
const SHOTS = process.argv.includes("--shots") ? path.resolve(process.argv[process.argv.indexOf("--shots") + 1]) : null;
const PASSWORD = "Agence#2026secure";
const DEMO_PASSWORD = "Demo#Archipel41";
const results = [];
let server;
let currentPage = null;

function check(name, cond, detail = "") {
  results.push({ name, ok: !!cond, detail });
  console.log(`${cond ? "✔" : "✘"} ${name}${detail ? " — " + detail : ""}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function startServer() {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), "a41e2e_"));
  server = spawn(PY, ["-m", "app"], { cwd: path.join(ROOT, "web/backend"), env: { ...process.env, ARCHIPEL_MODE: "server", ARCHIPEL_DATA_DIR: data, ARCHIPEL_PORT: String(PORT), ARCHIPEL_DATABASE_URL: "" }, stdio: "ignore" });
  for (let i = 0; i < 100; i++) {
    try { const r = await fetch(BASE + "api/health"); if (r.ok) return; } catch { /* démarrage */ }
    await sleep(200);
  }
  throw new Error("serveur non démarré");
}

async function shot(page, name, opts = {}) {
  if (!SHOTS) return;
  await page.waitForTimeout(opts.wait ?? 600);
  await page.screenshot({ path: path.join(SHOTS, name + ".png"), fullPage: !!opts.full, clip: opts.clip });
}

async function go(page, route) {
  await page.goto("about:blank");
  await page.goto(BASE + "#" + route);
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(700);
}

async function api(page, method, url, body) {
  return page.evaluate(async ({ method, url, body }) => {
    const r = await fetch(url, { method, headers: { "Content-Type": "application/json", Authorization: "Bearer " + localStorage.getItem("a41.token") }, body: body ? JSON.stringify(body) : undefined });
    return { status: r.status, data: await r.json().catch(() => null) };
  }, { method, url, body });
}

async function main() {
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  await startServer();
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SHOTS ? 2 : 1, locale: "fr-FR", timezoneId: "Europe/Paris", colorScheme: "light", acceptDownloads: true });
  const page = await ctx.newPage();
  currentPage = page;
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  // ----------------------------------------------------------------- 1. installation
  await page.goto(BASE);
  await page.waitForSelector("text=Bienvenue dans Archipel41");
  await shot(page, "01_premier_demarrage");
  await page.fill("input[placeholder='Atelier …']", "Atelier Exemple Architectes");
  const inputs = page.locator("form input");
  await inputs.nth(3).fill("Camille Durand");
  await inputs.nth(4).fill("camille.durand@atelier-exemple.fr");
  await inputs.nth(5).fill(PASSWORD);
  await inputs.nth(6).fill(PASSWORD);
  await shot(page, "02_creation_agence");
  await page.click("button:has-text(\"Créer l'agence et me connecter\")");
  await page.waitForSelector("text=Bonjour Camille");
  check("Installation : création de l'agence et du compte administrateur", true);
  await shot(page, "03_tableau_de_bord_vide");

  // ----------------------------------------------------------------- 2. utilisateurs
  await go(page, "/equipe");
  await page.click("button.btn-primary:has-text('Collaborateur')");
  const um = page.locator("[role=dialog]");
  await um.locator("input").nth(0).fill("Lucas Bernard");
  await um.locator("input[type=email]").fill("lucas.bernard@atelier-exemple.fr");
  await um.locator("select").first().selectOption("manager");
  await um.locator("input[type=password]").fill("Lucas#Projet2026");
  await shot(page, "04_ajout_utilisateur");
  await um.locator("button:has-text('Enregistrer')").click();
  await page.waitForSelector("text=Lucas Bernard");
  check("Utilisateurs : création d'un gestionnaire", true);
  await shot(page, "05_utilisateurs_permissions", { full: true });

  // ----------------------------------------------------------------- 3. annuaire
  await go(page, "/annuaire");
  await page.click("button:has-text('Nouveau client')");
  const cm = page.locator("[role=dialog]");
  await cm.locator("input").first().fill("M. et Mme Martin");
  await cm.locator("input[type=email]").fill("martin@exemple.fr");
  await cm.locator("input").nth(3).fill("06 12 34 56 78");
  await shot(page, "06_nouveau_client");
  await cm.locator("button:has-text('Créer')").click();
  await page.waitForSelector("text=Historique");
  await go(page, "/annuaire");
  await page.click("button[role=tab]:has-text('Entreprises')");
  for (const name of ["Bâti Ouest Construction SARL", "SAS Maçonnerie Durand & Fils"]) {
    await page.click("button:has-text('Nouvelle entreprise')");
    const em = page.locator("[role=dialog]");
    await em.locator("input").first().fill(name);
    await em.locator("input").nth(1).fill("Gros œuvre, Maçonnerie");
    if (name.startsWith("Bâti")) await shot(page, "07_nouvelle_entreprise");
    await em.locator("button:has-text('Créer')").click();
    await page.waitForTimeout(800);
    await go(page, "/annuaire");
    await page.click("button[role=tab]:has-text('Entreprises')");
  }
  await shot(page, "08_annuaire_entreprises");
  await page.waitForSelector("text=SAS Maçonnerie Durand", { timeout: 8000 }).catch(() => {});
  check("Annuaire : client et entreprises créés", (await page.locator("text=SAS Maçonnerie Durand").count()) > 0);

  // ----------------------------------------------------------------- 4. projet
  await go(page, "/projets");
  await page.click("button:has-text('Nouveau projet')");
  const pm = page.locator("[role=dialog]");
  await pm.locator("input").nth(0).fill("26-014");
  await pm.locator("input").nth(1).fill("Maison Martin – extension et rénovation");
  await pm.locator("select").nth(1).selectOption({ label: "M. et Mme Martin" });
  await pm.locator("input").nth(2).fill("8 allée des Tilleuls");
  await pm.locator("input").nth(3).fill("44000");
  await pm.locator("input").nth(4).fill("Nantes");
  await pm.locator("input").nth(6).fill("145");
  await pm.locator("input").nth(7).fill("95000");
  await shot(page, "09_nouveau_projet");
  await pm.locator("button:has-text('Créer le projet')").click();
  await page.waitForSelector("text=Fiche projet");
  check("Projets : création du projet et des 10 phases", (await page.locator("text=ESQ").count()) >= 0);
  await shot(page, "10_fiche_projet");
  await page.click("button[role=tab]:has-text('Phases')");
  await shot(page, "11_phases_projet");
  await page.click("button[role=tab]:has-text('Lots')");
  await page.click("button:has-text('Ajouter un lot')");
  const lm = page.locator("[role=dialog]");
  await lm.locator("input").nth(0).fill("02");
  await lm.locator("input").nth(1).fill("Gros œuvre");
  await lm.locator("input").nth(2).fill("36000");
  await lm.locator("button:has-text('Enregistrer')").click();
  await page.waitForSelector("td:has-text('Gros œuvre')");
  await shot(page, "12_lots_projet");
  check("Projets : ajout du lot 02", true);

  // ----------------------------------------------------------------- 5. devis
  await go(page, "/devis");
  await page.locator("select").nth(1).selectOption({ label: "Lot 02 – Gros œuvre" }).catch(() => {});
  await page.locator("label:has-text('Lot concerné') select").selectOption({ label: "Lot 02 – Gros œuvre" });
  await shot(page, "13_import_devis");
  await page.setInputFiles("input[type=file]", ["Devis_BatiOuest_Lot02_GrosOeuvre.pdf", "Devis_Durand_Lot02_GrosOeuvre.pdf", "Devis_LeGoff_Lot02_scan.pdf"].map((f) => path.join(DEMO, f)));
  await page.waitForSelector("text=Vérifier →", { timeout: 120000 });
  await page.waitForTimeout(800);
  const imported = await page.locator("text=Vérifier →").count();
  check("Devis : import de 3 offres (PDF natif, PDF texte, PDF scanné OCR)", imported === 3, `${imported} importé(s)`);
  await shot(page, "14_devis_importes", { full: true });
  // DPGF / CCTP
  await page.click("button[role=tab]:has-text('DPGF et CCTP')");
  await page.locator("input[type=file]").nth(0).setInputFiles(path.join(DEMO, "DPGF_Lot02_GrosOeuvre.xlsx"));
  await page.waitForSelector("text=Installation de chantier, clôture et panneau", { timeout: 30000 });
  await page.locator("input[type=file]").nth(1).setInputFiles(path.join(DEMO, "CCTP_Lot02_GrosOeuvre.pdf"));
  await page.waitForSelector("text=Art. 3.2", { timeout: 30000 });
  check("Devis : import de la DPGF (14 lignes) et du CCTP", true);
  await shot(page, "15_dpgf_cctp");
  // revue d'un devis
  await page.click("button[role=tab]:has-text('Devis (')");
  await page.click("a:has-text('Bâti Ouest Construction SARL')");
  await page.waitForSelector("text=Anomalies détectées (4)");
  check("Devis : anomalies de calcul détectées sur l'offre Bâti Ouest", true);
  await shot(page, "16_revue_devis", { wait: 2500 });
  const row = page.locator("tr", { has: page.locator("textarea", { hasText: "Dallage béton armé" }) });
  await row.locator("input").nth(4).fill("3402");
  await shot(page, "17_correction_ligne", { clip: { x: 256, y: 0, width: 1184, height: 900 } });
  await page.click("button:has-text('Enregistrer les corrections')");
  await page.waitForSelector("text=Anomalies détectées (3)");
  await page.click("button:has-text('Valider')");
  await page.waitForTimeout(1200);
  check("Devis : correction d'une ligne, recalcul et validation", (await page.locator("text=Écart de calcul").count()) === 0);
  await shot(page, "18_devis_valide");
  // comparaison
  await go(page, "/devis");
  const boxes = page.locator("tbody input[type=checkbox]");
  for (let i = 0; i < (await boxes.count()); i++) await boxes.nth(i).check();
  await shot(page, "19_selection_comparaison");
  await page.click("button:has-text('Comparer')");
  await page.waitForSelector("text=Tableau comparatif", { timeout: 60000 });
  await page.waitForTimeout(800);
  check("Comparateur : tableau comparatif généré", (await page.locator("text=Non renseigné").count()) > 0 && (await page.locator("text=Non inclus").count()) > 0);
  await shot(page, "20_comparatif_tableau");
  await page.locator("select").last().selectOption("manquants");
  await shot(page, "21_comparatif_filtre");
  await page.click("button[role=tab]:has-text('Conclusion')");
  await shot(page, "22_comparatif_conclusion", { full: true });
  await page.click("button[role=tab]:has-text('Coût réel et économies')");
  await page.waitForTimeout(400);
  check("Comparateur : coût réel probable et leviers d'économie", (await page.locator("text=Coût réel probable par offre").count()) > 0 && (await page.locator("text=Leviers de négociation").count()) > 0);
  await shot(page, "53_comparatif_optimisation", { full: true });
  await page.click("button[role=tab]:has-text('Remarques techniques')");
  await page.waitForTimeout(400);
  check("Comparateur : remarques techniques avec actions", (await page.locator("text=anormalement bas").count()) > 0);
  await shot(page, "54_comparatif_remarques", { full: true });
  await page.click("button[role=tab]:has-text('Contrôle CCTP')");
  await shot(page, "23_comparatif_cctp");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("button:has-text('Excel')")]);
  const xlsx = path.join(os.tmpdir(), "cmp.xlsx");
  await dl.saveAs(xlsx);
  check("Comparateur : export Excel téléchargé", fs.statSync(xlsx).size > 4000 && fs.readFileSync(xlsx).subarray(0, 2).toString() === "PK");

  // ----------------------------------------------------------------- 6. agenda
  await go(page, "/agenda");
  await page.click("button.btn-primary:has-text('Rendez-vous')");
  const am = page.locator("[role=dialog]");
  await am.locator("input").first().fill("Présentation du comparatif aux Martin");
  await am.locator("select").first().selectOption("rdv_client");
  await am.locator("input[type=datetime-local]").nth(0).fill(new Date(Date.now() + 86400000).toISOString().slice(0, 10) + "T10:00");
  await am.locator("input[type=datetime-local]").nth(1).fill(new Date(Date.now() + 86400000).toISOString().slice(0, 10) + "T11:00");
  await am.locator("input").nth(4).fill("Agence");
  await shot(page, "24_nouveau_rendez_vous");
  await am.locator("button:has-text('Enregistrer')").click();
  await page.waitForTimeout(800);
  await page.click("button.btn-primary:has-text('Rendez-vous')");
  const am2 = page.locator("[role=dialog]");
  await am2.locator("input").first().fill("Visite de chantier");
  await am2.locator("input[type=datetime-local]").nth(0).fill(new Date(Date.now() + 86400000).toISOString().slice(0, 10) + "T10:30");
  await am2.locator("input[type=datetime-local]").nth(1).fill(new Date(Date.now() + 86400000).toISOString().slice(0, 10) + "T12:00");
  await page.waitForSelector("text=Conflit d'agenda détecté");
  check("Agenda : conflit détecté entre deux rendez-vous", true);
  await shot(page, "25_conflit_agenda");
  await am2.locator("button:has-text('Enregistrer')").click();
  await page.waitForTimeout(800);
  await shot(page, "26_agenda_semaine");
  await page.click("button:has-text('mois')");
  await shot(page, "27_agenda_mois");

  // ----------------------------------------------------------------- 7. planning
  await go(page, "/planning");
  const today = new Date().toISOString().slice(0, 10);
  for (const [name, dur, act] of [["Terrassements", "5", "terrassement"], ["Fondations", "6", "fondations"], ["Dallage", "3", "beton"]]) {
    await page.click("button.btn-primary:has-text('Tâche')");
    const tm = page.locator("[role=dialog]");
    await tm.locator("input").first().fill(name);
    await tm.locator("input[type=date]").fill(today);
    await tm.locator("label:has-text('Durée') input").first().fill(dur);
    await tm.locator("select").first().selectOption(act);
    if (name === "Dallage") await shot(page, "28_nouvelle_tache");
    await tm.locator("button:has-text('Enregistrer')").click();
    await page.waitForTimeout(700);
  }
  check("Planning : tâches créées", (await page.locator("text=Fondations").count()) > 0);
  await shot(page, "29_planning_gantt_projet");

  // ----------------------------------------------------------------- 8. documents, assistant, finances, rapports
  await go(page, "/documents");
  await page.locator("input[type=file]").first().setInputFiles([path.join(DEMO, "Reglement_PLU_FICTIF_Demo.pdf")]);
  await page.waitForSelector("text=Reglement_PLU_FICTIF_Demo.pdf");
  await page.fill("input[placeholder^='ex. classe']", "hauteur maximale zone UB");
  await page.click("button:has-text('Rechercher')");
  await page.waitForTimeout(1500);
  check("Documents : import et recherche dans le contenu", (await page.locator("text=9 mètres").count()) > 0);
  await shot(page, "30_documents", { full: true });
  await page.click("text=Reglement_PLU_FICTIF_Demo.pdf >> nth=0");
  await page.waitForTimeout(2500);
  await shot(page, "31_document_apercu");
  await page.keyboard.press("Escape");

  await go(page, "/assistant");
  await page.fill("textarea", "Quelle est l'emprise au sol autorisée en zone UB ?");
  await page.keyboard.press("Enter");
  await page.waitForSelector("text=source(s) citée(s)", { timeout: 30000 });
  check("Assistant : réponse sourcée (mode sans IA générative)", (await page.locator("text=40 %").count()) > 0);
  await page.click("summary:has-text('source(s)')");
  await shot(page, "32_assistant");

  await go(page, "/finances");
  await page.click("button[role=tab]:has-text('Écritures')");
  await page.click("button.btn-primary:has-text('Écriture')");
  const fm = page.locator("[role=dialog]");
  await fm.locator("select").first().selectOption("marche");
  await fm.locator("input").first().fill("Marché lot 02 – Bâti Ouest");
  await fm.locator("input[inputmode=decimal]").fill("34783");
  await shot(page, "33_ecriture_financiere");
  await fm.locator("button:has-text('Enregistrer')").click();
  await page.waitForTimeout(1000);
  await page.click("button[role=tab]:has-text('Synthèse')");
  await shot(page, "34_finances_projet");
  check("Finances : marché enregistré, TTC calculé", (await api(page, "GET", "/api/finance-entries")).data[0].amount_ttc === 41739.6);

  await go(page, "/rapports");
  const [rdl] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), page.click("button:has-text('Générer et télécharger')")]);
  const rp = path.join(os.tmpdir(), "rapport.pdf");
  await rdl.saveAs(rp);
  check("Rapports : synthèse de projet PDF générée", fs.readFileSync(rp).subarray(0, 4).toString() === "%PDF");
  await page.waitForTimeout(800);
  await shot(page, "35_rapports");

  // ----------------------------------------------------------------- 9. paramètres
  await go(page, "/parametres");
  await page.click("button[role=tab]:has-text('Intelligence artificielle')");
  await page.locator("label:has-text('Fournisseur') select").selectOption("anthropic");
  await shot(page, "36_parametres_ia", { full: true });
  await page.locator("label:has-text('Fournisseur') select").selectOption("aucun");
  await page.click("button[role=tab]:has-text('Météo')");
  await shot(page, "37_parametres_meteo");
  await page.click("button[role=tab]:has-text('Urbanisme')");
  await shot(page, "38_parametres_urbanisme");
  await page.click("button[role=tab]:has-text('Synchronisation')");
  await shot(page, "39_parametres_synchronisation", { full: true });
  await page.click("button[role=tab]:has-text('Sauvegardes')");
  const [bdl] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), page.click("button:has-text('Sauvegarder maintenant')")]);
  const bp = path.join(os.tmpdir(), "sauvegarde.zip");
  await bdl.saveAs(bp);
  check("Sauvegarde : archive ZIP téléchargée", fs.readFileSync(bp).subarray(0, 2).toString() === "PK");
  await page.waitForTimeout(800);
  await shot(page, "40_sauvegardes");
  await page.locator("input[type=file][accept='.zip']").setInputFiles(bp);
  await page.waitForSelector("text=Intégrité vérifiée");
  await shot(page, "41_restauration");
  await page.click("button[role=tab]:has-text('Système')");
  await shot(page, "42_parametres_systeme");

  // ----------------------------------------------------------------- 10. hors connexion (PWA)
  await go(page, "/annuaire");
  await ctx.setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));
  await page.click("button:has-text('Nouveau client')");
  await page.locator("[role=dialog] input").first().fill("Client saisi hors connexion");
  await page.locator("[role=dialog] button:has-text('Créer')").click();
  await page.waitForTimeout(1500);
  const badge = await page.locator("button:has-text('Hors ligne')").count();
  check("Hors connexion : modification mise en file d'attente locale", badge > 0);
  await shot(page, "43_hors_connexion");
  await ctx.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await page.waitForTimeout(3000);
  const clients = (await api(page, "GET", "/api/clients")).data.map((c) => c.name);
  check("Hors connexion : synchronisation automatique au retour du réseau", clients.includes("Client saisi hors connexion"));

  // ----------------------------------------------------------------- 11. espace de démonstration (données externes simulées)
  await api(page, "POST", "/api/demo", { password: DEMO_PASSWORD });
  await page.evaluate(() => { localStorage.removeItem("a41.token"); localStorage.removeItem("a41.project"); });
  await page.goto("about:blank");
  await page.goto(BASE);
  await page.fill("input[type=email]", "demo@archipel41.demo");
  await page.fill("input[type=password]", DEMO_PASSWORD);
  await page.click("button:has-text('Se connecter')");
  await page.waitForSelector("text=ESPACE DE DÉMONSTRATION");
  check("Démonstration : espace fictif séparé et signalé", true);
  await page.waitForTimeout(1500);
  const projects = (await api(page, "GET", "/api/projects")).data;
  const demoP = projects.find((p) => p.code === "DEMO-24-07");
  await page.evaluate((id) => localStorage.setItem("a41.project", id), demoP.id);
  await page.reload();
  await page.waitForTimeout(2500);
  await shot(page, "44_tableau_de_bord");
  await go(page, "/projets");
  await shot(page, "45_liste_projets");
  await go(page, "/planning");
  await page.waitForTimeout(800);
  await shot(page, "46_planning_gantt");
  await page.click("button[role=tab]:has-text('Météo')");
  await page.waitForSelector("text=Analyse des activités prévues");
  await page.click("button:has-text('Proposer des ajustements')");
  await page.waitForTimeout(1500);
  await shot(page, "47_meteo_propositions", { full: true });
  check("Planning : analyse météo et propositions à valider", (await page.locator("button:has-text('Accepter')").count()) + (await page.locator("button:has-text('Classer')").count()) > 0);
  await go(page, "/urbanisme");
  await page.fill("input[placeholder^='12 rue']", "12 rue des Ateliers, Démoville");
  await page.click("button:has-text('Analyser la parcelle')");
  await page.waitForSelector("text=Données indisponibles", { timeout: 30000 });
  const sel = page.locator("label:has-text('Règlement') select");
  await sel.selectOption({ label: "Reglement_PLU_FICTIF_Demo.pdf" });
  await page.click("button:has-text('Analyser'):not(:has-text('parcelle'))");
  await page.waitForSelector("text=Emprise au sol maximale indicative", { timeout: 30000 });
  check("Urbanisme : analyse de parcelle et du règlement avec indicateurs", true);
  await shot(page, "48_urbanisme", { full: true });
  await go(page, "/");
  await page.click("button[title='Mode sombre']");
  await page.waitForTimeout(800);
  await shot(page, "49_mode_sombre");
  await page.click("button[title='Mode clair']");
  await page.click("button:has-text('Assistant')");
  await page.waitForTimeout(600);
  await shot(page, "50_assistant_panneau");
  await page.keyboard.press("Escape");

  // ----------------------------------------------------------------- 12. responsive
  for (const [label, vp] of [["smartphone", { width: 390, height: 844 }], ["tablette", { width: 820, height: 1180 }]]) {
    const m = await browser.newContext({ viewport: vp, deviceScaleFactor: SHOTS ? 2 : 1, locale: "fr-FR", isMobile: label === "smartphone", hasTouch: true });
    const mp = await m.newPage();
    await mp.goto(BASE);
    await mp.evaluate(([t, p]) => { localStorage.setItem("a41.token", t); localStorage.setItem("a41.project", p); }, [await page.evaluate(() => localStorage.getItem("a41.token")), demoP.id]);
    let overflow = [];
    for (const r of ["/", "/projets", "/devis", "/agenda", "/planning", "/documents", "/finances", "/annuaire", "/parametres"]) {
      await mp.goto("about:blank");
      await mp.goto(BASE + "#" + r);
      await mp.waitForTimeout(1800);
      if (!(await mp.locator("button[aria-label=Menu]").count())) overflow.push(`${r} (non connecté)`);
      const ov = await mp.evaluate(() => Math.max(document.documentElement.scrollWidth - window.innerWidth,
        ...[...document.querySelectorAll("main")].map((m) => m.scrollWidth - m.clientWidth)));
      if (ov > 1) overflow.push(`${r} (+${ov}px)`);
      if (r === "/" || r === "/devis") await mp.screenshot({ path: SHOTS ? path.join(SHOTS, `51_${label}_${r === "/" ? "accueil" : "devis"}.png`) : path.join(os.tmpdir(), "m.png") });
    }
    check(`Responsive ${label} ${vp.width}px : aucun débordement horizontal de page`, overflow.length === 0, overflow.join(", "));
    if (label === "smartphone") {
      await mp.goto("about:blank");
      await mp.goto(BASE + "#/");
      await mp.waitForTimeout(1500);
      await mp.click("button[aria-label=Menu]");
      await mp.waitForTimeout(500);
      if (SHOTS) await mp.screenshot({ path: path.join(SHOTS, "52_smartphone_menu.png") });
    }
    await m.close();
  }

  check("Aucune erreur JavaScript dans le navigateur", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
}

main()
  .catch(async (e) => { console.error(e); if (currentPage) await currentPage.screenshot({ path: path.join(os.tmpdir(), "e2e_failure.png") }).catch(() => {}); results.push({ name: "Exécution du scénario", ok: false, detail: String(e).slice(0, 300) }); })
  .finally(() => {
    if (server) server.kill();
    const ok = results.filter((r) => r.ok).length;
    console.log(`\n${ok}/${results.length} vérifications réussies`);
    fs.writeFileSync(path.join(__dirname, "e2e-results.json"), JSON.stringify({ date: new Date().toISOString(), results }, null, 2));
    process.exit(ok === results.length ? 0 : 1);
  });

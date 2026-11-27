/**
 * Lot 7 — bibliothèque documentaire, dans le navigateur :
 *  - arborescence ARCHIPEL 41 du projet, dossiers et compteurs, dossier propre au projet ;
 *  - visionneuses : tableur, Word (contenu échappé), plan DXF, maquette IFC ;
 *  - annotations sur un PDF (zone dessinée), traitement et suppression ; original inchangé ;
 *  - suggestion de classement acceptée, contrôle de nommage appliqué, statut, documents liés, similaires.
 *   node tests/e2e/documents.cjs [--shots dossier]
 */
const { chromium } = require("playwright");
const { spawn, execFileSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");
const crypto = require("crypto");

const ROOT = path.resolve(__dirname, "../..");
const PY = process.env.ARCHIPEL_PYTHON || path.join(ROOT, ".venv/bin/python");
const PORT = 28000 + Math.floor(Math.random() * 1500);
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
const dialog = (page) => page.locator("[role=dialog]");
async function openDoc(page, name) {
  await page.locator(`tr:has-text("${name}") button[title='Ouvrir']`).first().click();
  await page.waitForSelector("[role=dialog]");
  await page.waitForTimeout(400);
}
async function closeDoc(page) {
  await dialog(page).locator("button[aria-label=Fermer]").first().click();
  await page.waitForTimeout(300);
}
async function tab(page, label) {
  await dialog(page).locator(`button[role=tab]:has-text("${label}")`).click();
  await page.waitForTimeout(500);
}

async function main() {
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "a41docs_"));
  const files = path.join(tmp, "in"); fs.mkdirSync(files);
  execFileSync(PY, ["-c", `
import sys, io, shutil, datetime as dt
from pathlib import Path
d = Path(sys.argv[1]); demo = Path(sys.argv[2])
import openpyxl, docx
from PIL import Image
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Synthèse"
ws.append(["Lot", "Montant HT", "Date"]); ws.append(["Gros œuvre", 1250.5, dt.date(2026, 11, 27)]); ws.append(["Charpente", 98000, None])
wb.save(d / "Tableau des lots.xlsx")
w = docx.Document(); w.add_heading("Article 1 – Objet du marché", level=1)
w.add_paragraph("Clause de test <script>window.__pwned=1</script> à afficher en texte.")
t = w.add_table(rows=2, cols=2); t.cell(0,0).text="Lot"; t.cell(0,1).text="Montant"; t.cell(1,0).text="02"; t.cell(1,1).text="12 000 €"
w.save(d / "Note de synthèse.docx")
(d / "Plan RDC.dxf").write_text("""0\\nSECTION\\n2\\nENTITIES\\n0\\nLINE\\n8\\nMURS\\n10\\n0\\n20\\n0\\n11\\n10\\n21\\n0\\n0\\nLWPOLYLINE\\n8\\nMURS\\n90\\n4\\n70\\n1\\n10\\n0\\n20\\n0\\n10\\n10\\n20\\n0\\n10\\n10\\n20\\n6\\n10\\n0\\n20\\n6\\n0\\nTEXT\\n8\\nTEXTES\\n10\\n2\\n20\\n3\\n40\\n0.5\\n1\\nAtelier\\n0\\nENDSEC\\n0\\nEOF\\n""")
(d / "Maquette.ifc").write_text("""ISO-10303-21;
HEADER;FILE_DESCRIPTION(('V'),'2;1');FILE_NAME('m.ifc','2026-11-27',('A41'),('ARCHIPEL 41'),'IFC','ArchiCAD 27','');FILE_SCHEMA(('IFC4'));ENDSEC;
DATA;
#1=IFCPROJECT('0a',#2,'Extension concession',$,$,$,$,$,$);
#11=IFCBUILDING('0c',#2,'Bâtiment A',$,$,$,$,$,.ELEMENT.,$,$,$);
#20=IFCBUILDINGSTOREY('0d',#2,'RDC',$,$,$,$,$,.ELEMENT.,0.);
#30=IFCWALL('1a',#2,'Mur 1',$,$,$,$,$,$);
#31=IFCWALL('1b',#2,'Mur 2',$,$,$,$,$,$);
#32=IFCWALL('1c',#2,'Mur 3',$,$,$,$,$,$);
ENDSEC;
END-ISO-10303-21;
""", encoding="utf-8")
Image.new("RGB", (400, 300), (235, 235, 230)).save(d / "Facade sud.png")
shutil.copy(demo / "CCTP_Lot02_GrosOeuvre.pdf", d / "CCTP Lot 02 Gros oeuvre.pdf")
(d / "261127_A41-XXX-PRJ_ordre de service signe.txt").write_text("Ordre de service n° 3 : démarrage des travaux du lot 02.", encoding="utf-8")
`, files, path.join(ROOT, "database/seeds/demo_files")]);
  const pdfHash = crypto.createHash("sha256").update(fs.readFileSync(path.join(files, "CCTP Lot 02 Gros oeuvre.pdf"))).digest("hex");

  server = spawn(PY, ["-m", "app"], { cwd: path.join(ROOT, "web/backend"), env: { ...process.env, ARCHIPEL_MODE: "server", ARCHIPEL_DATA_DIR: tmp, ARCHIPEL_PORT: String(PORT), ARCHIPEL_DATABASE_URL: "" }, stdio: "ignore" });
  for (let i = 0; i < 100 && !(await healthy()); i++) await sleep(200);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SHOTS ? 2 : 1, locale: "fr-FR", timezoneId: "Europe/Paris" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const answers = [];
  page.on("dialog", async (d) => { if (d.type() === "prompt") await d.accept(answers.shift() ?? ""); else await d.accept(); });

  await page.goto(BASE);
  await page.waitForSelector("text=Bienvenue dans Archipel41");
  await page.fill("input[placeholder='Atelier …']", "Atelier Documents");
  const inputs = page.locator("form input");
  await inputs.nth(3).fill("Joseph Martin");
  await inputs.nth(4).fill("joseph@atelier-documents.fr");
  await inputs.nth(5).fill(PASSWORD);
  await inputs.nth(6).fill(PASSWORD);
  await page.click("button:has-text(\"Créer l'agence et me connecter\")");
  await page.waitForSelector("text=Bonjour Joseph");
  const p = (await api(page, "POST", "/api/projects", { code: "26-052", name: "Concession – DCE (démo)" })).data;
  await page.evaluate((id) => localStorage.setItem("a41.project", id), p.id);
  await page.goto(BASE + "#/documents"); await page.reload();
  await page.waitForSelector("text=Arborescence du projet");
  check("Arborescence ARCHIPEL 41 affichée", (await page.locator("ul[aria-label=Dossiers] > li").count()) === 6, "6 dossiers de premier niveau");

  // ---------------------------------------------------------- import
  // fichiers transmis par leur contenu : Playwright ignore les chemins accentués (« synthèse »), pas l'application
  const MIME = { pdf: "application/pdf", png: "image/png", txt: "text/plain", xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", dxf: "application/dxf", ifc: "application/x-step" };
  await page.setInputFiles("input[aria-label='Fichiers à importer']", fs.readdirSync(files).map((f) => ({
    name: f.normalize("NFC"), mimeType: MIME[f.split(".").pop()] || "application/octet-stream", buffer: fs.readFileSync(path.join(files, f)) })));
  await page.waitForSelector("text=document(s) importé(s)", { timeout: 90000 });
  const toastText = await page.locator("text=document(s) importé(s)").first().textContent();
  check("Import de 7 documents, suggestions de classement annoncées", /7 document\(s\) importé\(s\)/.test(toastText) && /suggestion/.test(toastText), toastText.trim());
  await page.waitForTimeout(800);
  const docs = (await api(page, "GET", `/api/documents?project_id=${p.id}`)).data;
  check("Aucun document classé sans accord", docs.length === 7 && docs.every((d) => !d.folder));
  await shot(page, "80_documents_arborescence");

  // ---------------------------------------------------------- visionneuses
  await openDoc(page, "Tableau des lots.xlsx");
  await page.waitForSelector("table[aria-label='Feuille Synthèse']");
  const sheet = await page.locator("table[aria-label='Feuille Synthèse']").textContent();
  check("Visionneuse tableur : feuille, montants et dates au format français", sheet.includes("Gros œuvre") && sheet.includes("1 250,5") && sheet.includes("27/11/2026"));
  await shot(page, "81_visionneuse_tableur"); await closeDoc(page);

  await openDoc(page, "Note de synthèse.docx");
  await page.waitForSelector("article.doc-html h2");
  const art = await page.locator("article.doc-html").textContent();
  const pwned = await page.evaluate(() => (window).__pwned === 1 || document.querySelectorAll("article.doc-html script").length > 0);
  check("Visionneuse Word : titres et tableau", art.includes("Article 1") && art.includes("12 000 €") && (await page.locator("article.doc-html table").count()) === 1);
  check("Visionneuse Word : le script du document est affiché comme texte, jamais exécuté", !pwned && art.includes("<script>"));
  await shot(page, "82_visionneuse_word"); await closeDoc(page);

  await openDoc(page, "Plan RDC.dxf");
  await page.waitForSelector("img[alt='Plan DXF']");
  check("Visionneuse DXF : plan dessiné avec ses calques", (await dialog(page).locator("text=MURS").count()) > 0 && (await dialog(page).locator("text=TEXTES").count()) > 0);
  await dialog(page).locator("button[aria-label='Zoom avant']").click();
  await shot(page, "83_visionneuse_dxf"); await closeDoc(page);

  await openDoc(page, "Maquette.ifc");
  await page.waitForSelector("text=Structure spatiale");
  const ifc = await dialog(page).textContent();
  check("Visionneuse IFC : bâtiment, niveaux et objets comptés", ifc.includes("Bâtiment A") && /Murs\s*3/.test(ifc) && ifc.includes("IFC4"));
  await shot(page, "84_visionneuse_ifc"); await closeDoc(page);

  // ---------------------------------------------------------- annotations sur le PDF
  await openDoc(page, "CCTP Lot 02 Gros oeuvre.pdf");
  await page.waitForSelector("[data-testid=annot-layer-1]", { timeout: 30000 });
  await dialog(page).locator("button:has-text('Annoter')").click();
  const box = await page.locator("[data-testid=annot-layer-1]").boundingBox();
  answers.push("Vérifier la classe d'exposition XC4 avec le BET");
  await page.mouse.move(box.x + box.width * 0.15, box.y + box.height * 0.2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.32, { steps: 6 });
  await page.mouse.up();
  await page.waitForSelector("ol[aria-label=Annotations] li", { timeout: 8000 }).catch(() => {});
  const ann = (await api(page, "GET", `/api/documents/${docs.find((d) => d.extension === "pdf").id}/annotations`)).data || [];
  const g = ann[0]?.geometry || {};
  check("Annotation de zone enregistrée avec sa position relative", ann.length === 1 && ann[0].kind === "zone" && Math.abs(g.x - 0.15) < 0.03 && Math.abs(g.w - 0.4) < 0.04, JSON.stringify(g));
  answers.push("Repère : joint de dilatation");
  await page.mouse.click(box.x + box.width * 0.7, box.y + box.height * 0.6);
  await page.waitForTimeout(1200);
  check("Repère ponctuel enregistré, deux annotations listées", (await page.locator("ol[aria-label=Annotations] li").count()) === 2);
  await dialog(page).locator("button:has-text('Annotation en cours')").click();
  await shot(page, "85_annotations_pdf");
  await page.locator("ol[aria-label=Annotations] li").first().locator("button[aria-label='Marquer comme traitée']").click();
  await page.waitForTimeout(800);
  await page.locator("ol[aria-label=Annotations] li").nth(1).locator("button[aria-label=\"Supprimer l'annotation\"]").click();
  await page.waitForTimeout(800);
  const ann2 = (await api(page, "GET", `/api/documents/${docs.find((d) => d.extension === "pdf").id}/annotations`)).data;
  check("Annotation traitée puis suppression de l'autre", ann2.length === 1 && ann2[0].resolved === true);
  const dlHash = await page.evaluate(async (id) => {
    const r = await fetch(`/api/documents/${id}/download`, { headers: { Authorization: "Bearer " + localStorage.getItem("a41.token") } });
    const b = await r.arrayBuffer(); const h = await crypto.subtle.digest("SHA-256", b);
    return Array.from(new Uint8Array(h)).map((x) => x.toString(16).padStart(2, "0")).join("");
  }, docs.find((d) => d.extension === "pdf").id);
  check("Fichier PDF original inchangé après annotation", dlHash === pdfHash);
  await closeDoc(page);

  // ---------------------------------------------------------- classement suggéré + nommage
  const osName = "261127_A41-XXX-PRJ_ordre de service signe.txt";
  await openDoc(page, osName);
  await tab(page, "Classement");
  await page.waitForSelector("text=Classement suggéré");
  const sugText = await dialog(page).locator("text=Classement suggéré").textContent();
  check("Suggestion : ordre de service → 64_OS (règle R49)", sugText.includes("64_OS") && (await dialog(page).locator("text=R49").count()) > 0);
  await shot(page, "86_classement_suggere");
  await dialog(page).locator("button:has-text('Classer ici')").click();
  await page.waitForTimeout(1000);
  check("Nom hors convention signalé avec proposition", (await dialog(page).locator("text=Nom hors convention").count()) > 0);
  await dialog(page).locator("button:has-text('Utiliser ce nom')").click();
  await dialog(page).locator("label:has-text('Statut') select").selectOption("valide");
  const pdfRow = dialog(page).locator("label:has(span:has-text('CCTP Lot 02 Gros oeuvre.pdf')) input[type=checkbox]");
  await pdfRow.check();
  await dialog(page).locator("button:has-text('Enregistrer le classement')").click();
  await page.waitForTimeout(1000);
  const osDoc = (await api(page, "GET", `/api/documents?project_id=${p.id}`)).data.find((d) => d.extension === "txt");
  check("Document classé dans 64_OS après acceptation", osDoc.folder === "5-Réalisation/05_Organisation chantier/64_OS");
  check("Nom conforme appliqué (AAAA-MM-JJ, « - »)", osDoc.name === "2026-11-27-A41-XXX-PRJ-ordre de service signe.txt", osDoc.name);
  check("Statut « Validé » et document lié enregistrés", osDoc.status === "valide" && osDoc.related_ids.length === 1);
  await tab(page, "Similaires");
  await page.waitForTimeout(1000);
  check("Onglet Similaires affiché", (await dialog(page).locator("text=proximité").count()) + (await dialog(page).locator("text=Aucun document au contenu proche").count()) > 0);
  await closeDoc(page);

  // ---------------------------------------------------------- arborescence : filtres et dossier propre au projet
  await page.reload(); await page.waitForSelector("text=Arborescence du projet");
  await page.locator("ul[aria-label=Dossiers] button[title]:has-text('5-Réalisation')").click();
  await page.waitForTimeout(400);
  await page.locator("ul[aria-label=Dossiers] button[title]:has-text('05_Organisation chantier')").click();
  await page.waitForTimeout(400);
  await page.locator("ul[aria-label=Dossiers] button[title]:has-text('64_OS')").click();
  await page.waitForTimeout(1000);
  const rows = await page.locator("tbody tr").count();
  check("Filtre par dossier : un document dans 64_OS, note « Classer ici » affichée", rows === 1 && (await page.locator("text=l'original des ordres de service signés").count()) > 0, `${rows} ligne(s)`);
  await shot(page, "87_arborescence_64_OS");
  await page.locator("button:has-text('Non classés')").click();
  await page.waitForTimeout(800);
  check("Filtre « Non classés »", (await page.locator("tbody tr").count()) === 6);
  await openDoc(page, "Tableau des lots.xlsx");
  await tab(page, "Classement");
  await dialog(page).locator("label:has-text('… ou dossier propre au projet') input").fill("5-Réalisation/06_EXE entreprises/71_Lots/Lot 03 - Charpente");
  await dialog(page).locator("button:has-text('Enregistrer le classement')").click();
  await page.waitForTimeout(800);
  await closeDoc(page);
  const t = (await api(page, "GET", `/api/documents/tree?project_id=${p.id}`)).data;
  check("Dossier propre au projet ajouté à l'arborescence", t.folders.some((f) => f.custom && f.path.endsWith("Lot 03 - Charpente")) && t.unfiled === 5);

  // ---------------------------------------------------------- aide contextuelle
  await page.click("button[aria-label='Aide sur cet écran']");
  await page.waitForSelector("[role=dialog][aria-label^='Aide']");
  const help = await page.locator("[role=dialog][aria-label^='Aide']").textContent();
  check("Aide contextuelle de l'écran Documents (conventions de l'agence rappelées)", help.includes("Documents") && help.includes("AAAA-MM-JJ") && help.includes("jamais écrasé"));
  await shot(page, "88_aide_contextuelle");
  const guide = await page.evaluate(async () => { const r = await fetch("/api/guides/guide-pratique", { headers: { Authorization: "Bearer " + localStorage.getItem("a41.token") } }); return { s: r.status, t: r.headers.get("content-type") }; });
  check("Guide pratique embarqué accessible depuis l'aide", guide.s === 200 && guide.t === "application/pdf");
  await page.keyboard.press("Escape");

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

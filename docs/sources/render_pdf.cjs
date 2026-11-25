/**
 * Rendu HTML → PDF (Chromium) en deux passes pour un sommaire paginé exact.
 *   node render_pdf.cjs document.html sortie.pdf "Titre courant"
 * Passe 1 : rendu, puis repérage de la page de chaque titre (marqueurs invisibles « ⟦id⟧ »).
 * Passe 2 : injection des numéros de page dans le sommaire et rendu final.
 */
const { chromium } = require("playwright");
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const [html, out, title] = process.argv.slice(2);
const PY = process.env.PYTHON || path.resolve(__dirname, "../../.venv/bin/python");

const footer = `<div style="font-family:Inter,Segoe UI,sans-serif;font-size:8px;color:#718578;width:100%;padding:0 16mm;display:flex;justify-content:space-between">
  <span>ARCHIPEL41 · ${title}</span><span>Page <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`;

async function render(page, file) {
  await page.pdf({ path: file, format: "A4", printBackground: true, displayHeaderFooter: true, headerTemplate: "<div></div>",
    footerTemplate: footer, margin: { top: "16mm", bottom: "16mm", left: "16mm", right: "16mm" } });
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("file://" + path.resolve(html), { waitUntil: "networkidle" });
  const tmp = out + ".pass1.pdf";
  await render(page, tmp);
  const pages = JSON.parse(execFileSync(PY, ["-c", `
import json, re, sys
from pypdf import PdfReader
r = PdfReader(sys.argv[1]); found = {}
for i, p in enumerate(r.pages, 1):
    for a, b in re.findall(r"ZZ(s\\d+)(?:.(\\d+))?ZZ", (p.extract_text() or "")):
        found.setdefault(a + ("x" + b if b else ""), i)
print(json.dumps(found))`, tmp]).toString());
  await page.evaluate((pg) => {
    document.querySelectorAll("[data-toc]").forEach((el) => { el.textContent = pg[el.getAttribute("data-toc")] || ""; });
  }, pages);
  await render(page, out);
  fs.unlinkSync(tmp);
  await browser.close();
  console.log(`${out} : ${Object.keys(pages).length} titres paginés`);
})();

/**
 * Lance toutes les suites navigateur et enregistre leurs résultats dans tests/reports/e2e_suites.json
 * (repris par la documentation technique).   node tests/e2e/run_all.cjs [--shots docs/screenshots]
 */
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const SUITES = [
  ["e2e.cjs", "parcours complet, hors connexion, responsive"], ["forms.cjs", "fiabilité des formulaires"],
  ["access.cjs", "connexion, rôles, autorisations, invités"], ["history.cjs", "historique, diagnostic, aperçu PDF"],
  ["terrain.cjs", "terrain et cartographie"], ["documents.cjs", "bibliothèque documentaire, visionneuses, annotations, aide"],
];
const extra = process.argv.slice(2);
const out = [];
let failed = 0;
for (const [file, label] of SUITES) {
  const t0 = new Date();
  const r = spawnSync(process.execPath, [path.join(__dirname, file), ...extra], { encoding: "utf-8", timeout: 900000 });
  const txt = (r.stdout || "") + (r.stderr || "");
  const m = txt.match(/(\d+)\/(\d+) vérifications réussies/);
  const ok = m ? +m[1] : 0, total = m ? +m[2] : 0;
  if (!m || ok !== total) failed++;
  console.log(`${!m || ok !== total ? "✘" : "✔"} ${file} — ${m ? `${ok}/${total}` : "aucun résultat"}`);
  txt.split("\n").filter((l) => l.startsWith("✘")).forEach((l) => console.log("    " + l));
  out.push({ suite: file, label, ok, total, date: t0.toISOString().slice(0, 16).replace("T", " ") });
}
const dir = path.resolve(__dirname, "../reports");
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(path.join(dir, "e2e_suites.json"), JSON.stringify(out, null, 1));
console.log(`\n${out.reduce((a, x) => a + x.ok, 0)}/${out.reduce((a, x) => a + x.total, 0)} vérifications navigateur réussies`);
process.exit(failed ? 1 : 0);

// Permet de construire l'installateur NSIS sous Linux sans Wine : electron-builder dispose d'un
// extracteur JavaScript du désinstalleur (UninstallerReader), qu'il n'active que sous macOS.
// Ce correctif idempotent l'active également lorsque A41_NO_WINE=1.
const fs = require("fs");
const path = require("path");
const file = path.join(__dirname, "../../desktop/electron/node_modules/app-builder-lib/out/targets/nsis/NsisTarget.js");
let src = fs.readFileSync(file, "utf8");
const needle = "if ((0, macosVersion_1.isMacOsCatalina)()) {";
if (src.includes("A41_NO_WINE")) {
  console.log("  correctif electron-builder déjà appliqué");
} else if (src.includes(needle)) {
  src = src.replace(needle, "if ((0, macosVersion_1.isMacOsCatalina)() || process.env.A41_NO_WINE === \"1\") {");
  fs.writeFileSync(file, src);
  console.log("  correctif electron-builder appliqué (désinstalleur extrait sans Wine)");
} else {
  throw new Error("Version d'electron-builder inattendue : correctif non applicable.");
}

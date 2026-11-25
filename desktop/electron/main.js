/**
 * Archipel41 – application de bureau (Electron).
 *
 * Le processus principal :
 *  1. affiche un écran de démarrage ;
 *  2. lance le moteur local Archipel41 (Python/FastAPI embarqué, base SQLite locale)
 *     sur un port libre de la boucle locale 127.0.0.1 ;
 *  3. attend qu'il réponde, puis ouvre l'interface dans une fenêtre indépendante ;
 *  4. fournit à l'interface les fonctions natives : notifications Windows,
 *     enregistrement de fichiers, ouverture de liens et de dossiers ;
 *  5. arrête proprement le moteur à la fermeture.
 *
 * Les données et paramètres sont conservés dans le profil de l'utilisateur
 * (%APPDATA%\Archipel41\data sous Windows) et survivent aux mises à jour.
 */
const { app, BrowserWindow, ipcMain, dialog, Notification, shell, Menu, nativeTheme } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const net = require("net");
const http = require("http");

const APP_NAME = "Archipel41";
app.setName(APP_NAME);
if (process.platform === "win32") app.setAppUserModelId("fr.archipel41.desktop");

// En version portable, les données restent à côté de l'exécutable si un dossier « Archipel41-data » existe.
const portableDir = process.env.PORTABLE_EXECUTABLE_DIR;
const userData = portableDir && fs.existsSync(path.join(portableDir, "Archipel41-data"))
  ? path.join(portableDir, "Archipel41-data")
  : app.getPath("userData");
app.setPath("userData", userData);
const DATA_DIR = path.join(userData, "data");
const LOG_DIR = path.join(DATA_DIR, "logs");
fs.mkdirSync(LOG_DIR, { recursive: true });
const logFile = path.join(LOG_DIR, "desktop.log");
function log(...args) {
  const line = `[${new Date().toISOString()}] ${args.join(" ")}\n`;
  try { fs.appendFileSync(logFile, line); } catch { /* journal indisponible */ }
  if (!app.isPackaged) process.stdout.write(line);
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
}

let backend = null;
let backendPort = null;
let mainWindow = null;
let splash = null;
let quitting = false;

function resourcesRoot() {
  return app.isPackaged ? process.resourcesPath : path.resolve(__dirname, "..", "build");
}

function pythonPath() {
  const root = resourcesRoot();
  if (process.env.ARCHIPEL_PYTHON) return process.env.ARCHIPEL_PYTHON;
  if (process.platform === "win32") return path.join(root, "python", "python.exe");
  const candidates = [path.join(root, "python", "bin", "python3"), path.join(root, "python-linux", "bin", "python3")];
  return candidates.find((p) => fs.existsSync(p)) || "python3";
}

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function waitForHealth(port, timeoutMs = 90000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get({ host: "127.0.0.1", port, path: "/api/health", timeout: 2000 }, (res) => {
        res.resume();
        if (res.statusCode === 200) return resolve();
        retry();
      });
      req.on("error", retry);
      req.on("timeout", () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (backend && backend.exitCode !== null) return reject(new Error(`Le moteur local s'est arrêté (code ${backend.exitCode}).`));
      if (Date.now() - started > timeoutMs) return reject(new Error("Le moteur local ne répond pas (délai dépassé)."));
      setTimeout(tick, 400);
    };
    tick();
  });
}

async function startBackend() {
  const root = resourcesRoot();
  const backendRoot = path.join(root, "backend");
  backendPort = await freePort();
  const env = {
    ...process.env,
    ARCHIPEL_MODE: "desktop",
    ARCHIPEL_ENV: "production",
    ARCHIPEL_DATA_DIR: DATA_DIR,
    ARCHIPEL_HOST: "127.0.0.1",
    ARCHIPEL_PORT: String(backendPort),
    ARCHIPEL_FRONTEND_DIST: path.join(backendRoot, "web", "frontend", "dist"),
    PYTHONPATH: [path.join(backendRoot, "web", "backend"), backendRoot].join(path.delimiter),
    PYTHONNOUSERSITE: "1",
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
  };
  const tess = path.join(root, "tesseract", process.platform === "win32" ? "tesseract.exe" : "tesseract");
  if (fs.existsSync(tess)) {
    env.ARCHIPEL_TESSERACT_CMD = tess;
    env.TESSDATA_PREFIX = path.join(root, "tesseract", "tessdata");
  }
  const py = pythonPath();
  log(`Démarrage du moteur : ${py} (port ${backendPort}, données ${DATA_DIR})`);
  const out = fs.openSync(path.join(LOG_DIR, "backend-console.log"), "a");
  backend = spawn(py, ["-m", "app"], {
    cwd: path.join(backendRoot, "web", "backend"),
    env,
    windowsHide: true,
    stdio: ["ignore", out, out],
  });
  backend.on("exit", (code, signal) => {
    log(`Moteur arrêté (code ${code}, signal ${signal})`);
    if (!quitting && mainWindow) {
      dialog.showErrorBox(APP_NAME, `Le moteur local d'Archipel41 s'est arrêté de façon inattendue.\n\nJournal : ${LOG_DIR}\n\nL'application va se fermer ; vos données sont conservées.`);
      app.quit();
    }
  });
  await waitForHealth(backendPort);
  log("Moteur prêt.");
}

function createSplash() {
  splash = new BrowserWindow({
    width: 460, height: 300, frame: false, resizable: false, show: true, backgroundColor: "#253A33",
    icon: path.join(__dirname, "..", "installer", "icon.png"),
    webPreferences: { sandbox: true, contextIsolation: true },
  });
  splash.loadFile(path.join(__dirname, "splash.html"));
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440, height: 920, minWidth: 980, minHeight: 640, show: false, title: APP_NAME,
    backgroundColor: nativeTheme.shouldUseDarkColors ? "#141917" : "#F8F7F2",
    icon: path.join(__dirname, "..", "installer", "icon.png"),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: true,
    },
  });
  mainWindow.webContents.session.setSpellCheckerLanguages(["fr"]);
  const appUrl = `http://127.0.0.1:${backendPort}/`;
  // Liens externes → navigateur par défaut ; la navigation reste confinée au moteur local.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      if (!url.startsWith(appUrl)) { shell.openExternal(url); return { action: "deny" }; }
    }
    return { action: "allow" };
  });
  mainWindow.webContents.on("will-navigate", (e, url) => {
    if (!url.startsWith(appUrl)) { e.preventDefault(); shell.openExternal(url); }
  });
  // Téléchargements déclenchés par l'interface : boîte « Enregistrer sous ».
  mainWindow.webContents.session.on("will-download", (_e, item) => {
    item.setSaveDialogOptions({ title: "Enregistrer le fichier", defaultPath: path.join(app.getPath("documents"), item.getFilename()) });
  });
  mainWindow.loadURL(appUrl);
  mainWindow.once("ready-to-show", () => {
    if (splash) { splash.destroy(); splash = null; }
    mainWindow.show();
    mainWindow.focus();
  });
  mainWindow.on("closed", () => { mainWindow = null; });
}

function buildMenu() {
  const template = [
    { label: "Fichier", submenu: [
      { label: "Ouvrir le dossier des données", click: () => shell.openPath(DATA_DIR) },
      { label: "Ouvrir le dossier des journaux", click: () => shell.openPath(LOG_DIR) },
      { type: "separator" },
      { label: "Quitter", role: "quit" },
    ] },
    { label: "Édition", submenu: [
      { label: "Annuler", role: "undo" }, { label: "Rétablir", role: "redo" }, { type: "separator" },
      { label: "Couper", role: "cut" }, { label: "Copier", role: "copy" }, { label: "Coller", role: "paste" }, { label: "Tout sélectionner", role: "selectAll" },
    ] },
    { label: "Affichage", submenu: [
      { label: "Recharger", role: "reload" }, { label: "Plein écran", role: "togglefullscreen" },
      { label: "Zoom avant", role: "zoomIn" }, { label: "Zoom arrière", role: "zoomOut" }, { label: "Taille réelle", role: "resetZoom" },
      { type: "separator" }, { label: "Outils de développement", role: "toggleDevTools" },
    ] },
    { label: "Aide", submenu: [
      { label: "Guides PDF (dossier docs)", click: () => shell.openPath(path.join(resourcesRoot(), "backend", "docs")) },
      { label: `À propos d'${APP_NAME}`, click: () => dialog.showMessageBox({ type: "info", title: APP_NAME, message: `${APP_NAME} ${app.getVersion()}`,
        detail: `Assistant numérique pour agences d'architecture.\n\nDonnées : ${DATA_DIR}` }) },
    ] },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ------------------------------------------------------------------ IPC (fonctions natives)
ipcMain.handle("a41:notify", (_e, title, body) => {
  if (Notification.isSupported()) new Notification({ title: String(title).slice(0, 120), body: String(body).slice(0, 300), icon: path.join(__dirname, "..", "installer", "icon.png") }).show();
  return true;
});
ipcMain.handle("a41:save-file", async (_e, name, bytes) => {
  const safe = String(name).replace(/[\\/:*?"<>|]+/g, "_").slice(0, 180) || "export";
  const res = await dialog.showSaveDialog(mainWindow, { title: "Enregistrer le fichier", defaultPath: path.join(app.getPath("documents"), safe) });
  if (res.canceled || !res.filePath) return false;
  await fs.promises.writeFile(res.filePath, Buffer.from(bytes));
  shell.showItemInFolder(res.filePath);
  return true;
});
ipcMain.handle("a41:open-external", (_e, url) => {
  if (/^https?:\/\//.test(url)) shell.openExternal(url);
});
ipcMain.handle("a41:info", () => ({ version: app.getVersion(), dataDir: DATA_DIR, platform: process.platform }));

// ------------------------------------------------------------------ cycle de vie
app.on("second-instance", () => {
  if (mainWindow) { if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.focus(); }
});

app.whenReady().then(async () => {
  buildMenu();
  createSplash();
  try {
    await startBackend();
    createMainWindow();
  } catch (err) {
    log("Échec du démarrage :", err && err.stack ? err.stack : String(err));
    if (splash) splash.destroy();
    dialog.showErrorBox(APP_NAME, `Impossible de démarrer le moteur local.\n\n${err.message}\n\nConsultez le journal : ${LOG_DIR}`);
    quitting = true;
    app.quit();
  }
});

app.on("window-all-closed", () => app.quit());

app.on("before-quit", () => {
  quitting = true;
  if (backend && backend.exitCode === null) {
    log("Arrêt du moteur…");
    try { backend.kill(); } catch { /* déjà arrêté */ }
  }
});

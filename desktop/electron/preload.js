// Pont sécurisé entre l'interface et les fonctions natives (contextIsolation activée).
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("archipelDesktop", {
  notify: (title, body) => ipcRenderer.invoke("a41:notify", title, body),
  saveFile: (name, bytes) => ipcRenderer.invoke("a41:save-file", name, bytes),
  openFile: (name, bytes) => ipcRenderer.invoke("a41:open-file", name, bytes),
  openExternal: (url) => ipcRenderer.invoke("a41:open-external", url),
  info: () => ipcRenderer.invoke("a41:info"),
});

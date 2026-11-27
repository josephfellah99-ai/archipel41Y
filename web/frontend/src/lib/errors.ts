/**
 * Remontée des erreurs de l'interface vers le journal technique (Historique › Erreurs).
 * - exceptions JavaScript et promesses rejetées non gérées ;
 * - erreurs serveur (5xx) et pages qui ne se chargent pas.
 * Limité (10 par minute), jamais de contenu de formulaire ni de jeton transmis.
 */
import { getToken } from "./api";

let sent: number[] = [];
let installed = false;

export function reportClientError(kind: "javascript" | "chargement" | "api", message: string, extra: Record<string, unknown> = {}) {
  try {
    const now = Date.now();
    sent = sent.filter((t) => now - t < 60000);
    if (sent.length >= 10 || !getToken()) return;
    sent.push(now);
    const body = JSON.stringify({ kind, message: String(message).slice(0, 2000), route: window.location.hash.replace(/^#/, "").split("?")[0],
      screen: `${window.innerWidth}×${window.innerHeight}`, ...extra });
    fetch(((window as any).ARCHIPEL_API_BASE || "") + "/api/history/client-errors", {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` }, body, keepalive: true,
    }).catch(() => { /* hors connexion : ignoré */ });
  } catch { /* le signalement ne doit jamais provoquer d'erreur */ }
}

export function installErrorReporting() {
  if (installed) return;
  installed = true;
  window.addEventListener("error", (e) => {
    if (!e.message || /ResizeObserver loop/.test(e.message)) return;
    reportClientError("javascript", e.message, { stack: e.error?.stack?.slice(0, 3000) });
  });
  window.addEventListener("unhandledrejection", (e) => {
    const r: any = e.reason;
    if (r?.status && r.status < 500) return; // erreurs métier déjà affichées à l'utilisateur
    if (r instanceof TypeError && /fetch|network/i.test(r.message)) return; // hors connexion
    reportClientError("javascript", r?.message || String(r), { stack: r?.stack?.slice(0, 3000) });
  });
}

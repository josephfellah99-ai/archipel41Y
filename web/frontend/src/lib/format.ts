export const eur = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v);

export const num = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "—" : new Intl.NumberFormat("fr-FR", { maximumFractionDigits: digits }).format(v);

export const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: digits }).format(v)} %`;

export const dateFr = (v?: string | null) => (v ? new Date(v.length === 10 ? v + "T12:00:00" : v).toLocaleDateString("fr-FR") : "—");
export const dateLong = (v?: string | Date | null) =>
  v ? new Date(typeof v === "string" && v.length === 10 ? v + "T12:00:00" : v).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) : "—";
export const timeFr = (v?: string | null) => (v ? new Date(v).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : "");
export const dateTimeFr = (v?: string | null) => (v ? `${dateFr(v)} ${timeFr(v)}` : "—");

export const isoDate = (d: Date) => {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return z.toISOString().slice(0, 10);
};
export const addDays = (d: Date, n: number) => {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
};
export const startOfWeek = (d: Date) => {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
};
/**
 * Lecture d'un nombre saisi « à la française » : « 1 234,56 », « 1.234,56 », « 1234.56 »,
 * « 12,5 % », « 3 402,00 € ». Retourne null si la saisie est vide ou invalide (jamais NaN).
 */
export const parseNum = (v: unknown): number | null => {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  let s = String(v).trim().replace(/[\s\u00a0\u202f]/g, "").replace(/€|%|eur/gi, "");
  if (!s || s === "-" || s === "—") return null;
  if (!/^-?[\d.,]+$/.test(s)) return null;
  const lc = s.lastIndexOf(","), ld = s.lastIndexOf(".");
  if (lc >= 0 && ld >= 0) s = lc > ld ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
  else if (lc >= 0) s = (s.match(/,/g) || []).length > 1 ? s.replace(/,/g, "") : s.replace(",", ".");
  else if ((s.match(/\./g) || []).length > 1) s = s.replace(/\./g, "");
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};
/** Vrai si la saisie est vide ou un nombre valide. */
export const isNumOrEmpty = (v: unknown) => v === null || v === undefined || String(v).trim() === "" || parseNum(v) !== null;
/** Convertit une saisie numérique pour l'API : "" → null ; invalide → lève une erreur explicite. */
export const toNum = (v: unknown, label = "Valeur"): number | null => {
  if (v === null || v === undefined || String(v).trim() === "") return null;
  const n = parseNum(v);
  if (n === null) throw new Error(`${label} : « ${v} » n'est pas un nombre valide (exemples acceptés : 1 250,50 ou 1250.50).`);
  return n;
};
export const bytes = (n: number) => (n < 1024 ? `${n} o` : n < 1048576 ? `${(n / 1024).toFixed(0)} Ko` : `${(n / 1048576).toFixed(1)} Mo`);

export const STATUS_PROJECT: Record<string, string> = { etude: "Études", consultation: "Consultation", chantier: "Chantier", reception: "Réception", archive: "Archivé" };
export const LOT_STATUS: Record<string, string> = { a_consulter: "À consulter", consultation: "En consultation", attribue: "Attribué", en_cours: "En cours", receptionne: "Réceptionné" };
export const EVENT_KINDS: Record<string, string> = { rdv_client: "Rendez-vous client", reunion_entreprise: "Réunion entreprise", visite_chantier: "Visite de chantier", interne: "Interne", autre: "Autre" };
export const EVENT_COLORS: Record<string, string> = { rdv_client: "#253A33", reunion_entreprise: "#46678C", visite_chantier: "#A07D52", interne: "#718578", autre: "#8A8F8C" };
export const QUOTE_STATUS: Record<string, string> = { a_verifier: "À vérifier", valide: "Validé", retenu: "Retenu", rejete: "Rejeté" };
export const LINE_STATUS: Record<string, string> = { inclus: "Inclus", exclu: "Exclu", optionnel: "Optionnel", variante: "Variante", a_verifier: "À vérifier" };
export const CMP_STATUS: Record<string, { label: string; cls: string }> = {
  inclus: { label: "Inclus", cls: "bg-ok/15 text-ok" },
  non_inclus: { label: "Non inclus", cls: "bg-danger/15 text-danger" },
  non_renseigne: { label: "Non renseigné", cls: "bg-warn/15 text-warn" },
  optionnel: { label: "Optionnel", cls: "bg-info/15 text-info" },
  variante: { label: "Variante", cls: "bg-[#7C5FA8]/15 text-[#7C5FA8] dark:text-[#B9A3DD]" },
  non_comparable: { label: "Non comparable", cls: "bg-muted/15 text-muted" },
  a_verifier: { label: "À vérifier", cls: "bg-warn/20 text-warn" },
};
export const FINANCE_KINDS: Record<string, string> = {
  marche: "Marché", travaux_supp: "Travaux supplémentaires", facture: "Facture", acompte: "Acompte", situation: "Situation de travaux",
  paiement: "Paiement", depense: "Dépense", honoraires: "Honoraires",
};
export const FIN_STATUS: Record<string, string> = { prevu: "Prévu", emis: "Émis", valide: "Validé", paye: "Payé", annule: "Annulé" };
export const ROLE_LABELS: Record<string, string> = { admin: "Administrateur", manager: "Gestionnaire", member: "Collaborateur", viewer: "Lecteur" };
export const ACTIVITY_LABELS: Record<string, string> = {
  terrassement: "Terrassement", fondations: "Fondations", beton: "Béton / coulage", maconnerie: "Maçonnerie", charpente: "Charpente",
  couverture: "Couverture", etancheite: "Étanchéité", facade: "Façade / enduits", peinture_ext: "Peinture extérieure",
  menuiseries_ext: "Menuiseries extérieures", vrd: "VRD", grue: "Levage / grue", interieur: "Travaux intérieurs", second_oeuvre: "Second œuvre", autre: "Autre",
};
export const DOC_CATEGORIES: Record<string, string> = {
  plan: "Plan", devis: "Devis", cctp: "CCTP", dpgf: "DPGF", contrat: "Contrat / marché", facture: "Facture", compte_rendu: "Compte rendu",
  photo: "Photo", administratif: "Administratif", urbanisme: "Urbanisme", maquette: "Maquette BIM", rapport: "Rapport", courrier: "Courrier", autre: "Autre",
};

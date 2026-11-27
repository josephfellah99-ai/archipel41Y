import { useEffect, useState } from "react";
import { ShieldCheck, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/app";
import { ErrorBox, Field, Notice } from "../components/ui";
import logo from "../logo.svg";

function Shell({ children, title, subtitle }: { children: React.ReactNode; title: string; subtitle: string }) {
  return (
    <div className="min-h-full grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-forest text-white p-12 dark:text-bg">
        <div className="flex items-center gap-3">
          <img src={logo} className="h-10 w-10" alt="" />
          <span className="tracking-[0.25em] font-semibold">ARCHIPEL41</span>
        </div>
        <div>
          <p className="text-3xl font-light leading-snug max-w-md">L'assistant numérique des agences d'architecture.</p>
          <p className="mt-4 text-white/70 max-w-md text-sm dark:text-bg/70">Projets, chantiers, devis, urbanisme, planning, finances et documents – réunis, analysés et sécurisés.</p>
        </div>
        <p className="text-xs text-white/50 dark:text-bg/60">Version 1.1 · Données hébergées par votre agence</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2 mb-8"><img src={logo} className="h-9 w-9" alt="" /><span className="tracking-[0.25em] font-semibold text-forest">ARCHIPEL41</span></div>
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="text-sm text-muted mt-1 mb-6">{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  );
}

type Mode = "admin" | "collaborateur" | "invite";

function Login({ hasDemo, onSetup }: { hasDemo: boolean; onSetup?: () => void }) {
  const { login } = useApp();
  const [mode, setMode] = useState<Mode>(() => (new URLSearchParams(window.location.search).get("invitation") ? "invite" : "collaborateur"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState(() => new URLSearchParams(window.location.search).get("invitation") || "");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      if (mode === "invite") {
        const r = await api.call("POST", "/api/guest/redeem", { code });
        await login(r.token);
      } else {
        const r = await api.call("POST", "/api/auth/login", { email, password, mode });
        await login(r.token);
      }
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  // Format du code : XXXX-XXXX-XXXX (saisie tolérante : minuscules, espaces, sans tirets)
  const fmtCode = (v: string) => {
    const raw = v.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 12);
    return raw.match(/.{1,4}/g)?.join("-") || "";
  };
  const TABS: { id: Mode; label: string; hint: string }[] = [
    { id: "admin", label: "Administrateur", hint: "Gestion de l'agence, des comptes, des accès et des paramètres." },
    { id: "collaborateur", label: "Collaborateur", hint: "Votre espace de travail : projets, documents, agenda et tâches." },
    { id: "invite", label: "Invité", hint: "Vous avez reçu un code d'invitation de l'agence." },
  ];
  return (
    <Shell title="Connexion" subtitle={TABS.find((t) => t.id === mode)!.hint}>
      <div className="grid grid-cols-3 border border-line rounded-lg p-1 mb-5 bg-sunken/60" role="tablist" aria-label="Mode de connexion">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={mode === t.id} onClick={() => { setMode(t.id); setErr(null); }}
            className={`text-sm py-2 rounded-md transition ${mode === t.id ? "bg-surface shadow-sm font-medium text-forest" : "text-muted hover:text-ink"}`}>
            {t.label}
          </button>))}
      </div>
      <form onSubmit={submit} className="space-y-4">
        {mode === "invite" ? (
          <>
            <Field label="Code d'invitation" hint="12 caractères, au format XXXX-XXXX-XXXX, transmis par l'agence.">
              <input className="input text-center tracking-[0.25em] font-mono text-lg uppercase" autoComplete="one-time-code" required value={code}
                onChange={(e) => setCode(fmtCode(e.target.value))} placeholder="XXXX-XXXX-XXXX" aria-label="Code d'invitation" /></Field>
            <ErrorBox error={err} />
            <button className="btn-primary w-full" disabled={busy || code.replace(/-/g, "").length !== 12}>{busy ? "Vérification…" : "Accéder en tant qu'invité"}</button>
            <p className="text-xs text-muted">Un accès invité est limité dans le temps et ne donne accès qu'aux éléments que l'agence a choisi de partager.</p>
          </>
        ) : (
          <>
            <Field label="Adresse e-mail"><input className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <Field label="Mot de passe"><input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
            <ErrorBox error={err} />
            <button className="btn-primary w-full" disabled={busy}>{busy ? "Connexion…" : mode === "admin" ? "Se connecter (administration)" : "Se connecter"}</button>
            {onSetup && <button type="button" className="btn-secondary w-full" onClick={onSetup}>Créer mon agence réelle</button>}
            {hasDemo && <p className="text-xs text-muted">Espace de démonstration disponible : compte <b>demo@archipel41.demo</b> avec le mot de passe choisi lors de sa création.</p>}
          </>
        )}
      </form>
    </Shell>
  );
}

function Setup({ onDone }: { onDone: () => void }) {
  const { login } = useApp();
  const [f, setF] = useState({ agency_name: "", agency_siret: "", agency_address: "", admin_name: "", admin_email: "", admin_password: "", confirm: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demoPw, setDemoPw] = useState("");
  const [tab, setTab] = useState<"agence" | "demo">("agence");
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (f.admin_password !== f.confirm) return setErr("Les deux mots de passe ne correspondent pas.");
    setBusy(true);
    try {
      const { confirm, ...payload } = f;
      const r = await api.call("POST", "/api/setup", { ...payload, agency_siret: payload.agency_siret || null, agency_address: payload.agency_address || null });
      await login(r.token);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  const demo = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.call("POST", "/api/demo", { password: demoPw });
      const r = await api.call("POST", "/api/auth/login", { email: "demo@archipel41.demo", password: demoPw });
      await login(r.token);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Shell title="Bienvenue dans Archipel41" subtitle="Première ouverture : créez votre agence et le compte administrateur.">
      <div className="flex gap-2 mb-5">
        <button className={tab === "agence" ? "btn-primary" : "btn-secondary"} onClick={() => setTab("agence")}><ShieldCheck size={15} /> Créer mon agence</button>
        <button className={tab === "demo" ? "btn-primary" : "btn-secondary"} onClick={() => setTab("demo")}><Sparkles size={15} /> Explorer la démonstration</button>
      </div>
      {tab === "agence" ? (
        <form onSubmit={submit} className="space-y-3">
          <Field label="Nom de l'agence *"><input className="input" required value={f.agency_name} onChange={set("agency_name")} placeholder="Atelier …" /></Field>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="SIRET"><input className="input" value={f.agency_siret} onChange={set("agency_siret")} /></Field>
            <Field label="Adresse"><input className="input" value={f.agency_address} onChange={set("agency_address")} /></Field>
          </div>
          <hr className="border-line my-2" />
          <Field label="Nom de l'administrateur *"><input className="input" required value={f.admin_name} onChange={set("admin_name")} /></Field>
          <Field label="E-mail de l'administrateur *"><input className="input" type="email" required value={f.admin_email} onChange={set("admin_email")} /></Field>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Mot de passe *" hint="10 caractères minimum, 3 types (minuscules, majuscules, chiffres, symboles)">
              <input className="input" type="password" required value={f.admin_password} onChange={set("admin_password")} autoComplete="new-password" /></Field>
            <Field label="Confirmation *"><input className="input" type="password" required value={f.confirm} onChange={set("confirm")} autoComplete="new-password" /></Field>
          </div>
          <ErrorBox error={err} />
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Création…" : "Créer l'agence et me connecter"}</button>
        </form>
      ) : (
        <form onSubmit={demo} className="space-y-3">
          <Notice tone="warn">L'espace de démonstration est une <b>agence fictive séparée</b> (projet « Maison Lambert », devis, planning, rendez-vous…). Il ne mélange jamais ses données avec les vôtres ; vous pourrez créer votre agence réelle ensuite.</Notice>
          <Field label="Mot de passe des comptes de démonstration" hint="Il protège les comptes demo@archipel41.demo et ses collaborateurs fictifs.">
            <input className="input" type="password" required value={demoPw} onChange={(e) => setDemoPw(e.target.value)} autoComplete="new-password" />
          </Field>
          <ErrorBox error={err} />
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Préparation de la démonstration…" : "Créer l'espace de démonstration"}</button>
        </form>
      )}
    </Shell>
  );
}

export default function AuthGate() {
  const [status, setStatus] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [forceSetup, setForceSetup] = useState(false);
  const load = () => api.call("GET", "/api/setup/status").then(setStatus).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (err) return <div className="p-10 max-w-lg mx-auto"><ErrorBox error={`Impossible de joindre le serveur Archipel41 : ${err}`} /></div>;
  if (!status) return null;
  if (status.needs_setup || forceSetup) return <Setup onDone={load} />;
  return <Login hasDemo={status.has_demo} onSetup={!status.has_real_agency ? () => setForceSetup(true) : undefined} />;
}

import { Settings as Cog, Plus, Save, Plug, Download, Upload, RefreshCw, ShieldCheck, AlertTriangle, Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, conflictItems, download, dropConflict, flushOutbox, outboxItems } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { bytes, dateTimeFr, ROLE_LABELS } from "../lib/format";
import { Card, Empty, ErrorBox, Field, Modal, Notice, PageHeader, Select, Spinner, Tabs } from "../components/ui";

function useSetting(key: string) {
  const s = useApi<any>(`/api/settings/${key}`);
  const [v, setV] = useState<any>(null);
  useEffect(() => { if (s.data) setV(s.data); }, [s.data]);
  return { v, setV, reload: s.reload, loading: s.loading };
}

function SaveBar({ onSave, onTest, busy }: { onSave: () => void; onTest?: () => void; busy?: boolean }) {
  return <div className="flex gap-2 mt-4">{onTest && <button className="btn-secondary" onClick={onTest} disabled={busy}><Plug size={15} /> Tester la connexion</button>}<button className="btn-primary" onClick={onSave} disabled={busy}><Save size={15} /> Enregistrer</button></div>;
}

function Secret({ label, value, isSet, onChange, hint }: { label: string; value: string; isSet: boolean; onChange: (v: string) => void; hint?: string }) {
  return <Field label={label} hint={hint || (isSet ? "Une valeur est enregistrée (chiffrée). Laissez vide pour la conserver." : "Aucune valeur enregistrée.")}>
    <input className="input" type="password" autoComplete="off" placeholder={isSet ? "•••••••• (inchangée)" : ""} value={value} onChange={(e) => onChange(e.target.value)} /></Field>;
}

function AgencyTab() {
  const { agency, refreshMe, perms, toast, toastError } = useApp();
  const [a, setA] = useState<any>(agency);
  const s = useSetting("agency");
  return (
    <Card title="Agence">
      <div className="grid sm:grid-cols-2 gap-3">
        {[["name", "Nom"], ["siret", "SIRET"], ["address", "Adresse"], ["email", "E-mail"], ["phone", "Téléphone"]].map(([k, l]) => (
          <Field key={k} label={l}><input className="input" disabled={!perms.admin} value={a?.[k] || ""} onChange={(e) => setA({ ...a, [k]: e.target.value })} /></Field>))}
        {s.v && <Field label="Taux de TVA par défaut (devis sans taux)"><Select disabled={!perms.admin} value={String(s.v.default_vat)} onChange={(x) => s.setV({ ...s.v, default_vat: Number(x) })} options={["20", "10", "5.5"].map((x) => ({ value: x, label: `${x.replace(".", ",")} %` }))} /></Field>}
      </div>
      {perms.admin && <SaveBar onSave={async () => { try { await api.call("PUT", "/api/agency", a); if (s.v) await api.call("PUT", "/api/settings/agency", s.v); toast("Agence enregistrée."); refreshMe(); } catch (e) { toastError(e); } }} />}
    </Card>
  );
}

function UsersTab() {
  const { perms, user, toast, toastError } = useApp();
  const users = useApi<any[]>("/api/users");
  const roles = useApi<any[]>("/api/roles");
  const [edit, setEdit] = useState<any>(null);
  const save = async () => {
    try {
      if (edit.id) { const { email, ...rest } = edit; await api.call("PUT", `/api/users/${edit.id}`, { full_name: rest.full_name, role: rest.role, active: rest.active, job_title: rest.job_title || null, phone: rest.phone || null, color: rest.color || null, ...(rest.password ? { password: rest.password } : {}) }); }
      else await api.call("POST", "/api/users", { email: edit.email, full_name: edit.full_name, role: edit.role, password: edit.password, job_title: edit.job_title || null, color: edit.color || null });
      toast("Utilisateur enregistré."); setEdit(null); users.reload();
    } catch (e) { toastError(e); }
  };
  const PERM_LABELS: Record<string, string> = { read: "Consulter", write: "Créer / modifier", delete: "Supprimer", validate: "Valider (devis, planning)", admin: "Administrer (utilisateurs, paramètres, sauvegardes)" };
  return (
    <div className="space-y-6">
      <Card title="Utilisateurs de l'agence" pad={false} actions={perms.admin && <button className="btn-primary" onClick={() => setEdit({ email: "", full_name: "", role: "member", password: "", active: true, color: "#718578" })}><Plus size={15} /> Utilisateur</button>}>
        <table className="table"><thead><tr><th>Nom</th><th>E-mail</th><th>Rôle</th><th>État</th><th>Dernière connexion</th></tr></thead>
          <tbody>{(users.data || []).map((u) => (
            <tr key={u.id} className={perms.admin ? "hover:bg-sunken/50 cursor-pointer" : ""} onClick={() => perms.admin && setEdit({ ...u, password: "" })}>
              <td className="font-medium"><span className="inline-block h-2.5 w-2.5 rounded-full mr-2" style={{ background: u.color || "#718578" }} />{u.full_name}{u.id === user?.id && <span className="text-xs text-muted"> (vous)</span>}</td>
              <td className="text-muted">{u.email}</td><td>{u.role_label}</td><td>{u.active ? <span className="chip bg-ok/15 text-ok">actif</span> : <span className="chip bg-sunken text-muted">désactivé</span>}</td>
              <td className="text-muted">{dateTimeFr(u.last_login_at)}</td></tr>))}</tbody></table>
      </Card>
      <Card title="Matrice des permissions">
        <div className="overflow-x-auto"><table className="table"><thead><tr><th>Permission</th>{(roles.data || []).map((r) => <th key={r.code} className="text-center">{r.label}</th>)}</tr></thead>
          <tbody>{Object.entries(PERM_LABELS).map(([p, l]) => <tr key={p}><td>{l}</td>{(roles.data || []).map((r) => <td key={r.code} className="text-center">{r.permissions.includes(p) ? <Check size={15} className="inline text-ok" /> : "—"}</td>)}</tr>)}</tbody></table></div>
        <p className="text-xs text-muted mt-3">Les projets marqués « confidentiels » ne sont visibles que de leur équipe, des chefs de projet et des administrateurs. Les données de chaque agence sont strictement isolées.</p>
      </Card>
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? edit.full_name : "Nouvel utilisateur"} footer={<><button className="btn-secondary" onClick={() => setEdit(null)}>Annuler</button><button className="btn-primary" onClick={save}>Enregistrer</button></>}>
        {edit && <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Nom complet *"><input className="input" value={edit.full_name} onChange={(e) => setEdit({ ...edit, full_name: e.target.value })} /></Field>
          <Field label="E-mail *"><input className="input" type="email" disabled={!!edit.id} value={edit.email} onChange={(e) => setEdit({ ...edit, email: e.target.value })} /></Field>
          <Field label="Rôle"><Select value={edit.role} onChange={(v) => setEdit({ ...edit, role: v })} options={Object.entries(ROLE_LABELS).map(([v, l]) => ({ value: v, label: l }))} /></Field>
          <Field label="Fonction"><input className="input" value={edit.job_title || ""} onChange={(e) => setEdit({ ...edit, job_title: e.target.value })} /></Field>
          <Field label={edit.id ? "Nouveau mot de passe (facultatif)" : "Mot de passe initial *"} hint="10 caractères minimum, 3 types de caractères."><input className="input" type="password" autoComplete="new-password" value={edit.password} onChange={(e) => setEdit({ ...edit, password: e.target.value })} /></Field>
          <Field label="Couleur"><input className="input h-10 p-1" type="color" value={edit.color || "#718578"} onChange={(e) => setEdit({ ...edit, color: e.target.value })} /></Field>
          {edit.id && <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={edit.active} onChange={(e) => setEdit({ ...edit, active: e.target.checked })} /> Compte actif</label>}
        </div>}
      </Modal>
    </div>
  );
}

function AITab() {
  const { toast, toastError } = useApp();
  const s = useSetting("ai");
  const [key, setKey] = useState("");
  const [test, setTest] = useState<any>(null);
  if (!s.v) return <Spinner />;
  const v = s.v;
  const presets: Record<string, any> = {
    mistral: { base_url: "https://api.mistral.ai/v1", model: "mistral-large-latest", embedding_model: "mistral-embed", external: true },
    openai: { base_url: "https://api.openai.com/v1", model: "gpt-4o", embedding_model: "text-embedding-3-small", external: true },
    ollama: { base_url: "http://localhost:11434/v1", model: "llama3.1", embedding_model: "nomic-embed-text", external: false },
  };
  const save = async () => { try { await api.call("PUT", "/api/settings/ai", { ...v, api_key: key || undefined }); setKey(""); toast("Paramètres IA enregistrés."); s.reload(); } catch (e) { toastError(e); } };
  return (
    <Card title="Intelligence artificielle">
      <Notice>Sans fournisseur configuré, Archipel41 fonctionne entièrement : extraction et comparaison des devis par moteur de règles, recherche documentaire locale (RAG), conclusions déterministes. Un fournisseur ajoute la rédaction (conclusions, synthèses, réponses de l'assistant).</Notice>
      <div className="grid sm:grid-cols-2 gap-3 mt-4">
        <Field label="Fournisseur"><Select value={v.provider} onChange={(x) => s.setV({ ...v, provider: x })} options={[{ value: "aucun", label: "Aucun (mode sans IA générative)" }, { value: "anthropic", label: "Anthropic – Claude" }, { value: "openai_compat", label: "Compatible OpenAI (Mistral, OpenAI, Azure, Ollama local…)" }]} /></Field>
        {v.provider === "openai_compat" && <Field label="Préréglage"><Select value="" onChange={(x) => x && s.setV({ ...v, ...presets[x] })} placeholder="— Choisir —" options={[{ value: "mistral", label: "Mistral AI (France)" }, { value: "openai", label: "OpenAI" }, { value: "ollama", label: "Ollama (modèle local, aucune donnée externe)" }]} /></Field>}
        {v.provider !== "aucun" && <>
          <Secret label="Clé API" value={key} isSet={!!v.api_key_set} onChange={setKey} hint={v.api_key_set ? `Clé enregistrée (${v.api_key}). Laissez vide pour la conserver.` : v.provider === "anthropic" ? "Clé créée sur console.anthropic.com (commence par « sk-ant- »)." : "Non requise pour Ollama."} />
          <Field label="Modèle" hint={v.provider === "anthropic" ? "Par défaut : claude-opus-5-5" : undefined}><input className="input" value={v.model || ""} onChange={(e) => s.setV({ ...v, model: e.target.value })} placeholder={v.provider === "anthropic" ? "claude-opus-5-5" : ""} /></Field>
          {v.provider === "openai_compat" && <><Field label="URL de l'API"><input className="input" value={v.base_url || ""} onChange={(e) => s.setV({ ...v, base_url: e.target.value })} /></Field>
            <Field label="Modèle d'embeddings (facultatif)" hint="Sinon : embeddings locaux hors ligne."><input className="input" value={v.embedding_model || ""} onChange={(e) => s.setV({ ...v, embedding_model: e.target.value })} /></Field></>}
          {v.provider === "anthropic" && <Field label="Niveau d'effort"><Select value={v.effort || "medium"} onChange={(x) => s.setV({ ...v, effort: x })} options={["low", "medium", "high"].map((x) => ({ value: x, label: { low: "Faible (rapide)", medium: "Moyen", high: "Élevé (analyses complexes)" }[x]! }))} /></Field>}
        </>}
      </div>
      <div className="mt-4 space-y-2 rounded-lg border border-line p-4">
        <div className="text-sm font-medium flex items-center gap-2"><ShieldCheck size={15} className="text-sage" /> Confidentialité</div>
        <label className="text-sm flex items-start gap-2"><input type="checkbox" className="mt-1" checked={v.allow_documents} onChange={(e) => s.setV({ ...v, allow_documents: e.target.checked })} /> Autoriser l'envoi d'extraits de documents non confidentiels au fournisseur externe (nécessaire pour les réponses rédigées de l'assistant).</label>
        <label className="text-sm flex items-start gap-2"><input type="checkbox" className="mt-1" checked={v.allow_confidential} onChange={(e) => s.setV({ ...v, allow_confidential: e.target.checked })} /> Autoriser aussi les documents et projets <b>confidentiels</b> (à n'activer qu'avec des garanties contractuelles adaptées : non-conservation, hébergement, DPA).</label>
        <p className="text-xs text-muted">Un modèle local (Ollama) n'est pas considéré comme externe : les données ne quittent pas votre infrastructure.</p>
      </div>
      <SaveBar onSave={save} onTest={async () => { await save(); setTest(await api.call("POST", "/api/settings/ai/test")); }} />
      {test && <div className="mt-3"><Notice tone={test.ok ? "ok" : "danger"}>{test.message}</Notice></div>}
    </Card>
  );
}

function ServiceTab({ k }: { k: "weather" | "urbanisme" }) {
  const { toast, toastError } = useApp();
  const s = useSetting(k);
  const [cid, setCid] = useState("");
  const [sec, setSec] = useState("");
  const [test, setTest] = useState<any>(null);
  if (!s.v) return <Spinner />;
  const v = s.v;
  const save = async () => { try { await api.call("PUT", `/api/settings/${k}`, { ...v, ...(k === "urbanisme" ? { legifrance_client_id: cid || v.legifrance_client_id, legifrance_client_secret: sec || undefined } : {}) }); setSec(""); toast("Paramètres enregistrés."); s.reload(); } catch (e) { toastError(e); } };
  return (
    <Card title={k === "weather" ? "Météo de chantier" : "Services urbanistiques"}>
      <Notice>{k === "weather" ? "Prévisions Open-Meteo (données Météo-France / ECMWF) et géocodage de la Base Adresse Nationale : services publics gratuits, sans clé API. Une connexion Internet est nécessaire."
        : "API Carto IGN (cadastre et Géoportail de l'Urbanisme), Géorisques et Base Adresse Nationale : sans clé API. Légifrance nécessite des identifiants gratuits de l'API PISTE (piste.gouv.fr)."}</Notice>
      <label className="text-sm flex items-center gap-2 mt-4"><input type="checkbox" checked={!!v.demo} onChange={(e) => s.setV({ ...v, demo: e.target.checked })} /> Mode démonstration (données <b>fictives</b>, sans connexion Internet – clairement signalées)</label>
      <div className="grid sm:grid-cols-2 gap-3 mt-3">
        {(k === "weather" ? [["base_url", "API de prévisions"], ["geocoder", "Géocodeur"]] : [["apicarto", "API Carto IGN"], ["georisques", "Géorisques"], ["geocoder", "Géocodeur"]]).map(([f, l]) => (
          <Field key={f} label={l}><input className="input" value={v[f] || ""} onChange={(e) => s.setV({ ...v, [f]: e.target.value })} /></Field>))}
        {k === "urbanisme" && <><Field label="Légifrance – identifiant client (PISTE)"><input className="input" value={cid || v.legifrance_client_id || ""} onChange={(e) => setCid(e.target.value)} /></Field>
          <Secret label="Légifrance – secret client (PISTE)" value={sec} isSet={!!v.legifrance_client_secret_set} onChange={setSec} /></>}
      </div>
      <SaveBar onSave={save} onTest={async () => { try { setTest(await api.call("POST", `/api/settings/${k}/test`)); } catch (e) { toastError(e); } }} />
      {test && <div className="mt-3"><Notice tone={test.ok ? "ok" : "danger"}>{test.results.map((r: any) => <div key={r.url}>{r.ok ? "✓" : "✗"} {r.url} – {r.status}</div>)}</Notice></div>}
    </Card>
  );
}

function SyncTab() {
  const { mode, perms, toast, toastError } = useApp();
  const st = useApi<any>("/api/sync/status");
  const conflicts = useApi<any[]>("/api/sync/conflicts");
  const [f, setF] = useState({ server_url: "", email: "", password: "", interval_minutes: 5 });
  const [local, setLocal] = useState<{ out: any[]; conf: any[] }>({ out: [], conf: [] });
  const loadLocal = async () => setLocal({ out: await outboxItems(), conf: await conflictItems() });
  useEffect(() => { loadLocal(); }, []);
  const resolve = async (id: string, keep: string) => { try { await api.call("POST", `/api/sync/conflicts/${id}/resolve`, { keep }); toast("Conflit résolu."); conflicts.reload(); st.reload(); } catch (e) { toastError(e); } };
  const s = st.data;
  return (
    <div className="space-y-6">
      <Card title="Fonctionnement">
        <div className="text-sm space-y-2">
          <p><b>Mode de ce poste : {mode === "desktop" ? "application de bureau (base locale SQLite)" : "serveur / navigateur"}.</b></p>
          <p className="text-muted">Archipel41 est « local-first » : chaque appareil conserve ses données et continue de fonctionner hors connexion. Le partage entre collaborateurs nécessite un <b>serveur central Archipel41</b> (PostgreSQL) accessible par le réseau : les postes de bureau s'y synchronisent dans les deux sens ; les navigateurs y accèdent directement et mettent en file d'attente leurs modifications hors connexion. Le stockage local seul ne permet pas de partager des données entre appareils.</p>
        </div>
      </Card>
      {mode === "desktop" && (
        <Card title="Serveur central" actions={s?.configured && <button className="btn-primary" onClick={async () => { try { const r = await api.call("POST", "/api/sync/run"); toast(`Synchronisé : ${r.push.accepted} envoyé(s), ${r.pull.applied || 0} reçu(s), ${r.push.conflicts + (r.pull.conflicts || 0)} conflit(s).`); st.reload(); conflicts.reload(); } catch (e) { toastError(e); st.reload(); } }}><RefreshCw size={15} /> Synchroniser maintenant</button>}>
          {s && <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm mb-4">
            <dt className="text-muted">État</dt><dd>{s.configured ? `Raccordé à ${s.server_url} (${s.email})` : "Non raccordé – données locales uniquement"}</dd>
            <dt className="text-muted">Dernière synchronisation</dt><dd>{dateTimeFr(s.last_sync_at)}</dd>
            <dt className="text-muted">Modifications en attente</dt><dd>{s.pending_changes}</dd>
            <dt className="text-muted">Conflits ouverts</dt><dd>{s.open_conflicts}</dd>
            {s.last_error && <><dt className="text-muted">Dernier message</dt><dd className="text-warn">{s.last_error}</dd></>}</dl>}
          {perms.admin && <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Adresse du serveur" hint="ex. https://archipel41.monagence.fr"><input className="input" value={f.server_url} onChange={(e) => setF({ ...f, server_url: e.target.value })} /></Field>
            <Field label="Intervalle (minutes)"><input className="input" type="number" min={1} value={f.interval_minutes} onChange={(e) => setF({ ...f, interval_minutes: Number(e.target.value) })} /></Field>
            <Field label="E-mail (compte serveur)"><input className="input" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
            <Field label="Mot de passe (compte serveur)"><input className="input" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
            <div className="sm:col-span-2"><button className="btn-primary" onClick={async () => { try { const r = await api.call("POST", "/api/sync/configure", f); toast(r.message); st.reload(); } catch (e) { toastError(e); } }}>Raccorder ce poste</button></div>
          </div>}
        </Card>
      )}
      <Card title="Conflits de synchronisation" pad={false}>
        {!(conflicts.data || []).filter((c) => c.status === "ouvert").length ? <Empty title="Aucun conflit ouvert" /> : (
          <ul className="divide-y divide-line">{conflicts.data!.filter((c) => c.status === "ouvert").map((c) => {
            const keys = Object.keys(c.remote_data).filter((k) => JSON.stringify(c.remote_data[k]) !== JSON.stringify(c.local_data[k]) && !["updated_at", "version", "updated_by"].includes(k));
            return (
              <li key={c.id} className="p-4">
                <div className="text-sm font-medium flex items-center gap-2"><AlertTriangle size={15} className="text-warn" /> {c.entity} · {c.local_data.name || c.local_data.title || c.local_data.label || c.entity_id}</div>
                <table className="table text-xs mt-2"><thead><tr><th>Champ</th><th>Ma version (v{c.local_version})</th><th>Version du serveur (v{c.remote_version})</th></tr></thead>
                  <tbody>{keys.map((k) => <tr key={k}><td>{k}</td><td>{String(JSON.stringify(c.local_data[k])).slice(0, 120)}</td><td>{String(JSON.stringify(c.remote_data[k])).slice(0, 120)}</td></tr>)}</tbody></table>
                <div className="flex gap-2 mt-2"><button className="btn-secondary" onClick={() => resolve(c.id, "local")}>Garder ma version</button><button className="btn-secondary" onClick={() => resolve(c.id, "remote")}>Garder la version du serveur</button></div>
              </li>);
          })}</ul>)}
      </Card>
      <Card title="File d'attente hors connexion de ce navigateur" actions={<button className="btn-secondary" onClick={async () => { const r = await flushOutbox(); toast(`${r.sent} envoyée(s), ${r.conflicts} refusée(s).`); loadLocal(); }}><RefreshCw size={15} /> Envoyer</button>}>
        {!local.out.length && !local.conf.length ? <div className="text-sm text-muted">Aucune modification en attente.</div> : <>
          <ul className="text-sm space-y-1">{local.out.map((o) => <li key={o.id}>⏳ {o.label} – {o.method} {o.url} ({dateTimeFr(o.createdAt)})</li>)}</ul>
          {local.conf.length > 0 && <div className="mt-3"><div className="label">Refusées par le serveur (conflit ou validation)</div>
            <ul className="text-sm space-y-2">{local.conf.map((c) => <li key={c.id} className="rounded-md bg-danger/10 p-2">{c.label} : {c.error}
              <button className="btn-ghost text-xs ml-2" onClick={async () => { await dropConflict(c.id); loadLocal(); }}>Ignorer ma modification</button></li>)}</ul></div>}
        </>}
      </Card>
    </div>
  );
}

function BackupTab() {
  const { toast, toastError, logout } = useApp();
  const list = useApi<any[]>("/api/backups");
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [manifest, setManifest] = useState<any>(null);
  const [confirm, setConfirm] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  const make = async () => { setBusy(true); try { const r = await api.call("POST", "/api/backups"); toast(`Sauvegarde créée (${bytes(r.size)}).`); list.reload(); await download(`/api/backups/${r.name}`, r.name); } catch (e) { toastError(e); } finally { setBusy(false); } };
  const inspect = async (f: File) => { setFile(f); const fd = new FormData(); fd.append("file", f); try { setManifest(await api.upload("/api/backups/inspect", fd)); } catch (e) { toastError(e); setManifest(null); } };
  const restore = async () => {
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    setBusy(true);
    try { await api.upload(`/api/restore?confirm=${encodeURIComponent(confirm)}`, fd); toast("Restauration terminée. Reconnectez-vous."); setTimeout(logout, 1500); } catch (e) { toastError(e); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-6">
      <Card title="Créer une sauvegarde" actions={<button className="btn-primary" onClick={make} disabled={busy}><Download size={15} /> {busy ? "Sauvegarde…" : "Sauvegarder maintenant"}</button>}>
        <p className="text-sm text-muted">L'archive ZIP contient toutes les données de l'agence (projets, devis, agenda, finances, paramètres, historique) et les fichiers des documents, avec un manifeste et des empreintes SHA-256 pour vérifier son intégrité. Les clés API restent chiffrées.</p>
        <table className="table mt-3"><thead><tr><th>Sauvegarde</th><th>Taille</th><th>Date</th><th /></tr></thead>
          <tbody>{(list.data || []).map((b) => <tr key={b.name}><td>{b.name}</td><td>{bytes(b.size)}</td><td>{new Date(b.created_at * 1000).toLocaleString("fr-FR")}</td>
            <td><button className="btn-ghost p-1" onClick={() => download(`/api/backups/${b.name}`, b.name).catch(toastError)}><Download size={15} /></button></td></tr>)}</tbody></table>
      </Card>
      <Card title="Restaurer une sauvegarde">
        <Notice tone="danger">La restauration <b>remplace</b> toutes les données actuelles de l'agence. Une sauvegarde de sécurité est créée automatiquement juste avant.</Notice>
        <input ref={ref} type="file" accept=".zip" hidden onChange={(e) => e.target.files?.[0] && inspect(e.target.files[0])} />
        <button className="btn-secondary mt-3" onClick={() => ref.current?.click()}><Upload size={15} /> Choisir une archive…</button>
        {manifest && <div className="mt-3 text-sm space-y-2">
          <div>Archive de <b>{manifest.agency_name}</b> créée le {dateTimeFr(manifest.created_at)} (version {manifest.app_version}) – {Object.values(manifest.counts).reduce((a: number, b: any) => a + b, 0)} enregistrements, {manifest.files} fichiers. Intégrité vérifiée ✓</div>
          <Field label="Pour confirmer, saisissez RESTAURER"><input className="input w-60" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
          <button className="btn-danger" disabled={confirm !== "RESTAURER" || busy} onClick={restore}>Restaurer</button></div>}
      </Card>
    </div>
  );
}

function AuditTab() {
  const { data, loading } = useApi<any[]>("/api/audit?limit=300");
  if (loading && !data) return <Spinner />;
  return <Card title="Journal d'audit" pad={false}><div className="overflow-x-auto max-h-[70vh] scrollbar-thin"><table className="table text-xs"><thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th><th>Objet</th><th>Détail</th><th>IP</th></tr></thead>
    <tbody>{(data || []).map((a, i) => <tr key={i}><td className="whitespace-nowrap">{dateTimeFr(a.at)}</td><td>{a.user}</td><td>{a.action}</td><td>{a.entity}</td><td className="max-w-md truncate">{a.summary}</td><td className="text-muted">{a.ip}</td></tr>)}</tbody></table></div></Card>;
}

function AccountTab() {
  const { user, theme, toggleTheme, toast, toastError } = useApp();
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <Card title="Mon compte"><div className="text-sm space-y-1"><div><b>{user?.full_name}</b></div><div className="text-muted">{user?.email} · {user?.role_label}</div></div>
        <div className="mt-4"><button className="btn-secondary" onClick={toggleTheme}>Basculer en mode {theme === "dark" ? "clair" : "sombre"}</button></div></Card>
      <Card title="Changer mon mot de passe">
        <div className="space-y-3">
          <Field label="Mot de passe actuel"><input className="input" type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
          <Field label="Nouveau mot de passe"><input className="input" type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
          <Field label="Confirmation"><input className="input" type="password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></Field>
          <button className="btn-primary" onClick={async () => { if (pw.new_password !== pw.confirm) return toast("Les mots de passe ne correspondent pas.", "error"); try { await api.call("POST", "/api/auth/change-password", pw); toast("Mot de passe modifié."); setPw({ current_password: "", new_password: "", confirm: "" }); } catch (e) { toastError(e); } }}>Modifier</button>
        </div>
      </Card>
    </div>
  );
}

function SystemTab() {
  const { data } = useApi<any>("/api/system/info");
  if (!data) return <Spinner />;
  return (
    <Card title="Système">
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-sm">
        <dt className="text-muted">Version</dt><dd>Archipel41 {data.version}</dd>
        <dt className="text-muted">Mode</dt><dd>{data.mode === "desktop" ? "Application de bureau (moteur local)" : "Serveur"}</dd>
        <dt className="text-muted">Base de données</dt><dd>{data.database === "sqlite" ? "SQLite (locale)" : "PostgreSQL"}{data.extensions ? ` – extensions : ${Object.entries(data.extensions).map(([k, v]) => `${k} ${v}`).join(", ")}` : ""}</dd>
        <dt className="text-muted">OCR (Tesseract)</dt><dd>{data.ocr ? <span className="text-ok">disponible</span> : <span className="text-warn">non installé – les PDF scannés et images ne peuvent pas être lus (voir le guide d'installation)</span>}</dd>
        <dt className="text-muted">LibreOffice (.doc)</dt><dd>{data.libreoffice ? <span className="text-ok">disponible</span> : <span className="text-muted">non installé – les fichiers Word 97-2003 (.doc) doivent être enregistrés en .docx</span>}</dd>
        <dt className="text-muted">IA</dt><dd>{data.ai.available ? `${data.ai.provider} – ${data.ai.model || ""}` : "Mode sans IA générative"}</dd>
        {data.data_dir && <><dt className="text-muted">Dossier des données</dt><dd className="break-all">{data.data_dir}</dd></>}
        <dt className="text-muted">API</dt><dd><a className="text-sage" href="./api/docs" target="_blank" rel="noreferrer">Documentation interactive (OpenAPI)</a></dd>
      </dl>
    </Card>
  );
}

export default function SettingsPage() {
  const { perms } = useApp();
  const [tab, setTab] = useState(perms.admin ? "agence" : "compte");
  const tabs = [
    ...(perms.admin ? [{ id: "agence", label: "Agence" }] : []), { id: "utilisateurs", label: "Utilisateurs et permissions" },
    ...(perms.admin ? [{ id: "ia", label: "Intelligence artificielle" }, { id: "meteo", label: "Météo" }, { id: "urbanisme", label: "Urbanisme" }] : []),
    { id: "sync", label: "Synchronisation" }, ...(perms.admin ? [{ id: "sauvegardes", label: "Sauvegardes" }, { id: "journal", label: "Journal" }] : []),
    { id: "compte", label: "Mon compte" }, { id: "systeme", label: "Système" },
  ];
  return (
    <div>
      <PageHeader title="Paramètres" icon={<Cog size={22} />} />
      <Tabs value={tab} onChange={setTab} tabs={tabs} />
      {tab === "agence" && <AgencyTab />}{tab === "utilisateurs" && <UsersTab />}{tab === "ia" && <AITab />}
      {tab === "meteo" && <ServiceTab k="weather" />}{tab === "urbanisme" && <ServiceTab k="urbanisme" />}{tab === "sync" && <SyncTab />}
      {tab === "sauvegardes" && <BackupTab />}{tab === "journal" && <AuditTab />}{tab === "compte" && <AccountTab />}{tab === "systeme" && <SystemTab />}
    </div>
  );
}

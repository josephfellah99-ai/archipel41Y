import { Files, Upload, Download, Eye, Search, Lock, Trash2, RefreshCw, Archive, Folder, FolderOpen, ChevronRight, ChevronDown, PenLine, ExternalLink, Link2, Info } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api, blobUrl, download, openNative } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { Comments } from "../components/Comments";
import { bytes, dateFr, dateTimeFr, DOC_CATEGORIES } from "../lib/format";
import { Card, Empty, ErrorBox, Field, Modal, Notice, PageHeader, Select, Spinner, Tabs, useDebounced, AsyncButton } from "../components/ui";
import { AnnotLayer, AnnotList, StructuredView, useAnnotations, type Annotation } from "../components/DocViewers";

const PREVIEWABLE = new Set(["pdf", "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "txt", "md"]);
const STRUCTURED = new Set(["xlsx", "xlsm", "xls", "csv", "tsv", "docx", "dxf", "ifc"]);
const ANNOTATABLE = new Set(["pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp"]);
export const DOC_STATUS: Record<string, string> = { travail: "Document de travail", valide: "Validé", archive: "Archivé" };
const STATUS_CHIP: Record<string, string> = { travail: "bg-sunken text-muted", valide: "bg-ok/15 text-ok", archive: "bg-ink/10 text-ink" };
const TEXT_STATUS: Record<string, string> = { ok: "Texte extrait", ocr: "Texte extrait par OCR", vide: "Aucun texte", non_supporte: "Format non analysé", erreur: "Erreur d'extraction", en_attente: "En attente" };

/** File d'attente : les pages sont rendues l'une après l'autre (jamais en parallèle), ce qui ménage le
 *  moteur local et affiche la première page au plus vite. */
let pageQueue: Promise<unknown> = Promise.resolve();
function queued<T>(job: () => Promise<T>): Promise<T> {
  const run = pageQueue.then(job, job);
  pageQueue = run.catch(() => undefined);
  return run;
}

function PageImage({ docId, n, version, overlay }: { docId: string; n: number; version?: number; overlay?: ReactNode }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let u: string | null = null;
    let alive = true;
    setFailed(false);
    queued(() => (alive ? blobUrl(`/api/documents/${docId}/page/${n}?scale=1.6${version ? `&version=${version}` : ""}`) : Promise.resolve(null)))
      .then((x) => { if (!x) return; if (alive) { u = x; setUrl(x); } else URL.revokeObjectURL(x); })
      .catch(() => alive && setFailed(true));
    return () => { alive = false; if (u) URL.revokeObjectURL(u); };
  }, [docId, n, version, attempt]);
  if (failed) return <div className="aspect-[1/1.41] w-full rounded-md bg-sunken flex flex-col items-center justify-center gap-2 text-sm text-muted">
    Aperçu de la page indisponible.<button className="btn-secondary py-1" onClick={() => setAttempt(attempt + 1)}>Réessayer</button></div>;
  return url ? <div className="relative"><img src={url} alt={`Page ${n}`} className="w-full rounded-md border border-line bg-white shadow-sm select-none" draggable={false} loading="lazy" />{overlay}</div>
    : <div className="aspect-[1/1.41] w-full rounded-md bg-sunken animate-pulse" />;
}

/** Aperçu PDF rendu par le serveur, page par page (indépendant de la visionneuse du navigateur). */
export function PdfPages({ docId, version, className = "", overlay }: { docId: string; version?: number; className?: string; overlay?: (n: number) => ReactNode }) {
  const [count, setCount] = useState<number | null>(null);
  const [shown, setShown] = useState(4);
  useEffect(() => { api.get(`/api/documents/${docId}/pages${version ? `?version=${version}` : ""}`).then((r: any) => setCount(r.pages)).catch(() => setCount(0)); }, [docId, version]);
  if (count === null) return <Spinner />;
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: Math.min(count, shown) }, (_, i) => <div key={i}><div className="text-[10px] text-muted mb-1">Page {i + 1} / {count}</div><PageImage docId={docId} n={i + 1} version={version} overlay={overlay?.(i + 1)} /></div>)}
      {count > shown && <button className="btn-secondary w-full" onClick={() => setShown(shown + 6)}>Afficher les pages suivantes ({count - shown})</button>}
    </div>
  );
}

type AnnotCtl = { items: Annotation[]; drawing: boolean; highlight: string | null; onCreate: (page: number, g: any) => void };

export function DocPreview({ doc, version, annot }: { doc: any; version?: number; annot?: AnnotCtl }) {
  const [url, setUrl] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const ext = (doc.extension || "").toLowerCase();
  useEffect(() => {
    let u: string | null = null;
    setUrl(null); setText(null); setErr(null);
    const v = version ? `&version=${version}` : "";
    if (ext === "pdf" || STRUCTURED.has(ext)) return;
    if (PREVIEWABLE.has(ext) && !["txt", "md"].includes(ext)) {
      blobUrl(`/api/documents/${doc.id}/download?inline=true${v}`).then((x) => { u = x; setUrl(x); }).catch((e) => setErr(e.message));
    } else {
      api.get(`/api/documents/${doc.id}/text${version ? `?version=${version}` : ""}`).then((r: any) => setText(r.text || "")).catch((e) => setErr(e.message));
    }
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [doc.id, version, ext]);
  const layer = (n: number) => annot && <AnnotLayer page={n} items={annot.items} drawing={annot.drawing} highlight={annot.highlight} onCreate={annot.onCreate} />;
  if (ext === "pdf") return <div className="max-h-[70vh] overflow-y-auto scrollbar-thin pr-1"><PdfPages docId={doc.id} version={version} overlay={annot ? layer : undefined} /></div>;
  if (STRUCTURED.has(ext)) return <StructuredView docId={doc.id} version={version} />;
  if (err) return <ErrorBox error={err} />;
  if (url) return <div className="relative inline-block max-w-full mx-auto"><img src={url} alt={doc.name} className="max-h-[70vh] mx-auto rounded-lg select-none" draggable={false} />{layer(1)}</div>;
  if (text !== null) return (
    <div>
      {["dwg", "ifc", "pln", "pla", "rvt", "skp"].includes(ext) &&
        <Notice>Fichier de CAO/BIM ({ext.toUpperCase()}) : conservé, versionné et téléchargeable. Ouvrez-le avec votre logiciel métier (ArchiCAD, AutoCAD, Revit, visionneuse IFC…).</Notice>}
      <pre className="whitespace-pre-wrap text-xs bg-sunken rounded-lg p-4 max-h-[65vh] overflow-auto scrollbar-thin mt-2">{text || "Aucun texte extrait pour ce document."}</pre>
    </div>
  );
  return <Spinner />;
}

/** Aperçu + annotations + ouverture dans le logiciel (bureau). */
function ViewerTab({ doc, version }: { doc: any; version?: number }) {
  const { perms, toast, toastError } = useApp();
  const ext = (doc.extension || "").toLowerCase();
  const annotatable = ANNOTATABLE.has(ext);
  const { items, reload } = useAnnotations(doc.id, version, annotatable);
  const [drawing, setDrawing] = useState(false);
  const [highlight, setHighlight] = useState<string | null>(null);
  const desktop = !!(window as any).archipelDesktop?.openFile;
  const create = async (page: number, g: any) => {
    const text = window.prompt(g.w || g.h ? "Observation sur la zone sélectionnée :" : "Observation au repère :", "");
    if (!text || !text.trim()) return;
    try {
      await api.call("POST", `/api/documents/${doc.id}/annotations`, { page, geometry: g, kind: g.w || g.h ? "zone" : "repere", text, version_number: version });
      toast("Annotation enregistrée (le fichier original n'est pas modifié)."); reload();
    } catch (e) { toastError(e); }
  };
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        {annotatable && perms.write && <button className={`btn-secondary py-1 ${drawing ? "!bg-forest !text-white" : ""}`} aria-pressed={drawing} onClick={() => setDrawing(!drawing)}>
          <PenLine size={14} /> {drawing ? "Annotation en cours — cliquez ou faites glisser sur la page" : "Annoter"}</button>}
        {desktop && <button className="btn-secondary py-1" onClick={async () => {
          try { const r = await openNative(`/api/documents/${doc.id}/download${version ? `?version=${version}` : ""}`, doc.name); if (!r.ok) toast(r.error || "Ouverture impossible.", "info"); } catch (e) { toastError(e); }
        }}><ExternalLink size={14} /> Ouvrir avec l'application</button>}
      </div>
      {annotatable ? (
        <div className="grid lg:grid-cols-[1fr_280px] gap-4">
          <DocPreview doc={doc} version={version} annot={{ items, drawing, highlight, onCreate: create }} />
          <div><h4 className="text-xs uppercase tracking-wider text-muted mb-2">Annotations ({items.length})</h4>
            <AnnotList items={items} onChanged={reload} onFocus={setHighlight} /></div>
        </div>
      ) : <DocPreview doc={doc} version={version} />}
    </div>
  );
}

function useTree(projectId?: string | null) {
  return useApi<any>(projectId ? `/api/documents/tree?project_id=${projectId}` : null);
}
const depthOf = (p: string) => p.split("/").length - 1;

function ClassementTab({ doc, full, onSaved }: { doc: any; full: any; onSaved: () => void }) {
  const { perms, toast, toastError, projects } = useApp();
  const tree = useTree(doc.project_id);
  const advice = useApi<any>(`/api/documents/${doc.id}/advice`);
  const siblings = useApi<any[]>(doc.project_id ? `/api/documents?project_id=${doc.project_id}` : null);
  const [meta, setMeta] = useState<any>({ name: doc.name, category: doc.category, tags: (doc.tags || []).join(", "), project_id: doc.project_id || "",
    confidential: doc.confidential, description: doc.description || "", folder: doc.folder || "", status: doc.status || "travail", related_ids: doc.related_ids || [] });
  const save = async (extra: any = {}) => {
    try {
      await api.call("PUT", `/api/documents/${doc.id}`, { ...meta, ...extra, project_id: meta.project_id || null, folder: (extra.folder ?? meta.folder) || null,
        tags: meta.tags.split(",").map((t: string) => t.trim()).filter(Boolean), version: full?.version });
      toast("Classement enregistré."); onSaved(); advice.reload();
    } catch (e) { toastError(e); }
  };
  const folderOpts = useMemo(() => {
    const f = (tree.data?.folders || []).map((x: any) => ({ value: x.path, label: `${"  ".repeat(depthOf(x.path))}${x.label}${x.custom ? " (dossier du projet)" : ""}` }));
    if (meta.folder && !f.some((x: any) => x.value === meta.folder)) f.push({ value: meta.folder, label: meta.folder });
    return f;
  }, [tree.data, meta.folder]);
  const sug = advice.data?.suggestion;
  const nm = advice.data?.nommage;
  const canValidate = perms.delete;
  return (
    <div className="space-y-4">
      {perms.write && sug && <div className="rounded-lg border border-sage/40 bg-sage/5 p-3 text-sm" role="status">
        <div className="font-medium flex items-center gap-1.5"><FolderOpen size={15} /> Classement suggéré : {sug.folder || "racine du dossier projet"}</div>
        <div className="text-xs text-muted mt-0.5">{sug.reason} · {sug.source} · certitude : {sug.certitude}. Rien n'est déplacé sans votre accord.</div>
        <div className="flex gap-2 mt-2"><AsyncButton className="btn-primary py-1" onClick={async () => { setMeta({ ...meta, folder: sug.folder }); await save({ folder: sug.folder }); }}>Classer ici</AsyncButton>
          <AsyncButton className="btn-secondary py-1" onClick={async () => { try { await api.call("PUT", `/api/documents/${doc.id}`, { linked: { ...(full?.linked || {}), suggestion_refusee: sug.folder }, version: full?.version }); onSaved(); advice.reload(); } catch (e) { toastError(e); } }}>Ignorer</AsyncButton></div>
      </div>}
      {perms.write && nm && !nm.conforme && <Notice tone="warn">
        <div><b>Nom hors convention de l'agence :</b> {nm.issues.join(" ")}</div>
        <div className="mt-1">Proposition : <code className="text-xs">{nm.proposition}</code> <button className="underline ml-1" onClick={() => setMeta({ ...meta, name: nm.proposition })}>Utiliser ce nom</button></div>
        <div className="text-[11px] mt-1">{nm.note}</div></Notice>}
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Nom" className="sm:col-span-2"><input className="input" disabled={!perms.write} value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} /></Field>
        <Field label="Dossier (arborescence du projet)" className="sm:col-span-2" hint={doc.project_id ? "Arborescence ARCHIPEL 41 ; un dossier propre au projet peut être saisi ci-dessous." : "Rattachez d'abord le document à un projet."}>
          <Select disabled={!perms.write || !doc.project_id} value={meta.folder} onChange={(v) => setMeta({ ...meta, folder: v })} placeholder="— Non classé —" options={folderOpts} /></Field>
        {perms.write && doc.project_id && <Field label="… ou dossier propre au projet" className="sm:col-span-2" hint="Ex. 5-Réalisation/06_EXE entreprises/71_Lots/Lot 03 - Charpente">
          <input className="input" value={meta.folder} onChange={(e) => setMeta({ ...meta, folder: e.target.value })} /></Field>}
        <Field label="Catégorie"><Select disabled={!perms.write} value={meta.category} onChange={(v) => setMeta({ ...meta, category: v })} options={Object.entries(DOC_CATEGORIES).map(([v, l]) => ({ value: v, label: l }))} /></Field>
        <Field label="Statut" hint={canValidate ? undefined : "Valider ou archiver : gestionnaires et administrateurs."}>
          <Select disabled={!perms.write} value={meta.status} onChange={(v) => setMeta({ ...meta, status: v })}
            options={Object.entries(DOC_STATUS).map(([v, l]) => ({ value: v, label: l, disabled: !canValidate && v !== "travail" && v !== doc.status }))} /></Field>
        <Field label="Projet"><Select disabled={!perms.write} value={meta.project_id} onChange={(v) => setMeta({ ...meta, project_id: v })} placeholder="— Documents de l'agence —" options={projects.map((p) => ({ value: p.id, label: `${p.code} – ${p.name}` }))} /></Field>
        <Field label="Mots-clés (séparés par des virgules)"><input className="input" disabled={!perms.write} value={meta.tags} onChange={(e) => setMeta({ ...meta, tags: e.target.value })} /></Field>
        <Field label="Description" className="sm:col-span-2"><textarea className="input" disabled={!perms.write} value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} /></Field>
        <Field label="Documents liés" className="sm:col-span-2" group>
          {!doc.project_id ? <div className="text-xs text-muted">Disponible pour les documents d'un projet.</div> :
            <div className="max-h-40 overflow-y-auto scrollbar-thin rounded-md border border-line p-2 space-y-1">{(siblings.data || []).filter((x) => x.id !== doc.id).map((x) => (
              <label key={x.id} className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={!perms.write} checked={meta.related_ids.includes(x.id)}
                onChange={(e) => setMeta({ ...meta, related_ids: e.target.checked ? [...meta.related_ids, x.id] : meta.related_ids.filter((y: string) => y !== x.id) })} />
                <span className="truncate">{x.name}</span></label>))}
              {siblings.data && siblings.data.length <= 1 && <div className="text-xs text-muted">Aucun autre document dans ce projet.</div>}</div>}
        </Field>
        <label className="text-sm flex items-center gap-2 sm:col-span-2"><input type="checkbox" disabled={!perms.write} checked={meta.confidential} onChange={(e) => setMeta({ ...meta, confidential: e.target.checked })} /> Document confidentiel (jamais transmis à un fournisseur d'IA externe sans autorisation de l'administrateur)</label>
        <div className="text-xs text-muted sm:col-span-2">Analyse du contenu : {TEXT_STATUS[doc.text_status] || doc.text_status} {doc.page_count ? `· ${doc.page_count} page(s)` : ""}
          {perms.write && <button className="text-sage ml-2" onClick={async () => { try { await api.call("POST", `/api/documents/${doc.id}/reindex`); toast("Document réindexé."); } catch (e) { toastError(e); } }}><RefreshCw size={11} className="inline" /> Réindexer</button>}</div>
        {perms.write && <div className="sm:col-span-2"><AsyncButton onClick={() => save()}>Enregistrer le classement</AsyncButton></div>}
      </div>
    </div>
  );
}

function SimilarTab({ doc, onOpen }: { doc: any; onOpen: (d: any) => void }) {
  const sim = useApi<any[]>(`/api/documents/${doc.id}/similar`);
  if (sim.loading && !sim.data) return <Spinner label="Recherche des documents proches…" />;
  if (!sim.data?.length) return <Empty title="Aucun document au contenu proche" icon={<Link2 size={18} />}>La comparaison porte sur le texte extrait des documents accessibles.</Empty>;
  return (
    <ul className="space-y-2">{sim.data.map((s) => (
      <li key={s.id} className="rounded-lg border border-line p-3 hover:bg-sunken/40 cursor-pointer" onClick={() => onOpen(s)}>
        <div className="text-sm font-medium">{s.name}<span className="text-xs text-muted float-right">proximité {Math.round(s.score * 100)} %</span></div>
        {s.excerpt && <div className="text-xs text-muted mt-1 line-clamp-2">{s.excerpt}</div>}</li>))}</ul>
  );
}

function DocModal({ doc, onClose, onChanged, onOpen }: { doc: any; onClose: () => void; onChanged: () => void; onOpen: (d: any) => void }) {
  const { perms, toast, toastError } = useApp();
  const full = useApi<any>(`/api/documents/${doc.id}`);
  const hist = useApi<any[]>(`/api/documents/${doc.id}/history`);
  const [tab, setTab] = useState("apercu");
  const [ver, setVer] = useState<number | undefined>();
  const fileRef = useRef<HTMLInputElement>(null);
  const newVersion = async (f: File) => {
    const fd = new FormData(); fd.append("file", f);
    try { await api.upload(`/api/documents/${doc.id}/versions`, fd); toast("Nouvelle version ajoutée ; la précédente reste consultable."); full.reload(); hist.reload(); onChanged(); } catch (e) { toastError(e); }
  };
  const d = full.data || doc;
  return (
    <Modal open onClose={onClose} title={d.name} wide footer={<>
      {perms.delete && <button className="btn-ghost text-danger mr-auto" onClick={async () => { await api.del(`/api/documents/${doc.id}`); onChanged(); onClose(); }}><Trash2 size={15} /> Supprimer</button>}
      <button className="btn-secondary" onClick={() => download(`/api/documents/${doc.id}/download${ver ? `?version=${ver}` : ""}`).catch(toastError)}><Download size={15} /> Télécharger</button>
      {perms.write && <><input ref={fileRef} type="file" hidden onChange={(e) => e.target.files?.[0] && newVersion(e.target.files[0])} />
        <button className="btn-primary" onClick={() => fileRef.current?.click()}><Upload size={15} /> Nouvelle version</button></>}</>}>
      <div className="flex flex-wrap gap-1.5 mb-2 text-xs">
        <span className={`chip ${STATUS_CHIP[d.status] || "bg-sunken"}`}>{DOC_STATUS[d.status] || d.status}</span>
        {d.folder ? <span className="chip bg-sunken"><Folder size={11} className="inline mr-1" />{d.folder}</span> : d.project_id && <span className="chip bg-warn/15 text-warn">Non classé</span>}
        {ver && <span className="chip bg-sage/10 text-sage">Version {ver} affichée</span>}
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "apercu", label: "Aperçu" }, { id: "infos", label: "Classement" }, { id: "versions", label: `Versions (${full.data?.versions?.length || doc.current_version})` },
        { id: "similaires", label: "Similaires" }, { id: "historique", label: "Historique" }, { id: "echanges", label: "Échanges" }]} />
      {tab === "apercu" && <ViewerTab doc={d} version={ver} />}
      {tab === "infos" && (full.data ? <ClassementTab doc={full.data} full={full.data} onSaved={() => { full.reload(); hist.reload(); onChanged(); }} /> : <Spinner />)}
      {tab === "versions" && (full.data ? (
        <table className="table"><thead><tr><th>Version</th><th>Fichier</th><th>Taille</th><th>Date</th><th>Commentaire</th><th /></tr></thead>
          <tbody>{full.data.versions.map((v: any) => (
            <tr key={v.id}><td>v{v.number}{v.number === full.data.current_version && <span className="chip bg-ok/15 text-ok ml-1">actuelle</span>}</td><td>{v.filename}</td><td>{bytes(v.size)}</td><td>{dateTimeFr(v.created_at)}</td><td className="text-muted">{v.comment || ""}</td>
              <td className="whitespace-nowrap">{v.has_file ? <><button className="btn-ghost p-1" onClick={() => { setVer(v.number); setTab("apercu"); }} title="Aperçu"><Eye size={14} /></button>
                <button className="btn-ghost p-1" onClick={() => download(`/api/documents/${doc.id}/download?version=${v.number}`).catch(toastError)} title="Télécharger"><Download size={14} /></button></> : <span className="text-xs text-warn">non synchronisé</span>}</td></tr>))}</tbody></table>) : <Spinner />)}
      {tab === "similaires" && <SimilarTab doc={doc} onOpen={onOpen} />}
      {tab === "echanges" && <Comments entity="documents" entityId={doc.id} />}
      {tab === "historique" && <ul className="space-y-2">{(hist.data || []).map((h, i) => <li key={i} className="text-sm"><span className="font-medium">{h.user}</span> · {h.op} · <span className="text-muted">{dateTimeFr(h.at)}</span>
        {h.changes && <span className="text-xs text-muted"> — {Object.keys(h.changes).join(", ")}</span>}</li>)}</ul>}
    </Modal>
  );
}

/** Arborescence ARCHIPEL 41 du projet : dossiers, nombre de documents, notes « Classer ici ». */
function FolderTree({ projectId, value, onChange }: { projectId: string; value: string; onChange: (f: string) => void }) {
  const tree = useTree(projectId);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [info, setInfo] = useState<any>(null);
  const folders: any[] = tree.data?.folders || [];
  const children = useMemo(() => {
    const m: Record<string, any[]> = {};
    for (const f of folders) { const parent = f.path.includes("/") ? f.path.slice(0, f.path.lastIndexOf("/")) : ""; (m[parent] ||= []).push(f); }
    return m;
  }, [folders]);
  useEffect(() => { if (value) setOpen((o) => { const n = new Set(o); value.split("/").forEach((_, i, a) => n.add(a.slice(0, i + 1).join("/"))); return n; }); }, [value]);
  const node = (f: any): ReactNode => {
    const kids = children[f.path] || [];
    const isOpen = open.has(f.path);
    return (
      <li key={f.path}>
        <div className={`flex items-center gap-1 rounded-md pr-1 ${value === f.path ? "bg-forest text-white" : "hover:bg-sunken"}`}>
          <button className="p-0.5 opacity-70" aria-label={isOpen ? "Replier" : "Déplier"} disabled={!kids.length} onClick={() => setOpen((o) => { const n = new Set(o); n.has(f.path) ? n.delete(f.path) : n.add(f.path); return n; })}>
            {kids.length ? (isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />) : <span className="inline-block w-[13px]" />}</button>
          <button className="flex-1 text-left truncate text-[13px] py-0.5" title={f.fonction} onClick={() => { onChange(value === f.path ? "" : f.path); setInfo(f); }}>
            {isOpen ? <FolderOpen size={13} className="inline mr-1" /> : <Folder size={13} className="inline mr-1" />}{f.label}{f.custom && <span className="text-[10px] opacity-70"> · projet</span>}</button>
          {f.total > 0 && <span className={`text-[10px] tabular-nums ${value === f.path ? "" : "text-muted"}`}>{f.total}</span>}
        </div>
        {isOpen && kids.length > 0 && <ul className="pl-3 border-l border-line ml-2">{kids.map(node)}</ul>}
      </li>
    );
  };
  if (tree.loading && !tree.data) return <Spinner />;
  return (
    <Card title="Arborescence du projet" pad={false}>
      <div className="px-3 pb-3">
        <div className="text-[11px] text-muted mb-2">{tree.data?.name} · {tree.data?.version}</div>
        <button className={`w-full text-left text-[13px] rounded-md px-2 py-0.5 mb-1 ${value === "" ? "bg-forest text-white" : "hover:bg-sunken"}`} onClick={() => { onChange(""); setInfo(null); }}>Tous les documents ({tree.data?.total ?? 0})</button>
        <button className={`w-full text-left text-[13px] rounded-md px-2 py-0.5 mb-2 ${value === "__none__" ? "bg-forest text-white" : "hover:bg-sunken"}`} onClick={() => { onChange("__none__"); setInfo(null); }}>Non classés ({tree.data?.unfiled ?? 0})</button>
        <ul className="max-h-[56vh] overflow-y-auto scrollbar-thin" aria-label="Dossiers">{(children[""] || []).map(node)}</ul>
        {info && value === info.path && <div className="mt-3 rounded-md bg-sunken p-2 text-xs space-y-1"><div className="font-medium flex items-center gap-1"><Info size={12} /> {info.label}</div>
          <div>{info.fonction}</div>{info.note && <div className="whitespace-pre-line text-muted">{info.note}</div>}
          {info.gabarit_sous_dossier && <div className="text-muted">Sous-dossier type : {info.gabarit_sous_dossier}</div>}</div>}
      </div>
    </Card>
  );
}

export function DocumentsTable({ projectId, folder = "" }: { projectId?: string | null; folder?: string }) {
  const { perms, toast, toastError } = useApp();
  const [params] = useSearchParams();
  const [cat, setCat] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [conf, setConf] = useState(false);
  const [open, setOpen] = useState<any>(null);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const qs = new URLSearchParams({ ...(projectId ? { project_id: projectId } : {}), ...(cat ? { category: cat } : {}), ...(dq ? { q: dq } : {}),
    ...(folder && projectId ? { folder } : {}), ...(status ? { status } : {}) });
  const { data, loading, error, reload } = useApi<any[]>(`/api/documents?${qs}`);
  useEffect(() => { const d = params.get("doc"); if (d && data) { const x = data.find((y) => y.id === d); if (x) setOpen(x); } }, [params, data]);
  const upload = async (files: File[]) => {
    if (!files.length) return;
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    if (projectId) fd.append("project_id", projectId);
    if (cat) fd.append("category", cat);
    fd.append("confidential", String(conf));
    setBusy(true);
    try {
      const r = await api.upload("/api/documents/upload", fd);
      const warn = r.extraction.filter((x: any) => x.warnings.length);
      const sug = r.extraction.filter((x: any) => x.suggestion).length;
      toast(`${r.documents.length} document(s) importé(s)${warn.length ? ` – ${warn.length} avec avertissement(s)` : ""}${sug ? ` – ${sug} suggestion(s) de classement à examiner (onglet Classement)` : ""}.`);
      reload();
      if (folder && folder !== "__none__" && projectId) {   // import dans le dossier sélectionné : classement explicite
        for (const d of r.documents) await api.call("PUT", `/api/documents/${d.id}`, { folder, version: d.version }).catch(() => {});
        reload();
      }
    } catch (e) { toastError(e); } finally { setBusy(false); }
  };
  return (
    <Card pad={false} title={`${data?.length ?? 0} document(s)${folder && folder !== "__none__" ? ` · ${folder.split("/").pop()}` : folder === "__none__" ? " · non classés" : ""}`} actions={<div className="flex flex-wrap gap-2 items-center">
      {sel.size > 0 && <button className="btn-secondary" onClick={() => download("/api/documents/export", "documents_archipel41.zip", { ids: [...sel] }).catch(toastError)}><Archive size={15} /> Exporter ({sel.size})</button>}
      {perms.write && <><label className="text-xs flex items-center gap-1.5"><input type="checkbox" checked={conf} onChange={(e) => setConf(e.target.checked)} /> Confidentiel</label>
        <input ref={fileRef} type="file" multiple hidden onChange={(e) => { upload(Array.from(e.target.files || [])); e.target.value = ""; }} aria-label="Fichiers à importer" />
        <button className="btn-primary" disabled={busy} onClick={() => fileRef.current?.click()}><Upload size={15} /> {busy ? "Import…" : folder && folder !== "__none__" ? "Importer dans ce dossier" : "Importer"}</button></>}
    </div>}>
      <div className="px-5 pb-3 flex flex-wrap gap-2">
        <div className="relative"><Search size={14} className="absolute left-3 top-2.5 text-muted" /><input className="input pl-8 w-72" placeholder="Nom, description ou contenu…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Select className="w-48" value={cat} onChange={setCat} placeholder="Toutes catégories" options={Object.entries(DOC_CATEGORIES).map(([v, l]) => ({ value: v, label: l }))} />
        <Select className="w-48" value={status} onChange={setStatus} placeholder="Tous statuts" options={Object.entries(DOC_STATUS).map(([v, l]) => ({ value: v, label: l }))} aria-label="Statut" />
      </div>
      <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); perms.write && upload(Array.from(e.dataTransfer.files)); }}>
        <ErrorBox error={error} />
        {loading && !data ? <Spinner /> : !data?.length ? <Empty title="Aucun document" icon={<Files size={18} />}>Glissez-déposez des fichiers ici : PDF, Word, Excel, images, DWG, DXF, IFC, PLN, PLA…</Empty> : (
          <div className="overflow-x-auto"><table className="table">
            <thead><tr><th className="w-8" /><th>Nom</th>{projectId && <th>Dossier</th>}<th>Statut</th><th>Catégorie</th><th>Version</th><th>Taille</th><th>Modifié</th><th /></tr></thead>
            <tbody>{data.map((d) => (
              <tr key={d.id} className="hover:bg-sunken/50">
                <td><input type="checkbox" checked={sel.has(d.id)} onChange={() => setSel((s) => { const n = new Set(s); n.has(d.id) ? n.delete(d.id) : n.add(d.id); return n; })} aria-label="Sélectionner" /></td>
                <td className="cursor-pointer" onClick={() => setOpen(d)}><span className="chip bg-sunken text-muted uppercase mr-2">{d.extension}</span><span className="font-medium hover:text-sage">{d.name}</span>{d.confidential && <Lock size={12} className="inline ml-1 text-muted" />}
                  {(d.tags || []).length > 0 && <div className="flex gap-1 mt-1">{d.tags.map((t: string) => <span key={t} className="chip bg-sage/10 text-sage">{t}</span>)}</div>}</td>
                {projectId && <td className="text-xs text-muted max-w-[220px] truncate" title={d.folder || ""}>{d.folder ? d.folder.split("/").pop() : <span className="text-warn">non classé</span>}</td>}
                <td><span className={`chip ${STATUS_CHIP[d.status] || "bg-sunken"}`}>{DOC_STATUS[d.status] || d.status}</span></td>
                <td>{DOC_CATEGORIES[d.category] || d.category}</td><td>v{d.current_version}</td><td className="text-muted">{bytes(d.size)}</td><td className="text-muted">{dateFr(d.updated_at)}</td>
                <td className="whitespace-nowrap"><button className="btn-ghost p-1" onClick={() => setOpen(d)} title="Ouvrir"><Eye size={15} /></button>
                  <button className="btn-ghost p-1" onClick={() => download(`/api/documents/${d.id}/download`).catch(toastError)} title="Télécharger"><Download size={15} /></button></td>
              </tr>))}</tbody>
          </table></div>)}
      </div>
      {open && <DocModal key={open.id} doc={open} onClose={() => setOpen(null)} onChanged={reload} onOpen={(x) => setOpen(x)} />}
    </Card>
  );
}

function SemanticSearch() {
  const { projectId } = useApp();
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    try { setRes(await api.get(`/api/documents/search?q=${encodeURIComponent(q)}${projectId ? `&project_id=${projectId}` : ""}`)); } finally { setBusy(false); }
  };
  return (
    <Card title="Recherche dans le contenu des documents">
      <form onSubmit={run} className="flex gap-2 mb-3"><input className="input" placeholder="ex. classe d'exposition du béton, hauteur maximale en zone UB…" value={q} onChange={(e) => setQ(e.target.value)} /><button className="btn-primary" disabled={busy}><Search size={15} /> Rechercher</button></form>
      <p className="text-xs text-muted mb-3">Recherche hybride (sémantique + mots-clés) dans le texte extrait de tous les documents accessibles, y compris les documents scannés passés à l'OCR.</p>
      {busy ? <Spinner /> : res && (res.length === 0 ? <Empty title="Aucun passage pertinent" /> : (
        <ul className="space-y-3">{res.map((r, i) => (
          <li key={i} className="rounded-lg border border-line p-3"><div className="text-sm font-medium">{r.document} {r.page && <span className="text-muted font-normal">· page {r.page}</span>}<span className="text-xs text-muted float-right">pertinence {Math.round(r.score * 100)} %</span></div>
            <div className="text-sm text-ink/80 mt-1 whitespace-pre-wrap line-clamp-5">{r.text}</div></li>))}</ul>))}
    </Card>
  );
}

export default function Documents() {
  const { projectId, projects } = useApp();
  const [scope, setScope] = useState<"projet" | "tous">(projectId ? "projet" : "tous");
  const [folder, setFolder] = useState("");
  useEffect(() => { setScope(projectId ? "projet" : "tous"); setFolder(""); }, [projectId]);
  const p = projects.find((x) => x.id === projectId);
  const inProject = scope === "projet" && !!projectId;
  return (
    <div>
      <PageHeader title="Documents" icon={<Files size={22} />} subtitle="Bibliothèque documentaire : arborescence de l'agence, classement, versions, visionneuses, annotations, recherche et exports."
        actions={projectId && <Select className="w-64" value={scope} onChange={(v) => setScope(v as any)} options={[{ value: "projet", label: `Projet ${p?.code || ""}` }, { value: "tous", label: "Toute l'agence" }]} />} />
      <div className="space-y-6">
        {inProject ? <div className="grid lg:grid-cols-[300px_1fr] gap-6 items-start">
          <FolderTree projectId={projectId!} value={folder} onChange={setFolder} />
          <DocumentsTable projectId={projectId} folder={folder} /></div>
          : <DocumentsTable projectId={null} />}
        <SemanticSearch />
      </div>
    </div>
  );
}

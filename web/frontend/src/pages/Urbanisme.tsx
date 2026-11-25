import { Map as MapIcon, Search, FileText, AlertTriangle, BookOpen, Landmark, ShieldAlert, Sparkles, ExternalLink, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, download } from "../lib/api";
import { useApi, useApp } from "../lib/app";
import { dateFr, dateTimeFr } from "../lib/format";
import { Card, Empty, ErrorBox, Field, Markdown, Notice, PageHeader, Select, Spinner } from "../components/ui";

function ParcelShape({ geometry }: { geometry: any }) {
  if (!geometry) return <div className="text-xs text-muted">Géométrie de la parcelle non disponible.</div>;
  const polys = geometry.type === "MultiPolygon" ? geometry.coordinates : [geometry.coordinates];
  const pts = polys.flat(2) as number[][];
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
  const lat = (miny + maxy) / 2;
  const k = Math.cos((lat * Math.PI) / 180);
  const w = (maxx - minx) * k || 1e-6, h = maxy - miny || 1e-6;
  const scale = 200 / Math.max(w, h);
  const path = polys.map((poly: number[][][]) => poly.map((ring) => "M" + ring.map((p) => `${((p[0] - minx) * k * scale + 10).toFixed(1)},${((maxy - p[1]) * scale + 10).toFixed(1)}`).join(" L") + " Z").join(" ")).join(" ");
  return (
    <svg viewBox={`0 0 ${w * scale + 20} ${h * scale + 20}`} className="w-full max-w-[260px] h-auto" role="img" aria-label="Tracé de la parcelle">
      <path d={path} fill="rgb(var(--sage) / 0.25)" stroke="rgb(var(--forest))" strokeWidth={2} />
    </svg>
  );
}

function Section({ title, icon, items, render, emptyText }: { title: string; icon: any; items: any[]; render: (x: any, i: number) => any; emptyText: string }) {
  return (
    <Card title={<span className="flex items-center gap-2">{icon}{title}</span>}>
      {items?.length ? <ul className="space-y-2 text-sm">{items.map(render)}</ul> : <div className="text-sm text-muted">{emptyText}</div>}
    </Card>
  );
}

function AnalysisView({ id, onDeleted }: { id: string; onDeleted: () => void }) {
  const { perms, toast, toastError, projectId } = useApp();
  const { data: a, loading, reload, setData } = useApi<any>(`/api/urbanisme/analyses/${id}`);
  const docs = useApi<any[]>("/api/documents?category=urbanisme");
  const ai = useApi<any>("/api/assistant/status");
  const [docId, setDocId] = useState("");
  const [zone, setZone] = useState("");
  const [useAi, setUseAi] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (a) setZone((a.results?.zones || [])[0]?.code || ""); }, [a?.id]);
  if (loading && !a) return <Spinner />;
  if (!a) return null;
  const r = a.results || {};
  const plu = a.rules?.plu;
  const feas = a.rules?.feasibility;
  const analyse = async () => {
    setBusy(true);
    try { setData(await api.call("POST", `/api/urbanisme/analyses/${id}/plu`, { document_id: docId, zone: zone || null, use_ai: useAi })); toast("Règlement analysé."); } catch (e) { toastError(e); } finally { setBusy(false); }
  };
  const report = async () => {
    try { const rep = await api.call("POST", "/api/reports", { kind: "urbanisme", fmt: "pdf", analysis_id: id }); toast("Rapport de faisabilité généré."); await download(rep.download_url); } catch (e) { toastError(e); }
  };
  const loc = r.location || {};
  const gpu = a.latitude ? `https://www.geoportail-urbanisme.gouv.fr/map/#tile=1&lon=${a.longitude}&lat=${a.latitude}&zoom=18` : null;
  return (
    <div className="space-y-6">
      {a.mode === "demo" && <Notice tone="warn"><b>Mode démonstration</b> : toutes les informations ci-dessous sont fictives. Désactivez le mode démonstration dans Paramètres › Urbanisme pour interroger les services officiels.</Notice>}
      <div className="grid lg:grid-cols-3 gap-6">
        <Card title="Terrain" className="lg:col-span-2" actions={<>
          {gpu && a.mode !== "demo" && <a className="btn-secondary" href={gpu} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Géoportail</a>}
          <button className="btn-primary" onClick={report}><FileText size={15} /> Rapport de faisabilité</button>
          {perms.delete && <button className="btn-ghost text-danger" onClick={async () => { await api.del(`/api/urbanisme/analyses/${id}`); onDeleted(); }}><Trash2 size={15} /></button>}</>}>
          <div className="grid sm:grid-cols-[1fr_auto] gap-4">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-muted">Localisation</dt><dd>{loc.label || a.query}</dd>
              <dt className="text-muted">Commune</dt><dd>{loc.commune || "—"} (INSEE {a.insee || "—"})</dd>
              <dt className="text-muted">Parcelle</dt><dd>{a.section ? `Section ${a.section} n° ${a.numero}` : "Non identifiée"}</dd>
              <dt className="text-muted">Surface</dt><dd>{a.area_m2 ? `${Math.round(a.area_m2).toLocaleString("fr-FR")} m²` : "Non disponible"} <span className="text-xs text-muted">{r.area_source}</span></dd>
              <dt className="text-muted">Coordonnées</dt><dd className="tabular-nums">{a.latitude ? `${a.latitude.toFixed(6)}, ${a.longitude.toFixed(6)}` : "—"}</dd>
              <dt className="text-muted">Document</dt><dd>{(r.documents || []).map((d: any) => `${d.type || ""} ${d.name || ""} (approuvé le ${dateFr(d.approved)})`).join(" ; ") || "Non disponible"}</dd>
              <dt className="text-muted">Zonage</dt><dd>{(r.zones || []).map((z: any) => <span key={z.code} className="chip bg-forest text-white mr-1 dark:text-bg">{z.code}</span>)}{(r.zones || [])[0]?.label}</dd>
            </dl>
            <ParcelShape geometry={a.geometry} />
          </div>
        </Card>
        <Card title={<span className="flex items-center gap-2"><AlertTriangle size={15} className="text-warn" />Données indisponibles</span>}>
          {a.unavailable?.length ? <ul className="text-sm space-y-1.5">{a.unavailable.map((u: any, i: number) => <li key={i}><b>{u.source}</b> : <span className="text-muted">{u.reason}</span></li>)}</ul> : <div className="text-sm text-ok">Toutes les sources interrogées ont répondu.</div>}
        </Card>
      </div>
      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-6">
        <Section title="Servitudes d'utilité publique" icon={<ShieldAlert size={15} />} items={r.servitudes} emptyText="Aucune servitude publiée pour ce terrain."
          render={(s, i) => <li key={i}><span className="chip bg-sunken mr-1">{s.category}</span>{s.label}{s.category_label && <div className="text-xs text-muted">{s.category_label}</div>}</li>} />
        <Section title="Prescriptions" icon={<BookOpen size={15} />} items={r.prescriptions} emptyText="Aucune prescription publiée."
          render={(p, i) => <li key={i}>{p.label}<div className="text-xs text-muted">{p.kind}{p.text ? ` – ${p.text}` : ""}</div></li>} />
        <Section title="Patrimoine" icon={<Landmark size={15} />} items={r.patrimoine} emptyText="Aucune protection patrimoniale publiée."
          render={(p, i) => <li key={i}>{p.label}<div className="text-xs text-muted">{p.category_label}</div></li>} />
        <Card title={<span className="flex items-center gap-2"><AlertTriangle size={15} />Risques</span>}>
          <dl className="text-sm space-y-1.5"><dt className="text-muted text-xs">Risques recensés (commune)</dt><dd>{(r.risques?.commune || []).join(", ") || "Non disponible"}</dd>
            <dt className="text-muted text-xs">Sismicité</dt><dd>{r.risques?.sismicite || "Non disponible"}</dd>
            <dt className="text-muted text-xs">Retrait-gonflement des argiles</dt><dd>{r.risques?.argiles || "Non disponible"}</dd></dl>
        </Card>
      </div>
      <Card title="Analyse du règlement écrit du PLU">
        {perms.write && (
          <div className="grid sm:grid-cols-4 gap-3 items-end mb-4">
            <Field label="Règlement (document importé)" className="sm:col-span-2" hint={!docs.data?.length ? "Importez le règlement écrit dans Documents (catégorie Urbanisme)." : undefined}>
              <Select value={docId} onChange={setDocId} placeholder="— Choisir —" options={(docs.data || []).map((d) => ({ value: d.id, label: d.name }))} /></Field>
            <Field label="Zone"><input className="input" value={zone} onChange={(e) => setZone(e.target.value)} placeholder="ex. UB" /></Field>
            <div className="flex flex-col gap-2">
              <label className="text-xs flex items-center gap-1.5"><input type="checkbox" disabled={!ai.data?.available} checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> Synthèse rédigée par l'IA</label>
              <button className="btn-primary" disabled={!docId || busy} onClick={analyse}><Search size={15} /> {busy ? "Analyse…" : "Analyser"}</button></div>
          </div>)}
        {!plu ? <Empty title="Aucun règlement analysé">Les dispositions sont recherchées article par article ; seuls des extraits réellement présents dans le document sont affichés.</Empty> : (
          <div>
            {plu.scope_note && <div className="mb-3"><Notice tone="warn">{plu.scope_note}</Notice></div>}
            <div className="grid md:grid-cols-2 gap-3">{Object.entries(plu.themes).map(([k, t]: any) => (
              <div key={k} className={`rounded-lg border p-3 ${t.found ? "border-line" : "border-dashed border-warn/50 bg-warn/5"}`}>
                <div className="flex items-center justify-between gap-2"><div className="text-sm font-medium">{t.label}</div>{t.page && <span className="text-xs text-muted">p. {t.page}</span>}</div>
                {t.found ? <>
                  {t.article && <div className="text-xs text-sage mt-0.5">{t.article}</div>}
                  <p className="text-xs text-ink/80 mt-1 whitespace-pre-wrap line-clamp-6">{t.excerpt}</p>
                  {t.values?.length > 0 && <div className="flex flex-wrap gap-1 mt-1.5">{t.values.map((v: string) => <span key={v} className="chip bg-forest/10 text-forest">{v}</span>)}</div>}
                  {t.note && <div className="text-[11px] text-warn mt-1">{t.note}</div>}
                </> : <div className="text-xs text-warn mt-1">{t.message}</div>}
              </div>))}</div>
          </div>)}
      </Card>
      {feas && (
        <Card title="Faisabilité">
          {feas.indicators?.length > 0 && <table className="table mb-4"><thead><tr><th>Indicateur</th><th>Valeur</th><th>Calcul</th><th>Source</th></tr></thead>
            <tbody>{feas.indicators.map((i: any) => <tr key={i.label}><td>{i.label}</td><td className="font-medium">{i.value} {i.unit}</td><td className="text-muted">{i.formula}</td><td className="text-muted text-xs">{i.source}</td></tr>)}</tbody></table>}
          <div className="label">Recommandations</div><ul className="list-disc pl-5 text-sm space-y-1">{feas.recommendations.map((x: string) => <li key={x}>{x}</li>)}</ul>
        </Card>
      )}
      {a.rules?.ai_summary && <Card title={<span className="flex items-center gap-2"><Sparkles size={15} className="text-sage" />Analyse rédigée par l'assistant (à vérifier)</span>}><Markdown text={a.rules.ai_summary} /></Card>}
      {a.rules?.ai_summary_unavailable && <Notice tone="warn">{a.rules.ai_summary_unavailable}</Notice>}
      <Card title="Sources consultées">
        <ul className="text-xs space-y-1">{(a.sources || []).map((s: any, i: number) => <li key={i}><b>{s.source}</b> · consulté le {dateTimeFr(s.consulted_at)} {s.url && <span className="text-muted break-all">· {s.url}</span>}</li>)}</ul>
      </Card>
    </div>
  );
}

export default function Urbanisme() {
  const { perms, projectId, toastError } = useApp();
  const [qt, setQt] = useState("adresse");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [sel, setSel] = useState<string | null>(null);
  const list = useApi<any[]>(`/api/urbanisme/analyses${projectId ? `?project_id=${projectId}` : ""}`);
  const lf = useApi<any>("/api/settings/urbanisme");
  const [lq, setLq] = useState("");
  const [lres, setLres] = useState<any>(null);
  useEffect(() => { if (!sel && list.data?.length) setSel(list.data[0].id); }, [list.data, sel]);
  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try { const r = await api.call("POST", "/api/urbanisme/analyses", { query_type: qt, query: q, project_id: projectId }); list.reload(); setSel(r.id); } catch (e) { toastError(e); } finally { setBusy(false); }
  };
  const placeholder = { adresse: "12 rue des Ateliers, 44000 Nantes", cadastre: "44109 AB 0123 (INSEE + section + numéro)", coordonnees: "47.2184, -1.5536 (latitude, longitude)" }[qt];
  return (
    <div>
      <PageHeader title="Urbanisme et contraintes de site" icon={<MapIcon size={22} />} subtitle="Sources officielles : Géoportail de l'Urbanisme, API Carto IGN (cadastre), Géorisques, Base Adresse Nationale, Légifrance." />
      {lf.data?.demo && <div className="mb-4"><Notice tone="warn">Mode démonstration actif : les recherches renvoient des données fictives.</Notice></div>}
      {perms.write && (
        <Card className="mb-6">
          <form onSubmit={run} className="grid sm:grid-cols-[180px_1fr_auto] gap-3 items-end pt-3">
            <Field label="Rechercher par"><Select value={qt} onChange={setQt} options={[{ value: "adresse", label: "Adresse" }, { value: "cadastre", label: "Référence cadastrale" }, { value: "coordonnees", label: "Coordonnées GPS" }]} /></Field>
            <Field label="Terrain"><input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} required /></Field>
            <button className="btn-primary" disabled={busy}><Search size={15} /> {busy ? "Interrogation des services…" : "Analyser la parcelle"}</button>
          </form>
        </Card>
      )}
      <div className="grid xl:grid-cols-[260px_1fr] gap-6">
        <Card title="Analyses" pad={false}>
          {!list.data?.length ? <Empty title="Aucune analyse" /> : <ul className="divide-y divide-line">{list.data.map((a) => (
            <li key={a.id}><button onClick={() => setSel(a.id)} className={`w-full text-left px-4 py-2.5 text-sm hover:bg-sunken ${sel === a.id ? "bg-sunken" : ""}`}>
              <div className="font-medium truncate">{a.label || a.query}</div><div className="text-xs text-muted">{dateFr(a.created_at)}{a.mode === "demo" ? " · démo" : ""}</div></button></li>))}</ul>}
        </Card>
        <div>{sel ? <AnalysisView key={sel} id={sel} onDeleted={() => { setSel(null); list.reload(); }} /> : <Empty title="Lancez une recherche">Indiquez une adresse, une référence cadastrale ou des coordonnées.</Empty>}</div>
      </div>
      <div className="mt-6">
        <Card title="Légifrance – code de l'urbanisme">
          {!lf.data?.legifrance_client_secret_set ? <div className="text-sm text-muted">Connecteur Légifrance non configuré : renseignez vos identifiants de l'API PISTE (DILA) dans Paramètres › Urbanisme pour rechercher les articles du code de l'urbanisme.</div> : (
            <>
              <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); try { setLres(await api.get(`/api/urbanisme/legifrance?q=${encodeURIComponent(lq)}`)); } catch (err) { toastError(err); } }}>
                <input className="input" value={lq} onChange={(e) => setLq(e.target.value)} placeholder="ex. emprise au sol, règlement national d'urbanisme, R111-2" /><button className="btn-primary">Rechercher</button></form>
              {lres && <ul className="mt-3 space-y-2">{lres.results.map((x: any) => <li key={x.id} className="text-sm"><b>Article {x.num}</b> {x.url && <a className="text-sage text-xs" href={x.url} target="_blank" rel="noreferrer">Légifrance</a>}<div className="text-xs text-muted">{x.text}</div></li>)}</ul>}
            </>)}
        </Card>
      </div>
    </div>
  );
}

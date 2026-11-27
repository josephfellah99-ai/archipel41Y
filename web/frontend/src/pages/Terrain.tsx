import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { Map as MapIcon, Layers, Ruler, Square, MapPin, Search, Download, Printer, Eye, EyeOff, Trash2, Crosshair, Upload, Globe, Plus, Info } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUrl, download } from "../lib/api";
import { useApi, useApp, useEditable } from "../lib/app";
import { DOC_CATEGORIES, dateFr, num } from "../lib/format";
import { AsyncButton, Card, Empty, ErrorBox, Field, Notice, NumberInput, PageHeader, Select, Spinner, Tabs } from "../components/ui";
import { NeedProject } from "./Quotes";
import { StaleNotice } from "./Projects";
import Urbanisme from "./Urbanisme";

const R = 6371008.8;
const rad = (d: number) => (d * Math.PI) / 180;
export function lengthM(pts: [number, number][]) {
  let t = 0;
  for (let i = 1; i < pts.length; i++) {
    const [lo1, la1] = pts[i - 1], [lo2, la2] = pts[i];
    const h = Math.sin(rad(la2 - la1) / 2) ** 2 + Math.cos(rad(la1)) * Math.cos(rad(la2)) * Math.sin(rad(lo2 - lo1) / 2) ** 2;
    t += 2 * R * Math.asin(Math.sqrt(h));
  }
  return t;
}
/** Aire géodésique (sphère) d'un anneau [lon, lat] — même formule que le serveur. */
export function areaM2(ring: [number, number][]) {
  if (ring.length < 3) return 0;
  let s = 0;
  for (let i = 0; i < ring.length; i++) {
    const [lo1, la1] = ring[i], [lo2, la2] = ring[(i + 1) % ring.length];
    s += rad(lo2 - lo1) * (2 + Math.sin(rad(la1)) + Math.sin(rad(la2)));
  }
  return Math.abs((s * R * R) / 2);
}
/** Les fournisseurs de tuiles (OpenStreetMap notamment) exigent l'origine de la requête. */
const TILE_OPTS: any = { referrerPolicy: "strict-origin-when-cross-origin" };
const fmtLen = (m: number) => (m >= 1000 ? `${num(m / 1000, 3)} km` : `${num(m, 1)} m`);
const fmtArea = (m2: number) => (m2 >= 10000 ? `${num(m2, 0)} m² (${num(m2 / 10000, 4)} ha)` : `${num(m2, 1)} m²`);

type Tool = "none" | "distance" | "area" | "point" | "line" | "polygon" | "parcel";

function MapView({ project, layers, onChanged }: { project: any; layers: any[]; onChanged: () => void }) {
  const { perms, toast, toastError } = useApp();
  const bm = useApi<any>("/api/geo/basemaps");
  const div = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const base = useRef<L.TileLayer | null>(null);
  const groups = useRef<Record<string, L.Layer>>({});
  const draw = useRef<{ pts: L.LatLng[]; shape: L.Layer | null }>({ pts: [], shape: null });
  const [baseId, setBaseId] = useState("ign_plan");
  const [cadastre, setCadastre] = useState(false);
  const [tool, setTool] = useState<Tool>("none");
  const [measure, setMeasure] = useState<string | null>(null);
  const [parcel, setParcel] = useState<any>(null);
  const toolRef = useRef<Tool>("none");
  toolRef.current = tool;
  const ann = layers.find((l) => l.kind === "annotations");

  // création de la carte
  useEffect(() => {
    if (!div.current || map.current) return;
    const m = L.map(div.current, { zoomControl: true, preferCanvas: true, attributionControl: true }).setView(
      project.latitude && project.longitude ? [project.latitude, project.longitude] : [46.6, 2.4], project.latitude ? 17 : 6);
    L.control.scale({ imperial: false }).addTo(m);
    m.on("moveend", () => { try { const b = m.getBounds(); sessionStorage.setItem("a41.mapbounds", JSON.stringify([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()])); } catch { /* */ } });
    map.current = m;
    setTimeout(() => m.invalidateSize(), 50);
    return () => { m.remove(); map.current = null; };
  }, [project.id]);

  // fond de carte
  useEffect(() => {
    const m = map.current;
    if (!m || !bm.data) return;
    base.current?.remove();
    const b = bm.data.basemaps.find((x: any) => x.id === baseId) || bm.data.basemaps[0];
    base.current = L.tileLayer(b.url, { ...TILE_OPTS, attribution: b.attribution, maxZoom: 22, maxNativeZoom: b.max_zoom }).addTo(m);
    base.current.bringToBack();
  }, [bm.data, baseId]);

  // parcelles cadastrales (indicatif)
  useEffect(() => {
    const m = map.current;
    if (!m || !bm.data) return;
    groups.current.__cad?.remove();
    delete groups.current.__cad;
    if (cadastre) {
      const o = bm.data.overlays[0];
      groups.current.__cad = L.tileLayer(o.url, { ...TILE_OPTS, attribution: o.attribution, opacity: o.opacity, maxZoom: 22, maxNativeZoom: o.max_zoom }).addTo(m);
    }
  }, [bm.data, cadastre]);

  // couches du projet
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    Object.entries(groups.current).forEach(([k, g]) => { if (!k.startsWith("__")) { g.remove(); delete groups.current[k]; } });
    for (const l of layers) {
      if (!l.visible) continue;
      let g: L.Layer | null = null;
      if ((l.kind === "vector" || l.kind === "wfs" || l.kind === "annotations") && l.data) {
        const st = l.style || {};
        g = L.geoJSON(l.data, {
          style: () => ({ color: st.color || "#253A33", weight: st.weight || 2, fillOpacity: st.fillOpacity ?? 0.15 }),
          pointToLayer: (_f, ll) => L.circleMarker(ll, { radius: l.kind === "annotations" ? 7 : 4, color: st.color || "#253A33", weight: 2, fillOpacity: 0.8 }),
          onEachFeature: (f, lay) => {
            const p = f.properties || {};
            const rows = Object.entries(p).filter(([, v]) => v !== null && v !== "" && typeof v !== "object").slice(0, 12)
              .map(([k, v]) => `<tr><td style="color:#718578;padding-right:8px">${String(k).replace(/</g, "&lt;")}</td><td>${String(v).replace(/</g, "&lt;")}</td></tr>`).join("");
            lay.bindPopup(`<div style="font:12px Inter,sans-serif"><b>${String(p.label || p.name || p.nom || l.name).replace(/</g, "&lt;")}</b><table>${rows}</table></div>`);
          },
        });
      } else if (l.kind === "image" && l.image?.bounds) {
        const [w, s, e, n] = l.image.bounds;
        g = L.imageOverlay(apiUrl(`/api/geo/layers/${l.id}/image`, true), [[s, w], [n, e]], { opacity: l.image.opacity ?? 0.75 });
      } else if (l.kind === "wms" && l.service) {
        g = L.tileLayer.wms(l.service.url, { ...TILE_OPTS, layers: l.service.layers, format: l.service.format || "image/png", transparent: true, opacity: l.service.opacity ?? 0.8, attribution: l.service.attribution || "" });
      } else if (l.kind === "wmts" && l.service) {
        g = L.tileLayer(l.service.url, { ...TILE_OPTS, opacity: l.service.opacity ?? 0.8, attribution: l.service.attribution || "" });
      }
      if (g) { g.addTo(m); groups.current[l.id] = g; }
    }
  }, [layers]);

  // repère du projet
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    groups.current.__proj?.remove();
    if (project.latitude && project.longitude) {
      groups.current.__proj = L.circleMarker([project.latitude, project.longitude], { radius: 8, color: "#fff", weight: 2, fillColor: "#253A33", fillOpacity: 1 })
        .bindTooltip(`${project.code} – ${project.name}`).addTo(m);
    }
  }, [project.latitude, project.longitude]);

  const resetDraw = () => { draw.current.shape?.remove(); draw.current = { pts: [], shape: null }; setMeasure(null); };

  const saveAnnotation = async (geometry: any, extra: any = {}) => {
    try {
      const layer = ann || (await api.call("POST", `/api/projects/${project.id}/geo/annotations`));
      const label = window.prompt("Intitulé du repère ou de l'observation :", extra.label || "");
      if (label === null) return;
      const note = window.prompt("Observation (facultatif) :", "") || "";
      const fc = layer.data || { type: "FeatureCollection", features: [] };
      fc.features = [...(fc.features || []), { type: "Feature", geometry, properties: { label, note, auteur: "", date: new Date().toISOString().slice(0, 10), ...extra } }];
      await api.call("PUT", `/api/geo/layers/${layer.id}`, { data: fc, version: layer.version });
      toast("Annotation enregistrée.");
      onChanged();
    } catch (e) { toastError(e); }
  };

  // interactions selon l'outil
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const click = async (ev: L.LeafletMouseEvent) => {
      const t = toolRef.current;
      if (t === "none") return;
      if (t === "parcel") {
        setParcel({ loading: true });
        try { setParcel(await api.get(`/api/geo/parcel?lat=${ev.latlng.lat}&lon=${ev.latlng.lng}`)); } catch (e: any) { setParcel({ found: false, reason: e.message }); }
        return;
      }
      if (t === "point") { await saveAnnotation({ type: "Point", coordinates: [ev.latlng.lng, ev.latlng.lat] }); return; }
      draw.current.pts.push(ev.latlng);
      draw.current.shape?.remove();
      const pts = draw.current.pts;
      const ll = pts.map((p) => [p.lng, p.lat] as [number, number]);
      if (t === "distance" || t === "line") {
        draw.current.shape = L.polyline(pts, { color: "#9C3B29", weight: 3, dashArray: t === "distance" ? "6 4" : undefined }).addTo(m);
        setMeasure(`Longueur : ${fmtLen(lengthM(ll))}`);
      } else {
        draw.current.shape = L.polygon(pts, { color: "#9C3B29", weight: 2, fillOpacity: 0.15 }).addTo(m);
        setMeasure(`Surface : ${fmtArea(areaM2(ll))} · périmètre ${fmtLen(lengthM([...ll, ll[0]]))}`);
      }
    };
    const dbl = async () => {
      const t = toolRef.current;
      const ll = draw.current.pts.map((p) => [p.lng, p.lat] as [number, number]);
      if (t === "line" && ll.length >= 2) await saveAnnotation({ type: "LineString", coordinates: ll }, { longueur_m: Math.round(lengthM(ll) * 10) / 10 });
      if (t === "polygon" && ll.length >= 3) await saveAnnotation({ type: "Polygon", coordinates: [[...ll, ll[0]]] }, { surface_m2: Math.round(areaM2(ll)) });
      if (t === "line" || t === "polygon") resetDraw();
    };
    m.on("click", click);
    m.on("dblclick", dbl);
    if (tool !== "none") m.doubleClickZoom.disable(); else m.doubleClickZoom.enable();
    div.current?.style.setProperty("cursor", tool === "none" ? "" : "crosshair");
    return () => { m.off("click", click); m.off("dblclick", dbl); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool, ann?.id, ann?.version]);

  const fitAll = () => {
    const m = map.current;
    if (!m) return;
    const b = L.latLngBounds([]);
    layers.forEach((l) => { if (l.bounds) b.extend([[l.bounds[1], l.bounds[0]], [l.bounds[3], l.bounds[2]]]); });
    if (project.latitude) b.extend([project.latitude, project.longitude]);
    if (b.isValid()) m.fitBounds(b.pad(0.15)); else toast("Aucune donnée localisée pour ce projet.", "info");
  };
  useEffect(() => { if (layers.length) setTimeout(fitAll, 100); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [layers.length]);
  const pick = (t: Tool) => { resetDraw(); setParcel(null); setTool(tool === t ? "none" : t); };
  const TOOLS: { id: Tool; label: string; icon: any; write?: boolean }[] = [
    { id: "distance", label: "Mesurer une distance", icon: Ruler }, { id: "area", label: "Mesurer une surface", icon: Square },
    { id: "parcel", label: "Identifier la parcelle", icon: Search }, { id: "point", label: "Ajouter un repère", icon: MapPin, write: true },
    { id: "line", label: "Tracer une ligne annotée", icon: Ruler, write: true }, { id: "polygon", label: "Tracer une zone annotée", icon: Square, write: true },
  ];
  const HELP: Record<Tool, string> = {
    none: "", distance: "Cliquez les points successifs ; la longueur cumulée s'affiche.", area: "Cliquez les sommets de la zone ; surface et périmètre s'affichent.",
    parcel: "Cliquez sur la carte pour identifier la parcelle cadastrale (service IGN, connexion requise).", point: "Cliquez à l'endroit du repère, puis saisissez son intitulé.",
    line: "Cliquez les points, double-cliquez pour terminer et enregistrer.", polygon: "Cliquez les sommets, double-cliquez pour terminer et enregistrer.",
  };
  return (
    <div className="grid xl:grid-cols-[1fr_300px] gap-4">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-1.5 no-print">
          {TOOLS.filter((t) => !t.write || perms.write).map((t) => (
            <button key={t.id} onClick={() => pick(t.id)} title={t.label} aria-pressed={tool === t.id}
              className={`btn-secondary py-1 px-2 ${tool === t.id ? "!bg-forest !text-white" : ""}`}><t.icon size={14} /> <span className="hidden md:inline">{t.label}</span></button>))}
          <span className="flex-1" />
          <button className="btn-secondary py-1 px-2" onClick={fitAll} title="Cadrer sur le projet"><Crosshair size={14} /></button>
          <button className="btn-secondary py-1 px-2" onClick={() => download(`/api/projects/${project.id}/geo/export?fmt=geojson`).catch(toastError)} title="Exporter (GeoJSON)"><Download size={14} /> GeoJSON</button>
          <button className="btn-secondary py-1 px-2" onClick={() => download(`/api/projects/${project.id}/geo/export?fmt=kml`).catch(toastError)} title="Exporter (KML, Google Earth)"><Download size={14} /> KML</button>
          <button className="btn-secondary py-1 px-2" onClick={() => window.print()} title="Imprimer la carte"><Printer size={14} /></button>
        </div>
        {(tool !== "none" || measure) && <div className="text-xs bg-sunken rounded-md px-3 py-1.5 flex items-center gap-2 no-print"><Info size={13} />{HELP[tool]} {measure && <b className="text-ink">{measure}</b>}
          {measure && <button className="underline ml-auto" onClick={resetDraw}>Effacer</button>}</div>}
        <div ref={div} className="h-[64vh] min-h-[380px] w-full border border-line rounded-lg print:h-[180mm]" aria-label="Carte du terrain" role="application" />
        <div className="text-[11px] text-muted">{bm.data?.notice}</div>
      </div>
      <div className="space-y-4 no-print">
        <Card title="Fond de carte">
          {bm.data?.basemaps.map((b: any) => <label key={b.id} className="flex items-center gap-2 text-sm py-0.5"><input type="radio" name="fond" checked={baseId === b.id} onChange={() => setBaseId(b.id)} />{b.label}</label>)}
          <label className="flex items-center gap-2 text-sm pt-2 mt-2 border-t border-line"><input type="checkbox" checked={cadastre} onChange={(e) => setCadastre(e.target.checked)} />Parcelles cadastrales (indicatif)</label>
          <p className="text-[11px] text-muted mt-2">Fonds en ligne (IGN, OpenStreetMap) : sans connexion, seules vos couches restent affichées.</p>
        </Card>
        <Card title={`Couches du projet (${layers.length})`}>
          {!layers.length ? <div className="text-sm text-muted">Aucune couche : importez des données dans l'onglet « Couches et imports ».</div> : (
            <ul className="space-y-1.5">{layers.map((l) => (
              <li key={l.id} className="flex items-center gap-2 text-sm">
                <button className="btn-ghost p-1" aria-label={l.visible ? "Masquer" : "Afficher"} onClick={async () => { try { await api.call("PUT", `/api/geo/layers/${l.id}`, { visible: !l.visible }); onChanged(); } catch (e) { toastError(e); } }}>
                  {l.visible ? <Eye size={14} /> : <EyeOff size={14} className="text-muted" />}</button>
                <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: l.style?.color || "#718578" }} />
                <span className={`flex-1 truncate ${l.visible ? "" : "text-muted"}`} title={l.notes || ""}>{l.name}</span>
                <span className="text-[10px] text-muted">{l.kind === "image" ? "image" : l.kind === "wms" || l.kind === "wmts" ? l.kind.toUpperCase() : `${l.feature_count}`}</span>
                <button className="btn-ghost p-1" aria-label="Cadrer" onClick={() => l.bounds && map.current?.fitBounds([[l.bounds[1], l.bounds[0]], [l.bounds[3], l.bounds[2]]], { padding: [30, 30] })}><Crosshair size={13} /></button>
              </li>))}</ul>)}
        </Card>
        {parcel && <Card title="Parcelle identifiée">{parcel.loading ? <Spinner /> : parcel.found ? (
          <div className="text-sm space-y-1"><div><b>{parcel.reference}</b> — {parcel.commune}</div>
            <div>Contenance cadastrale : {parcel.contenance_m2 ? `${num(parcel.contenance_m2, 0)} m²` : "—"}</div>
            {parcel.surface_calculee_m2 && <div className="text-muted text-xs">Surface calculée sur le tracé : {num(parcel.surface_calculee_m2, 0)} m²</div>}
            <Notice tone="warn">{parcel.notice}</Notice></div>
        ) : <div className="text-sm text-muted">{parcel.reason}</div>}</Card>}
      </div>
    </div>
  );
}

const LIMITS: Record<string, string> = { inconnues: "Non connues", cadastre: "Plan cadastral uniquement (indicatif)", bornage: "Bornage réalisé par un géomètre-expert", releve: "Relevé de géomètre (non contradictoire)" };

function TerrainSheet({ project, onSaved }: { project: any; onSaved: () => void }) {
  const { perms, toast, toastError } = useApp();
  const docs = useApi<any[]>(`/api/documents?project_id=${project.id}`);
  const ed = useEditable(project, (p: any) => ({ terrain: { ...(p.terrain || {}) }, latitude: p.latitude ?? "", longitude: p.longitude ?? "", address: p.address || "", postal_code: p.postal_code || "", city: p.city || "" }));
  const v = ed.value!;
  const t = v.terrain;
  const set = (k: string, val: any) => ed.setValue((prev) => ({ ...prev, terrain: { ...prev.terrain, [k]: val } }));
  const can = perms.write;
  const save = async () => {
    try {
      const { toNum } = await import("../lib/format");
      await api.put(`/api/projects/${project.id}`, { terrain: { ...t, superficie_m2: t.superficie_m2 === "" ? null : t.superficie_m2 }, latitude: toNum(v.latitude, "Latitude"), longitude: toNum(v.longitude, "Longitude"),
        address: v.address || null, postal_code: v.postal_code || null, city: v.city || null, version: project.version });
      ed.markSaved(); toast("Fiche terrain enregistrée."); onSaved();
    } catch (e: any) { toastError(e); }
  };
  const txt = (k: string, label: string, rows = 2, hint?: string) => (
    <Field label={label} hint={hint}><textarea className="input" rows={rows} disabled={!can} value={t[k] ?? ""} onChange={(e) => set(k, e.target.value)} /></Field>);
  const urbaDocs = (docs.data || []).filter((d) => d.category === "urbanisme");
  const photos = (docs.data || []).filter((d) => d.category === "photo");
  return (
    <div className="space-y-6">
      <StaleNotice stale={ed.stale} onDiscard={ed.discard} />
      <div className="grid lg:grid-cols-2 gap-6">
        <Card title="Identification">
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Adresse" className="sm:col-span-2"><input className="input" disabled={!can} value={v.address} onChange={(e) => ed.setValue((p) => ({ ...p, address: e.target.value }))} /></Field>
            <Field label="Code postal"><input className="input" disabled={!can} value={v.postal_code} onChange={(e) => ed.setValue((p) => ({ ...p, postal_code: e.target.value }))} /></Field>
            <Field label="Commune"><input className="input" disabled={!can} value={v.city} onChange={(e) => ed.setValue((p) => ({ ...p, city: e.target.value }))} /></Field>
            <Field label="Références cadastrales" hint="Ex. 44109 AB 142, AB 143"><input className="input" disabled={!can} value={t.parcelle ?? ""} onChange={(e) => set("parcelle", e.target.value)} /></Field>
            <Field label="Superficie du terrain (m²)"><NumberInput disabled={!can} min={0} suffix="m²" value={t.superficie_m2 ?? t.surface_cadastrale_m2 ?? ""} onChange={(x) => set("superficie_m2", x)} /></Field>
            <Field label="Latitude (WGS84)"><NumberInput disabled={!can} min={-90} max={90} value={v.latitude} onChange={(x) => ed.setValue((p) => ({ ...p, latitude: x }))} /></Field>
            <Field label="Longitude (WGS84)"><NumberInput disabled={!can} min={-180} max={180} value={v.longitude} onChange={(x) => ed.setValue((p) => ({ ...p, longitude: x }))} /></Field>
            <Field label="Zone du PLU"><input className="input" disabled={!can} value={t.zone_plu ?? ""} onChange={(e) => set("zone_plu", e.target.value)} /></Field>
            <Field label="Orientation" hint="Ex. façade principale au sud-ouest"><input className="input" disabled={!can} value={t.orientation ?? ""} onChange={(e) => set("orientation", e.target.value)} /></Field>
          </div>
        </Card>
        <Card title="Limites de propriété">
          <Field label="Origine des limites connues"><Select disabled={!can} value={t.limites_origine || "inconnues"} onChange={(x) => set("limites_origine", x)} options={Object.entries(LIMITS).map(([k, l]) => ({ value: k, label: l }))} /></Field>
          <div className="mt-3">{txt("limites", "Description des limites", 3, "Clôtures, murs mitoyens, bornes retrouvées, références du procès-verbal de bornage…")}</div>
          <div className="mt-3"><Notice tone={t.limites_origine === "bornage" ? "info" : "warn"}>{t.limites_origine === "bornage"
            ? "Limites issues d'un bornage contradictoire : joignez le procès-verbal dans les documents du projet."
            : "Le tracé cadastral est indicatif et ne vaut pas bornage. Pour une implantation en limite, faites établir un bornage par un géomètre-expert."}</Notice></div>
        </Card>
      </div>
      <Card title="Caractéristiques du site">
        <div className="grid md:grid-cols-2 gap-3">
          {txt("topographie", "Topographie", 2, "Pente, dénivelé, points hauts et bas, talus")}
          {txt("nature_sol", "Nature du sol / géotechnique", 2, "Étude G1/G2, portance, présence d'eau")}
          {txt("acces", "Accès", 2, "Accès véhicules et piétons, largeur, servitudes de passage")}
          {txt("voiries", "Voiries et réseaux", 2, "Voies desservantes ; réseaux : eau, assainissement, électricité, gaz, télécom")}
          {txt("environnement", "Environnement immédiat", 2, "Voisinage, vues, nuisances, végétation remarquable")}
          {txt("servitudes", "Servitudes connues", 2, "Servitudes de droit privé ou d'utilité publique (SUP)")}
          {txt("notes", "Observations", 3)}
        </div>
      </Card>
      <div className="grid lg:grid-cols-2 gap-6">
        <Card title={`Documents d'urbanisme (${urbaDocs.length})`}>{!urbaDocs.length ? <div className="text-sm text-muted">Importez le règlement et les extraits du PLU dans Documents (catégorie « Urbanisme »).</div>
          : <ul className="text-sm space-y-1">{urbaDocs.map((d) => <li key={d.id}><Link className="hover:text-sage" to={`/documents?doc=${d.id}`}>{d.name}</Link> <span className="text-xs text-muted">· {dateFr(d.updated_at)}</span></li>)}</ul>}</Card>
        <Card title={`Photographies du site (${photos.length})`}>{!photos.length ? <div className="text-sm text-muted">Importez les photos dans Documents (catégorie « {DOC_CATEGORIES.photo} »).</div>
          : <div className="grid grid-cols-3 gap-2">{photos.slice(0, 9).map((d) => <Link key={d.id} to={`/documents?doc=${d.id}`}><img className="aspect-square object-cover w-full border border-line" alt={d.name} loading="lazy" src={apiUrl(`/api/documents/${d.id}/download?inline=true`, true)} /></Link>)}</div>}</Card>
      </div>
      {can && <div className="flex justify-end"><AsyncButton onClick={save}>Enregistrer la fiche terrain</AsyncButton></div>}
    </div>
  );
}

function Imports({ project, layers, onChanged }: { project: any; layers: any[]; onChanged: () => void }) {
  const { perms, toast, toastError } = useApp();
  const bm = useApi<any>("/api/geo/basemaps");
  const [epsg, setEpsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<any>(null);
  const [svc, setSvc] = useState({ kind: "wms", url: "", layers: "", name: "" });
  const fileRef = useRef<HTMLInputElement>(null);
  const placeRef = useRef<HTMLInputElement>(null);
  const [bounds, setBounds] = useState<string[]>(["", "", "", ""]);
  const send = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true);
    try {
      const fd = new FormData();
      Array.from(files).forEach((f) => fd.append("files", f));
      if (epsg) fd.append("epsg", epsg);
      const r = await api.upload(`/api/projects/${project.id}/geo/import`, fd);
      setLast(r); toast(`Couche « ${r.name} » importée (${r.format}).`); onChanged();
    } catch (e) { toastError(e); } finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  const useView = () => { try { const b = JSON.parse(sessionStorage.getItem("a41.mapbounds") || "null"); if (b) setBounds(b.map((x: number) => String(Math.round(x * 1e6) / 1e6))); else toast("Ouvrez d'abord l'onglet Carte et cadrez la zone.", "info"); } catch { /* */ } };
  const place = async () => {
    const f = placeRef.current?.files?.[0];
    if (!f) return toast("Choisissez le plan (PDF ou image).", "info");
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("bounds", JSON.stringify(bounds.map(Number)));
      const r = await api.upload(`/api/projects/${project.id}/geo/place-image`, fd);
      toast(`Plan « ${r.name} » positionné.`); onChanged();
    } catch (e) { toastError(e); }
  };
  return (
    <div className="space-y-6">
      {perms.write && <div className="grid lg:grid-cols-2 gap-6">
        <Card title="Importer des données géographiques">
          <p className="text-sm text-muted mb-3">GeoJSON, KML / KMZ, GPX, Shapefile (archive ZIP ou fichiers .shp, .shx, .dbf, .prj ensemble), GeoPackage, DXF (plan topographique, relevé de géomètre),
            GeoTIFF ou image + fichier de calage (.jgw, .pgw, .tfw) pour les orthophotos, MNT au format ESRI ASCII (.asc). Les coordonnées Lambert-93, CC42 à CC50, Lambert II étendu et UTM sont converties automatiquement.</p>
          <Field label="Système de coordonnées" hint="Laissez « automatique » : il est lu dans le fichier ou déduit des valeurs (vous en êtes informé)."><Select value={epsg} onChange={setEpsg} placeholder="Automatique"
            options={(bm.data?.crs || []).map((c: any) => ({ value: String(c.epsg), label: `${c.label} (EPSG:${c.epsg})` }))} /></Field>
          <input ref={fileRef} type="file" multiple className="hidden" onChange={(e) => send(e.target.files)} aria-label="Fichiers géographiques" />
          <button className="btn-primary mt-3" disabled={busy} onClick={() => fileRef.current?.click()}><Upload size={15} /> {busy ? "Import en cours…" : "Choisir les fichiers"}</button>
          {last && <div className="mt-3 text-sm space-y-1"><div><b>{last.name}</b> — {last.format}, {last.kind === "image" ? "image" : `${last.feature_count} objet(s)`}</div>
            <div className="text-xs text-muted">{last.crs_note}</div>
            {Object.keys(last.stats || {}).length > 0 && <div className="text-xs">{Object.entries(last.stats).map(([k, v]) => `${k.replace(/_/g, " ")} : ${Array.isArray(v) ? v.join(", ") : v}`).join(" · ")}</div>}
            {last.warnings?.map((w: string, i: number) => <div key={i} className="text-xs text-warn">⚠ {w}</div>)}</div>}
        </Card>
        <Card title="Ajouter un service cartographique">
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Type"><Select value={svc.kind} onChange={(k) => setSvc({ ...svc, kind: k })} options={[{ value: "wms", label: "WMS (images)" }, { value: "wmts", label: "WMTS (tuiles, modèle d'URL)" }, { value: "wfs", label: "WFS (objets)" }]} /></Field>
            <Field label="Nom affiché"><input className="input" value={svc.name} onChange={(e) => setSvc({ ...svc, name: e.target.value })} /></Field>
            <Field label="Adresse du service" className="sm:col-span-2" hint={svc.kind === "wmts" ? "Modèle avec {z}, {x}, {y}" : "Ex. https://data.geopf.fr/wms-r/wms"}><input className="input" value={svc.url} onChange={(e) => setSvc({ ...svc, url: e.target.value })} /></Field>
            {svc.kind !== "wmts" && <Field label={svc.kind === "wfs" ? "Nom de la couche (typeName)" : "Couche(s)"} className="sm:col-span-2"><input className="input" value={svc.layers} onChange={(e) => setSvc({ ...svc, layers: e.target.value })} /></Field>}
          </div>
          <AsyncButton className="btn-secondary mt-3" disabled={!svc.url} onClick={async () => { try { await api.call("POST", `/api/projects/${project.id}/geo/service`, svc); toast("Service ajouté."); setSvc({ kind: svc.kind, url: "", layers: "", name: "" }); onChanged(); } catch (e) { toastError(e); } }}>
            <Globe size={14} /> Ajouter</AsyncButton>
          <p className="text-[11px] text-muted mt-2">Respectez les conditions d'utilisation et les licences des services ajoutés.</p>
        </Card>
        <Card title="Positionner un plan non géoréférencé">
          <p className="text-sm text-muted mb-3">Plan cadastral PDF, plan de masse, image : indiquez son emprise (ouest, sud, est, nord en degrés) ou reprenez celle de la carte. Précision limitée : à vérifier visuellement.</p>
          <input ref={placeRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="text-sm" aria-label="Plan à positionner" />
          <div className="grid grid-cols-4 gap-2 mt-2">{["Ouest", "Sud", "Est", "Nord"].map((l, i) => <Field key={l} label={l}><input className="input py-1" value={bounds[i]} onChange={(e) => setBounds(bounds.map((b, j) => (j === i ? e.target.value : b)))} /></Field>)}</div>
          <div className="flex gap-2 mt-3"><button className="btn-secondary" onClick={useView}>Emprise de la carte</button><AsyncButton className="btn-secondary" onClick={place}>Positionner</AsyncButton></div>
        </Card>
      </div>}
      <Card title={`Couches (${layers.length})`} pad={false}>{!layers.length ? <Empty title="Aucune couche" icon={<Layers size={18} />} /> : (
        <div className="overflow-x-auto"><table className="table text-sm">
          <thead><tr><th>Couche</th><th>Format</th><th>Objets</th><th>Système source</th><th>Remarques</th><th /></tr></thead>
          <tbody>{layers.map((l) => (
            <tr key={l.id}><td className="font-medium">{l.name}</td><td>{l.source_format || l.kind}</td><td>{l.kind === "image" ? "image" : l.feature_count || "—"}</td>
              <td className="text-xs text-muted">{l.crs_source || "—"}</td><td className="text-xs text-muted max-w-[360px] whitespace-pre-line">{l.notes || ""}</td>
              <td>{perms.write && <button className="btn-ghost text-danger p-1" aria-label="Supprimer la couche" onClick={async () => { if (!window.confirm(`Supprimer la couche « ${l.name} » ?`)) return; try { await api.call("DELETE", `/api/geo/layers/${l.id}`); onChanged(); } catch (e) { toastError(e); } }}><Trash2 size={14} /></button>}</td></tr>))}</tbody></table></div>)}
      </Card>
    </div>
  );
}

export default function TerrainPage() {
  const { projectId } = useApp();
  const [tab, setTab] = useState("carte");
  const p = useApi<any>(projectId ? `/api/projects/${projectId}` : null);
  const layers = useApi<any[]>(projectId ? `/api/projects/${projectId}/geo/layers` : null);
  const sorted = useMemo(() => [...(layers.data || [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)), [layers.data]);
  return (
    <div>
      <PageHeader title="Terrain et cartographie" icon={<MapIcon size={22} />} subtitle="Carte interactive, données cadastrales et géographiques, fiche terrain et analyse urbanistique du projet." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "carte", label: "Carte" }, { id: "fiche", label: "Fiche terrain" }, { id: "couches", label: "Couches et imports" }, { id: "urbanisme", label: "Analyse urbanistique" }]} />
      {tab === "urbanisme" ? <Urbanisme /> : !projectId ? <NeedProject what="Le terrain" /> : p.loading && !p.data ? <Spinner /> : !p.data ? <ErrorBox error={p.error} /> : (
        <>
          {tab === "carte" && <MapView project={p.data} layers={sorted} onChanged={layers.reload} />}
          {tab === "fiche" && <TerrainSheet project={p.data} onSaved={p.reload} />}
          {tab === "couches" && <Imports project={p.data} layers={sorted} onChanged={layers.reload} />}
        </>)}
    </div>
  );
}

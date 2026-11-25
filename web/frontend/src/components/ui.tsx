import { X, Loader2, Inbox } from "lucide-react";
import { Fragment, useEffect, useState, type ReactNode } from "react";

export function PageHeader({ title, subtitle, actions, icon }: { title: string; subtitle?: ReactNode; actions?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between mb-6">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-forest">{icon}<h1 className="text-2xl font-semibold tracking-tight text-ink truncate">{title}</h1></div>
        {subtitle && <div className="text-sm text-muted mt-1">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, actions, children, className = "", pad = true }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 px-5 pt-4 pb-2">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <div className="flex gap-2">{actions}</div>
        </header>
      )}
      <div className={pad ? "px-5 pb-5 pt-1" : ""}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, icon, tone = "forest" }: { label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode; tone?: string }) {
  return (
    <div className="card p-4 flex items-start gap-3">
      {icon && <div className={`rounded-lg p-2 bg-${tone}/10 text-${tone}`}>{icon}</div>}
      <div className="min-w-0">
        <div className="text-xs text-muted">{label}</div>
        <div className="text-2xl font-semibold tracking-tight mt-0.5">{value}</div>
        {hint && <div className="text-xs text-muted mt-0.5">{hint}</div>}
      </div>
    </div>
  );
}

export function Field({ label, children, hint, className = "" }: { label: string; children: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="label">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted mt-1">{hint}</span>}
    </label>
  );
}

export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: "ok" | "danger" | "warn" | "info" | "muted" | "forest" | "sage" }) {
  return <span className={`chip bg-${tone}/12 text-${tone} ${tone === "muted" ? "bg-sunken" : ""}`} style={{ backgroundColor: undefined }}>{children}</span>;
}

export function Spinner({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted p-6 justify-center">
      <Loader2 className="animate-spin" size={16} /> {label}
    </div>
  );
}

export function Empty({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="text-center py-10 px-4">
      <div className="mx-auto w-11 h-11 rounded-full bg-sunken flex items-center justify-center text-muted mb-3">{icon || <Inbox size={20} />}</div>
      <div className="font-medium">{title}</div>
      {children && <div className="text-sm text-muted mt-1 max-w-md mx-auto">{children}</div>}
    </div>
  );
}

export function ErrorBox({ error }: { error: string | null }) {
  if (!error) return null;
  return <div className="rounded-lg border border-danger/30 bg-danger/10 text-danger text-sm px-4 py-3 my-3">{error}</div>;
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" | "danger" | "ok" }) {
  return <div className={`rounded-lg border border-${tone}/30 bg-${tone}/10 text-sm px-4 py-3`}>{children}</div>;
}

export function Modal({ open, onClose, title, children, footer, wide = false }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title}
        className={`card w-full ${wide ? "sm:max-w-4xl" : "sm:max-w-xl"} max-h-[92vh] flex flex-col rounded-b-none sm:rounded-xl`}
        onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <h2 className="font-semibold">{title}</h2>
          <button className="btn-ghost p-1.5" onClick={onClose} aria-label="Fermer"><X size={18} /></button>
        </div>
        <div className="px-5 py-4 overflow-y-auto scrollbar-thin">{children}</div>
        {footer && <div className="px-5 py-3 border-t border-line flex justify-end gap-2 flex-wrap">{footer}</div>}
      </div>
    </div>
  );
}

export function Tabs({ tabs, value, onChange }: { tabs: { id: string; label: ReactNode }[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="flex gap-1 border-b border-line mb-5 overflow-x-auto scrollbar-thin" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={`px-3.5 py-2 text-sm whitespace-nowrap border-b-2 -mb-px transition ${value === t.id ? "border-forest text-forest font-medium" : "border-transparent text-muted hover:text-ink"}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Progress({ value, tone = "forest" }: { value: number; tone?: string }) {
  return (
    <div className="h-1.5 rounded-full bg-sunken overflow-hidden" aria-valuenow={value} role="progressbar">
      <div className={`h-full bg-${tone} rounded-full`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Confirm({ open, title, message, onConfirm, onClose, danger = true, confirmLabel = "Confirmer" }: {
  open: boolean; title: string; message: ReactNode; onConfirm: () => void; onClose: () => void; danger?: boolean; confirmLabel?: string;
}) {
  return (
    <Modal open={open} onClose={onClose} title={title}
      footer={<><button className="btn-secondary" onClick={onClose}>Annuler</button>
        <button className={danger ? "btn-danger" : "btn-primary"} onClick={() => { onConfirm(); onClose(); }}>{confirmLabel}</button></>}>
      <div className="text-sm">{message}</div>
    </Modal>
  );
}

/** Rendu Markdown minimal et sûr (aucun HTML interprété). */
export function Markdown({ text }: { text: string }) {
  const lines = (text || "").split("\n");
  const out: ReactNode[] = [];
  let list: string[] = [];
  const inline = (s: string, k: number) => {
    const parts = s.split(/(\*\*[^*]+\*\*|\[S\d+\]|_[^_]+_)/g);
    return parts.map((p, i) => {
      if (p.startsWith("**") && p.endsWith("**")) return <strong key={`${k}-${i}`}>{p.slice(2, -2)}</strong>;
      if (/^\[S\d+\]$/.test(p)) return <sup key={`${k}-${i}`} className="text-[10px] font-semibold text-sage ml-0.5">{p}</sup>;
      if (p.startsWith("_") && p.endsWith("_") && p.length > 2) return <em key={`${k}-${i}`} className="text-muted">{p.slice(1, -1)}</em>;
      return <Fragment key={`${k}-${i}`}>{p}</Fragment>;
    });
  };
  const flush = (k: number) => {
    if (list.length) {
      out.push(<ul key={`ul-${k}`}>{list.map((l, i) => <li key={i}>{inline(l, i)}</li>)}</ul>);
      list = [];
    }
  };
  lines.forEach((raw, i) => {
    const l = raw.trim();
    if (/^[-*•] /.test(l)) { list.push(l.slice(2)); return; }
    flush(i);
    if (!l) return;
    if (l === "---") out.push(<hr key={i} />);
    else if (l.startsWith("### ")) out.push(<h3 key={i}>{inline(l.slice(4), i)}</h3>);
    else if (l.startsWith("## ") || l.startsWith("# ")) out.push(<h2 key={i}>{inline(l.replace(/^#+ /, ""), i)}</h2>);
    else out.push(<p key={i}>{inline(l, i)}</p>);
  });
  flush(lines.length);
  return <div className="prose-a41 text-sm">{out}</div>;
}

export function useDebounced<T>(value: T, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function Select({ value, onChange, options, placeholder, className = "", ...rest }: {
  value: string | null | undefined; onChange: (v: string) => void; options: { value: string; label: string }[]; placeholder?: string; className?: string; [k: string]: any;
}) {
  return (
    <select className={`input ${className}`} value={value ?? ""} onChange={(e) => onChange(e.target.value)} {...rest}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

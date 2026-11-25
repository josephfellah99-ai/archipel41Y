import { Search as SearchIcon } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useApi } from "../lib/app";
import { Card, Empty, PageHeader, Spinner } from "../components/ui";

export default function SearchPage() {
  const [p] = useSearchParams();
  const q = p.get("q") || "";
  const { data, loading } = useApi<any>(q ? `/api/search?q=${encodeURIComponent(q)}` : null);
  return (
    <div>
      <PageHeader title={`Recherche : « ${q} »`} icon={<SearchIcon size={22} />} subtitle="Projets, clients, entreprises, devis, tâches, rendez-vous, documents et contenu des documents." />
      {loading ? <Spinner /> : data && (
        <div className="grid lg:grid-cols-2 gap-6">
          <Card title={`Éléments (${data.results.length})`}>
            {!data.results.length ? <Empty title="Aucun élément" /> : <ul className="divide-y divide-line">{data.results.map((r: any) => (
              <li key={r.kind + r.id} className="py-2 text-sm flex gap-2"><span className="chip bg-sunken text-muted w-24 justify-center">{r.kind}</span><Link className="hover:text-sage" to={r.link}>{r.label}</Link></li>))}</ul>}
          </Card>
          <Card title={`Passages de documents (${data.passages.length})`}>
            {!data.passages.length ? <Empty title="Aucun passage" /> : <ul className="space-y-3">{data.passages.map((x: any, i: number) => (
              <li key={i} className="text-sm"><Link className="font-medium hover:text-sage" to={`/documents?doc=${x.document_id}`}>{x.document}</Link>{x.page ? <span className="text-muted"> · p. {x.page}</span> : null}
                <div className="text-xs text-muted line-clamp-3 mt-0.5">{x.text}</div></li>))}</ul>}
          </Card>
        </div>)}
    </div>
  );
}

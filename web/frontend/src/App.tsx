import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui";
import { useApp } from "./lib/app";
import AuthGate from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import { ProjectDetail, ProjectsList } from "./pages/Projects";
import { QuotesPage, QuoteReview, ComparisonView } from "./pages/Quotes";
import Agenda from "./pages/Agenda";
import Planning from "./pages/Planning";
import Urbanisme from "./pages/Urbanisme";
import { AssistantPage } from "./pages/Assistant";
import Documents from "./pages/Documents";
import { Directory, ClientDetail, CompanyDetail } from "./pages/Directory";
import Finances from "./pages/Finances";
import Reports from "./pages/Reports";
import SettingsPage from "./pages/Settings";
import SearchPage from "./pages/Search";
import TeamPage from "./pages/Team";
import GuestApp from "./pages/Guest";
import Chantiers from "./pages/Chantiers";
import HistoryPage from "./pages/History";
import TerrainPage from "./pages/Terrain";

export default function App() {
  const { user, loading, guest } = useApp();
  if (loading) return <div className="h-full flex items-center justify-center"><Spinner label="Démarrage d'Archipel41…" /></div>;
  if (!user) return <AuthGate />;
  if (guest) return <GuestApp />;
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/projets" element={<ProjectsList />} />
        <Route path="/projets/:id" element={<ProjectDetail />} />
        <Route path="/devis" element={<QuotesPage />} />
        <Route path="/devis/:id" element={<QuoteReview />} />
        <Route path="/comparatifs/:id" element={<ComparisonView />} />
        <Route path="/agenda" element={<Agenda />} />
        <Route path="/planning" element={<Planning />} />
        <Route path="/urbanisme" element={<Urbanisme />} />
        <Route path="/terrain" element={<TerrainPage />} />
        <Route path="/chantiers" element={<Chantiers />} />
        <Route path="/equipe" element={<TeamPage />} />
        <Route path="/historique" element={<HistoryPage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/annuaire" element={<Directory />} />
        <Route path="/annuaire/clients/:id" element={<ClientDetail />} />
        <Route path="/annuaire/entreprises/:id" element={<CompanyDetail />} />
        <Route path="/finances" element={<Finances />} />
        <Route path="/rapports" element={<Reports />} />
        <Route path="/parametres" element={<SettingsPage />} />
        <Route path="/recherche" element={<SearchPage />} />
        <Route path="*" element={<Dashboard />} />
      </Routes>
    </Layout>
  );
}

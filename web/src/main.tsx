import { StrictMode, Suspense, lazy, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import "./index.css";
import { AuthProvider, useAuth } from "./lib/auth";
import { Shell } from "./components/Shell";
import { PageSkeleton } from "./components/ui";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Landing from "./pages/Landing";
import SignIn from "./pages/SignIn";

const Overview = lazy(() => import("./pages/Overview"));
const Investigations = lazy(() => import("./pages/Investigations"));
const InvestigationDetail = lazy(() => import("./pages/InvestigationDetail"));
const PlanDetail = lazy(() => import("./pages/PlanDetail"));
const TrialDetail = lazy(() => import("./pages/TrialDetail"));
const ActionDetail = lazy(() => import("./pages/ActionDetail"));
const EvidenceDetail = lazy(() => import("./pages/EvidenceDetail"));
const MemoryDetail = lazy(() => import("./pages/MemoryDetail"));
const ReportDetail = lazy(() => import("./pages/ReportDetail"));
const CopilotPage = lazy(() => import("./pages/CopilotPage"));
const Operations = lazy(() => import("./pages/Operations"));
const SponsorProof = lazy(() => import("./pages/SponsorProof"));
const NotFound = lazy(() => import("./pages/NotFound"));

function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  const loc = useLocation();
  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center text-sm text-muted">Checking your session…</div>
    );
  }
  if (!me) return <Navigate to="/signin" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

function S({ children }: { children: ReactNode }) {
  return <ErrorBoundary><Suspense fallback={<PageSkeleton />}>{children}</Suspense></ErrorBoundary>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/signin" element={<SignIn />} />
          <Route
            path="/app"
            element={
              <RequireAuth>
                <Shell />
              </RequireAuth>
            }
          >
            <Route index element={<S><Overview /></S>} />
            <Route path="investigations" element={<S><Investigations /></S>} />
            <Route path="investigations/:id" element={<S><InvestigationDetail /></S>} />
            <Route path="plans/:id" element={<S><PlanDetail /></S>} />
            <Route path="trials/:id" element={<S><TrialDetail /></S>} />
            <Route path="actions/:id" element={<S><ActionDetail /></S>} />
            <Route path="evidence/:id" element={<S><EvidenceDetail /></S>} />
            <Route path="memories/:id" element={<S><MemoryDetail /></S>} />
            <Route path="reports/:id" element={<S><ReportDetail /></S>} />
            <Route path="copilot" element={<S><CopilotPage /></S>} />
            <Route path="operations" element={<S><Operations /></S>} />
            <Route path="sponsors" element={<S><SponsorProof /></S>} />
            <Route path="*" element={<S><NotFound /></S>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ErrorBoundary>
  </StrictMode>,
);

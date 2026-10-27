import { useState } from "react";
import { NavLink, Outlet, useLocation, Link } from "react-router-dom";
import { LayoutDashboard, Search, Sparkles, Settings2, Award, LogOut, Menu, X, ExternalLink, Lock, ShieldCheck } from "lucide-react";
import { useAuth } from "../lib/auth";
import { Logo } from "./illustrations";
import { cx, Drawer } from "./ui";
import { CopilotChat, CopilotContextProvider, useCopilotContextId } from "./Copilot";
import { modeLabel } from "../lib/format";

function ModeBadge({ mode, writes }: { mode: string; writes: boolean }) {
  const styles: Record<string, string> = {
    sample: "bg-unk-bg text-unk ring-unk/25",
    connected_demo: "bg-pass-bg text-pass ring-pass/25",
    replay: "bg-lav text-ink-2 ring-line-2",
  };
  return (
    <span className="flex items-center gap-1.5">
      <span title="Server runtime mode (from /v1/me)" className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-semibold ring-1 ring-inset", styles[mode] ?? "bg-unk-bg text-unk ring-unk/25")}>
        <span className="size-1.5 rounded-full bg-current" />
        {modeLabel(mode)}
      </span>
      <span
        title={writes ? "Sandbox writes are enabled on the server" : "Sandbox writes are disabled on the server: nothing can be executed"}
        className={cx("hidden items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium ring-1 ring-inset sm:inline-flex", writes ? "bg-warn-bg text-warn ring-warn/25" : "bg-white text-muted ring-line")}
      >
        {writes ? <ShieldCheck className="size-3" /> : <Lock className="size-3" />}
        {writes ? "Writes on" : "Writes off"}
      </span>
    </span>
  );
}

function ShellInner() {
  const { me, signOut, isAdmin } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const loc = useLocation();
  const ctxInv = useCopilotContextId();
  const onCopilotPage = loc.pathname.startsWith("/app/copilot");

  const nav = [
    { to: "/app", label: "Overview", icon: LayoutDashboard, end: true },
    { to: "/app/investigations", label: "Investigations", icon: Search },
    { to: "/app/sponsors", label: "Sponsor proof", icon: Award },
    { to: "/app/copilot", label: "Ops Copilot", icon: Sparkles },
    ...(isAdmin ? [{ to: "/app/operations", label: "Operations", icon: Settings2 }] : []),
  ];

  const navList = (
    <nav className="space-y-1">
      {nav.map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.end}
          onClick={() => setNavOpen(false)}
          className={({ isActive }) =>
            cx(
              "flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14px] font-semibold transition",
              isActive ? "bg-accent text-white shadow-[0_8px_20px_-10px_rgb(36_56_245/0.8)]" : "text-ink-2 hover:bg-lav",
            )
          }
        >
          <n.icon className="size-[18px]" aria-hidden />
          {n.label}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      {/* Sidebar (desktop) */}
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-white/80 px-4 py-5 backdrop-blur lg:flex">
        <Link to="/" className="px-2"><Logo /></Link>
        <div className="mt-8 px-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-faint">Workbench</div>
        <div className="mt-2">{navList}</div>
        <div className="mt-auto space-y-3">
          <div className="rounded-2xl bg-gradient-to-br from-accent to-[#5465ff] p-4 text-white">
            <div className="font-display text-[15px] font-bold leading-tight">Rejections are <em className="font-extrabold">wins</em>.</div>
            <p className="mt-1 text-[12px] leading-snug text-white/80">A justified NO_CHANGE is the evidence loop working, not failing.</p>
          </div>
          <a href="/docs" target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-xl px-3 py-2 text-[13px] font-medium text-muted hover:bg-lav hover:text-ink">
            API docs (Swagger) <ExternalLink className="size-3.5" />
          </a>
        </div>
      </aside>

      <div className="min-w-0">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-wash/85 px-4 backdrop-blur sm:px-6">
          <button className="grid size-9 place-items-center rounded-xl hover:bg-lav lg:hidden" onClick={() => setNavOpen(true)} aria-label="Open navigation">
            <Menu className="size-5" />
          </button>
          <Link to="/" className="lg:hidden"><Logo className="[&_span:last-child]:hidden sm:[&_span:last-child]:inline" /></Link>
          <div className="hidden items-center gap-2 text-[13px] text-muted md:flex">
            <span className="rounded-lg bg-white px-2 py-1 font-semibold text-ink ring-1 ring-line">support-demo · superops-aws</span>
            <span>tenant {me?.tenant_id}</span>
          </div>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            {me && <ModeBadge mode={me.runtime_mode} writes={me.sandbox_writes_enabled} />}
            <div className="flex items-center gap-2 rounded-full bg-white py-1 pl-1 pr-1 ring-1 ring-line sm:pr-3">
              <span className="grid size-7 place-items-center rounded-full bg-ink text-[12px] font-bold uppercase text-white">{me?.display_name?.[0] ?? "?"}</span>
              <span className="hidden leading-tight sm:block">
                <span className="block max-w-[160px] truncate text-[12.5px] font-semibold text-ink">{me?.display_name}</span>
                <span className="block text-[10.5px] uppercase tracking-wider text-faint">{me?.role}</span>
              </span>
            </div>
            <button onClick={signOut} className="grid size-9 place-items-center rounded-full text-muted hover:bg-lav hover:text-ink" aria-label="Sign out" title="Sign out">
              <LogOut className="size-4" />
            </button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1320px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>

      {/* Mobile nav */}
      <div className={cx("fixed inset-0 z-50 lg:hidden", !navOpen && "pointer-events-none")}>
        <div className={cx("absolute inset-0 bg-ink/30 transition-opacity", navOpen ? "opacity-100" : "opacity-0")} onClick={() => setNavOpen(false)} />
        <aside className={cx("absolute inset-y-0 left-0 w-72 bg-white p-5 shadow-2xl transition-transform", navOpen ? "translate-x-0" : "-translate-x-full")}>
          <div className="flex items-center justify-between">
            <Logo />
            <button onClick={() => setNavOpen(false)} className="grid size-8 place-items-center rounded-full hover:bg-lav" aria-label="Close navigation"><X className="size-4" /></button>
          </div>
          <div className="mt-8">{navList}</div>
        </aside>
      </div>

      {/* Floating copilot */}
      {!onCopilotPage && (
        <button
          onClick={() => setChatOpen(true)}
          className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-ink py-3 pl-3 pr-4 text-[13.5px] font-semibold text-white shadow-[0_18px_40px_-12px_rgb(11_16_48/0.6)] transition hover:-translate-y-0.5"
        >
          <span className="grid size-7 place-items-center rounded-full bg-accent"><Sparkles className="size-4" /></span>
          Ask Copilot
        </button>
      )}
      <Drawer open={chatOpen} onClose={() => setChatOpen(false)} title={<span className="flex items-center gap-2"><Sparkles className="size-4 text-accent" /> Ops Copilot</span>} width="max-w-lg">
        {chatOpen && <CopilotChat compact investigationId={ctxInv} onNavigate={() => setChatOpen(false)} />}
      </Drawer>
    </div>
  );
}

export function Shell() {
  return (
    <CopilotContextProvider>
      <ShellInner />
    </CopilotContextProvider>
  );
}

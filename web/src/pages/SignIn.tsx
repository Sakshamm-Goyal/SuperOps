import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, KeyRound, Eye, EyeOff, Info } from "lucide-react";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Logo } from "../components/illustrations";
import { Button } from "../components/ui";

interface DemoLogin { actor_id: string; role: string; token: string }

export default function SignIn() {
  const { me, signIn, error, loading } = useAuth();
  const [tok, setTok] = useState("");
  const [show, setShow] = useState(false);
  const [demos, setDemos] = useState<DemoLogin[]>([]);
  const nav = useNavigate();
  const loc = useLocation();
  const from = (loc.state as { from?: string } | null)?.from ?? "/app";

  useEffect(() => {
    api.get<{ logins: DemoLogin[] }>("/v1/demo-logins").then((r) => setDemos(r.logins)).catch(() => {});
  }, []);

  if (me) return <Navigate to={from} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (await signIn(tok)) nav(from, { replace: true });
  }

  async function demoSignIn(token: string) {
    if (await signIn(token)) nav(from, { replace: true });
  }

  return (
    <div className="grid-paper relative min-h-screen">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-wash" />
      <div className="relative mx-auto flex min-h-screen max-w-md flex-col px-4 py-8">
        <Link to="/"><Logo /></Link>
        <div className="my-auto">
          <div className="card rise p-7 shadow-[var(--shadow-float)] sm:p-8">
            <span className="grid size-11 place-items-center rounded-2xl bg-accent-50 text-accent"><KeyRound className="size-5" /></span>
            <h1 className="display mt-5 text-[32px] text-ink">Sign in to the <em>workbench</em></h1>
            <p className="mt-2 text-[14px] text-muted">Paste a sandbox bearer token. The server maps it to an actor, tenant and role; the browser never chooses them.</p>
            <form onSubmit={submit} className="mt-6 space-y-3">
              <label className="block text-[14px] font-semibold text-ink" htmlFor="token">Sandbox token</label>
              <div className="flex items-center rounded-xl bg-wash ring-1 ring-line focus-within:ring-2 focus-within:ring-accent/50">
                <input
                  id="token"
                  type={show ? "text" : "password"}
                  autoComplete="off"
                  spellCheck={false}
                  value={tok}
                  onChange={(e) => setTok(e.target.value)}
                  placeholder="Paste token"
                  className="mono h-11 min-w-0 flex-1 bg-transparent px-3.5 text-[14px] text-ink outline-none placeholder:font-sans placeholder:text-faint"
                />
                <button type="button" onClick={() => setShow((s) => !s)} className="grid size-11 place-items-center text-faint hover:text-ink" aria-label={show ? "Hide token" : "Show token"}>
                  {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {error && <div role="alert" className="rounded-xl bg-fail-bg px-3 py-2 text-[14px] text-fail">{error}</div>}
              <Button type="submit" size="lg" className="w-full" loading={loading} disabled={!tok.trim()}>
                Sign in <ArrowRight className="size-4" />
              </Button>
            </form>
            {demos.length > 0 && (
              <div className="mt-6">
                <div className="flex items-center gap-3 text-[12px] uppercase tracking-wide text-faint">
                  <span className="h-px flex-1 bg-line" />demo access<span className="h-px flex-1 bg-line" />
                </div>
                <div className="mt-3 grid gap-2">
                  {demos.map((d) => (
                    <button key={d.actor_id} type="button" onClick={() => demoSignIn(d.token)} disabled={loading}
                      className="flex items-center justify-between rounded-xl bg-wash px-3.5 py-2.5 text-[14px] text-ink ring-1 ring-line hover:ring-accent/50 disabled:opacity-60">
                      <span className="font-semibold capitalize">{d.actor_id}</span>
                      <span className="mono text-[12px] text-muted">{d.role} <ArrowRight className="inline size-3.5" /></span>
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-[12px] text-faint">Shared sandbox logins for reviewers. Synthetic data; actions stay gated server-side.</p>
              </div>
            )}
            <div className="mt-6 flex gap-2.5 rounded-xl bg-lav p-3 text-[13.5px] text-ink-2">
              <Info className="mt-0.5 size-4 shrink-0 text-accent" />
              <div>
                Tokens are created by <code className="mono text-[12.5px]">scripts/bootstrap.py</code> in <code className="mono text-[12.5px]">var/actors.local.json</code>. Roles: <b>lead</b> operator, <b>teammate</b>/<b>judge</b> viewer, <b>admin</b> admin. The <b>autopilot</b> automation role can only start investigations. The token stays in this tab's session storage and is never put in a URL.
              </div>
            </div>
          </div>
        </div>
        <p className="text-center text-[12px] text-faint">Limited sandbox authentication — not an enterprise identity platform.</p>
      </div>
    </div>
  );
}

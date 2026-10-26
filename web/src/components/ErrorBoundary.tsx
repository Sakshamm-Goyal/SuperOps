import { Component, type ReactNode } from "react";

/** Last-resort boundary so a rendering bug shows a recoverable message instead of a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mx-auto max-w-lg p-8">
        <div className="card p-6">
          <div className="font-display text-lg font-bold text-ink">This view failed to render</div>
          <p className="mt-1 text-sm text-muted">Nothing was changed on the server. Reload the page; if it keeps happening, the message below helps debugging.</p>
          <pre className="mono mt-3 overflow-auto rounded-xl bg-wash p-3 text-[11.5px] text-fail">{this.state.error.message}</pre>
          <button className="mt-4 rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white" onClick={() => location.reload()}>Reload</button>
        </div>
      </div>
    );
  }
}

import type { ReactNode } from "react";
import { Bot, Brain, Cloud, Cpu, Database, Network, Sparkles, ShieldCheck, type LucideIcon } from "lucide-react";
import { cx } from "./ui";

/** Thin-line cloud over an isometric rack, drawn inline (no external art). */
export function CloudIllustration({ className }: { className?: string }) {
  const stroke = "#2438f5";
  return (
    <svg viewBox="0 0 520 420" className={className} fill="none" role="img" aria-label="Line drawing of a cloud above three server racks connected by evidence lines">
      <defs>
        <linearGradient id="cloud-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#eef0ff" />
        </linearGradient>
        <radialGradient id="halo" cx="0.5" cy="0.45" r="0.55">
          <stop offset="0" stopColor="#2438f5" stopOpacity="0.14" />
          <stop offset="1" stopColor="#2438f5" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="260" cy="190" rx="250" ry="180" fill="url(#halo)" />
      {/* cloud */}
      <path
        d="M150 190c-30 0-52-22-52-50s22-50 52-50c6-38 40-66 80-66 34 0 63 20 75 50 6-2 13-3 20-3 36 0 64 28 64 63 0 31-24 56-55 56H150Z"
        fill="url(#cloud-fill)"
        stroke={stroke}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M176 150c0-18 15-33 33-33" stroke={stroke} strokeOpacity=".35" strokeWidth="1.4" strokeLinecap="round" />
      {/* check seal inside cloud */}
      <circle cx="262" cy="142" r="26" fill="#2438f5" />
      <path d="m250 142 8 8 16-17" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {/* evidence lines from cloud to racks */}
      {[150, 262, 374].map((x, i) => (
        <path key={i} d={`M262 190 C 262 230, ${x} 222, ${x} 262`} stroke={stroke} strokeOpacity=".55" strokeWidth="1.3" className="flow" />
      ))}
      {/* three isometric racks */}
      {[150, 262, 374].map((x, i) => (
        <g key={x} transform={`translate(${x - 52} ${262 + (i === 1 ? 10 : 0)})`}>
          <path d="M52 0 104 26 52 52 0 26Z" fill="#fff" stroke={stroke} strokeWidth="1.4" strokeLinejoin="round" />
          <path d="M0 26v62l52 26V52Z" fill="#f4f5ff" stroke={stroke} strokeWidth="1.4" strokeLinejoin="round" />
          <path d="M104 26v62l-52 26V52Z" fill="#e9ecff" stroke={stroke} strokeWidth="1.4" strokeLinejoin="round" />
          {[0, 1, 2].map((r) => (
            <g key={r}>
              <path d={`M8 ${42 + r * 18} 44 ${60 + r * 18}`} stroke={stroke} strokeOpacity=".5" strokeWidth="1.2" />
              <circle cx={66 + r * 0} cy={70 + r * 0} r="0" />
              <path d={`M60 ${66 + r * 18 - 8} 96 ${48 + r * 18 - 8}`} stroke={stroke} strokeOpacity=".35" strokeWidth="1.2" />
            </g>
          ))}
          <circle cx="14" cy="44" r="2.2" fill={i === 0 ? "#d63c44" : "#0d8f62"} />
        </g>
      ))}
      {/* small floating sparks */}
      <circle cx="80" cy="96" r="3" fill={stroke} fillOpacity=".25" />
      <circle cx="452" cy="120" r="4" fill={stroke} fillOpacity=".2" />
      <path d="M440 40v14M433 47h14" stroke={stroke} strokeOpacity=".4" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M70 250v10M65 255h10" stroke={stroke} strokeOpacity=".35" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export interface HubNode { name: string; role: string; icon: LucideIcon }

export const SPONSOR_NODES: HubNode[] = [
  { name: "Zetaris", role: "Federated SQL across two physical sources", icon: Network },
  { name: "Meterless H-MEM", role: "Scoped, versioned memory of outcomes", icon: Brain },
  { name: "NVIDIA Nemotron", role: "Agent reasoning + semantic embeddings", icon: Cpu },
  { name: "Claude Haiku 4.5", role: "Ops Copilot chat over committed records", icon: Sparkles },
  { name: "PostgreSQL", role: "Sole holder of action authority", icon: Database },
  { name: "Google ADK", role: "Bounded agent roles and tools", icon: Bot },
  { name: "AWS", role: "Live EC2, CloudWatch and Price List sandbox", icon: Cloud },
];

/** Integration hub: a centre seal with six satellite nodes on an orbit, connected by animated dashed lines. */
export function IntegrationHub({ nodes = SPONSOR_NODES, center }: { nodes?: HubNode[]; center?: ReactNode }) {
  const R = 38; // % radius
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[520px]">
      <svg viewBox="0 0 100 100" className="absolute inset-0 size-full" aria-hidden>
        <circle cx="50" cy="50" r={R} fill="none" stroke="#dfe3ff" strokeWidth=".35" />
        <circle cx="50" cy="50" r={R - 14} fill="none" stroke="#eef0ff" strokeWidth=".35" />
        {nodes.map((_, i) => {
          const a = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
          return <line key={i} x1="50" y1="50" x2={50 + R * Math.cos(a)} y2={50 + R * Math.sin(a)} stroke="#2438f5" strokeOpacity=".45" strokeWidth=".35" className="flow" />;
        })}
      </svg>
      <div className="absolute left-1/2 top-1/2 grid size-[26%] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-[28%] bg-accent text-white shadow-[0_20px_50px_-15px_rgb(36_56_245/0.8)]">
        {center ?? (
          <div className="flex flex-col items-center">
            <ShieldCheck className="size-8 sm:size-10" strokeWidth={1.6} />
            <span className="mt-1 font-display text-[10px] font-bold uppercase tracking-widest sm:text-xs">SuperOps</span>
          </div>
        )}
      </div>
      {nodes.map((n, i) => {
        const a = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
        const left = 50 + R * Math.cos(a);
        const top = 50 + R * Math.sin(a);
        const Icon = n.icon;
        return (
          <div key={n.name} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${left}%`, top: `${top}%` }}>
            <div className="group relative flex flex-col items-center">
              <div className="grid size-12 place-items-center rounded-2xl bg-white text-accent shadow-[var(--shadow-float)] ring-1 ring-line transition group-hover:-translate-y-0.5 sm:size-14">
                <Icon className="size-5 sm:size-6" strokeWidth={1.7} />
              </div>
              <div className="mt-1.5 whitespace-nowrap rounded-full bg-white/90 px-2 py-0.5 text-[10.5px] font-semibold text-ink ring-1 ring-line sm:text-xs">{n.name}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Logo({ className, mono }: { className?: string; mono?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-2", className)}>
      <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
        <rect width="32" height="32" rx="10" fill={mono ? "#0b1030" : "#2438F5"} />
        <path d="M9 20.5a4.5 4.5 0 0 1 1.2-8.84A6 6 0 0 1 21.6 12.4 4 4 0 0 1 22 20.5H9Z" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinejoin="round" />
        <path d="m12.6 16.4 2.2 2.2 4.6-4.7" fill="none" stroke="#fff" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="font-display text-[17px] font-bold tracking-tight text-ink">
        Super<em className="font-extrabold italic text-accent">Ops</em>
      </span>
    </span>
  );
}

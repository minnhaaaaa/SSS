import { ArrowLeft, CircleUserRound, Database, RadioTower, RefreshCw, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { useControlRoom } from "../app/control-room-context";
import { titleCase } from "../lib/format";

export function ProfilePage() {
  const { apiConnection, liveConnection, serviceName, lastEventType, dataMode, retryConnections } =
    useControlRoom();

  return (
    <main className="mx-auto min-h-[calc(100vh-104px)] w-full max-w-[1040px] px-5 py-10 text-[#FFF9F4]">
      <Link to="/" className="inline-flex items-center gap-2 text-sm text-[#BCC9CD] no-underline transition hover:text-[#FFF9F4]">
        <ArrowLeft size={16} aria-hidden="true" /> Dashboard
      </Link>

      <section className="mt-6 overflow-hidden rounded-[24px] bg-[#626362]">
        <div className="flex flex-col gap-5 border-b border-[#0C0F0C]/35 px-6 py-7 sm:flex-row sm:items-center">
          <span className="grid size-20 place-items-center rounded-full bg-[#1E3B29] text-[#FFF9F4]">
            <CircleUserRound size={36} strokeWidth={1.5} aria-hidden="true" />
          </span>
          <div>
            <p className="m-0 font-mono text-xs tracking-[0.14em] text-[#0C0F0C]/55">OPERATOR PROFILE</p>
            <h1 className="mt-2 mb-0 text-3xl font-semibold tracking-[-0.04em] text-[#0C0F0C]">Local Operator</h1>
            <p className="mt-2 mb-0 text-sm text-[#0C0F0C]/65">Account identity is not configured by the current backend.</p>
          </div>
        </div>

        <div className="grid gap-4 p-6 md:grid-cols-3">
          <ProfileCard icon={Database} label="Data source" value={dataMode === "prototype" ? "Demo dataset" : "Live control plane"} />
          <ProfileCard icon={ShieldCheck} label="API connection" value={serviceName ?? titleCase(apiConnection)} />
          <ProfileCard icon={RadioTower} label="Event stream" value={titleCase(liveConnection)} />
        </div>

        <div className="mx-6 mb-6 rounded-[18px] bg-[#0C0F0C] p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="m-0 text-sm font-medium">Current session</p>
              <p className="mt-1 mb-0 font-mono text-xs text-[#BCC9CD]">Last event: {lastEventType ?? "None received"}</p>
            </div>
            <button type="button" onClick={retryConnections} className="inline-flex h-10 items-center gap-2 rounded-full bg-[#7C8970] px-4 text-xs font-semibold text-[#0C0F0C] transition hover:bg-[#95a488]">
              <RefreshCw size={14} aria-hidden="true" /> Refresh connections
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

function ProfileCard({ icon: Icon, label, value }: { readonly icon: typeof Database; readonly label: string; readonly value: string }) {
  return (
    <article className="rounded-[18px] bg-[#0C0F0C] p-5">
      <Icon size={19} className="text-[#4CD7F6]" aria-hidden="true" />
      <p className="mt-5 mb-0 text-xs uppercase tracking-[0.08em] text-[#BCC9CD]">{label}</p>
      <strong className="mt-2 block font-mono text-sm font-medium text-[#FFF9F4]">{value}</strong>
    </article>
  );
}

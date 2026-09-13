import { FlaskConical, Gauge, LayoutDashboard, PackageSearch, Radar, RefreshCw, Scale, ShieldCheck, UserRound } from "lucide-react";
import { useMemo, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useControlRoom } from "../app/control-room-context";
import Dock from "./dock";
import { PackageInspector } from "./package-inspector";

const navigation = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/radar", label: "Radar", icon: Radar },
  { path: "/packages", label: "Packages", icon: PackageSearch },
  { path: "/decisions", label: "Decisions", icon: Scale },
  { path: "/coverage", label: "Coverage", icon: ShieldCheck },
  { path: "/demo", label: "Demo", icon: FlaskConical },
] as const;

export function AppShell() {
  const [popoverOpen, setPopoverOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { apiConnection, liveConnection, serviceName, lastEventType, dataMode, retryConnections } =
    useControlRoom();

  const statusLabel = dataMode === "prototype"
    ? "DEMO MODE"
    : apiConnection === "online"
      ? "AGENT PROTECTED"
      : "SYSTEM CHECK";
  const dockItems = useMemo(
    () => (dataMode === "live" ? navigation.filter(({ path }) => path === "/demo") : navigation)
      .map(({ path, label, icon: Icon }) => ({
        icon: <Icon size={17} />,
        label,
        active: path === "/" ? location.pathname === path : location.pathname.startsWith(path),
        onClick: () => navigate(path),
      })),
    [dataMode, location.pathname, navigate],
  );

  return (
    <div className="relative min-h-screen bg-[#0C0F0C]">
      <NavLink
        className="absolute top-[30px] left-[clamp(18px,2.1vw,30px)] z-30 hidden h-[58px] w-[58px] items-center justify-center xl:flex"
        to="/"
        aria-label="SSS agent protection"
      >
        <img className="h-[58px] w-[58px] object-contain" src="/sss-logo.svg" alt="SSS" />
      </NavLink>

      <div className="fixed top-[30px] left-1/2 z-50 -translate-x-1/2">
        <Dock items={dockItems} panelHeight={48} baseItemSize={35} magnification={45} dockHeight={68} />
      </div>

      <div className="absolute top-[30px] right-[clamp(18px,2.1vw,30px)] z-40 hidden items-center gap-3 lg:flex">
        <span className="inline-flex h-[48px] min-w-[134px] items-center justify-center rounded-full bg-[#7C8970] px-5 font-mono text-[0.65rem] font-semibold tracking-[0.1em] text-[#0C0F0C]">
          {statusLabel}
        </span>
        <div className="relative">
          <button
            className="grid size-[48px] place-items-center rounded-full bg-[#1E3B29] text-[#FFF9F4] transition hover:bg-[#264c35]"
            type="button"
            aria-label="Open system status"
            aria-expanded={popoverOpen}
            onClick={() => setPopoverOpen((value) => !value)}
          >
            <Gauge size={17} aria-hidden="true" />
          </button>

          {popoverOpen && (
            <div className="status-popover">
              <div className="status-popover__header">
                <span>Connection state</span>
                <strong>{apiConnection}</strong>
              </div>
              <dl>
                <div>
                  <dt>Data source</dt>
                  <dd>{dataMode === "prototype" ? "Local demonstration dataset" : "Live control plane"}</dd>
                </div>
                <div>
                  <dt>API</dt>
                  <dd>{serviceName ?? apiConnection}</dd>
                </div>
                <div>
                  <dt>Live events</dt>
                  <dd>{liveConnection}</dd>
                </div>
                <div>
                  <dt>Last event</dt>
                  <dd>{lastEventType ?? "None received"}</dd>
                </div>
              </dl>
              <button className="button button--quiet" type="button" onClick={retryConnections}>
                <RefreshCw size={15} aria-hidden="true" /> Reconnect
              </button>
            </div>
          )}
        </div>
        <NavLink
          to="/profile"
          aria-label="Open operator profile"
          className={({ isActive }) =>
            "grid size-[48px] place-items-center rounded-full transition " +
            (isActive ? "bg-[#7C8970] text-[#0C0F0C]" : "bg-[#1E3B29] text-[#FFF9F4] hover:bg-[#264c35]")
          }
        >
          <UserRound size={18} strokeWidth={1.8} aria-hidden="true" />
        </NavLink>
      </div>

      <div className={location.pathname === "/" ? "min-h-screen" : "min-h-screen pt-[104px]"}>
        <Outlet />
      </div>
      <PackageInspector />
    </div>
  );
}

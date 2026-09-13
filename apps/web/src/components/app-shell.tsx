import { Gauge, RefreshCw, UserRound } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useControlRoom } from "../app/control-room-context";
import { PackageInspector } from "./package-inspector";

const navigation = [
  { path: "/", label: "Dashboard" },
  { path: "/radar", label: "Radar" },
  { path: "/packages", label: "Packages" },
  { path: "/decisions", label: "Decisions" },
  { path: "/coverage", label: "Coverage" },
  { path: "/demo", label: "Demo" },
] as const;

export function AppShell() {
  const [popoverOpen, setPopoverOpen] = useState(false);
  const location = useLocation();
  const { apiConnection, liveConnection, serviceName, lastEventType, dataMode, retryConnections } =
    useControlRoom();

  const statusLabel = dataMode === "prototype"
    ? "DEMO MODE"
    : apiConnection === "online"
      ? "SYSTEM ACTIVE"
      : "SYSTEM CHECK";

  return (
    <div className="relative min-h-screen bg-[#0C0F0C]">
      <NavLink
        className="absolute top-[30px] left-[clamp(18px,2.1vw,30px)] z-30 hidden h-[58px] w-[58px] items-center justify-center xl:flex"
        to="/"
        aria-label="SSS dashboard"
      >
        <img className="h-[58px] w-[58px] object-contain" src="/sss-logo.svg" alt="SSS" />
      </NavLink>

      <nav className="overview-nav-scroll fixed top-[30px] left-1/2 z-50 flex h-[48px] w-[min(756px,calc(100vw-32px))] -translate-x-1/2 items-center overflow-x-auto rounded-full border border-[#FFF9F4]/14 bg-[#0D0F0D]/95 p-[6px] shadow-[0_10px_28px_rgba(0,0,0,0.28)] backdrop-blur-md" aria-label="Primary navigation">
        <div className="flex min-w-max flex-1 items-center justify-between gap-0.5">
          {navigation.map(({ path, label }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/"}
              aria-label={label}
              className={({ isActive }) =>
                "inline-flex h-[35px] items-center justify-center rounded-full px-3 text-[0.68rem] font-medium whitespace-nowrap no-underline transition-colors sm:px-4 sm:text-xs md:min-w-[92px] " +
                (isActive
                  ? "bg-[#7C8970] text-[#0C0F0C]"
                  : "text-[#CEC9C4] hover:bg-[#FFF9F4]/8 hover:text-[#FFF9F4]")
              }
            >
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

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

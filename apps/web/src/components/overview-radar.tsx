import { LocateFixed, Minus, Plus, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type { Ecosystem, PackageState, PackageSummary } from "../domain/control-room";
import { titleCase } from "../lib/format";

interface OverviewRadarProps {
  readonly nodes: readonly PackageSummary[];
  readonly onSelectPackage: (name: string) => void;
  readonly stats?: readonly RadarStat[];
  readonly legendStats?: readonly RadarLegendStat[];
}

type EcosystemFilter = "all" | Ecosystem;
type SignalFilter = "risk" | "protected" | "verified";

interface RadarStat {
  readonly label: string;
  readonly value: number;
  readonly color: string;
}

interface RadarLegendStat extends RadarStat {
  readonly kind: SignalFilter;
}

interface PositionedNode {
  readonly item: PackageSummary;
  readonly x: number;
  readonly y: number;
}

const radarPositions = [
  [515, 168],
  [626, 184],
  [565, 232],
  [333, 198],
  [352, 392],
  [485, 333],
  [615, 406],
  [252, 326],
] as const;

export function OverviewRadar({ nodes, onSelectPackage, stats = [], legendStats = [] }: OverviewRadarProps) {
  const [ecosystem, setEcosystem] = useState<EcosystemFilter>("all");
  const [query, setQuery] = useState("");
  const [zoom, setZoom] = useState(1);
  const [signalFilter, setSignalFilter] = useState<SignalFilter | null>(null);
  const [hoveredName, setHoveredName] = useState<string | null>(null);
  const [lastHoveredName, setLastHoveredName] = useState(nodes[0]?.name ?? null);
  const radarField = useRef<HTMLDivElement>(null);
  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return nodes.filter(
      (item) =>
        (ecosystem === "all" || item.ecosystem === ecosystem) &&
        (!normalized || item.name.toLocaleLowerCase().includes(normalized)) &&
        (!signalFilter || matchesSignal(item.state, signalFilter)),
    );
  }, [ecosystem, nodes, query, signalFilter]);
  const positioned = useMemo(
    () => filtered.slice(0, radarPositions.length).map((item, index) => positionNode(item, index)),
    [filtered],
  );
  const hovered = positioned.find((node) => node.item.name === hoveredName) ?? null;
  const tooltipNode = positioned.find((node) => node.item.name === lastHoveredName) ?? positioned[0] ?? null;

  const activateNode = (name: string) => {
    setHoveredName(name);
    setLastHoveredName(name);
  };

  useEffect(() => {
    const field = radarField.current;
    if (!field) return;

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      setZoom((value) => clampZoom(value + (event.deltaY < 0 ? 0.12 : -0.12)));
    };

    field.addEventListener("wheel", handleWheel, { passive: false });
    return () => field.removeEventListener("wheel", handleWheel);
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-[32px] flex-wrap items-center gap-2">
        <div className="flex h-7 items-center rounded-full bg-[#0C0F0C] p-[3px]" aria-label="Radar registry filter">
          {(["all", "npm", "pypi"] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={ecosystem === value}
              onClick={() => setEcosystem(value)}
              className={
                "h-[22px] rounded-full px-3 font-mono text-[0.61rem] leading-none transition-colors " +
                (ecosystem === value
                  ? "bg-[#7C8970] text-[#0C0F0C]"
                  : "text-[#BCC9CD] hover:text-[#FFF9F4]")
              }
            >
              {value === "all" ? `ALL (${nodes.length})` : value}
            </button>
          ))}
        </div>

        <label className="group flex h-7 w-[min(250px,100%)] items-center gap-2 rounded-full border border-[#0C0F0C]/25 bg-[#1E3B29] px-3 text-[#4CD7F6] shadow-[inset_0_1px_0_rgba(255,249,244,0.08)] transition focus-within:border-[#7C8970] focus-within:bg-[#173322]">
          <Search size={12} strokeWidth={1.8} aria-hidden="true" />
          <span className="sr-only">Search radar packages</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="min-w-0 flex-1 bg-transparent font-mono text-[0.62rem] text-[#FFF9F4] outline-none placeholder:text-[#FFF9F4]/58 focus-visible:outline-none"
            placeholder="synthetic-npm-name"
          />
        </label>

        {legendStats.length > 0 && (
          <div className="flex basis-full flex-wrap items-center gap-1 md:ml-auto md:basis-auto" aria-label="Radar signal legend">
            {legendStats.map((item) => {
              const active = signalFilter === item.kind;
              return (
                <button
                  key={item.kind}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setSignalFilter((value) => value === item.kind ? null : item.kind)}
                  className="flex h-7 items-center gap-1.5 rounded-full border px-1.5 pr-2.5 font-mono text-[0.55rem] text-[#0C0F0C] transition hover:bg-[#FFF9F4]/28 focus-visible:outline-none"
                  style={{ borderColor: active ? item.color : "#0C0F0C33", backgroundColor: active ? `${item.color}88` : "transparent" }}
                >
                  <strong className="grid size-5 place-items-center rounded-full text-[0.58rem]" style={{ backgroundColor: item.color }}>
                    {item.value}
                  </strong>
                  {item.label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="mt-2 h-px shrink-0 bg-[#0C0F0C]" aria-hidden="true" />

      <div ref={radarField} className="relative mt-6 min-h-0 flex-1 overflow-hidden rounded-[20px] bg-[#0C0F0C]">
        {stats.length > 0 && <div className="absolute top-4 left-4 z-20 grid gap-2" aria-label="Dashboard statistics">
          {stats.map((item) => (
            <div key={item.label} className="flex h-7 items-center gap-2 font-mono text-[0.63rem] font-medium text-[#FFF9F4]">
              <strong className="grid size-6 place-items-center rounded-full text-[0.7rem] font-semibold text-[#0C0F0C]" style={{ backgroundColor: item.color }}>
                {item.value}
              </strong>
              <span>{item.label}</span>
            </div>
          ))}
        </div>}

        <div className="absolute right-4 bottom-4 z-20 flex items-center gap-1.5 rounded-full border border-[#FFF9F4]/12 bg-[#1E3B29]/95 p-1 shadow-[0_10px_26px_rgba(0,0,0,0.32)] backdrop-blur" aria-label="Radar controls">
          <RadarControl label="Zoom out" onClick={() => setZoom((value) => clampZoom(value - 0.15))}>
            <Minus size={13} />
          </RadarControl>
          <output className="min-w-9 text-center font-mono text-[0.58rem] text-[#FFF9F4]" aria-label="Radar zoom level">
            {Math.round(zoom * 100)}%
          </output>
          <RadarControl label="Zoom in" onClick={() => setZoom((value) => clampZoom(value + 0.15))}>
            <Plus size={13} />
          </RadarControl>
          <RadarControl label="Reset radar" onClick={() => { setZoom(1); setEcosystem("all"); setSignalFilter(null); setQuery(""); setHoveredName(null); }}>
            <LocateFixed size={13} />
          </RadarControl>
        </div>

        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 881 628"
          preserveAspectRatio="xMidYMid meet"
          aria-label="Global recurrence radar with package targets"
        >
          <title>Global recurrence radar with interactive package targets</title>
          <defs>
            <linearGradient id="overviewSweep" x1="441" y1="314" x2="655" y2="76" gradientUnits="userSpaceOnUse">
              <stop stopColor="#4CD7F6" stopOpacity="0.27" />
              <stop offset="1" stopColor="#4CD7F6" stopOpacity="0" />
            </linearGradient>
            <filter id="overviewNodeGlow" x="-180%" y="-180%" width="460%" height="460%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <g transform={`translate(441 314) scale(${zoom}) translate(-441 -314)`}>
            <g aria-hidden="true">
              <circle cx="441" cy="314" r="80" fill="none" stroke="#7C8970" strokeOpacity="0.75" />
              <circle cx="441" cy="314" r="143" fill="none" stroke="#FFF9F4" strokeOpacity="0.62" />
              <circle cx="441" cy="314" r="205" fill="none" stroke="#7C8970" strokeOpacity="0.72" strokeDasharray="4 5" />
              <circle cx="441" cy="314" r="267" fill="none" stroke="#FFF9F4" strokeOpacity="0.7" />
              <path d="M441 43V585M164 314H718" stroke="#7C8970" strokeOpacity="0.62" />
            </g>

            <g className="overview-radar__sweep" aria-hidden="true">
              <path d="M441 314V47A267 267 0 0 1 657 157Z" fill="url(#overviewSweep)" />
              <path d="M441 314L657 157" stroke="#4CD7F6" strokeOpacity="0.75" />
            </g>

            {positioned.map((node) => {
              const color = stateColor(node.item.state);
              const active = hovered?.item.id === node.item.id;
              const labelOnLeft = node.x > 570;
              return (
                <g
                  key={node.item.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`${node.item.name}, ${titleCase(node.item.state)}, score ${node.item.attractiveness}`}
                  onMouseEnter={() => activateNode(node.item.name)}
                  onMouseLeave={() => setHoveredName(null)}
                  onFocus={() => activateNode(node.item.name)}
                  onBlur={() => setHoveredName(null)}
                  onClick={() => onSelectPackage(node.item.name)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectPackage(node.item.name);
                    }
                  }}
                  className="cursor-pointer outline-none"
                >
                  <circle cx={node.x} cy={node.y} r={active ? 15 : 11.5} fill="none" stroke={color} strokeOpacity={active ? 0.76 : 0.38} />
                  <circle cx={node.x} cy={node.y} r={active ? 6.9 : 5.75} fill={color} filter="url(#overviewNodeGlow)" />
                  <text x={node.x + (labelOnLeft ? -15 : 15)} y={node.y + 3} textAnchor={labelOnLeft ? "end" : "start"} fill="#BCC9CD" fillOpacity="0.84" fontFamily="monospace" fontSize="8">
                    {node.item.name}
                  </text>
                </g>
              );
            })}

            <g aria-hidden="true">
              <circle cx="441" cy="314" r="15" fill="#626362" fillOpacity="0.72" />
              <circle cx="441" cy="314" r="5" fill="#4CD7F6" />
              <path d="M430 314H452M441 303V325" stroke="#0C0F0C" strokeWidth="1.5" />
            </g>
          </g>

          {tooltipNode && (
            <NodeTooltip node={tooltipNode} visible={Boolean(hovered)} zoom={zoom} />
          )}
        </svg>

        {!positioned.length && (
          <div className="absolute inset-0 grid place-items-center text-sm text-[#BCC9CD]">
            No targets match the current filters.
          </div>
        )}
      </div>
    </div>
  );
}

function RadarControl({ label, onClick, children }: { readonly label: string; readonly onClick: () => void; readonly children: ReactNode }) {
  return (
    <button type="button" aria-label={label} onClick={onClick} className="grid size-7 place-items-center rounded-full text-[#FFF9F4] transition duration-150 hover:bg-[#7C8970] hover:text-[#0C0F0C] focus-visible:bg-[#7C8970] focus-visible:text-[#0C0F0C]">
      {children}
    </button>
  );
}

function NodeTooltip({ node, visible, zoom }: { readonly node: PositionedNode; readonly visible: boolean; readonly zoom: number }) {
  const color = stateColor(node.item.state);
  const policyRisk = node.item.policyRisk === null ? "NOT SCORED" : `${node.item.policyRisk} / 100`;
  const scaledX = 441 + (node.x - 441) * zoom;
  const scaledY = 314 + (node.y - 314) * zoom;

  return (
    <g
      pointerEvents="none"
      opacity={visible ? 1 : 0}
      style={{ transition: "opacity 90ms ease-out" }}
      aria-hidden={!visible}
    >
      <path d={`M${scaledX + 8} ${scaledY - 5}L640 104`} fill="none" stroke={color} strokeOpacity="0.78" />
      <g transform="translate(640 48)">
        <rect width="220" height="112" rx="5" fill="#0C0F0C" stroke={color} strokeWidth="1.25" />
        <rect width="3" height="112" rx="1.5" fill={color} />
        <text x="14" y="18" fill={color} fontFamily="monospace" fontSize="8" fontWeight="700" letterSpacing="0.5">
          NODE INTELLIGENCE
        </text>
        <text x="14" y="36" fill="#FFF9F4" fontFamily="monospace" fontSize="9" fontWeight="700">
          {node.item.name}
        </text>
        <text x="14" y="53" fill="#BCC9CD" fontFamily="monospace" fontSize="7.5">
          REGISTRY  {node.item.ecosystem.toUpperCase()}   ·   STATE  {titleCase(node.item.state).toUpperCase()}
        </text>
        <text x="14" y="69" fill="#BCC9CD" fontFamily="monospace" fontSize="7.5">
          ATTRACTIVENESS  {node.item.attractiveness} / 100
        </text>
        <text x="14" y="85" fill="#BCC9CD" fontFamily="monospace" fontSize="7.5">
          POLICY RISK  {policyRisk}
        </text>
        <text x="14" y="101" fill="#BCC9CD" fontFamily="monospace" fontSize="7.5">
          LAST SEEN  {formatRadarDate(node.item.lastSeen)}
        </text>
      </g>
    </g>
  );
}

function positionNode(item: PackageSummary, index: number): PositionedNode {
  const [x, y] = radarPositions[index] ?? radarPositions[0];
  return { item, x, y };
}

function stateColor(state: PackageState): string {
  if (state === "blocked" || state === "high_risk") return "#D9544F";
  if (state === "registered") return "#E6AA3C";
  if (state === "monitored") return "#4CD7F6";
  return "#FFF9F4";
}

function matchesSignal(state: PackageState, filter: SignalFilter): boolean {
  if (filter === "risk") return state === "blocked" || state === "high_risk";
  if (filter === "protected") return state === "monitored";
  return state === "registered";
}

function clampZoom(value: number): number {
  return Math.min(Math.max(value, 0.5), 3);
}

function formatRadarDate(value: string | null): string {
  if (!value) return "NO OBSERVATION";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.toUpperCase();
  return new Intl.DateTimeFormat("en", { month: "short", day: "2-digit", year: "numeric" })
    .format(date)
    .toUpperCase();
}

import type { LucideIcon } from "lucide-react";

interface MetricTileProps {
  readonly label: string;
  readonly value: string | number;
  readonly detail: string;
  readonly icon: LucideIcon;
  readonly tone?: "signal" | "danger" | "neutral";
}

export function MetricTile({ label, value, detail, icon: Icon, tone = "neutral" }: MetricTileProps) {
  return (
    <article className={`metric-tile metric-tile--${tone}`} data-reveal>
      <div className="metric-tile__topline">
        <span>{label}</span>
        <Icon size={18} strokeWidth={1.7} aria-hidden="true" />
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

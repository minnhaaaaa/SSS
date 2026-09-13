import type { ReactNode } from "react";

interface PanelProps {
  readonly title?: string;
  readonly eyebrow?: string;
  readonly action?: ReactNode;
  readonly className?: string;
  readonly children: ReactNode;
}

export function Panel({ title, eyebrow, action, className = "", children }: PanelProps) {
  return (
    <section className={`panel ${className}`} data-reveal>
      {(title || eyebrow || action) && (
        <header className="panel__header">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <h2>{title}</h2>}
          </div>
          {action}
        </header>
      )}
      <div className="panel__body">{children}</div>
    </section>
  );
}

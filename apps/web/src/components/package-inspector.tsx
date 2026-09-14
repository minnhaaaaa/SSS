import { Activity, Clock3, ShieldCheck, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useControlRoom } from "../app/control-room-context";
import { api } from "../app/services";
import type { EvidenceItem, PackageDetail } from "../domain/control-room";
import { formatTimestamp, score, titleCase } from "../lib/format";
import { gsap, useGSAP } from "../motion/register";
import { EmptyState, ErrorState, LoadingState } from "./async-state";

export function PackageInspector() {
  const { selectedPackage, closePackage } = useControlRoom();
  const root = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const [detail, setDetail] = useState<PackageDetail | null>(null);
  const [evidence, setEvidence] = useState<readonly EvidenceItem[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!selectedPackage) {
      setDetail(null);
      setEvidence([]);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void Promise.all([
      api.getPackage(selectedPackage, controller.signal),
      api.getEvidence(selectedPackage, controller.signal),
    ])
      .then(([packageDetail, packageEvidence]) => {
        setDetail(packageDetail);
        setEvidence(packageEvidence);
        setLoading(false);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason : new Error("Package data unavailable"));
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [selectedPackage, revision]);

  useEffect(() => {
    if (!selectedPackage) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closePackage();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedPackage, closePackage]);

  useGSAP(
    () => {
      if (!selectedPackage) {
        return;
      }
      const media = gsap.matchMedia();
      media.add({ reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
        if (context.conditions?.reduceMotion) {
          gsap.set(".inspector-backdrop, .package-inspector", { autoAlpha: 1, xPercent: 0 });
        } else {
          gsap
            .timeline({ defaults: { ease: "power3.out" } })
            .fromTo(".inspector-backdrop", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.25 })
            .fromTo(
              ".package-inspector",
              { autoAlpha: 0, xPercent: 8 },
              { autoAlpha: 1, xPercent: 0, duration: 0.48 },
              "<0.04",
            );
        }
        closeButton.current?.focus();
      });
      return () => media.revert();
    },
    { dependencies: [selectedPackage], scope: root, revertOnUpdate: true },
  );

  const open = selectedPackage !== null;

  return (
    <div className="inspector-layer" data-open={open} ref={root} aria-hidden={!open}>
      <button
        className="inspector-backdrop"
        type="button"
        tabIndex={open ? 0 : -1}
        onClick={closePackage}
        aria-label="Close package inspector"
      />
      <aside className="package-inspector" role="dialog" aria-modal="true" aria-label="Package Inspector">
        <header className="package-inspector__header">
          <h2>Package Inspector</h2>
          <button ref={closeButton} className="icon-button" type="button" onClick={closePackage}>
            <X aria-hidden="true" />
            <span className="sr-only">Close inspector</span>
          </button>
        </header>

        <div className="package-inspector__content">
          {loading && <LoadingState label="Loading package evidence" />}
          {error && <ErrorState error={error} retry={() => setRevision((value) => value + 1)} />}
          {!loading && !error && detail && (
            <>
              <div className="package-identity">
                <p><span>{detail.ecosystem}:</span> {detail.name}</p>
                <span className={`state-chip state-chip--${detail.state}`}>
                  {titleCase(detail.state)}
                </span>
              </div>

              <div className="score-grid">
                <ScoreBlock label="Attractiveness" value={score(detail.attractiveness)} />
                <ScoreBlock label="Policy risk" value={score(detail.policyRisk)} />
                <ScoreBlock label="Absence confidence" value={score(detail.absenceConfidence)} />
              </div>

              <section className="inspector-section">
                <div className="section-label">
                  <ShieldCheck size={16} aria-hidden="true" /> Lifecycle
                </div>
                {detail.lifecycle.length ? (
                  <ol className="lifecycle-list">
                    {detail.lifecycle.map((step, index) => (
                      <li key={`${step}-${index}`}>
                        <span className={lifecycleTone(step)} aria-hidden="true" />
                        <div>
                          <strong>{step}</strong>
                          <small>Stage {String(index + 1).padStart(2, "0")}</small>
                        </div>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <EmptyState title="No lifecycle events" detail="The API returned no lifecycle state." />
                )}
              </section>

              <section className="inspector-section">
                <div className="section-label">
                  <Activity size={16} aria-hidden="true" /> Recent Activity
                </div>
                {evidence.length ? (
                  <ol className="evidence-list">
                    {evidence.map((item) => (
                      <li key={item.id}>
                        <span className={`evidence-list__dot evidence-list__dot--${item.type}`} aria-hidden="true" />
                        <div>
                          <strong>{item.label}</strong>
                          <span>{item.provenance}</span>
                        </div>
                        <time dateTime={item.occurredAt}><Clock3 size={12} aria-hidden="true" /> {formatTimestamp(item.occurredAt)}</time>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <EmptyState title="No evidence returned" detail="No evidence rows exist for this package." />
                )}
              </section>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

function ScoreBlock({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="score-block">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{value === "—" ? "not scored" : "/ 100"}</small>
    </div>
  );
}

function lifecycleTone(step: string): string {
  const normalized = step.toLocaleLowerCase();
  if (normalized.includes("blocked") || normalized.includes("risk")) return "is-danger";
  if (normalized.includes("registration") || normalized.includes("registry transition")) return "is-warning";
  if (normalized.includes("monitored") || normalized.includes("recommendation")) return "is-cyan";
  return "is-neutral";
}

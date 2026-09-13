import { Clock3, ShieldX, X } from "lucide-react";
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
          <div>
            <p className="eyebrow">Package inspector</p>
            <h2>{selectedPackage ?? "Package"}</h2>
          </div>
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
                <div>
                  <span className={`state-chip state-chip--${detail.state}`}>
                    {titleCase(detail.state)}
                  </span>
                  <span className="registry-chip">{detail.ecosystem}</span>
                </div>
                <p>High-risk temporal patterns require evidence review, not unsupported attribution.</p>
              </div>

              <div className="score-grid">
                <ScoreBlock label="Target attractiveness" value={score(detail.attractiveness)} />
                <ScoreBlock label="Absence confidence" value={score(detail.absenceConfidence)} />
                <ScoreBlock label="Policy risk" value={score(detail.policyRisk)} />
              </div>

              <section className="inspector-section">
                <div className="section-label">
                  <ShieldX size={16} aria-hidden="true" /> Package lifecycle
                </div>
                {detail.lifecycle.length ? (
                  <ol className="lifecycle-list">
                    {detail.lifecycle.map((step, index) => (
                      <li key={`${step}-${index}`}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        {step}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <EmptyState title="No lifecycle events" detail="The API returned no lifecycle state." />
                )}
              </section>

              <section className="inspector-section">
                <div className="section-label">
                  <Clock3 size={16} aria-hidden="true" /> Evidence timeline
                </div>
                {evidence.length ? (
                  <ol className="evidence-list">
                    {evidence.map((item) => (
                      <li key={item.id}>
                        <time dateTime={item.occurredAt}>{formatTimestamp(item.occurredAt)}</time>
                        <strong>{item.label}</strong>
                        <span>{item.provenance}</span>
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
      <small>/ 100</small>
    </div>
  );
}

import {
  Ban,
  Check,
  CircleDotDashed,
  Play,
  Radio,
  Shield,
  Terminal,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { useRef, useState } from "react";

import { api, dataMode } from "../app/services";
import { ErrorState, LoadingState } from "../components/async-state";
import { PageFrame } from "../components/page-frame";
import { Panel } from "../components/panel";
import type { DemoAction, DemoStatus } from "../domain/control-room";
import { useApiResource } from "../hooks/use-api-resource";
import { gsap, useGSAP } from "../motion/register";

const actions: readonly { id: DemoAction; label: string; detail: string }[] = [
  { id: "replay-evidence", label: "Replay Evidence", detail: "Ingest historical observations" },
  { id: "register-target", label: "Register Target", detail: "Publish to the controlled registry" },
  { id: "run-unprotected", label: "Run Unprotected", detail: "Observe the isolated canary" },
  { id: "run-protected", label: "Run Protected", detail: "Prove pre-execution blocking" },
];

export function DemoPage() {
  const resource = useApiResource((signal) => api.getDemoStatus(signal), []);
  const [pendingAction, setPendingAction] = useState<DemoAction | null>(null);
  const [actionError, setActionError] = useState<Error | null>(null);

  const execute = async (action: DemoAction) => {
    setPendingAction(action);
    setActionError(null);
    try {
      await api.runDemoAction(action);
      resource.reload();
    } catch (error) {
      setActionError(error instanceof Error ? error : new Error("Demo action failed"));
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <PageFrame
      eyebrow="Proof / Controlled lab"
      title="Attack & Prevention"
      description={
        dataMode === "prototype"
          ? "Walk through the temporary replay, registration, and isolated enforcement sequence."
          : "The dashboard is optional evidence. Run the real protection flow in the coding-agent and operator terminals."
      }
    >
      {dataMode === "live" && (
        <Panel eyebrow="Primary demo surface" title="Agent protection active">
          <p className="demo-message">
            <Terminal aria-hidden="true" /> Agent: <code>./scripts/demo.sh agent</code>
          </p>
          <p className="demo-message">
            <Shield aria-hidden="true" /> Operator: <code>./scripts/demo.sh operator</code>
          </p>
        </Panel>
      )}
      {resource.loading && <LoadingState label="Reading demo state" />}
      {resource.error && <ErrorState error={resource.error} retry={resource.reload} />}
      {actionError && <ErrorState error={actionError} retry={resource.reload} />}
      {resource.data && <DemoExperience status={resource.data} pending={pendingAction} execute={execute} />}
    </PageFrame>
  );
}

function DemoExperience({
  status,
  pending,
  execute,
}: {
  readonly status: DemoStatus;
  readonly pending: DemoAction | null;
  readonly execute: (action: DemoAction) => Promise<void>;
}) {
  const root = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      if (status.state !== "blocked") return;
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        gsap
          .timeline({ defaults: { duration: 0.5, ease: "power3.out" } })
          .from(".blocked-hero__icon", { scale: 0.65, rotation: -12, autoAlpha: 0 })
          .from(".blocked-hero h2, .blocked-hero p", { y: 14, autoAlpha: 0, stagger: 0.08 }, "-=0.22")
          .from(".proof-tile", { y: 12, autoAlpha: 0, stagger: 0.06 }, "-=0.2");
      });
      return () => media.revert();
    },
    { dependencies: [status.state], scope: root, revertOnUpdate: true },
  );

  return (
    <div className="demo-experience" ref={root}>
      {status.state === "blocked" && (
        <section className="blocked-hero" data-reveal>
          <Ban className="blocked-hero__icon" aria-hidden="true" />
          <p className="eyebrow">SSS Guard interception</p>
          <h2>Installation Blocked</h2>
          {status.targetPackage && <p className="blocked-hero__package">{status.targetPackage}</p>}
          <div className="interception-line" aria-label="Agent request blocked before package manager">
            <span><Terminal aria-hidden="true" /> Agent</span>
            <i aria-hidden="true" />
            <strong><Shield aria-hidden="true" /> Guard / Block</strong>
            <i className="is-blocked" aria-hidden="true" />
            <span><Ban aria-hidden="true" /> Package manager</span>
          </div>
        </section>
      )}

      <ol className="demo-steps" data-reveal>
        {actions.map((action, index) => {
          const complete = status.completedSteps.includes(action.id);
          const available = status.availableActions.includes(action.id);
          return (
            <li key={action.id} data-complete={complete}>
              <span>{complete ? <Check aria-hidden="true" /> : String(index + 1).padStart(2, "0")}</span>
              <div>
                <strong>{action.label}</strong>
                <small>{action.detail}</small>
              </div>
              {dataMode === "prototype" ? (
                <button
                  className="button button--action"
                  type="button"
                  disabled={!available || pending !== null}
                  onClick={() => void execute(action.id)}
                >
                  {pending === action.id ? <CircleDotDashed className="spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
                  {complete ? (available ? "Run again" : "Complete") : "Run"}
                </button>
              ) : (
                <span className="button button--action" aria-label={`${action.label}: terminal controlled`}>
                  <Terminal aria-hidden="true" /> Terminal
                </span>
              )}
            </li>
          );
        })}
      </ol>

      <section className="proof-grid" data-reveal>
        <ProofTile
          label="Unprotected canary"
          value={status.unprotectedCanaryCount}
          detail="Executions observed"
          icon={TriangleAlert}
          tone="danger"
        />
        <ProofTile
          label="Protected canary"
          value={status.protectedCanaryCount}
          detail="Executions observed"
          icon={Shield}
          tone="signal"
        />
        <ProofTile
          label="Package manager"
          value={status.packageManagerStarted === null ? "Not attempted" : status.packageManagerStarted ? "Started" : "Not started"}
          detail="Backend-reported child state"
          icon={Terminal}
        />
      </section>

      <section className="proof-grid" aria-label="Frozen policy evidence" data-reveal>
        <ProofTile
          label="Absence confidence"
          value={status.scores.absenceConfidence}
          detail={`${status.registrationAgeMinutes} minute registration transition`}
          icon={Shield}
          tone="signal"
        />
        <ProofTile
          label="Target attractiveness"
          value={status.scores.targetAttractiveness}
          detail="46 verified recommendations"
          icon={TriangleAlert}
          tone="danger"
        />
        <ProofTile
          label="Package policy risk"
          value={status.scores.packagePolicyRisk}
          detail={status.policyVersion}
          icon={Ban}
          tone="danger"
        />
      </section>

      {status.message && (
        <Panel eyebrow="Lab response" title="Latest Result">
          <p className="demo-message" aria-live="polite"><Radio aria-hidden="true" /> {status.message}</p>
        </Panel>
      )}
    </div>
  );
}

function ProofTile({
  label,
  value,
  detail,
  icon: Icon,
  tone = "neutral",
}: {
  readonly label: string;
  readonly value: string | number;
  readonly detail: string;
  readonly icon: LucideIcon;
  readonly tone?: "signal" | "danger" | "neutral";
}) {
  return (
    <article className={`proof-tile proof-tile--${tone}`}>
      <Icon aria-hidden="true" />
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

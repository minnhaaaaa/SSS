import { useRef, type ReactNode } from "react";

import { gsap, useGSAP } from "../motion/register";

interface PageFrameProps {
  readonly eyebrow: string;
  readonly title: string;
  readonly description: string;
  readonly meta?: ReactNode;
  readonly children: ReactNode;
}

export function PageFrame({ eyebrow, title, description, meta, children }: PageFrameProps) {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const media = gsap.matchMedia();
      media.add(
        { reduceMotion: "(prefers-reduced-motion: reduce)" },
        (context) => {
          const reduceMotion = Boolean(context.conditions?.reduceMotion);
          if (reduceMotion) {
            gsap.set("[data-reveal]", { autoAlpha: 1, y: 0 });
            return;
          }
          gsap
            .timeline({ defaults: { duration: 0.55, ease: "power3.out" } })
            .from(".page-heading > *", { autoAlpha: 0, y: 16, stagger: 0.07 })
            .from("[data-reveal]", { autoAlpha: 0, y: 20, stagger: 0.06 }, "-=0.25");
        },
      );
      return () => media.revert();
    },
    { scope: root },
  );

  return (
    <main className="page-frame" ref={root}>
      <header className="page-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {meta && <div className="page-heading__meta">{meta}</div>}
      </header>
      {children}
    </main>
  );
}

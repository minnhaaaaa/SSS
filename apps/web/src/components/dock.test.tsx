import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import Dock from "./dock";

vi.mock("motion/react", async (importOriginal) => ({
  ...await importOriginal<typeof import("motion/react")>(),
  useReducedMotion: () => true,
}));

function renderDock() {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/radar"]}>
      <Dock
        items={[
          {
            icon: <span>R</span>,
            label: "Radar",
            to: "/radar",
          },
        ]}
      />
    </MemoryRouter>,
  );
}

describe("Dock", () => {
  it("renders route destinations as navigation links", () => {
    const markup = renderDock();

    expect(markup).toContain("<nav");
    expect(markup).toContain('aria-label="Primary navigation"');
    expect(markup).toContain('href="/radar"');
    expect(markup).toContain('aria-current="page"');
    expect(markup).not.toContain('role="toolbar"');
  });

  it("keeps dock dimensions static when reduced motion is enabled", () => {
    const markup = renderDock();

    expect(markup).toContain('data-reduced-motion="true"');
    expect(markup).toContain('style="height:48px"');
    expect(markup).toContain('style="width:35px;height:35px"');
  });

  it("renders a transform-safe static tooltip when reduced motion is enabled", () => {
    const markup = renderDock();

    expect(markup).toContain('class="dock-label dock-label--static"');
    expect(markup).toContain('class="dock-label__content"');
    expect(markup).toContain("Radar</span>");
  });
});

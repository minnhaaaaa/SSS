import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const workspaceDir = path.resolve(scriptDir, "..");
const SKILL_DIR = process.env.SKILL_DIR;
const RUNTIME_PYTHON = process.env.RUNTIME_PYTHON;
if (!path.isAbsolute(SKILL_DIR ?? "") || !path.isAbsolute(RUNTIME_PYTHON ?? "")) {
  throw new Error("Set absolute SKILL_DIR and RUNTIME_PYTHON paths");
}
const { resolvePresentationFont, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href
);

const family = resolvePresentationFont();
const outputDir = path.join(workspaceDir, "docs/pitch");
const stagingDir = path.join(workspaceDir, ".runtime/pitch-build");
const finalPath = path.join(outputDir, "SSS-pitch-deck.pptx");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(stagingDir, { recursive: true });

const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const C = {
  ink: "#07131A",
  paper: "#F3F0E7",
  lime: "#C9F64A",
  coral: "#FF705C",
  cyan: "#59D4D4",
  muted: "#9EB0B7",
  white: "#FFFFFF",
};

function box(slide, left, top, width, height, fill, radius = 0) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    position: { left, top, width, height },
    fill,
    line: { fill: "none", width: 0 },
  });
}

function text(slide, value, left, top, width, height, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left, top, width, height },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    typeface: family,
    fontSize: options.size ?? 24,
    bold: options.bold ?? false,
    color: options.color ?? C.white,
    autoFit: "shrinkText",
    alignment: options.align ?? "left",
    verticalAlignment: options.valign ?? "middle",
  };
  return shape;
}

function base(title, number, background = C.ink) {
  const slide = deck.slides.add();
  slide.background.fill = background;
  const foreground = background === C.paper ? C.ink : C.white;
  text(slide, title, 64, 46, 1080, 62, { size: 34, bold: true, color: foreground });
  text(slide, String(number).padStart(2, "0"), 1180, 50, 40, 32, {
    size: 15,
    color: C.muted,
    align: "right",
  });
  box(slide, 64, 116, 1152, 3, C.lime);
  return slide;
}

function note(slide, value) {
  slide.speakerNotes.textFrame.setText(value);
}

// 1. Cover
{
  const slide = deck.slides.add();
  slide.background.fill = C.ink;
  box(slide, 70, 72, 14, 550, C.lime);
  text(slide, "SSS", 126, 120, 360, 96, { size: 72, bold: true, color: C.lime });
  text(slide, "Stop Slop Squatting", 126, 218, 910, 86, { size: 46, bold: true });
  text(
    slide,
    "Temporal package intelligence that stops unsafe agent installs before execution",
    126,
    326,
    900,
    112,
    { size: 27, color: C.muted }
  );
  text(slide, "EXASOL  •  PYPI + NPM  •  SELF HOSTED", 126, 554, 850, 34, {
    size: 16,
    bold: true,
    color: C.cyan,
  });
  note(slide, "Open with the agent install problem. The product demo starts in a terminal, not in the Radar UI.");
}

// 2. Threat
{
  const slide = base("A real package can still carry a dangerous history", 2);
  text(slide, "MODEL", 84, 162, 170, 36, { size: 18, bold: true, color: C.cyan });
  text(slide, "recommends a package\nthat does not exist", 84, 204, 240, 110, { size: 25, bold: true });
  box(slide, 350, 208, 120, 5, C.muted);
  text(slide, "ATTACKER", 520, 162, 190, 36, { size: 18, bold: true, color: C.coral });
  text(slide, "registers the same\nplausible name later", 520, 204, 240, 110, { size: 25, bold: true });
  box(slide, 786, 208, 120, 5, C.muted);
  text(slide, "AGENT", 954, 162, 170, 36, { size: 18, bold: true, color: C.lime });
  text(slide, "finds a valid registry\nentry and installs it", 954, 204, 250, 110, { size: 25, bold: true });
  text(
    slide,
    "A registry lookup answers whether the name exists now. SSS remembers whether trusted systems invented it before it existed.",
    84,
    442,
    1080,
    118,
    { size: 29, color: C.paper }
  );
  note(slide, "Slopsquatting is the package equivalent of occupying a name that models repeatedly hallucinate. SSS uses only controlled or attributable evidence.");
}

// 3. Temporal insight
{
  const slide = base("The timeline changes the decision", 3, C.paper);
  text(slide, "T0", 100, 164, 70, 32, { size: 18, bold: true, color: C.ink });
  text(slide, "T1", 520, 164, 70, 32, { size: 18, bold: true, color: C.ink });
  text(slide, "T2", 950, 164, 70, 32, { size: 18, bold: true, color: C.ink });
  box(slide, 126, 238, 920, 6, C.ink);
  for (const [x, color] of [[140, C.cyan], [560, C.coral], [990, C.lime]]) box(slide, x, 220, 42, 42, color, 12);
  text(slide, "Verified absence", 90, 292, 240, 44, { size: 24, bold: true, color: C.ink });
  text(slide, "Repeated recommendations", 455, 292, 310, 44, { size: 24, bold: true, color: C.ink });
  text(slide, "Later registration", 905, 292, 250, 44, { size: 24, bold: true, color: C.ink });
  text(slide, "Immutable 404 evidence", 90, 340, 240, 34, { size: 18, color: "#43545B" });
  text(slide, "Independent sources recur", 455, 340, 310, 34, { size: 18, color: "#43545B" });
  text(slide, "Same logical origin", 905, 340, 250, 34, { size: 18, color: "#43545B" });
  box(slide, 84, 474, 1110, 108, C.ink, 12);
  text(slide, "404 proves absence.  401, 403, 429, 5xx, DNS and TLS failures remain UNKNOWN.", 116, 494, 1048, 66, { size: 25, bold: true });
  note(slide, "Only the approved package metadata endpoint returning 404 earns conclusive absence. Later registration creates a transition without rewriting T0.");
}

// 4. Agent demo
{
  const slide = base("The agent is the primary product surface", 4);
  box(slide, 78, 154, 1124, 412, "#02070A", 14);
  box(slide, 78, 154, 1124, 44, "#12242D", 14);
  text(slide, "PROTECTED AGENT", 102, 160, 220, 30, { size: 15, bold: true, color: C.cyan });
  const terminal = [
    "$ pnpm add @sss-demo/reserved-synthetic@1.0.0",
    "SSS BLOCK — @sss-demo/reserved-synthetic@1.0.0",
    "Absence confidence: 100     Target attractiveness: 95",
    "Package policy risk: 75     Exit code: 23",
    "Installation was not started.",
  ].join("\n");
  text(slide, terminal, 108, 220, 1030, 250, { size: 25, color: C.paper });
  text(slide, "ZERO package-manager children", 108, 490, 520, 40, { size: 20, bold: true, color: C.lime });
  text(slide, "Human intervention created", 700, 490, 430, 40, { size: 20, bold: true, color: C.coral });
  note(slide, "Run the controlled agent fixture. The package-manager shim sees the original argv, calls Guard, records child_started=false and exits 23.");
}

// 5. Approval
{
  const slide = base("Human control stays exact and temporary", 5, C.paper);
  text(slide, "KEEP BLOCKED", 84, 170, 320, 42, { size: 20, bold: true, color: C.coral });
  text(slide, "Default when the operator does nothing", 84, 220, 330, 70, { size: 27, bold: true, color: C.ink });
  text(slide, "ALLOW ONCE", 488, 170, 300, 42, { size: 20, bold: true, color: "#3A7C00" });
  text(slide, "One package, version, registry and artifact hash", 488, 220, 330, 100, { size: 27, bold: true, color: C.ink });
  text(slide, "RETRY", 902, 170, 220, 42, { size: 20, bold: true, color: "#007177" });
  text(slide, "Atomic consume. Changed fields or replay block.", 902, 220, 290, 100, { size: 27, bold: true, color: C.ink });
  box(slide, 84, 420, 1110, 126, C.ink, 12);
  text(slide, "Grant claims", 112, 440, 190, 34, { size: 18, bold: true, color: C.lime });
  text(slide, "package  •  version  •  registry  •  artifact SHA-256  •  project  •  expiry  •  nonce  •  policy", 112, 478, 1040, 44, { size: 21 });
  note(slide, "The operator issues a five minute one-use token. The exact retry consumes it and removes token and nonce from the child environment.");
}

// 6. Exasol
{
  const slide = base("Exasol is the memory and the operating ledger", 6);
  text(slide, "INTELLIGENCE", 90, 166, 280, 34, { size: 17, bold: true, color: C.cyan });
  text(slide, "Immutable observations\nRegistry checks\nRecurrence and transitions", 90, 212, 320, 180, { size: 27, bold: true });
  box(slide, 438, 160, 5, 390, C.lime);
  text(slide, "POLICY", 490, 166, 250, 34, { size: 17, bold: true, color: C.lime });
  text(slide, "Versioned evidence reads\nDeterministic scores\nDecision attestations", 490, 212, 320, 180, { size: 27, bold: true });
  box(slide, 838, 160, 5, 390, C.lime);
  text(slide, "OPERATIONS", 890, 166, 280, 34, { size: 17, bold: true, color: C.coral });
  text(slide, "Attempts and interventions\nSingle-use approvals\nWorker cursors and readiness", 890, 212, 320, 180, { size: 27, bold: true });
  text(slide, "Ordered migrations  •  parameterized queries  •  backup and restore", 90, 584, 1090, 36, { size: 20, color: C.muted, align: "center" });
  note(slide, "Exasol stores both temporal intelligence and durable operational state. API restarts preserve decisions, intervention status and approval consumption.");
}

// 7. Proof
{
  const slide = base("The fixed rehearsal makes the claim testable", 7, C.paper);
  const metrics = [
    ["46", "verified recommendations"],
    ["3", "model configurations"],
    ["8", "client pseudonyms"],
    ["5", "public failed references"],
    ["11", "observation days"],
  ];
  metrics.forEach(([value, label], index) => {
    const x = 66 + index * 238;
    text(slide, value, x, 168, 200, 72, { size: 48, bold: true, color: C.ink, align: "center" });
    text(slide, label, x, 248, 200, 70, { size: 18, color: "#43545B", align: "center" });
  });
  box(slide, 74, 386, 1130, 132, C.ink, 12);
  text(slide, "100", 108, 412, 170, 54, { size: 38, bold: true, color: C.cyan, align: "center" });
  text(slide, "95", 398, 412, 170, 54, { size: 38, bold: true, color: C.lime, align: "center" });
  text(slide, "75", 688, 412, 170, 54, { size: 38, bold: true, color: C.coral, align: "center" });
  text(slide, "exit 23", 978, 412, 170, 54, { size: 38, bold: true, color: C.white, align: "center" });
  text(slide, "absence", 108, 470, 170, 24, { size: 16, color: C.muted, align: "center" });
  text(slide, "attractiveness", 398, 470, 170, 24, { size: 16, color: C.muted, align: "center" });
  text(slide, "policy risk", 688, 470, 170, 24, { size: 16, color: C.muted, align: "center" });
  text(slide, "no child", 978, 470, 170, 24, { size: 16, color: C.muted, align: "center" });
  note(slide, "These fixed synthetic values come from demo/fixtures/fixed-intelligence.json and the committed measurement record. Scores are indices, not probabilities.");
}

// 8. Deployment
{
  const slide = base("Single organization deployment", 8);
  text(slide, "PROTECTED ZONE", 88, 166, 280, 34, { size: 17, bold: true, color: C.lime });
  box(slide, 84, 214, 360, 250, "#10242C", 14);
  text(slide, "Local coding agent\nPackage-manager shims\nNo direct registry route\nNo Docker socket", 116, 244, 296, 185, { size: 25, bold: true });
  text(slide, "CONTROL PLANE", 514, 166, 280, 34, { size: 17, bold: true, color: C.cyan });
  box(slide, 510, 214, 300, 250, "#10242C", 14);
  text(slide, "Guard API\nPrivate Radar\nOperator approvals\nRegistry gateway", 542, 244, 236, 185, { size: 25, bold: true });
  text(slide, "DATA", 878, 166, 220, 34, { size: 17, bold: true, color: C.coral });
  box(slide, 874, 214, 320, 250, "#10242C", 14);
  text(slide, "Exasol Personal\nApproved model endpoint\nFrozen registry origins", 906, 244, 256, 185, { size: 25, bold: true });
  text(slide, "Zero cost local qualification uses Exasol Docker Edition. Cloud infrastructure remains optional and billable.", 90, 538, 1090, 66, { size: 22, color: C.muted, align: "center" });
  note(slide, "Production exposes only the TLS proxy. Host firewall rules restrict control and gateway egress. Exasol Personal is external to the application Compose profile.");
}

// 9. Close
{
  const slide = deck.slides.add();
  slide.background.fill = C.ink;
  box(slide, 70, 88, 14, 530, C.lime);
  text(slide, "Package installs need memory", 126, 142, 960, 90, { size: 52, bold: true });
  text(slide, "SSS remembers the absence, recognizes the transition and stops the agent before execution.", 126, 270, 930, 126, { size: 31, color: C.paper });
  text(slide, "SOURCE  •  RUNBOOK  •  REPRODUCIBLE DEMO", 126, 520, 900, 34, { size: 17, bold: true, color: C.cyan });
  text(slide, "github.com / SSS", 126, 574, 500, 32, { size: 18, color: C.muted });
  note(slide, "Close by returning to the exact terminal proof: block before child execution, then one exact human-authorized retry.");
}

const candidatePath = path.join(stagingDir, "candidate.pptx");
await (await PresentationFile.exportPptx(deck)).save(candidatePath);
const receiptPath = path.join(stagingDir, "SSS-pitch-deck.validation.json");
try {
  await fs.rm(finalPath);
} catch (error) {
  if (error?.code !== "ENOENT") throw error;
}
try {
  await fs.rm(receiptPath);
} catch (error) {
  if (error?.code !== "ENOENT") throw error;
}
await finalizePresentation({
  explicitTotalSlideCount: 9,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  fontPolicy: { basis: "design", families: [family] },
  verifyArtifactToolImport: true,
  receiptPath,
});
console.log(finalPath);

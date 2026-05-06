export const todayConsole = {
  operator: {
    authority: "workspace owner",
    environment: "devint",
    name: "mfshaf7",
    role: "operator",
    sessionMode: "governed session",
  },
  aiRuntime: {
    pluggedProfiles: ["Codex-approved placeholder", "local-provider TBD"],
    policyGate: "approval required before model-backed workflow",
    status: "inactive",
    readiness: [
      {
        detail: "Provider wiring is intentionally dormant until the governed profile is approved.",
        label: "Runtime",
        status: "inactive",
        tone: "warn",
      },
      {
        detail: "Operator has approved Codex-style assist as the first placeholder profile only.",
        label: "Approved profile",
        status: "placeholder",
        tone: "info",
      },
      {
        detail: "No OpenAI API key or external model provider is configured for this prototype.",
        label: "Provider secret",
        status: "missing",
        tone: "muted",
      },
      {
        detail: "Future model context must enter through CGG packet admission, not raw logs.",
        label: "Context gate",
        status: "required",
        tone: "ok",
      },
    ],
  },
  pulse: [
    {
      detail: "No active ART execution front after parking the cybersecurity baseline.",
      label: "Active fronts",
      tone: "ok",
      value: "0",
    },
    {
      detail: "Governed AI assist remains blocked until runtime intake path exists.",
      label: "Blockers",
      tone: "warn",
      value: "1",
    },
    {
      detail: "Cybersecurity baseline and console ART shell are intentionally parked.",
      label: "Parked scope",
      tone: "info",
      value: "2",
    },
    {
      detail: "Closeout-ready items remain visible but are not the active front.",
      label: "Pending review",
      tone: "muted",
      value: "6",
    },
  ],
  todayCommand: {
    focusCards: [
      {
        detail: "Lock the premium command-center layout before wiring live data.",
        label: "Prototype Studio",
        value: "Console candidate",
      },
      {
        detail: "Keep write workflows disabled until identity and durable approval state exist.",
        label: "Boundary",
        value: "Read-only first",
      },
      {
        detail: "Model slots are visible, but every AI path is inactive by default.",
        label: "AI posture",
        value: "Prepared only",
      },
    ],
    nextAction: "Review and refine the Today screen shape",
    summary:
      "The console starts as a premium read-only cockpit. It tells the operator what matters now, what is blocked, what is parked, which controls are proven, and which lane owns the next movement.",
    title: "Approve the first operator cockpit",
  },
  controls: [
    {
      detail: "catalog receipt available",
      name: "WGCF",
      status: "ok",
      tone: "ok",
    },
    {
      detail: "packet admission active for large context",
      name: "CGG",
      status: "ok",
      tone: "ok",
    },
    {
      detail: "projection clean and workflow healthy",
      name: "Delivery ART",
      status: "ok",
      tone: "ok",
    },
    {
      detail: "prototype preview lane pending app profile",
      name: "Devint",
      status: "warn",
      tone: "warn",
    },
  ],
  lastReceipt: "control-receipt:d7406d0b92ce31a0fc74adb3",
  decisions: [
    {
      detail: "Choose whether this Today cockpit is the design baseline candidate.",
      state: "needs operator",
      title: "First-screen direction",
      tone: "info",
    },
    {
      detail: "Governed AI assist waits for runtime intake path and model approval state.",
      state: "blocked",
      title: "#251 governed AI assist",
      tone: "warn",
    },
    {
      detail: "Broad security epic is deferred until a dedicated security tranche is selected.",
      state: "parked",
      title: "#87 cybersecurity baseline",
      tone: "muted",
    },
  ],
  lanes: [
    {
      name: "Prototype Studio",
      next: "design baseline",
      state: "Governance Operations Console candidate is the current shaping lane.",
      tone: "info",
    },
    {
      name: "Delivery ART",
      next: "no active front",
      state: "#251 is blocked; #87 is parked; prototype work is outside heavy ART flow.",
      tone: "muted",
    },
    {
      name: "Platform",
      next: "prototype-devint",
      state: "Preview profile is expected later; no stage or prod release action.",
      tone: "warn",
    },
    {
      name: "Security",
      next: "review 2026-05-21",
      state: "Baseline remains valid but intentionally deferred from active execution.",
      tone: "muted",
    },
    {
      name: "Client Portfolio",
      next: "intake model pending",
      state: "Client delivery views are planned, not exposed or client-visible yet.",
      tone: "muted",
    },
  ],
  signals: [
    {
      detail: "Workspace Prototype Studio is onboarded as the fast lane for internal and client app shaping.",
      title: "Prototype lane established",
    },
    {
      detail: "The cybersecurity baseline was parked to remove active-front confusion.",
      title: "Security front parked",
    },
    {
      detail: "Console surface is read-only with synthetic data and no model invocation.",
      title: "Safe prototype boundary",
    },
  ],
};


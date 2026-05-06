"use client";

import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  Boxes,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock3,
  Gauge,
  GitBranch,
  Layers3,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { motion } from "motion/react";
import { todayConsole } from "../data/today";

type Tone = "ok" | "warn" | "muted" | "info" | "danger";

const toneClass: Record<Tone, string> = {
  danger: "text-[var(--red)]",
  info: "text-[var(--blue)]",
  muted: "text-[var(--subtle)]",
  ok: "text-[var(--green)]",
  warn: "text-[var(--amber)]",
};

function StatusDot({ tone = "ok", pulse = false }: { tone?: Tone; pulse?: boolean }) {
  return (
    <span
      className={[
        "inline-block h-2.5 w-2.5 rounded-full",
        toneClass[tone],
        pulse ? "pulse-orb" : "",
      ].join(" ")}
      style={{ backgroundColor: "currentColor" }}
    />
  );
}

function SectionTitle({
  kicker,
  title,
}: {
  kicker?: string;
  title: string;
}) {
  return (
    <div>
      {kicker ? (
        <p className="mono mb-2 text-[10px] uppercase tracking-[0.28em] text-[var(--subtle)]">
          {kicker}
        </p>
      ) : null}
      <h2 className="text-lg font-semibold tracking-[-0.02em] text-[var(--text)]">
        {title}
      </h2>
    </div>
  );
}

function Panel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.section
      className={`glass-panel rounded-[28px] p-5 ${className}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
    >
      {children}
    </motion.section>
  );
}

function MetricCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
}) {
  return (
    <div className="rounded-2xl border hairline bg-white/[0.045] p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-[var(--muted)]">{label}</span>
        <StatusDot tone={tone} />
      </div>
      <div className="mt-5 flex items-end justify-between gap-3">
        <strong className="text-4xl font-semibold tracking-[-0.08em]">{value}</strong>
        <span className="max-w-[150px] text-right text-xs leading-5 text-[var(--subtle)]">
          {detail}
        </span>
      </div>
    </div>
  );
}

function TopCommandBar() {
  const { operator, aiRuntime } = todayConsole;

  return (
    <Panel className="overflow-hidden p-0">
      <div className="relative p-6 md:p-7">
        <div className="absolute right-0 top-0 h-40 w-72 rounded-bl-full bg-[rgba(88,227,208,0.11)] blur-3xl" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="mono mb-3 text-xs uppercase tracking-[0.32em] text-[var(--teal)]">
              Workspace Governance Console
            </p>
            <h1 className="max-w-3xl text-4xl font-semibold tracking-[-0.055em] text-[var(--text)] md:text-6xl">
              Today
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--muted)]">
              A calm command surface for work-state truth, control proof,
              parked scope, and operator decisions before any model-backed
              workflow is activated.
            </p>
          </div>

          <div className="grid min-w-full gap-3 md:min-w-[520px] md:grid-cols-2">
            <div className="rounded-2xl border hairline bg-black/20 p-4">
              <div className="mb-4 flex items-center gap-2 text-sm font-medium">
                <UserRound className="h-4 w-4 text-[var(--teal)]" />
                Logged in operator
              </div>
              <p className="text-lg font-semibold">{operator.name}</p>
              <p className="mt-1 text-sm text-[var(--muted)]">
                {operator.role} / {operator.authority}
              </p>
              <p className="mono mt-4 text-xs uppercase tracking-[0.2em] text-[var(--subtle)]">
                {operator.environment} / {operator.sessionMode}
              </p>
            </div>

            <div className="rounded-2xl border hairline bg-black/20 p-4">
              <div className="mb-4 flex items-center gap-2 text-sm font-medium">
                <Bot className="h-4 w-4 text-[var(--amber)]" />
                AI runtime
              </div>
              <div className="flex items-center justify-between">
                <p className="text-lg font-semibold">{aiRuntime.status}</p>
                <span className="rounded-full border border-[rgba(231,185,91,0.34)] bg-[rgba(231,185,91,0.08)] px-3 py-1 text-xs text-[var(--amber)]">
                  not active
                </span>
              </div>
              <p className="mt-1 text-sm text-[var(--muted)]">{aiRuntime.policyGate}</p>
              <p className="mono mt-4 text-xs uppercase tracking-[0.2em] text-[var(--subtle)]">
                {aiRuntime.pluggedProfiles.join(" / ")}
              </p>
            </div>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function WorkspacePulse() {
  return (
    <Panel>
      <SectionTitle kicker="Workspace Pulse" title="Operating posture" />
      <div className="mt-5 grid gap-3">
        {todayConsole.pulse.map((metric) => (
          <MetricCard key={metric.label} {...metric} tone={metric.tone as Tone} />
        ))}
      </div>
      <div className="mt-5 rounded-2xl border border-[rgba(88,227,208,0.22)] bg-[rgba(88,227,208,0.07)] p-4">
        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-[var(--teal)]">
          <Gauge className="h-4 w-4" />
          System mood
        </div>
        <p className="text-2xl font-semibold tracking-[-0.04em]">Calm / no fire</p>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          Active execution is intentionally quiet while the operator shapes the
          console surface.
        </p>
      </div>
    </Panel>
  );
}

function TodayCommand() {
  const command = todayConsole.todayCommand;

  return (
    <Panel className="relative overflow-hidden">
      <div className="absolute right-[-80px] top-[-80px] h-64 w-64 rounded-full bg-[rgba(122,167,255,0.16)] blur-3xl" />
      <div className="relative">
        <SectionTitle kicker="Today's Command" title={command.title} />
        <p className="mt-4 max-w-2xl text-lg leading-8 text-[var(--muted)]">
          {command.summary}
        </p>
        <div className="mt-7 rounded-3xl border border-[rgba(88,227,208,0.28)] bg-[rgba(88,227,208,0.08)] p-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="mono text-xs uppercase tracking-[0.25em] text-[var(--teal)]">
                Next safe action
              </p>
              <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">
                {command.nextAction}
              </p>
            </div>
            <div className="flex items-center gap-2 rounded-full border hairline bg-black/25 px-4 py-2 text-sm text-[var(--muted)]">
              <LockKeyhole className="h-4 w-4 text-[var(--amber)]" />
              read-only prototype
            </div>
          </div>
        </div>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {command.focusCards.map((card) => (
            <div key={card.label} className="rounded-2xl border hairline bg-white/[0.045] p-4">
              <p className="mono text-[10px] uppercase tracking-[0.22em] text-[var(--subtle)]">
                {card.label}
              </p>
              <p className="mt-3 text-base font-semibold">{card.value}</p>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{card.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function ControlProof() {
  return (
    <Panel>
      <SectionTitle kicker="Control Proof" title="Receipt posture" />
      <div className="mt-5 space-y-3">
        {todayConsole.controls.map((control) => (
          <div
            key={control.name}
            className="flex items-center justify-between rounded-2xl border hairline bg-white/[0.045] px-4 py-3"
          >
            <div className="flex items-center gap-3">
              <StatusDot tone={control.tone as Tone} pulse={control.tone === "ok"} />
              <div>
                <p className="font-medium">{control.name}</p>
                <p className="text-xs text-[var(--subtle)]">{control.detail}</p>
              </div>
            </div>
            <span className="mono text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
              {control.status}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-5 rounded-2xl border hairline bg-black/20 p-4">
        <p className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--subtle)]">
          Last receipt
        </p>
        <p className="mt-3 text-sm text-[var(--muted)]">{todayConsole.lastReceipt}</p>
      </div>
    </Panel>
  );
}

function DecisionQueue() {
  return (
    <Panel className="lg:col-span-2">
      <SectionTitle kicker="Decision Queue" title="What needs operator attention" />
      <div className="mt-5 divide-y divide-[rgba(245,239,226,0.11)] overflow-hidden rounded-3xl border hairline bg-black/20">
        {todayConsole.decisions.map((decision) => (
          <div key={decision.title} className="grid gap-4 p-4 md:grid-cols-[180px_1fr_auto] md:items-center">
            <div className="flex items-center gap-2">
              {decision.tone === "warn" ? (
                <AlertTriangle className="h-4 w-4 text-[var(--amber)]" />
              ) : decision.tone === "ok" ? (
                <CheckCircle2 className="h-4 w-4 text-[var(--green)]" />
              ) : (
                <CircleDot className="h-4 w-4 text-[var(--blue)]" />
              )}
              <span className="mono text-xs uppercase tracking-[0.2em] text-[var(--subtle)]">
                {decision.state}
              </span>
            </div>
            <div>
              <p className="font-semibold">{decision.title}</p>
              <p className="mt-1 text-sm leading-6 text-[var(--muted)]">
                {decision.detail}
              </p>
            </div>
            <ChevronRight className="hidden h-5 w-5 text-[var(--subtle)] md:block" />
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ModelReadiness() {
  const { aiRuntime } = todayConsole;

  return (
    <Panel>
      <SectionTitle kicker="AI / Model Readiness" title="Prepared, not active" />
      <div className="mt-5 space-y-4">
        {aiRuntime.readiness.map((item) => (
          <div key={item.label} className="rounded-2xl border hairline bg-white/[0.045] p-4">
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm text-[var(--muted)]">{item.label}</p>
              <span className={`mono text-xs uppercase tracking-[0.18em] ${toneClass[item.tone as Tone]}`}>
                {item.status}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--subtle)]">{item.detail}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Lanes() {
  const icons = [Sparkles, GitBranch, Boxes, ShieldCheck, Layers3];

  return (
    <Panel className="lg:col-span-3">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <SectionTitle kicker="Lanes" title="Where work is moving" />
        <p className="max-w-2xl text-sm leading-6 text-[var(--muted)]">
          Lanes separate prototype work, delivery truth, platform runtime,
          security posture, and future client portfolio visibility so the
          operator does not confuse parked scope with executable work.
        </p>
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        {todayConsole.lanes.map((lane, index) => {
          const Icon = icons[index] ?? Activity;
          return (
            <div
              key={lane.name}
              className="group relative overflow-hidden rounded-3xl border hairline bg-white/[0.045] p-5 transition duration-300 hover:border-[rgba(88,227,208,0.36)] hover:bg-white/[0.07]"
            >
              <div className="absolute right-[-40px] top-[-40px] h-28 w-28 rounded-full bg-[rgba(88,227,208,0.08)] blur-2xl transition duration-300 group-hover:bg-[rgba(88,227,208,0.16)]" />
              <div className="relative">
                <div className="mb-5 flex items-center justify-between">
                  <span className="rounded-2xl border hairline bg-black/25 p-2">
                    <Icon className="h-5 w-5 text-[var(--teal)]" />
                  </span>
                  <StatusDot tone={lane.tone as Tone} />
                </div>
                <p className="text-lg font-semibold tracking-[-0.03em]">{lane.name}</p>
                <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{lane.state}</p>
                <p className="mono mt-5 text-[10px] uppercase tracking-[0.22em] text-[var(--subtle)]">
                  {lane.next}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function ActivityStrip() {
  return (
    <Panel className="lg:col-span-3">
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <div>
          <SectionTitle kicker="Timeline" title="Recent operator-safe signals" />
          <div className="mt-5 grid gap-3">
            {todayConsole.signals.map((signal) => (
              <div key={signal.title} className="flex gap-4 rounded-2xl border hairline bg-black/20 p-4">
                <Clock3 className="mt-1 h-4 w-4 shrink-0 text-[var(--blue)]" />
                <div>
                  <p className="font-medium">{signal.title}</p>
                  <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{signal.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-3xl border border-[rgba(122,167,255,0.22)] bg-[rgba(122,167,255,0.07)] p-5">
          <p className="mono text-[10px] uppercase tracking-[0.24em] text-[var(--blue)]">
            Prototype proof
          </p>
          <p className="mt-4 text-2xl font-semibold tracking-[-0.04em]">
            Synthetic data only
          </p>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            This screen proves the operator experience before wiring to OOS,
            WGCF, CGG, platform runtime, identity, or model providers.
          </p>
          <div className="mt-5 flex items-center gap-2 text-sm text-[var(--teal)]">
            <ArrowUpRight className="h-4 w-4" />
            Ready for design baseline review
          </div>
        </div>
      </div>
    </Panel>
  );
}

export default function TodayPage() {
  return (
    <main className="console-shell">
      <div className="console-stage space-y-5">
        <TopCommandBar />
        <div className="grid gap-5 lg:grid-cols-[320px_1fr_360px]">
          <WorkspacePulse />
          <TodayCommand />
          <ControlProof />
          <DecisionQueue />
          <ModelReadiness />
          <Lanes />
          <ActivityStrip />
        </div>
      </div>
    </main>
  );
}


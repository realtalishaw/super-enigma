# Weave Linter & Validator — Technical Specification

**Owner:** Workflow Platform
**Last updated:** Aug 2025
**Scope:** Validation, linting, and auto-repair for Template, Executable, and DAG workflow specs

## 1) Purpose & Non-Goals

### Purpose

* **Block** unsafe/invalid workflows before execution (hard errors).
* **Surface** best-practice risks (warnings/hints) without blocking.
* **Auto-repair** fixable issues deterministically.
* **Guarantee** that only well-formed DAGs reach the Executor.

### Non-Goals

* Running workflows (Executor).
* Scheduling (Cron Scheduler).
* Managing provider auth (Connections service).

---

## 2) Core Concepts

* **Template JSON** (authoring): high-level intent, placeholders allowed.
* **Executable JSON** (resolved): concrete tools, connections, inputs/params.
* **DAG JSON** (runtime graph): nodes, edges, routing semantics for the Executor.

Each stage has **Validators** (hard pass/fail) and **Linters** (soft guidance/repairs).

---

## 3) Architecture

```
Authoring UI / API
      │
      ▼
┌───────────────────────────────┐
│   Stage Validators & Linters  │  ← library + service
│  ┌───────────┐ ┌───────────┐  │
│  │ Template  │ │ Executable│  │
│  └───────────┘ └───────────┘  │
│        ┌───────────────┐      │
│        │      DAG      │      │
│        └───────────────┘      │
│            ▲   ▲   ▲          │
│   Catalog  │   │   │  Dataflow/Expr Engine
└────────────┴───┴───┴──────────┘
      │ compiled plan / dag
      ▼
   Compiler(s)  ──►  Executor
```

**Deploy modes**

* **Library** (preferred): imported by compilers, API servers, CLI.
* **Service** (optional): HTTP/GRPC façade for UI or other microservices.

---

## 4) Interfaces (Library & Service)

### 4.1 Library API

```ts
// Stage-typed inputs with discriminators
type Stage = "template" | "executable" | "dag";

interface ValidateOptions { fast?: boolean; failFast?: boolean }
interface LintOptions { level?: "standard"|"strict"; maxFindings?: number }

interface ValidationError {
  code: string; path: string; message: string; stage: Stage; meta?: any;
}
interface LintFinding {
  code: string; severity: "ERROR"|"WARNING"|"HINT";
  path: string; message: string; hint?: string; docs?: string; meta?: any;
}
interface LintReport { errors: LintFinding[]; warnings: LintFinding[]; hints: LintFinding[] }

interface ValidateResponse { ok: boolean; errors: ValidationError[] }
interface CompileResponse { ok: boolean; compiled?: any; errors?: ValidationError[]; lint?: LintReport }
interface RepairRecord { ruleCode: string; description: string; beforePath: string; afterPath: string; }

function validate(stage: Stage, doc: any, opts?: ValidateOptions): ValidateResponse;
function lint(stage: Stage, doc: any, ctx: LintContext, opts?: LintOptions): LintReport;
function attemptRepair(stage: Stage, doc: any, lint: LintReport): { patched: any; repairs: RepairRecord[] };

function validateAndCompile(
  concreteDoc: any,
  ctx: CompileContext
): CompileResponse;
```

**Contexts**

```ts
interface Catalog { /* in-memory provider/actions/params/scopes */ }
interface Connections { /* map connection_id -> scopes/status */ }
interface LintContext { catalog: Catalog; connections?: Connections; tenantConfig?: TenantConfig }
interface CompileContext extends LintContext { compilerFlags?: Record<string,any> }
```

### 4.2 Service API (optional)

* `POST /lint/{stage}` → `LintReport`
* `POST /validate/{stage}` → `ValidateResponse`
* `POST /validate-compile` → `CompileResponse`
* `POST /attempt-repair/{stage}` → patched doc + `repairs[]`

Service auth: mTLS or service JWT; rate-limit per tenant.

---

## 5) Validators (Hard, Stage-Specific)

### 5.1 Template Validator

* JSON Schema conformance (types/enums/required).
* Triggers/actions minimally specified; placeholders **allowed**.
* Flow-control syntax valid (conditions structure).
* Missing info prompts valid (prompt text/type/name).

### 5.2 Executable Validator

* JSON Schema conformance for fully-resolved fields.
* Provider/tool/action exist in **Catalog**.
* **Parameters**: required present, types/enum within spec, no extra unknowns.
* **Connections**: referenced `connection_id` exists; **scopes** cover action needs.
* Triggers: concrete `trigger_slug`, configuration, filters verified.
* Schedules: cron + tz valid; constraints coherent (`start_at <= end_at`).

### 5.3 DAG Validator

* Graph integrity: unique node IDs; edges reference existing nodes.
* Node shape: `{id, type, data}`; edge shape: `{source, target, condition? when?}`.
* Acyclicity (except explicit loop constructs), reachable from at least one trigger.
* Expression validation: parseable, safe subset; refers only to allowed namespaces (`inputs`, `vars`, `globals`, upstream outputs).
* Dataflow: refs resolved to producer nodes; type bridges are valid or flagged.
* Join soundness: join modes `all/any/quorum` with coherent incoming edges.

**Return:** `ok=false` + structured errors; no auto-repair at validator layer.

---

## 6) Linters (Soft Guidance + Repairs)

### 6.1 Rule Registry

* Rules defined via a registry with metadata and handlers per stage.
* Configurable severities per tenant; toggle-able; parameters per rule.
* Each rule:

  * `id` (e.g., `E001`, `W202`), `stage`, `severity`, `message`, `docs`, `autoRepairable?`.
  * `applies(doc, ctx) => boolean`
  * `check(doc, ctx) => LintFinding[]`
  * optional `repair(doc, finding) => Patch[]`

Example registration:

```ts
registerRule({
  id: "E001",
  stage: ["template","executable"],
  severity: "ERROR",
  message: "Unknown provider/action/trigger",
  docs: "/rules/E001",
  applies: (doc, ctx) => true,
  check: (doc, ctx) => checkUnknownTool(doc, ctx.catalog),
});
```

### 6.2 Canonical Rule Sets (initial)

**A. Catalog & Tooling**

* `E001 UnknownTool`
* `E002 ParamSpecMismatch`
* `E003 DeliveryUnsupported`
* `E004 ScopeMissing`
* `E005 RateLimitConfigMissing`
* `W101 DeprecatedAction`
* `W102 VersionDrift`
* `W103 MissingRecommendedParam`

**B. Graph & Dataflow**

* `E006 CycleInGraph`
* `E007 DisconnectedNode`
* `E008 UnresolvedRef`
* `E009 TypeBridgeMissing` *(auto-repair: insert transform node)*
* `W201 AggressiveFanout`
* `W202 MissingChoiceGuard`
* `W203 WeakTriggerFilter`

**C. Triggers & Schedules**

* `E010 CronInvalid`
* `E011 PollNoCursor` *(auto-repair: add cursor settings)*
* `E012 WebhookNoVerify` *(auto-repair: enable verification)*
* `W301 ScheduleDSTRisk`
* `W302 PollIntervalHot`

**D. Security & Secrets**

* `E013 PlaintextSecret` *(auto-repair: replace with secret ref)*
* `E014 TokenLeakPath`
* `W401 PiiInLogs`
* `W402 BroadScopes`

**E. Execution Safety & Cost**

* `E015 ForbiddenStepType`
* `E016 ExternalHTTPUnvetted`
* `W501 NoIdempotency`
* `W502 MissingRetryPolicy`
* `W503 LargePayloadRisk`
* `W504 CostlyLLMStep`

**F. Consent & Privacy**

* `E017 ConsentMissing`
* `W601 ConsentStale`

**G. Observability**

* `W701 NoNotifyOnError`
* `W702 SparseAudit`

**H. Provider-Specific**

* `E018 ProviderQuirkViolation`
* `W801 ProviderQuotaRisk`

> The mapping above reflects your earlier rule taxonomy; keep codes stable for developer familiarity.

---

## 7) Expression & Dataflow Engine

* **Expression Parser**: safe, deterministic subset (boolean ops, comparisons, `len()`, null checks); time-boxed; no side effects.
* **Reference Resolver**: JSONPath/JMESPath-like over `inputs`, `vars`, `globals`, `node[id].outputs`.
* **Dataflow Index**: map producers → consumers; detect unresolved refs and unreachable nodes.
* **Type System**: lightweight shape/type descriptors from Catalog (e.g., `image`, `text`, `array<string>`).

---

## 8) Auto-Repair Framework

* **Patch model**: JSON-patch style edits (`add`/`replace`/`remove`) with `path` and `value`.
* **Deterministic**: repairs must be idempotent; produce `RepairRecord[]`.
* **Chain**: run repairs → re-validate → re-lint; stop on any new ERRORs.

Common repairs:

* Insert typed transform node for `E009 TypeBridgeMissing`.
* Add default rate limit bucket for `E005`.
* Add cursor/dedupe config for `E011`.
* Enable webhook signature verify for `E012`.
* Replace inline secret with connection/secret ref for `E013`.

---

## 9) Compile Orchestration

`validateAndCompile(concreteDoc, ctx)` pipeline:

1. `validate("executable", concreteDoc)` → fail on errors.
2. `lint("executable", concreteDoc, ctx)` → warnings/hints; **attemptRepair** on repairable **ERRORs** only.
3. Re-validate + re-lint if repaired.
4. **Compile** to DAG (lowering conditions/parallel groups).
5. `validate("dag", dag)` + `lint("dag", dag, ctx)`.
6. Return `{ ok, compiled: dag, lint }`. Block persistence if any **ERROR** remains.

*Executor preflight* may call a **fast** `validate("dag", …, {fast:true})` for runtime-only checks (auth presence, resolvable slugs, etc.).

---

## 10) Config & Policy

* YAML/JSON config per tenant:

  * Enable/disable rules.
  * Override severities (e.g., `W→E`).
  * Rule parameters (e.g., `W201.maxFanout=8`).
  * Allowed outbound domains for `E016`.
* Inline suppressions (warnings only):

  * `doc.observability.suppress: ["W701"]` with justification.
  * **Never** suppress `ERROR` class.

---

## 11) Performance SLOs

* **Schema validation:** < 50ms simple, < 120ms complex.
* **Catalog validation:** < 120ms cached, < 400ms if refresh needed.
* **Linting:** < 200ms simple, < 500ms complex, with `maxFindings` cutoff.
* **Auto-repair:** < 300ms typical; < 1s worst-case.
* Memory cap per doc: ≤ 32MB.
* Provide `fast` mode for executor preflight (< 30ms).

---

## 12) Observability

* **Metrics**:

  * `validator.errors_total{stage,code}`
  * `linter.findings_total{stage,code,severity}`
  * `autorepair.applied_total{rule}`
  * latencies histograms per phase
* **Logs**:

  * Structured JSON with doc `id/version`, stage, rule code, path.
  * Redact secrets/PII by default.
* **Tracing**:

  * Spans: `validate_template`, `lint_executable`, `compile_to_dag`, etc.

---

## 13) Testing & CI

* **Golden cases** matching your earlier list:

  * Happy path (Gmail→Slack).
  * E001/E002/E013/E015, E009 with auto-repair, E011 with auto-repair.
  * W203/W701/W402, etc.
* **Fuzzing**:

  * Expression parser robustness.
  * Graph edge-cases: large fan-outs, deep chains, missing producers.
* **Performance**:

  * Benchmark suites in CI; alert on regressions > 15%.

CLI examples:

```bash
weave lint --stage executable examples/complex.json
weave validate --stage dag out/dag.json
weave fix --stage executable examples/broken.json --out examples/fixed.json
```

---

## 14) Security

* Static denylist rules for secrets in params/headers (`E013`, `E014`).
* Allowed domains & timeouts for external HTTP (`E016`).
* Rule evaluation sandboxed; expressions have CPU & time limits.
* All logs pass through redaction filters.

---

## 15) Migration & Rollout

1. **Phase 1 (shadow)**: run new linter/validator alongside existing, compare findings; no blocking.
2. **Phase 2 (warn)**: surface new warnings/hints to authors; still no blocks.
3. **Phase 3 (enforce)**: enable ERROR blocks in create/update paths.
4. **Phase 4 (executor preflight)**: switch executor to fast validation; gate on ERROR if somehow bypassed.

Backward compatibility:

* Maintain existing rule codes/names where possible.
* Provide a code-map for renamed rules.

---

## 16) Example End-to-End

```ts
// Create/update workflow
const v1 = validate("template", templateDoc);
if (!v1.ok) return 400;

const v2 = validate("executable", execDoc);
if (!v2.ok) return 400;

const lintExec = lint("executable", execDoc, ctx);
const repaired = attemptRepair("executable", execDoc, lintExec);
// Re-run checks if repaired
const execReady = repaired ? repaired.patched : execDoc;

const compileRes = validateAndCompile(execReady, ctx);
if (!compileRes.ok) return 400;             // contains dag validation & lint report

// Persist DAG + lint report
storeCompiled(workflowId, compileRes.compiled, compileRes.lint);
```

---

## 17) Implementation Plan (milestones)

* **M1:** Stage schemas + base validators (Template/Executable/DAG).
* **M2:** Catalog integration (UnknownTool, ParamSpec, Scopes).
* **M3:** Expression/Dataflow engine; Graph checks.
* **M4:** Core lint set + auto-repairs (E009, E011, E012, E013, E005).
* **M5:** Service façade + CLI; metrics & tracing.
* **M6:** Shadow → Warn → Enforce rollout.

---

### TL;DR

* One **shared module**, three **stage profiles**.
* Validators = **must pass**; Linters = **warn/fix**.
* Deterministic **auto-repairs** with audit.
* Fast executor preflight; rich CI + telemetry.
* Backward-compatible with your earlier rules and codes.

# cron scheduler — technical specification

## 1) purpose & scope

The **Cron Scheduler** fires schedule-based triggers at the right times and starts workflow runs via **RunLauncher**. It does not execute DAGs, does not talk to Composio, and does not manage actions. It only keeps time and initiates runs.

**Goals**

* Register/modify/pause schedules when workflows are deployed or edited.
* Wake up on time (timezone/DST aware), apply overlap & catch-up policies.
* Start runs exactly once per tick (idempotent), even across restarts.
* Provide basic observability (next fire time, recent runs).

**Non-goals**

* Executing node actions (Executor’s job).
* Managing event/webhook triggers (Composio + your webhook handler do that).
* Long-term run history (Executor/Run DB handle that).

---

## 2) architecture

**Components**

* **Scheduler Registrar (library/endpoint)**: Upserts schedules during workflow deploy/compile.
* **Scheduler Worker (process/service)**: Scans due schedules and starts runs.
* **RunLauncher (library/endpoint)**: Loads DAG JSON and calls Executor.
* **Workflow Store**: Where DAG JSONs are stored (DB or object store).
* **Scheduler DB**: Two small tables: `schedules`, `schedule_runs`.

**Call paths**

* Compiler/Deployer → `SchedulerRegistrar.upsert(...)`
* Scheduler Worker → `RunLauncher.start(workflow_id, version, user_id, run_at, idem_key)`
* RunLauncher → `Executor.run(dag_json, meta)`

---

## 3) data model

### `schedules`

* `schedule_id` (PK, string) – deterministic or generated.
* `workflow_id` (string)
* `version` (int)
* `user_id` (string)
* `cron_expr` (string, standard 5-field or 6-field)
* `timezone` (string, IANA tz like `America/New_York`)
* `start_at` (timestamp, optional)
* `end_at` (timestamp, optional)
* `next_run_at` (timestamp, UTC, computed)
* `paused` (bool, default false)
* `jitter_ms` (int, default 0)
* `overlap_policy` (`'allow'|'skip'|'queue'`, default `'skip'`)
* `catchup_policy` (`'none'|'fire_immediately'|'spread'`, default `'none'`)
* `updated_at` (timestamp)

### `schedule_runs`

* `idempotency_key` (PK, string) – `sha256(schedule_id + ":" + epoch(run_at))`
* `schedule_id` (string, FK)
* `run_at` (timestamp, tz-aware planned time)
* `status` (`'ENQUEUED'|'STARTED'|'SUCCESS'|'FAILED'|'SKIPPED'`)
* `run_id` (string, optional—assigned by Executor)
* `created_at`, `updated_at` (timestamp)

---

## 4) public interface (callable from code or HTTP)

Choose internal function calls if all services live in one repo; expose HTTP only if you want microservice boundaries. The semantics are identical.

### Registrar

* `upsert_schedule(input) -> { schedule_id, next_run_at }`

  * `input`: `{ schedule_id?, workflow_id, version, user_id, cron_expr, timezone, start_at?, end_at?, jitter_ms?, overlap_policy?, catchup_policy? }`
* `pause_schedule(schedule_id, paused: boolean) -> void`
* `delete_schedule(schedule_id) -> void`
* `get_schedule(schedule_id) -> Schedule + preview(next 5 fire times)`

### Worker → RunLauncher

* `RunLauncher.start(workflow_id, version, user_id, scheduled_for, idempotency_key) -> bool`

> If you prefer HTTP:
>
> * `POST /schedules/upsert`, `POST /schedules/pause`, `DELETE /schedules/:id`, `GET /schedules/:id`
> * `POST /run-launcher/start`

---

## 5) life cycle

**Register (during deploy/compile)**

1. Detect `schedule_based` triggers in the executable/DAG.
2. Call `upsert_schedule(...)`.
3. Registrar validates CRON & tz, stores row, and precomputes `next_run_at`.

**Tick**

1. Worker wakes every 1s (configurable), fetches schedules with `next_run_at <= now + lookahead`.
2. For each, expands all due `run_at` times within the window honoring tz and DST.
3. For each `run_at`:

   * Build `idempotency_key`.
   * Apply **overlap\_policy**:

     * `'allow'`: always fire.
     * `'skip'`: if an inflight schedule run exists, mark this `SKIPPED`.
     * `'queue'`: if inflight exists, stop emitting more for this schedule this tick.
   * Apply **catchup\_policy** for missed ticks during downtime.
   * Apply **jitter** (± up to `jitter_ms`).
   * Call `RunLauncher.start(...)`.
   * Insert `schedule_runs` with `'ENQUEUED'` or `'FAILED'`.

**Advance**

* After processing, set `next_run_at = cron_next_after(last_considered_time)` and save.

---

## 6) policies

* **overlap\_policy**

  * `allow`: multiple concurrent runs per schedule.
  * `skip`: drop a tick if prior run hasn’t finished.
  * `queue`: defer until prior finishes (serial execution).

* **catchup\_policy**

  * `none`: ignore missed times during downtime.
  * `fire_immediately`: emit all missed ticks next wake.
  * `spread`: distribute missed ticks across the lookahead window.

* **jitter**

  * Random offset to `run_at` to avoid thundering herd: `uniform(-jitter_ms, +jitter_ms)`.

---

## 7) failure handling & idempotency

* **Idempotency**: Always compute `idempotency_key = sha256(schedule_id + ":" + epoch_seconds(run_at))`. If a row with that key exists in `schedule_runs`, skip starting another run.
* **Retries to RunLauncher**: Retry a few times with small backoff; if still failing, record `'FAILED'` for that tick.
* **Worker restart**: On boot, worker simply resumes from DB; missed ticks are handled per `catchup_policy`.
* **Executor feedback (optional)**: If Executor can call back with run status, you can update `schedule_runs.status` → `'STARTED'|'SUCCESS'|'FAILED'`. Nice-to-have, not required.

---

## 8) concurrency & deployment

* **Single instance** is fine to start.
* **Multi-instance**: use a leader lock (e.g., Redis `SETNX` or Postgres advisory lock) so only one worker scans at a time. Others sleep.
* **Scaling out**: If Worker → RunLauncher volume is high, you can:

  * Replace direct calls with a queue (SQS/Redis/Rabbit) that the RunLauncher consumes.
  * Shard schedules by hash and run multiple workers each owning a shard.

---

## 9) observability

* Logs: schedule decisions, run emissions, reasons for SKIPPED/FAILED.
* Metrics:

  * `schedules_due`, `runs_emitted`, `runs_skipped_overlap`, `runs_failed_launch`
  * scheduling drift histogram: `abs(actual_fire_ts - planned_run_at)`
* Admin endpoints: list next 5 fire times, last N runs per schedule.

---

## 10) security

* If exposing HTTP, require service-to-service auth (mTLS or signed JWT).
* Validate CRON syntax and tz against allowlist.
* Bound lookahead window to prevent emitting a storm of catch-up runs.

---

## 11) configuration

* `TICK_MS` (default 1000)
* `LOOKAHEAD_MS` (default 60000)
* `MAX_CATCHUP_PER_TICK` (default 100)
* `DEFAULT_OVERLAP_POLICY` (`skip`)
* `DEFAULT_CATCHUP_POLICY` (`none`)
* `DEFAULT_JITTER_MS` (0)

---

## 12) pseudo-code (copy-ready)

### Registrar

```text
function upsert_schedule(input):
    assert valid_cron(input.cron_expr)
    assert valid_tz(input.timezone)

    id   = input.schedule_id or gen_id()
    now  = now_utc()
    base = max(now, input.start_at or now)
    next = cron_next_after(input.cron_expr, input.timezone, base)

    db.upsert("schedules", {
      schedule_id:    id,
      workflow_id:    input.workflow_id,
      version:        input.version,
      user_id:        input.user_id,
      cron_expr:      input.cron_expr,
      timezone:       input.timezone,
      start_at:       input.start_at,
      end_at:         input.end_at,
      next_run_at:    next,
      paused:         false,
      jitter_ms:      input.jitter_ms or 0,
      overlap_policy: input.overlap_policy or 'skip',
      catchup_policy: input.catchup_policy or 'none',
      updated_at:     now
    })

    return { schedule_id: id, next_run_at: next }
```

### Worker

```text
BOOT:
  db        = connect_db()
  tick_ms   = env.TICK_MS or 1000
  lookahead = env.LOOKAHEAD_MS or 60000
  leader    = try_acquire_leader_lock()   # no-op if single instance

LOOP:
  if leader and !leader.alive(): leader = try_acquire_leader_lock()
  if leader and !leader.owned(): sleep(tick_ms); continue

  now = now_utc()
  due = db.query(`
      SELECT * FROM schedules
       WHERE paused = false
         AND (end_at IS NULL OR end_at >= ?)
         AND next_run_at <= ?
  `, [now, now + lookahead])

  for sched in due:
    run_times = enumerate_due_times(sched, now, lookahead)

    for run_at in run_times:
      idem = sha256(sched.schedule_id + ":" + epoch_seconds(run_at))
      if db.exists("schedule_runs", {idempotency_key: idem}): continue

      if sched.overlap_policy != 'allow' and has_inflight(sched.schedule_id):
        if sched.overlap_policy == 'skip':
          insert_run(sched.schedule_id, run_at, 'SKIPPED', idem); continue
        if sched.overlap_policy == 'queue':
          break  # stop emitting more for this schedule now

      fire_at = apply_jitter(run_at, sched.jitter_ms)
      if fire_at <= now:
        ok = RunLauncher.start(sched.workflow_id, sched.version, sched.user_id, run_at, idem)
        insert_run(sched.schedule_id, run_at, ok ? 'ENQUEUED' : 'FAILED', idem)
      else:
        schedule_timer(fire_at, () => {
          ok = RunLauncher.start(sched.workflow_id, sched.version, sched.user_id, run_at, idem)
          insert_run(sched.schedule_id, run_at, ok ? 'ENQUEUED' : 'FAILED', idem)
        })

    last_considered = max(now, last(run_times) or sched.next_run_at)
    next = cron_next_after(sched.cron_expr, sched.timezone, last_considered)
    db.update("schedules", {schedule_id: sched.schedule_id}, {next_run_at: next, updated_at: now})

  sleep(tick_ms)
```

### Helpers

```text
function enumerate_due_times(sched, now, lookahead):
  times = []
  t = sched.next_run_at
  horizon = now + lookahead
  while t <= horizon:
    if in_window(t, sched.start_at, sched.end_at): times.push(t)
    t = cron_next_after(sched.cron_expr, sched.timezone, t)

  switch sched.catchup_policy:
    case 'none':            return filter(times, t => t >= now)
    case 'fire_immediately':return times
    case 'spread':          return spread_across_window(times, horizon - now)

function has_inflight(schedule_id):
  n = db.scalar(`
    SELECT COUNT(*) FROM schedule_runs
     WHERE schedule_id = ? AND status IN ('ENQUEUED','STARTED')
  `, [schedule_id])
  return n > 0

function insert_run(schedule_id, run_at, status, idem):
  db.insert("schedule_runs", {
    idempotency_key: idem,
    schedule_id: schedule_id,
    run_at: run_at,
    status: status,
    created_at: now_utc(),
    updated_at: now_utc()
  })
```

### RunLauncher

```text
object RunLauncher:
  function start(workflow_id, version, user_id, scheduled_for, idempotency_key):
    dag = WorkflowStore.load_dag(workflow_id, version)
    if not dag: return false

    # In-process call or RPC/HTTP to executor
    Executor.run(dag, {
      source: 'schedule',
      user_id: user_id,
      scheduled_for: scheduled_for,
      idempotency_key: idempotency_key
    })
    return true
```

### Cron iterator (tz/DST-aware)

```text
function cron_next_after(cron_expr, timezone, after_ts):
  # Use a cron library that supports IANA tz and DST.
  # Pseudocode: croniter_tz(cron_expr, timezone).next(after_ts)
  return croniter_tz_next(cron_expr, timezone, after_ts)
```

---

## 13) notes & trade-offs

* You can run **Scheduler Worker + RunLauncher** in the same process to start. Later, split them if you need scaling or boundaries.
* If you ever add a queue: Worker publishes messages; RunLauncher consumes them. The rest of the spec stays unchanged.
* The Executor remains untouched and only ever receives **DAG JSON**.

want me to also drop a tiny JSON example for `upsert_schedule` that your compiler can call during “deploy”?

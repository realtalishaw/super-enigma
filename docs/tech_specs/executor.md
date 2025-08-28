# Execution Engine — Complete Pseudo-Code (copy-ready)

> Language-agnostic, single-process orchestrator. Assumes you receive Composio webhooks and call the executor inline. Includes idempotency, retries, IF/ELSE, parallel, joins, and loops.

## Inputs

* **DAG JSON** conforming to your schema (nodes with `{ id, type, data }`, edges `{ source, target, condition? }`) .
* **Event payload** from Composio (for event-based triggers) or a **tick** (for schedules).

---

## Step 0 — Boot

```
state_store  := connect_db()        # tables: runs, node_executions, joins
idem_cache   := connect_cache()     # idempotency keys -> compact outputs
metrics      := init_metrics()
tracer       := init_tracer()
```

---

## Step 1 — Tiny Preflight (runtime safety, not schema validation)

```
assert DAG.nodes not empty
assert all edge.source/edge.target reference existing nodes
defaults.retry   := DAG.globals.retry or {retries: 1, backoff: "linear", delay_ms: 1000}
defaults.timeout := DAG.globals.timeout_ms or 45000

for each node in DAG.nodes where node.type == "action":
    assert node.data.tool and node.data.action present
    assert node.data.connection_id present (if tool requires auth)
```

(Full structural validation lives in your template→executable→DAG compilers.)

---

## Step 2 — Trigger Registration (id = hash(user\_id, workflow\_id, version, node\_id))

```
for node in DAG.nodes where node.type == "trigger":
    if node.data.trigger.kind == "event_based":
        persist trigger_instance { id, tool, slug, connection_id, config }   # for lookup
    if node.data.trigger.kind == "schedule_based":
        scheduler.register(trigger_instance_id, node.data.trigger.cron_expr)
```

> You don’t need a separate “webhook” trigger type: Composio posts to your webhook, you look up the event’s trigger instance, and start a run.

---

## Step 3 — Activation (turns an external event into an in-system run)

```
on_webhook(event):
    trig := resolve_trigger_instance(event)        # by toolkit_slug/slug/connection_id/filters
    if not trig: return 204

    run_id := uuid()
    context := {
        inputs: event.payload,     # email body, subject, sender, etc.
        vars: {},                  # small scalars you compute along the way
        artifacts: {},             # large payloads (by reference)
        errors: {}                 # node_id -> brief error
    }
    persist_run(run_id, DAG.workflow_id, DAG.version, status="RUNNING", t0=now)

    ready := queue()
    for edge in outgoing_edges(trig.node_id): ready.enqueue(edge.target)

    orchestrate(run_id, context, ready)
```

---

## Step 4 — Orchestrator Loop

```
function orchestrate(run_id, context, ready):
    while not ready.empty():
        node_id := ready.dequeue()
        if node_already_final(run_id, node_id): continue

        node := get_node(node_id)

        switch node.type:

            case "action":
                exec_action(run_id, node, context)

            case "gateway_if":
                # branches: [{name, expr, to}], else_to?
                target := null
                for b in node.data.branches:
                    if eval_expr(b.expr, context): target := b.to; break
                mark_done(run_id, node_id, output={branch: target or "else"})
                if target: ready.enqueue(target) else if node.data.else_to: ready.enqueue(node.data.else_to)

            case "gateway_switch":
                key    := eval_value(node.data.selector, context)
                target := case_lookup(key, node.data.cases) or node.data.default_to
                mark_done(run_id, node_id, output={case: key})
                if target: ready.enqueue(target)

            case "parallel":
                # fan-out to all successors whose edge condition (if any) passes
                mark_done(run_id, node_id, output={fanout: true})
                for edge in outgoing_edges(node_id):
                    if edge_condition_true(edge, context): ready.enqueue(edge.target)

            case "join":
                arrived := record_join_arrival(run_id, node_id, context.__last_node_id)
                if join_ready(node, arrived):               # mode: all|any|quorum:n
                    mark_done(run_id, node_id, output={arrived: arrived})
                    for edge in outgoing_edges(node_id):
                        if edge_condition_true(edge, context): ready.enqueue(edge.target)
                else:
                    continue   # wait for more arrivals

            case "loop_while":
                if eval_expr(node.data.condition, context):
                    bump_loop_counter(run_id, node_id) or fail_if_over_limit(node)
                    ready.enqueue(node.data.body_start)
                else:
                    mark_done(run_id, node_id, output={loop: "exited"})

            case "loop_foreach":
                items := eval_value(node.data.source_array_expr, context)    # must be list
                n     := length(items)
                mark_progress(run_id, node_id, {spawned: n})
                spawn_shards(run_id, node_id, items, node.data.body_start,
                             max_conc = node.data.max_concurrency or DAG.globals.max_parallelism or 5)
                mark_done(run_id, node_id, output={spawned: n})

            case "trigger":
                mark_skipped(run_id, node_id)

        route_successors(run_id, node_id, context, ready)

    finalize_run_status(run_id)
```

---

## Step 5 — Action Execution (Composio call + idempotency + retries)

```
function exec_action(run_id, node, context):
    retry   := node.data.retry or defaults.retry
    timeout := node.data.timeout_ms or defaults.timeout

    # construct idempotency key from run + node + input digest
    idem_key := hash(run_id, node.id, digest(render_preview(node.data.input_template, context)))
    if idem_cache.has(idem_key):
        cached := idem_cache.get(idem_key)
        mark_done(run_id, node.id, output=cached, from_cache=true)
        return

    # render tool arguments (Jinja/Handlebars/JSONPath allowed)
    args := render_template(node.data.input_template, context)

    attempt := 0
    loop:
        attempt += 1
        try:
            result := composio.execute(
                        tool            = node.data.tool,
                        action          = node.data.action,
                        connection_id   = node.data.connection_id,
                        arguments       = args,
                        timeout_ms      = timeout,
                        idempotency_key = idem_key   # if provider supports
                      )
            # persist compact pieces to vars; large bodies/artifacts by reference
            update_context_from_result(context, node, result)
            idem_cache.put(idem_key, slim(result), ttl=24h)
            mark_done(run_id, node.id, output=slim(result))
            metrics.inc("node_success", {tool: node.data.tool})
            return

        catch RetriableError e:
            if attempt > retry.retries:
                mark_error(run_id, node.id, error=brief(e))
                metrics.inc("node_failed", {tool: node.data.tool, reason: "retries_exhausted"})
                return
            sleep(backoff(retry, attempt))      # linear/exponential based on policy
            continue loop

        catch FatalError e:
            mark_error(run_id, node.id, error=brief(e))
            metrics.inc("node_failed", {tool: node.data.tool, reason: "fatal"})
            return
```

---

## Step 6 — Routing to Successors

```
function route_successors(run_id, node_id, context, ready):
    status := node_status(run_id, node_id)   # DONE | ERROR | SKIPPED
    for edge in outgoing_edges(node_id):
        when_ok :=
            (edge.when is null) or
            (edge.when == "always") or
            (edge.when == "success" and status == "DONE") or
            (edge.when == "error"   and status == "ERROR")

        if when_ok and edge_condition_true(edge, context):    # uses edge.condition if present
            ready.enqueue(edge.target)
```

> You can place conditions either on **edges** (your schema supports a structured `condition` on `DAGEdge`) or inside **gateway** nodes if you prefer centralizing branching. The executor supports both.&#x20;

---

## Step 7 — Helpers

```
function edge_condition_true(edge, context):
    return (edge.condition is null) or eval_condition(edge.condition, context)

function join_ready(node, arrived_count):
    switch node.data.mode:
        case "all":    return arrived_count == incoming_count(node.id)
        case "any":    return arrived_count >= 1
        case "quorum": return arrived_count >= (node.data.count or 2)

function render_template(template, context):
    # Apply string interpolation + JSONPath/JMESPath
    return interpolate(template, context)

function update_context_from_result(context, node, result):
    # Example: map result fields to context.vars via node.data.output_vars
    for (k, path) in node.data.output_vars?: context.vars[k] = jsonpath(result, path)
    if is_large(result): context.artifacts[node.id] = store_blob(result)
```

---

## Step 8 — Finalization

```
function finalize_run_status(run_id):
    if any_required_node_failed(run_id):
        set_run_status(run_id, "FAILED", finished_at=now)
    else:
        set_run_status(run_id, "SUCCESS", finished_at=now)
    emit_run_summary(run_id)   # optional, for UI
```

---

## Minimal Persistence (recommended)

* **runs**: `run_id`, `workflow_id`, `version`, `user_id`, `status`, `started_at`, `finished_at`, `trigger_digest`.
* **node\_executions**: `run_id`, `node_id`, `status`, `attempt`, `output_ref`, `error`, timestamps, `arrivals` (for joins).

---

### Why idempotency?

Webhooks retry and workers crash. Using a **stable key** per node execution (e.g., `hash(run_id, node_id, input_digest)`) ensures replays don’t duplicate side-effects (like posting twice in Slack).
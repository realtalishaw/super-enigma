# Weave — UI Tech Spec (Python, FastAPI Templates)

## scope

* pages: **home**, **workflow suggestions**, **workflow builder**, **preferences**
* auth modal (email only) in header
* server-rendered HTML via **Jinja2** + **HTMX** (+ minimal Alpine.js for toggles)
* styling with **TailwindCSS**
* NO business logic here. Only: templates, static, htmx endpoints that call existing APIs.

---

## stack

* **FastAPI** + `Jinja2Templates` for rendering
* **HTMX** for progressive interactions (search, modals, partial refresh)
* **Alpine.js** (tiny state in header/menu)
* **TailwindCSS** (precompiled)
* **Heroicons/Lucide** SVGs
* **Playwright** for UI e2e, **pytest** for template smoke

---

## url map (ui routes only)

> All routes return HTML; HTMX endpoints return **partials**.

* `GET /` → **Home**
* `GET /suggestions` → **Workflow Suggestions**
* `GET /builder/{workflow_id}` → **Workflow Builder**
* `GET /preferences` → **Preferences**

**HTMX/UI partials**

* `GET /partials/auth/modal` → email sign-in modal
* `GET /partials/integrations` → integration multi-select list (filtered)
* `POST /partials/suggestions` → suggestion cards grid (from prompt/integrations)
* `GET /partials/builder/inputs/{workflow_id}` → inputs form
* `GET /partials/builder/graph/{workflow_id}` → SVG/HTML canvas of nodes (client DnD via tiny lib or draggable)
* `GET /partials/builder/logs/{workflow_id}` → outputs/logs panel (poll)
* `GET /partials/header` → header fragment (switch sign-in ↔ profile)

> These partials **call backend APIs** under the hood; this spec only states what JSON they expect.

---

## templates (jinja)

```
templates/
  base.html
  components/
    header.html
    footer.html
    modal.html
    input_textarea.html
    integrations_picker.html
    suggestion_card.html
    kv_list.html
    button.html
    badge.html
  pages/
    home.html
    suggestions.html
    builder.html
    preferences.html
  partials/
    auth_modal.html
    integrations_list.html
    suggestions_grid.html
    builder_inputs.html
    builder_graph.html
    builder_logs.html
```

---

## page specs

### home (`GET /`)

**goal:** collect prompt + integrations; send to suggestions.

**ui**

* centered **textarea** (`name="prompt"`, rotating placeholder)
* **integrations picker**: search input + results list with checkboxes, chips for selected
* primary **Get suggestions** button (disabled while loading)
* header right: **Sign in** (opens modal via HTMX)

**interactions (htmx)**

* integrations search:

  * `hx-get="/partials/integrations"` `hx-trigger="input changed delay:300ms"` `hx-target="#integrations-list"`
* open auth modal:

  * `hx-get="/partials/auth/modal"` `hx-target="#modal-root"`

**submit**

* form `method="post" hx-post="/partials/suggestions" hx-target="#suggestions-preview" hx-swap="innerHTML"`
* success path: client receives preview + “Continue” button linking to `/suggestions?prompt=...&integrations=...`

**empty/error**

* if integrations fetch fails → inline error div + retry button

### workflow suggestions (`GET /suggestions`)

**ui**

* top bar shows submitted **prompt** + selected **integrations** (badges)
* grid of 3–5 **suggestion\_card** components:

  * title, short desc, required integrations
  * actions: **Use this**, **Preview steps** (collapsible)

**actions**

* **Use this**: standard link to `GET /builder/{workflow_id}` after UI calls API:

  * button carries `hx-post="/api/suggestions:generate"` (handled by a small UI handler thin controller) with `{suggestionId}`
  * on 201, `hx-redirect="/builder/{id}"`

**empty/error**

* "No suggestions" → show **Regenerate** (re-POST to `/partials/suggestions` with existing query)

### workflow builder (`GET /builder/{workflow_id}`)

**layout** (CSS grid; 3 panes):

* **left**: Inputs form (read-only labels + missing fields editable)
* **center**: Node canvas (n8n-style)
* **right**: Outputs/logs (polling)

**controls (top bar)**

* status chip
* **Run** (disabled - workflows not available in this version)
* **Stop** (disabled - workflows not available in this version)
* **Save** (disabled - workflows not available in this version)
* **Reset** (client reload)

**partials**

* inputs: `GET /partials/builder/inputs/{id}` (on page load & after save)
* graph: `GET /partials/builder/graph/{id}` (on load; exposes data-attrs for node ids; simple DnD with minimal JS)
* logs: `GET /partials/builder/logs/{id}` with `hx-trigger="every 3s"` while status ∈ {queued,running}

**errors**

* node errors render red badge + tooltip; clicking focuses node in center pane

### preferences (`GET /preferences`)

**ui**

* read-only **kv\_list** grouped: Profile, Notifications, Linked Integrations
* no edit controls; disabled inputs for clarity

---

## header/auth

**header**

* left: Weave logo
* right:

  * signed-out: **Sign in** (htmx loads `/partials/auth/modal`)
  * signed-in: profile avatar button opens menu:

    * copyable **User ID**
    * **Preferences** link
    * **Sign out** (posts to `/api/auth/signout`, then htmx swaps header via `GET /partials/header`)

**auth modal (email)**

* form: `email`
* `hx-post="/api/auth/request"` → on success close modal, refresh header partial

---

## components (key)

* `integrations_picker.html`

  * search `<input id="integration-search">`
  * results `<ul id="integrations-list">` (htmx filled)
  * selected chips area
* `suggestion_card.html`

  * props: `title, desc, required_integrations[], suggestion_id`
  * buttons wired with `hx-post` for create-workflow
* `builder_graph.html`

  * renders nodes as positioned `<div class="node">` with `data-node-id`
  * edges as SVG `<path>`; minimal DnD to update `style.left/top` and queue a “Save layout” button
* `builder_inputs.html`

  * generated from schema: render labels + inputs (text, select, secret masked)
* `builder_logs.html`

  * log lines in `<pre>`; auto-scroll on update

---

## ui → api contracts (expected json)

> UI will call these; defined here only to shape rendering.

* `GET /api/integrations?search=...`

```json
{ "items": [ { "id":"gmail", "name":"Gmail", "iconUrl":"/static/icons/gmail.svg" } ] }
```

* `POST /api/suggestions:generate`

```json
{ "suggestions":[
  { "id":"s1","title":"Auto-triage support","description":"...", "requiredIntegrationIds":["gmail","slack"], "stepsPreview":[{"label":"Trigger: New email"}, {"label":"Classify"}, {"label":"Notify Slack"}] }
]}
```

* `GET /api/preferences/{user_id}`

```json
{ "profile":{"email":"t@ex.com","userId":"user_1"}, "notifications":{"email":true}, "integrations":[{"id":"gmail","name":"Gmail","connected":true,"updatedAt":"2025-08-20"}] }
```

* `GET /api/auth/session` → `{ "userId":"user_1","email":"t@ex.com" }` or `401`
* `POST /api/auth/request` → `{ "ok":true }`
* `POST /api/auth/signout` → `{ "ok":true }`

---

## accessibility

* focus traps for modals; `aria-modal="true"`, labelled titles
* visible focus outlines; color contrast AA
* buttons are real `<button>`
* live region (`aria-live="polite"`) in logs panel
* keyboard DnD alternative: arrow-key nudge + inputs for X/Y

---

## performance

* Tailwind precompiled; static icons
* lazy load heavy partials (graph, logs)
* debounce integration search (300ms)
* cache integrations on server for 5m; client uses htmx swaps

---

## errors/empty states

* toast area in base layout
* standardized inline error block component
* skeletons: integrations list, suggestions grid, builder panes

---

## testing

* **template smoke**: render each page with fixture context
* **playwright**: sign-in modal open/close, integration search, suggestions flow, builder run/stop (mocked), preferences read-only
* **axe** checks per page

---

## file structure (ui only)

```
app/
  main.py                  # mounts template routes + partials (ui only)
  ui_routes.py             # GET pages, HTMX partials (no business logic)
  services/ui_client.py    # thin HTTP client to call real APIs
  templates/...
  static/
    css/tailwind.css
    js/alpine.min.js
    js/htmx.min.js
    js/dnd.js             # tiny DnD helper for nodes
    icons/*.svg
tests/
  ui/
    test_pages_render.py
    e2e/
      test_home_flow.spec.ts
      test_builder.spec.ts
```

---

## definition of done (ui v1)

* all 4 pages render
* auth modal works; header swaps state
* integrations search + multi-select
* suggestions list renders via partial; “Use this” creates and redirects
* builder shows inputs, graph, logs; run/stop buttons wired
* preferences displays read-only data
* keyboard+a11y pass; e2e happy path green


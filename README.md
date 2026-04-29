# terra-cli

A **notebook-native Terraform analysis toolkit**. Loads plans, state, and
remote backends into pandas DataFrames; renders the dependency graph as an
interactive Cytoscape widget; scores risky changes before `apply`.

The package name is `terra` (the `cli` in the repo name nods to the original
prototype). Primary surface is a Python API + IPython magics; a thin `terra`
CLI wraps the same library calls.

---

## Why

Terraform's ecosystem is dominated by CLIs and SaaS dashboards. Platform and
data-platform engineers who already live in Jupyter have no native way to
*query* infrastructure the way they query a warehouse. `terra` closes that
gap: plans and state become DataFrames; the resource graph becomes a widget;
risky changes get scored in a notebook cell before anyone runs `apply`.

The dependency-graph and (stretch) drift abstractions translate naturally to
multi-cluster orchestration work — the kind of platform tooling listed on the
BQuant JD. The W4 local-k3s drift demo is the proof point.

---

## Architecture

```
                 ┌──────────────────────────────────────────────┐
                 │                   sources                    │
                 │                                              │
                 │  terraform show -json plan.bin               │
                 │  terraform state pull                        │
                 │  s3://bucket/key/terraform.tfstate (boto3)   │
                 └──────────────────────┬───────────────────────┘
                                        │ raw JSON
                                        ▼
                 ┌──────────────────────────────────────────────┐
                 │  terra.schema  (Pydantic v2 models)          │
                 │   Plan, State, ResourceChange, Resource,     │
                 │   Configuration, Module, Provider            │
                 └──────────────────────┬───────────────────────┘
                                        │ typed objects
                                        ▼
                 ┌──────────────────────────────────────────────┐
                 │  terra.frame   (flatteners → pandas/Arrow)   │
                 │   state.to_frame()  →  resources DataFrame   │
                 │   plan.to_frame()   →  changes DataFrame     │
                 │   plan.summary()    →  add/change/destroy    │
                 └──────────────────────┬───────────────────────┘
                                        │
                       ┌────────────────┴────────────────┐
                       ▼                                 ▼
              ┌────────────────┐              ┌────────────────────┐
              │ terra.graph    │              │ terra.risk         │
              │  ipycytoscape  │              │  rule-based score  │
              │  dep widget    │              │  per change row    │
              └────────────────┘              └────────────────────┘
                                        │
                                        ▼
                 ┌──────────────────────────────────────────────┐
                 │  terra.magic   (%%terraform IPython magic)   │
                 │  run plan/apply, auto-bind result to var     │
                 └──────────────────────────────────────────────┘

                       ─ ─ ─ ─ ─ ─ ─ stretch (W4) ─ ─ ─ ─ ─ ─ ─
                                        │
                                        ▼
                 ┌──────────────────────────────────────────────┐
                 │  terra.drift.k3s   (local k3s only)          │
                 │  diff state ↔ live objects on a local node   │
                 └──────────────────────────────────────────────┘
```

Each layer has one job. The Pydantic layer is the contract — every loader
returns models, every analyser consumes models. DataFrames are produced at
the boundary so users can `df.query(...)`, merge with their own data, or
export to Parquet via PyArrow.

---

## Data flow, end to end

1. **Acquire JSON.** `terra.load.plan(path)` shells out to
   `terraform show -json plan.bin`. `terra.load.state_local(path)` reads
   `terraform.tfstate`. `terra.load.state_s3(bucket, key)` uses `boto3` (with
   optional DynamoDB lock awareness — read-only, never touch the lock).
2. **Parse.** Raw JSON → `terra.schema.Plan` / `terra.schema.State` via
   Pydantic v2. Schemas track the documented Terraform plan/state JSON
   formats (`format_version` 1.x for plan, 4 for state). Unknown fields are
   preserved in `extra` so we don't break on minor Terraform upgrades.
3. **Flatten.** `terra.frame.resources_df(state)` walks
   `state.values.root_module` (recursively into `child_modules`) and emits
   one row per resource: `address`, `type`, `name`, `provider`, `module`,
   `mode`, plus selected attributes. PyArrow types are used so the frame
   round-trips to Parquet for caching.
4. **Diff.** `terra.frame.changes_df(plan)` flattens `plan.resource_changes`:
   one row per resource, columns for `actions` (create/update/delete/replace),
   `before`/`after` JSON blobs, and a precomputed `attr_diff` list of changed
   attribute paths.
5. **Graph.** `terra.graph.from_state(state)` builds a `networkx.DiGraph`
   from each resource's `dependencies` field; `terra.graph.render(g)` returns
   an `ipycytoscape.CytoscapeWidget` styled by resource type. For plans,
   edges come from `configuration.root_module.resources[*].expressions.*.references`.
6. **Risk score.** `terra.risk.score(changes_df)` applies a rules pack:
   deletes on stateful resources (RDS, EBS) → high; replaces on resources
   with no `create_before_destroy` → high; in-place updates on tags only →
   low. Output adds `risk` and `risk_reasons` columns.
7. **Magic.** `%%terraform plan -out=tfplan` runs the command, captures
   stdout/stderr, parses the resulting plan, and binds it to a user variable
   (default `_plan`).
8. **(Stretch, W4) Local k3s drift.** `terra.drift.k3s(state)` filters to
   resources managed against a local k3s node, fetches live objects via the
   `kubernetes` client pointed at `~/.kube/config` (k3s context only), and
   diffs `manifest` vs live spec. Out of scope: remote clusters, EKS/GKE,
   multi-cluster fan-out.

---

## Module layout

```
terra/
  __init__.py          # re-exports public API
  schema/
    __init__.py
    plan.py            # Pydantic: Plan, ResourceChange, Configuration
    state.py           # Pydantic: State, Resource, Module
    common.py          # shared enums (Action, Mode), Provider
  load/
    __init__.py
    local.py           # plan(path), state_local(path), runs terraform CLI
    s3.py              # state_s3(bucket, key, profile=None)
  frame/
    __init__.py
    resources.py       # resources_df(state)
    changes.py         # changes_df(plan), summary(plan)
    _flatten.py        # shared module-tree walker
  graph/
    __init__.py
    build.py           # from_state, from_plan → networkx.DiGraph
    render.py          # render(g) → CytoscapeWidget; styles per resource type
  risk/
    __init__.py
    rules.py           # rule registry
    score.py           # score(changes_df)
  magic/
    __init__.py        # load_ipython_extension
    terraform.py       # %%terraform cell magic
  drift/               # W4 stretch — local k3s only
    __init__.py
    k3s.py             # k3s(state, kubeconfig=...) → drift DataFrame
  cli.py               # `terra` entrypoint via click — thin wrapper
notebooks/
  01_quickstart.ipynb
  02_dependency_graph.ipynb
  03_remote_state_and_risk.ipynb
  04_k3s_drift.ipynb           # W4 stretch
tests/
  fixtures/            # canned plan.json, state.json
  test_schema.py
  test_frame.py
  test_graph.py
  test_risk.py
  test_magic.py
  test_drift_k3s.py    # W4 stretch
pyproject.toml
.github/workflows/ci.yml
```

---

## Public API (what a user types in a notebook)

```python
import terra

state = terra.load.state_s3("my-tf-bucket", "prod/terraform.tfstate")
df    = terra.frame.resources_df(state)
df.query("type == 'aws_s3_bucket' and module == ''")

plan  = terra.load.plan("tfplan.bin")
terra.frame.summary(plan)            # {'add': 3, 'change': 1, 'destroy': 0}
changes = terra.frame.changes_df(plan)
risky   = terra.risk.score(changes).query("risk == 'high'")

g = terra.graph.from_state(state)
terra.graph.render(g)                # CytoscapeWidget in the cell
```

```python
%load_ext terra
```
```
%%terraform plan -out=tfplan
# any tf args; result bound to _plan automatically
```

W4 stretch:
```python
drift = terra.drift.k3s(state)       # local k3s node only
drift.groupby("drift_type").size()
```

---

## Tech-stack mapping (each piece has a specific job)

| Tech                  | Role in the system                                                |
|-----------------------|-------------------------------------------------------------------|
| Python 3.11           | Host language; uses `match`, PEP 695 type aliases.                |
| Pydantic v2           | Parse + validate Terraform plan/state JSON into typed objects.    |
| pandas                | DataFrame surface for resources, changes, risk.                   |
| PyArrow               | Typed columnar backing; Parquet cache of parsed state.            |
| networkx              | Dependency graph algebra (cycles, reachability, blast radius).    |
| ipycytoscape          | Interactive resource-graph widget in Jupyter.                     |
| ipywidgets            | Filter controls (module, provider, action) bound to DataFrames.   |
| boto3                 | Pull remote state from S3 backends.                               |
| IPython               | `%%terraform` cell magic; auto-binds parsed plan to a variable.   |
| click                 | Thin `terra` CLI mirroring the library API.                       |
| pytest                | Unit + integration tests against canned plan/state fixtures.      |
| mypy (strict)         | Type-checks the Pydantic-typed core.                              |
| ruff                  | Lint + format.                                                    |
| GitHub Actions        | CI matrix: 3.11/3.12, lint → typecheck → test → build wheel.      |
| kubernetes (client)   | **W4 stretch only.** Read live objects from a local k3s node.     |
| k3s                   | **W4 stretch only.** Single-node local cluster used as the drift target. |

---

## Implementation plan

### Weekend 1 — schema + frame core (MVP)
- [ ] `pyproject.toml` (hatch), package skeleton, ruff + mypy + pytest configured.
- [ ] Pydantic models: `Plan`, `State`, `ResourceChange`, `Resource`,
      `Configuration`, `Module`. Pin to plan format 1.x / state format 4.
- [ ] Fixture set: capture `terraform show -json` output for a small AWS
      module; commit under `tests/fixtures/`.
- [ ] `terra.frame.resources_df(state)` — recursive module walk, returns a
      typed DataFrame. PyArrow dtypes for `module`, `provider`.
- [ ] `terra.frame.changes_df(plan)` and `terra.frame.summary(plan)`.
- [ ] `terra.load.plan` / `state_local` (subprocess to `terraform`).
- [ ] CI green: lint, mypy --strict on `terra.schema` and `terra.frame`,
      pytest with ≥80% coverage on those two modules.
- [ ] `notebooks/01_quickstart.ipynb` — load fixture, show both DataFrames,
      run `summary`. Committed with outputs cleared.

**Deliverable:** `pip install -e .` then run the quickstart notebook end to
end on the committed fixture.

### Weekend 2 — magic + graph (v0.2)
- [ ] `terra.magic.terraform` — IPython cell magic. Parses argstring, runs
      `terraform <subcmd>` in a temp dir or the notebook cwd, captures plan
      file, parses it, binds to `_plan` (or `--var name`).
- [ ] `terra.graph.build.from_state` — `dependencies` field → `DiGraph`.
- [ ] `terra.graph.build.from_plan` — references in `configuration` →
      DiGraph with edges annotated by referenced attribute.
- [ ] `terra.graph.render` — `CytoscapeWidget` with per-type icons/colors,
      hover shows `address`, click highlights downstream nodes (blast radius).
- [ ] `ipywidgets` filter panel: dropdowns for module / provider / action;
      filtering rebinds the graph and the changes DataFrame.
- [ ] `notebooks/02_dependency_graph.ipynb` — graph + filter widget demo.
- [ ] Tests: graph isomorphism against a hand-rolled expected graph for the
      fixture; magic test using `IPython.testing`.

**Deliverable:** opening notebook 02 produces an interactive graph widget;
`%%terraform plan` works in a fresh kernel.

### Weekend 3 — remote state + risk + ship (v0.3)
- [ ] `terra.load.s3` — boto3 client, supports profile + assume-role.
      Read only. Lock object detection (warn if `terraform.tfstate.tflock`
      exists) but never write.
- [ ] `terra.risk.score` — rule pack v1: stateful-delete, no-CBD-replace,
      cross-module reference break, IAM widening (regex on policy docs).
      Each rule is a `Callable[[pd.Series], tuple[Risk, str] | None]`.
- [ ] `terra` CLI via click: `terra summary <plan>`, `terra graph --out
      graph.html` (export widget as standalone HTML), `terra risk <plan>`.
- [ ] Parquet cache: `state.to_parquet(path)` round-trip via PyArrow; loader
      skips re-parsing if cache fresher than source.
- [ ] `notebooks/03_remote_state_and_risk.ipynb` — pull state from S3
      (LocalStack or moto in CI), render graph, risk-score upcoming changes.
- [ ] PyPI publish via GitHub Actions on tag (`v0.3.0`); trusted publisher,
      no API token in repo.
- [ ] README badges: PyPI, CI, coverage, mypy strict.

**Deliverable:** `pip install terra-tf` from PyPI; the project is complete
and shippable without any Kubernetes dependency.

### Weekend 4 — local k3s drift (stretch, v0.4)
The base project ships at the end of W3. W4 is an optional capstone that
proves the abstraction generalises to live infrastructure, scoped narrowly
to a local k3s cluster so it can run on a laptop and in CI without cloud
credentials.

- [ ] Provision a single-node k3s cluster (`k3s` binary or `k3d`) in a
      Makefile target — same recipe used locally and in CI.
- [ ] `terra.drift.k3s(state, kubeconfig=...)` — for each `kubernetes_*`
      resource in state, fetch the live object via the `kubernetes` client
      and diff `manifest` vs live spec, ignoring server-side fields
      (`status`, `metadata.managedFields`, `metadata.resourceVersion`).
      Refuses to run if the kubeconfig context isn't a k3s/k3d context — we
      do not point this at remote clusters in v0.4.
- [ ] Per-type adapter registry for older typed resources
      (`kubernetes_deployment_v1`, `kubernetes_service_v1`, …) — no generic
      differ; each adapter declares which fields it owns.
- [ ] `notebooks/04_k3s_drift.ipynb` — apply a tiny manifest with
      Terraform, mutate it via `kubectl`, re-run `terra.drift.k3s`, show
      the drift DataFrame.
- [ ] Integration test in CI: spin up k3s/k3d, apply, mutate, assert drift.
- [ ] Tag `v0.4.0` if green.

**Deliverable:** the k3s-drift notebook runs end to end against a fresh
k3s cluster started by `make k3s-up` (or skipped cleanly if k3s is absent).

---

## Non-goals (explicitly out of scope)

- Writing or mutating Terraform state. Read-only by design.
- Replacing `terraform plan` / `apply`. We parse their output, not replace it.
- **Kubernetes drift against any remote or managed cluster.** The W4 stretch
  is deliberately scoped to a local k3s/k3d node so the project remains
  laptop-runnable and CI-runnable without cloud credentials. EKS, GKE, AKS,
  and multi-cluster orchestration are explicitly out of scope.
- Cloud-specific drift (AWS, GCP, Azure). Drift is a v0.4+ question and the
  k3s capstone is the only drift target shipped.
- Web UI / hosted service. The whole point is that Jupyter *is* the UI.

---

## Open questions to resolve before each phase

**Before W1.** Terraform plan/state JSON format is documented but not stable
across major versions. Pin to Terraform ≥1.6 and capture exact
`format_version` in fixtures; bump deliberately.

**Before W3.** Risk-rule severity thresholds: do we expose a config file or
hardcode v1? Decision: hardcode v1, expose `terra.risk.rules.register()` for
extension; config file is post-v0.3.

**Before W4 (stretch).** ipycytoscape is maintenance-mode; if it bitrots,
fall back to `ipysigma` or `pyvis`. Keep `terra.graph.render`'s return type
a duck-typed widget so swapping is local. Also: confirm that
`kubernetes_manifest` resources in the local k3s fixture round-trip cleanly
through the per-type adapter registry before committing to the W4 scope.

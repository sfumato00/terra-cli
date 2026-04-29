# Implementation plan

## Weekend 1 — schema + frame core (MVP) ✓
- [x] `pyproject.toml` (hatch), package skeleton, ruff + mypy + pytest configured.
- [x] Pydantic models: `Plan`, `State`, `ResourceChange`, `Resource`,
      `Configuration`, `Module`. Pin to plan format 1.x / state format 4.
- [x] Fixture set: canned `plan.json` and `state.json` under `tests/fixtures/`.
- [x] `terra.frame.resources_df(state)` — recursive module walk, returns a
      typed DataFrame. PyArrow dtypes for `module`, `provider`.
- [x] `terra.frame.changes_df(plan)` and `terra.frame.summary(plan)`.
- [x] `terra.load.plan` / `state_local` (subprocess to `terraform`) +
      `terra.load.plan_json` (no binary needed).
- [x] CI green: lint, mypy --strict on `terra.schema` and `terra.frame`,
      pytest with 84% coverage (≥80% required).
- [x] `notebooks/01_quickstart.ipynb` — load fixture, show both DataFrames,
      run `summary`. Committed with outputs cleared.

**Deliverable:** `pip install -e .` then run the quickstart notebook end to
end on the committed fixture. ✓

## Weekend 2 — magic + graph (v0.2) ✓
- [x] `terra.magic.terraform` — IPython cell magic. Parses argstring, runs
      `terraform <subcmd>`, captures plan file, parses it, binds to `_plan`
      (or `--var name`). Exits cleanly when `terraform` is not on `$PATH`.
- [x] `terra.graph.build.from_state` — `dependencies` field → `DiGraph`.
- [x] `terra.graph.build.from_plan` — references in `configuration` →
      `DiGraph` with edges from `expressions.*.references`.
- [x] `terra.graph.render` — `CytoscapeWidget` with per-type colors, node
      labels set to resource address, `cose` layout. Raises `ImportError`
      with install hint when ipycytoscape is absent.
- [x] `ipywidgets` filter panel: dropdowns for module / provider / action;
      filtering rebinds the subgraph and the changes DataFrame in notebook 02.
- [x] `notebooks/02_dependency_graph.ipynb` — state graph, plan graph, filter
      widget demo, and `%%terraform` magic example.
- [x] Tests: node/edge counts and isomorphism for fixture graphs
      (`test_graph.py`, 17 tests); magic registration, arg parsing, and
      subprocess mocking via `IPython.testing` (`test_magic.py`, 11 tests).
      Coverage: 81.6% (≥80% required). CI green.

**Deliverable:** opening notebook 02 produces an interactive graph widget;
`%%terraform plan` works in a fresh kernel. ✓

## Weekend 3 — remote state + risk + ship (v0.3)
- [x] `terra.load.s3` — boto3 client, supports profile + assume-role.
      Read only. Lock object detection (warn if `terraform.tfstate.tflock`
      exists) but never write.
- [x] `terra.risk.score` — rule pack v1 (each rule is a
      `Callable[[pd.Series], tuple[Risk, str] | None]`):
  - Stateful delete: `delete` on RDS, EBS, S3 → high.
  - No-CBD replace: destroy-before-create replace → high.
  - IAM widening: detects `*` actions or `*` resources added → high.
  - `user_data` mutation: any change to `user_data` /
    `user_data_base64` on an instance type → high (forces reprovision).
  - Tag-only update → low.
- [x] `terra.risk.blast_radius(g, address)` — returns `nx.ancestors(g, address)`
      (graph edges go dependent→dependency; ancestors = resources that depend on
      address and are destroyed when it is).
- [x] `terra.risk.user_data_diff(changes_df)` — for rows where
      `user_data` or `user_data_base64` appears in `attr_diff`, decode
      base64, attempt gzip decompress, return a unified diff per row.
- [x] `terra.frame.state_diff(before, after)` — compare two `State`
      objects; return a DataFrame with `address`, `diff_type`, `changed_attrs`.
- [x] `terra` CLI: `terra summary <plan>`, `terra resources <state>`, `terra risk <plan> [--high-only]`.
- [ ] Parquet cache: `state.to_parquet(path)` round-trip via PyArrow; loader
      skips re-parsing if cache fresher than source.
- [ ] `notebooks/03_remote_state_and_risk.ipynb`
- [ ] PyPI publish via GitHub Actions on tag (`v0.3.0`).
- [ ] README badges: PyPI, CI, coverage, mypy strict.

**Deliverable:** `pip install terra-tf` from PyPI; the project is complete
and shippable without any Kubernetes dependency.

## Weekend 4 — local k3s drift (stretch, v0.4)
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

# Non-goals (explicitly out of scope)

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

# Open questions to resolve before each phase

**Before W1.** Terraform plan/state JSON format is documented but not stable
across major versions. Pin to Terraform ≥1.6 and capture exact
`format_version` in fixtures; bump deliberately.

**Before W3.** Risk-rule severity thresholds: do we expose a config file or
hardcode v1? Decision: hardcode v1, expose `terra.risk.rules.register()` for
extension; config file is post-v0.3.

**Before W3 (user_data diff).** `user_data` can be raw shell script,
base64-encoded gzip, or a cloud-init YAML multipart. Scope for v0.3: decode
base64, attempt gzip decompress, fall back to raw text; output a unified diff.
Full cloud-init YAML parsing (merge keys, write_files, etc.) is post-v0.3.

**Before W3 (state diff).** `terraform.tfstate.backup` is only written on
successful applies, not on plan. Scope: diff any two local state files the
user provides; do not try to auto-detect the backup path.

**Before W4 (stretch).** ipycytoscape is maintenance-mode; if it bitrots,
fall back to `ipysigma` or `pyvis`. Keep `terra.graph.render`'s return type
a duck-typed widget so swapping is local. Also: confirm that
`kubernetes_manifest` resources in the local k3s fixture round-trip cleanly
through the per-type adapter registry before committing to the W4 scope.

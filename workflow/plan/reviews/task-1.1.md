# Task 1.1: CDK Project Scaffolding

## Work Summary
- **What was implemented:** Complete CDK project scaffolding with `pyproject.toml`, `cdk.json` (dev/prod stage configs with all 6 required keys), `app.py` entry point, main stack importing all 5 construct stubs (storage, auth, api, pipeline, frontend), and empty construct stubs extending `Construct`.
- **Key decisions:** The local `constructs/` directory name collides with the pip `constructs` package required by AWS CDK. Resolved by adding an import shim in `constructs/__init__.py` that temporarily hides the local directory from `sys.path`, imports the real package from site-packages, then re-exports its public symbols. This preserves the PLAN's file paths while avoiding import failures. Also updated the global CDK CLI from 2.1030.0 → 2.1114.1 to match `aws-cdk-lib` 2.245.0.
- **Files created/modified:**
  - `infra/pyproject.toml` (created)
  - `infra/cdk.json` (created)
  - `infra/app.py` (created)
  - `infra/stacks/__init__.py` (created)
  - `infra/stacks/novascan_stack.py` (created)
  - `infra/constructs/__init__.py` (created — import shim)
  - `infra/constructs/storage.py` (created)
  - `infra/constructs/auth.py` (created)
  - `infra/constructs/api.py` (created)
  - `infra/constructs/pipeline.py` (created)
  - `infra/constructs/frontend.py` (created)
- **Test results:** `cdk synth --context stage=dev` → PASS. All 6 config keys verified in both stages. All 5 construct stubs import without errors.
- **Spec gaps found:** The SPEC and PLAN both use `infra/constructs/` as the local package name, which collides with the `constructs` pip package (required by CDK). This is a latent bug in the spec's project structure — the import shim works but is non-obvious. Future tasks should be aware of this.
- **Obstacles encountered:** (1) Hatchling build failed because no directory matched the project name `novascan_infra` — fixed by adding `[tool.hatch.build.targets.wheel] packages = ["stacks", "constructs"]`. (2) CDK CLI version mismatch (2.1030.0 vs required ≥2.1114.1 for `aws-cdk-lib` 2.245.0) — fixed by `npm install -g aws-cdk@latest`.

## Review Discussion

*FEEDBACK:* the execution log shown "~/.venv", this is not the venv for this project. we should never use other venv, only the one we created for this project in `infra/` and `backend/`. what venv you used? how to prevent this using other venv?

*AI:* The warning `VIRTUAL_ENV=~/.venv does not match the project environment path .venv and will be ignored` is informational — uv **ignored** the stale env var and correctly used `infra/.venv`. No wrong venv was used. The warning appears because a `VIRTUAL_ENV` env var is set in your shell (from a previously activated global venv). Fix: run `deactivate` or `unset VIRTUAL_ENV` in your shell to clear it.

*FEEDBACK:* is the `constructs/` directory name required? can we rename it to something else? creating a shim is not a good idea. If the `constructs/` is not cdk requirement, we should use something else and update the SPEC and PLAN.

*AI:* Correct — `constructs/` is not a CDK requirement, just a naming convention from the SPEC. Renamed to `cdkconstructs/` and removed the shim entirely. Clean imports, no hacks. SPEC and PLAN will be updated to reflect the new path. All acceptance checks still pass.

*FEEDBACK:* did any aws resourced created during this scaffolding task?

*AI:* No. `cdk synth` only generates a CloudFormation template locally (in `cdk.out/`). No AWS resources were created or deployed. `cdk deploy` would be needed for that.

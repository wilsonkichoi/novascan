# Task 1.10: CDK Infrastructure Tests

## Work Summary
- **What was implemented:** CDK infrastructure tests verifying all construct outputs against SPEC.md requirements using `aws_cdk.assertions.Template`. Tests cover Storage (DynamoDB key schema, GSI1, billing, PITR, S3), Auth (User Pool, groups, triggers, app client), API (HTTP API, CORS, authorizer, Lambda), Frontend (CloudFront, SPA routing, HTTPS), and full stack (snapshot, outputs, composition, stage isolation).
- **Key decisions:**
  - Used `skip_cyclical_dependencies_check=True` in `Template.from_stack()` to work around a circular dependency bug in the Auth construct. Added a dedicated `xfail` test to track this bug.
  - Added `[tool.pytest.ini_options] testpaths = ["tests"]` to `pyproject.toml` to prevent pytest from collecting conftest.py files inside `cdk.out/` bundled assets.
  - Snapshot test auto-creates the snapshot on first run, then compares on subsequent runs.
  - Session-scoped fixture for template synthesis (expensive operation, only done once).
- **Files created/modified:**
  - `infra/tests/__init__.py` (created)
  - `infra/tests/conftest.py` (created -- shared fixtures)
  - `infra/tests/test_storage_construct.py` (created -- 9 tests)
  - `infra/tests/test_auth_construct.py` (created -- 11 tests including cycle bug detection)
  - `infra/tests/test_api_construct.py` (created -- 9 tests)
  - `infra/tests/test_frontend_construct.py` (created -- 6 tests)
  - `infra/tests/test_stack.py` (created -- 12 tests)
  - `infra/tests/snapshots/novascan-dev.template.json` (created -- snapshot)
  - `infra/pyproject.toml` (modified -- added pytest testpaths)
- **Test results:** 46 passed, 1 xfailed (circular dependency bug)
- **Spec gaps found:** None
- **Obstacles encountered:**
  1. pytest was collecting conftest.py from `cdk.out/` bundled numpy/pandas assets, causing `ModuleNotFoundError: hypothesis`. Fixed by adding `testpaths = ["tests"]`.
  2. `resource_count_is()` requires an integer, not a `Match.any_value()` matcher. Fixed by using `find_resources()` with a length assertion.
  3. **Critical implementation bug discovered** (see below).

## Bugs Found

### BUG-1: Circular dependency in Auth construct (Critical)

- **SEVERITY:** Critical
- **TEST:** `test_auth_construct.py::TestAuthDependencyCycle::test_no_circular_dependencies`
- **EXPECTED:** `Template.from_stack()` should succeed without `skip_cyclical_dependencies_check=True`. The CloudFormation template must be deployable without circular dependencies.
- **ACTUAL:** `Template.from_stack()` raises `RuntimeError: Template is undeployable, these resources have a dependency cycle: AuthPostConfirmationFnServiceRoleDefaultPolicy -> AuthUserPool -> AuthPostConfirmationFn -> AuthPostConfirmationFnServiceRoleDefaultPolicy`
- **SPEC REF:** Section 3 (Auth Flow) -- Post-Confirmation Lambda must add user to 'user' group, which requires `cognito-idp:AdminAddUserToGroup` permission scoped to the User Pool ARN. The User Pool must reference the Post-Confirmation Lambda as a trigger.
- **ROOT CAUSE:** The Post-Confirmation Lambda's IAM policy uses `Fn::GetAtt` on the User Pool ARN, creating a dependency from the policy to the User Pool. The User Pool has the Post-Confirmation Lambda as a trigger (dependency from User Pool to Lambda). The Lambda has `DependsOn` on its IAM policy. This creates a cycle: Policy -> User Pool -> Lambda -> Policy.
- **SUGGESTED FIX:** Use a wildcard or constructed ARN (`arn:aws:cognito-idp:{region}:{account}:userpool/*`) in the IAM policy instead of `Fn::GetAtt` on the User Pool resource, breaking the cycle. Alternatively, use `CfnUserPool` override to add the trigger after the User Pool is created.
- **NOTE:** `cdk synth` succeeds (it does not check for cycles), but `cdk deploy` would fail at CloudFormation validation time. The `skip_cyclical_dependencies_check=True` flag is a test-only workaround.

## Review Discussion

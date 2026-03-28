# Task 1.5: Auth Construct + Cognito Lambda Triggers

## Work Summary
- **What was implemented:** Cognito User Pool with email-only sign-in, App Client with ALLOW_USER_AUTH and ALLOW_REFRESH_TOKEN_AUTH flows, three Cognito Groups (admin/staff/user with precedence 0/1/2), Pre-Sign-Up Lambda trigger (auto-confirm + auto-verify email), Post-Confirmation Lambda trigger (adds user to 'user' group via admin_add_user_to_group). Auth construct exports user_pool_id, user_pool_arn, and app_client_id for downstream constructs.
- **Key decisions:**
  - Lambda code is bundled from `backend/src/novascan/auth/` directory directly (not the full backend package). Each trigger Lambda only needs its own handler file.
  - Post-Confirmation Lambda gets USER_POOL_ID via environment variable (not hardcoded).
  - Post-Confirmation Lambda has a scoped IAM policy: only `cognito-idp:AdminAddUserToGroup` on the specific User Pool ARN.
  - Pre-Sign-Up Lambda needs no IAM permissions beyond basic execution role -- it only sets response flags.
  - CDK `AuthFlow(user=True)` maps to `ALLOW_USER_AUTH`. `ALLOW_REFRESH_TOKEN_AUTH` is automatically included by CDK for all app clients.
  - User Pool removal policy is DESTROY for dev, RETAIN for prod.
- **Verified assumption:** Post-Confirmation trigger fires after user creation/confirmation. Per AWS docs, this trigger runs after a user is confirmed (step after Pre-Sign-Up auto-confirm). The user exists in the pool at this point, so `admin_add_user_to_group` works correctly. No deviation needed.
- **Files created/modified:**
  - `infra/cdkconstructs/auth.py` (modified -- full auth construct implementation)
  - `backend/src/novascan/auth/__init__.py` (created)
  - `backend/src/novascan/auth/pre_signup.py` (created)
  - `backend/src/novascan/auth/post_confirmation.py` (created)
  - `workflow/plan/reviews/task-1.5.md` (created)
- **Test results:** PASS -- cdk synth produces template with 1 UserPool, 3 UserPoolGroups, 2 Lambda functions with correct triggers, correct auth flows, correct IAM policies
- **Spec gaps found:** none
- **Obstacles encountered:** CDK `AuthFlow` uses `user=True` (not `user_auth=True`) to map to `ALLOW_USER_AUTH`. Initial code had the wrong parameter name; caught during development.

## Review Discussion

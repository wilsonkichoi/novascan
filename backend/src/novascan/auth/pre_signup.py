"""Cognito Pre-Sign-Up Lambda trigger.

This trigger fires before the user is created in Cognito. It is kept as
a no-op placeholder — the Lambda and trigger remain wired in CDK so the
hook can be repurposed later (e.g., domain validation, rate limiting).

Previously this auto-confirmed users and auto-verified emails, which
allowed arbitrary account creation without proof of email ownership.
Removed to enforce Cognito's default verification code flow.

See: SPEC.md Section 3 (Auth Flow).
"""

from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """No-op — return the event unchanged.

    Cognito will proceed with its default behavior:
    - User is created with status UNCONFIRMED
    - A verification code is sent to the user's email
    - User must call ConfirmSignUp with the code to become CONFIRMED
    """
    return event

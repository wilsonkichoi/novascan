"""Cognito Pre-Sign-Up Lambda trigger.

Auto-confirms the user and auto-verifies their email address.
This trigger fires before the user is created in Cognito, so we cannot
call Cognito APIs here — we can only set response flags.

See: SPEC.md Section 3 (Auth Flow), step 4.
"""

from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Auto-confirm user and auto-verify email.

    Cognito Pre-Sign-Up trigger response must set these flags:
    - autoConfirmUser: skip the confirmation step
    - autoVerifyEmail: mark email as verified without sending a verification code

    This enables the passwordless email OTP flow where SignUp immediately
    creates a confirmed, email-verified user.
    """
    event["response"]["autoConfirmUser"] = True
    event["response"]["autoVerifyEmail"] = True
    return event

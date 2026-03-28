"""Cognito Post-Confirmation Lambda trigger.

Adds newly confirmed users to the 'user' Cognito group.
This trigger fires after the user is created and confirmed, so
admin_add_user_to_group is safe to call here.

See: SPEC.md Section 3 (Auth Flow, RBAC).

Verification note: The Post-Confirmation trigger fires after a user is
confirmed (either via admin confirmation or auto-confirmation from the
Pre-Sign-Up trigger). At this point the user exists in the User Pool,
so admin_add_user_to_group works correctly. This has been confirmed via
AWS documentation: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-post-confirmation.html
"""

import logging
import os
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito_client = boto3.client("cognito-idp")

DEFAULT_GROUP = "user"


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Add the newly confirmed user to the 'user' Cognito group.

    The User Pool ID is passed via environment variable to avoid
    hardcoding. The username comes from the trigger event.
    """
    user_pool_id = os.environ["USER_POOL_ID"]
    username = event["userName"]

    logger.info(
        "Adding user to '%s' group: user_pool=%s, username=%s",
        DEFAULT_GROUP,
        user_pool_id,
        username,
    )

    cognito_client.admin_add_user_to_group(
        UserPoolId=user_pool_id,
        Username=username,
        GroupName=DEFAULT_GROUP,
    )

    return event

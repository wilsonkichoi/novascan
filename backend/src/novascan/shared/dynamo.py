"""DynamoDB client helper.

Reads the table name from the TABLE_NAME environment variable
and returns a boto3 DynamoDB Table resource.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table


def get_table() -> Table:
    """Return a boto3 DynamoDB Table resource.

    The table name is read from the TABLE_NAME environment variable,
    which is set by CDK when deploying the Lambda function.

    Raises:
        KeyError: If TABLE_NAME environment variable is not set.
    """
    table_name = os.environ["TABLE_NAME"]
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)

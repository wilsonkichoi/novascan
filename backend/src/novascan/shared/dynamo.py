"""DynamoDB client helper.

Reads the table name from the TABLE_NAME environment variable
and returns a boto3 DynamoDB Table resource.
"""

import os

import boto3


def get_table():
    """Return a boto3 DynamoDB Table resource.

    The table name is read from the TABLE_NAME environment variable,
    which is set by CDK when deploying the Lambda function.

    Raises:
        KeyError: If TABLE_NAME environment variable is not set.
    """
    table_name = os.environ["TABLE_NAME"]
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)

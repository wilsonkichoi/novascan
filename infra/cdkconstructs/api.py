"""API construct: API Gateway HTTP API, Cognito JWT authorizer, and API Lambda.

Creates:
- API Gateway HTTP API with CORS configuration
- Cognito JWT authorizer (excludes /api/health)
- API Lambda function with Powertools handler (bundled via uv)
- Lambda environment: TABLE_NAME, LOG_LEVEL, STAGE

See: SPEC.md Section 3 (Component Overview), Section 13 (CORS).
"""

import pathlib
import shutil
import subprocess
import tempfile
from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_apigatewayv2 as apigwv2
import aws_cdk.aws_apigatewayv2_authorizers as apigwv2_authorizers
import aws_cdk.aws_apigatewayv2_integrations as apigwv2_integrations
import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_s3 as s3
import jsii
from constructs import Construct

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "backend"
_EXCLUDE_DIRS = {"auth", "__pycache__"}


@jsii.implements(cdk.ILocalBundling)
class _UvLocalBundling:
    """Bundles API Lambda locally using uv (falls back to Docker if uv unavailable)."""

    def __init__(self, backend_dir: pathlib.Path) -> None:
        self._backend_dir = backend_dir

    def try_bundle(self, output_dir: str, *args: Any, **kwargs: Any) -> bool:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                req_file = f"{tmp}/requirements.txt"
                subprocess.run(
                    ["uv", "export", "--frozen", "--no-dev", "--no-editable", "-o", req_file],
                    cwd=self._backend_dir,
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    ["uv", "pip", "install", "--no-cache", "-r", req_file, "--target", output_dir],
                    cwd=self._backend_dir,
                    check=True,
                    capture_output=True,
                )
            shutil.copytree(
                self._backend_dir / "src" / "novascan",
                output_dir,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*_EXCLUDE_DIRS),
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


class ApiConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        stage: str,
        config: dict[str, Any],
        user_pool: cognito.IUserPool,
        app_client: cognito.IUserPoolClient,
        table: dynamodb.ITable,
        allowed_origins: list[str],
        receipts_bucket: s3.IBucket | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # --- API Lambda (bundled with uv) ---
        self.api_function = lambda_.Function(
            self,
            "ApiFunction",
            function_name=f"novascan-{stage}-api",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="api.app.handler",
            code=lambda_.Code.from_asset(
                str(BACKEND_DIR),
                bundling=cdk.BundlingOptions(
                    image=cdk.DockerImage.from_registry(
                        "ghcr.io/astral-sh/uv:python3.13-bookworm-slim"
                    ),
                    command=[
                        "bash",
                        "-c",
                        "uv export --frozen --no-dev --no-editable -o /tmp/requirements.txt && "
                        "uv pip install --no-cache -r /tmp/requirements.txt --target /asset-output && "
                        "cp -au src/novascan/. /asset-output/ && "
                        "rm -rf /asset-output/auth /asset-output/__pycache__",
                    ],
                    local=_UvLocalBundling(BACKEND_DIR),
                ),
            ),
            timeout=cdk.Duration.seconds(30),
            memory_size=256,
            environment={
                "TABLE_NAME": table.table_name,
                "LOG_LEVEL": config.get("logLevel", "INFO"),
                "STAGE": stage,
                "POWERTOOLS_SERVICE_NAME": "novascan-api",
                "POWERTOOLS_LOG_LEVEL": config.get("logLevel", "INFO"),
            },
            tracing=lambda_.Tracing.ACTIVE,
            description="NovaScan API Lambda — all REST routes via Powertools resolver",
        )

        # Grant DynamoDB access
        table.grant_read_write_data(self.api_function)

        # Grant S3 access if receipts bucket provided
        if receipts_bucket:
            receipts_bucket.grant_read_write(self.api_function)

        # --- Cognito JWT Authorizer ---
        authorizer = apigwv2_authorizers.HttpJwtAuthorizer(
            "CognitoAuthorizer",
            jwt_issuer=f"https://cognito-idp.{cdk.Stack.of(self).region}.amazonaws.com/{user_pool.user_pool_id}",
            jwt_audience=[app_client.user_pool_client_id],
        )

        # --- API Gateway HTTP API ---
        self.http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name=f"novascan-{stage}",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.PUT,
                    apigwv2.CorsHttpMethod.DELETE,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_headers=["Authorization", "Content-Type"],
                allow_origins=allowed_origins,
                max_age=cdk.Duration.seconds(86400),
            ),
            description=f"NovaScan API ({stage})",
        )

        # Lambda integration
        integration = apigwv2_integrations.HttpLambdaIntegration(
            "ApiIntegration",
            handler=self.api_function,
        )

        # Health check route — no auth
        self.http_api.add_routes(
            path="/api/health",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )

        # Catch-all authorized route
        self.http_api.add_routes(
            path="/api/{proxy+}",
            methods=[
                apigwv2.HttpMethod.GET,
                apigwv2.HttpMethod.POST,
                apigwv2.HttpMethod.PUT,
                apigwv2.HttpMethod.DELETE,
            ],
            integration=integration,
            authorizer=authorizer,
        )

        # --- Outputs ---
        self.api_url = self.http_api.api_endpoint

from typing import Any

import aws_cdk as cdk
from constructs import Construct

from cdkconstructs.storage import StorageConstruct
from cdkconstructs.auth import AuthConstruct
from cdkconstructs.api import ApiConstruct
from cdkconstructs.pipeline import PipelineConstruct
from cdkconstructs.frontend import FrontendConstruct


class NovascanStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        config: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.storage = StorageConstruct(self, "Storage", stage=stage, config=config)
        self.auth = AuthConstruct(self, "Auth", stage=stage, config=config)
        self.pipeline = PipelineConstruct(self, "Pipeline", stage=stage, config=config)
        self.frontend = FrontendConstruct(
            self,
            "Frontend",
            stage=stage,
            config=config,
            frontend_bucket=self.storage.frontend_bucket,
        )
        self.api = ApiConstruct(
            self,
            "Api",
            stage=stage,
            config=config,
            user_pool=self.auth.user_pool,
            app_client=self.auth.app_client,
            table=self.storage.table,
            allowed_origins=[f"https://{self.frontend.domain_name}"],
        )

        # --- Stack Outputs ---
        cdk.CfnOutput(self, "ApiUrl", value=self.api.api_url, description="API Gateway URL")
        cdk.CfnOutput(
            self,
            "CloudFrontDomain",
            value=self.frontend.domain_name,
            description="CloudFront distribution domain",
        )
        cdk.CfnOutput(
            self,
            "UserPoolId",
            value=self.auth.user_pool_id,
            description="Cognito User Pool ID",
        )
        cdk.CfnOutput(
            self,
            "AppClientId",
            value=self.auth.app_client_id,
            description="Cognito App Client ID",
        )
        cdk.CfnOutput(
            self,
            "FrontendBucketName",
            value=self.storage.frontend_bucket.bucket_name,
            description="S3 bucket for frontend static assets",
        )
        cdk.CfnOutput(
            self,
            "DistributionId",
            value=self.frontend.distribution_id,
            description="CloudFront distribution ID for cache invalidation",
        )

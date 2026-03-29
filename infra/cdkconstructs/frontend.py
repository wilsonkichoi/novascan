"""Frontend construct: CloudFront distribution with S3 origin and SPA routing.

Creates:
- CloudFront distribution with S3 origin access control
- Custom error responses for SPA routing (403/404 → /index.html 200)

See: SPEC.md Section 13 (CloudFront SPA Routing, Deployment Architecture).
"""

from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_cloudfront as cloudfront
import aws_cdk.aws_cloudfront_origins as origins
import aws_cdk.aws_s3 as s3
from constructs import Construct


class FrontendConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        stage: str,
        config: dict[str, Any],
        frontend_bucket: s3.IBucket,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # --- CloudFront Distribution ---
        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(frontend_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
            ],
            comment=f"NovaScan frontend ({stage})",
        )

        # --- Outputs ---
        self.domain_name = self.distribution.distribution_domain_name
        self.distribution_id = self.distribution.distribution_id

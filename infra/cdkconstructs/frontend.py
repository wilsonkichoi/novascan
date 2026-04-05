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

        # --- Security Response Headers (SECURITY-REVIEW M2) ---
        security_headers_policy = cloudfront.ResponseHeadersPolicy(
            self,
            "SecurityHeadersPolicy",
            response_headers_policy_name=f"novascan-{stage}-security-headers",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=cdk.Duration.seconds(63072000),
                    include_subdomains=True,
                    override=True,
                ),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(
                    override=True,
                ),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.DENY,
                    override=True,
                ),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
                    override=True,
                ),
                content_security_policy=cloudfront.ResponseHeadersContentSecurityPolicy(
                    content_security_policy=(
                        "default-src 'self'; "
                        "connect-src 'self' https://*.amazonaws.com https://*.execute-api.*.amazonaws.com; "
                        "img-src 'self' data: blob:; "
                        "style-src 'self' 'unsafe-inline'; "
                        "script-src 'self'"
                    ),
                    override=True,
                ),
            ),
        )

        # --- CloudFront Distribution ---
        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(frontend_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=security_headers_policy,
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

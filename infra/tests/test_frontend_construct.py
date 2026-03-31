"""Tests for the Frontend construct against SPEC.md Section 13 (Deployment Architecture).

Verifies:
- CloudFront distribution exists
- S3 origin configured
- Error responses for SPA routing (403/404 -> /index.html with 200)

Spec references:
- Section 3: Architecture ('Static React SPA served from S3 via CloudFront')
- Section 13: CloudFront SPA Routing, CORS Configuration
"""

from __future__ import annotations

from aws_cdk.assertions import Match, Template


class TestCloudFrontDistribution:
    """CloudFront distribution per SPEC.md Section 3, 13."""

    def test_distribution_exists(self, dev_template: Template) -> None:
        """At least one CloudFront distribution must be created.

        Spec Section 3: 'CloudFront distribution serving frontend from S3'
        """
        dev_template.resource_count_is(
            "AWS::CloudFront::Distribution", 1
        )

    def test_distribution_has_s3_origin(self, dev_template: Template) -> None:
        """Distribution must have an S3 origin for serving the frontend SPA.

        Spec Section 3: 'Static React SPA served from S3 via CloudFront'
        """
        dev_template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": {
                    "Origins": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "S3OriginConfig": Match.any_value(),
                                }
                            )
                        ]
                    ),
                },
            },
        )

    def test_distribution_enabled(self, dev_template: Template) -> None:
        """Distribution must be enabled."""
        dev_template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": {
                    "Enabled": True,
                },
            },
        )


class TestSpaRouting:
    """SPA routing error responses per SPEC.md Section 13."""

    def test_custom_error_response_for_403(self, dev_template: Template) -> None:
        """403 errors from S3 must be routed to /index.html with 200 status.

        Spec Section 13: 'CloudFront custom error response: 403/404 from S3
        -> return /index.html with HTTP 200'
        """
        dev_template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": {
                    "CustomErrorResponses": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "ErrorCode": 403,
                                    "ResponseCode": 200,
                                    "ResponsePagePath": "/index.html",
                                }
                            )
                        ]
                    ),
                },
            },
        )

    def test_custom_error_response_for_404(self, dev_template: Template) -> None:
        """404 errors from S3 must be routed to /index.html with 200 status.

        Spec Section 13: 'CloudFront custom error response: 403/404 from S3
        -> return /index.html with HTTP 200'
        """
        dev_template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": {
                    "CustomErrorResponses": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "ErrorCode": 404,
                                    "ResponseCode": 200,
                                    "ResponsePagePath": "/index.html",
                                }
                            )
                        ]
                    ),
                },
            },
        )


class TestViewerProtocol:
    """HTTPS enforcement per SPEC.md Section 12."""

    def test_viewer_protocol_redirects_to_https(
        self, dev_template: Template
    ) -> None:
        """CloudFront should enforce HTTPS for all viewers.

        Spec Section 12: 'All data in transit over HTTPS'
        Milestone 6 AC: 'HTTPS enforced (HTTP redirects to HTTPS)'

        The default behavior should redirect HTTP to HTTPS or require HTTPS.
        """
        dev_template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": {
                    "DefaultCacheBehavior": {
                        "ViewerProtocolPolicy": Match.string_like_regexp(
                            r"(redirect-to-https|https-only)"
                        ),
                    },
                },
            },
        )

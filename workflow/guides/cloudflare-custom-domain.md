# Cloudflare DNS Setup for subdomain.example.com

This guide covers the manual DNS steps required after `cdk deploy --context stage=prod`.

## Prerequisites

- Cloudflare account managing the `example.com` zone
- AWS CDK prod stack ready to deploy: `cd infra && uv run cdk synth --context stage=prod` succeeds
- AWS CLI configured with the correct profile/region

## Existing DNS Context

The `example.com` zone already has these records (do NOT modify them):
- **NS** — `eugene.ns.cloudflare.com`, `miki.ns.cloudflare.com` (Cloudflare nameservers)
- **MX** — Cloudflare email routing (`route1/2/3.mx.cloudflare.net`)
- **TXT** — DKIM (`cf2024-1._domainkey`) and SPF (`v=spf1 include:_spf.mx.cloudflare.net`)

Adding CNAME records for the `novascan` subdomain does NOT affect any of these. Subdomain DNS records are independent of zone-level records.

## Step 1: Deploy Prod Stack + ACM Certificate Validation

Run `cd infra && uv run cdk deploy --context stage=prod`. The deploy will **block** waiting for ACM certificate validation. You must add the DNS CNAME record in Cloudflare WHILE the deploy is running. If the deploy times out (~30 min), re-run it after DNS is configured — ACM will pick up the existing CNAME.

The deploy outputs two values for ACM certificate validation:

| Output Key | Example Value |
|-----------|---------------|
| `AcmCnameName` | `_abc123.subdomain.example.com` |
| `AcmCnameValue` | `_def456.acm-validations.aws.` |

In Cloudflare:

1. Go to **DNS** > **Records** > **Add Record**
2. Type: **CNAME**
3. Name: paste the `AcmCnameName` value (e.g., `_abc123.subdomain.example.com`)
4. Target: paste the `AcmCnameValue` value (e.g., `_def456.acm-validations.aws.`)
5. Proxy status: **DNS only** (gray cloud icon) -- this MUST NOT be proxied
6. TTL: Auto
7. Click **Save**

Wait for ACM to validate the certificate. This usually takes 5-15 minutes. You can check status in the AWS Console under Certificate Manager, or run:

```bash
aws acm describe-certificate \
  --certificate-arn <ARN from stack output> \
  --query 'Certificate.Status' \
  --output text
```

Expected result: `ISSUED`

## Step 2: CloudFront CNAME

After the ACM certificate shows `ISSUED`, add the CloudFront CNAME:

| Output Key | Example Value |
|-----------|---------------|
| `CloudFrontDomain` | `d1234abcdef.cloudfront.net` |

In Cloudflare:

1. Go to **DNS** > **Records** > **Add Record**
2. Type: **CNAME**
3. Name: `novascan`
4. Target: paste the `CloudFrontDomain` value (e.g., `d1234abcdef.cloudfront.net`)
5. Proxy status: **DNS only** (gray cloud icon)
6. TTL: Auto
7. Click **Save**

**CRITICAL: Cloudflare proxy must be OFF (gray cloud, not orange).** Cloudflare's reverse proxy terminates SSL and re-encrypts with its own certificate. This conflicts with CloudFront's SSL termination and will cause certificate mismatch errors. Always use DNS-only mode for CloudFront origins.

## Step 3: Verify

Wait 1-2 minutes for DNS propagation, then:

```bash
# Check DNS resolution
dig subdomain.example.com CNAME +short
# Expected: d1234abcdef.cloudfront.net.

# Check HTTPS
curl -I https://subdomain.example.com
# Expected: HTTP/2 200, with headers:
#   x-cache: Hit from cloudfront (or Miss on first request)
#   strict-transport-security: max-age=63072000; includeSubdomains
#   x-content-type-options: nosniff
#   x-frame-options: DENY

# Check full page load
curl -s https://subdomain.example.com | head -5
# Expected: HTML content (<!DOCTYPE html>...)
```

## Step 4: Cache Invalidation (if needed)

If the site loads stale content after a frontend deployment:

```bash
aws cloudfront create-invalidation \
  --distribution-id <distribution-id from stack output> \
  --paths "/*"
```

## Troubleshooting

### SSL/TLS Error (ERR_SSL_PROTOCOL_ERROR)

**Cause:** Cloudflare proxy is ON (orange cloud).

**Fix:** In Cloudflare DNS, click the orange cloud icon next to the `novascan` CNAME to toggle it to gray (DNS only). Wait 1-2 minutes.

### 403 Forbidden

**Cause:** CloudFront hasn't picked up the alternate domain name yet, or the ACM certificate isn't validated.

**Fix:**
1. Verify ACM certificate status is `ISSUED`
2. Run a cache invalidation (Step 4 above)
3. Wait 5 minutes and retry

### ACM Certificate Stuck in "Pending validation"

**Cause:** CNAME validation record is incorrect or hasn't propagated.

**Fix:**
1. Double-check the CNAME name and value match the stack output exactly
2. Verify proxy is OFF (gray cloud) -- Cloudflare proxy interferes with ACM validation
3. Verify the record exists: `dig _abc123.subdomain.example.com CNAME +short`
4. Wait up to 30 minutes -- ACM validation can be slow on first attempt

### Mixed Content or API Errors After Domain Switch

**Cause:** Frontend was built with the old CloudFront URL, not the custom domain.

**Fix:** Rebuild and redeploy the frontend. The deploy script queries CloudFormation for live stack outputs automatically:
```bash
python scripts/deploy.py frontend prod
```

## DNS Records Summary

After setup, your Cloudflare DNS should have these records for the `example.com` zone:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| CNAME | `_abc123.novascan` | `_def456.acm-validations.aws.` | DNS only |
| CNAME | `novascan` | `d1234abcdef.cloudfront.net` | DNS only |

## Multi-Provider Subdomains

The `example.com` zone can host subdomains pointing to different cloud providers simultaneously:

- `subdomain.example.com` → AWS CloudFront (this setup)
- `asdf.example.com` → GCP (future)
- `other.example.com` → any provider (future)

Each subdomain gets its own independent CNAME/A record. There are no cross-provider conflicts because:

1. **TLS certificates are per-subdomain.** NovaScan's ACM certificate covers only `subdomain.example.com`. Other subdomains use their own provider's certificates.
2. **Cloudflare proxy setting is per-record.** DNS-only (gray cloud) for the `novascan` CNAME doesn't affect proxy settings on other subdomain records. Future subdomains can independently choose proxied or DNS-only.
3. **No wildcard certificate.** We use a single-domain cert, not `*.example.com`, so there's no ownership conflict between providers.

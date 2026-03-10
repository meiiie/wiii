# Magic Link Auth — Production Setup

## Prerequisites
1. Resend account (resend.com — free tier: 3,000 emails/month)
2. Domain `holilihu.online` managed in Cloudflare DNS

## Step 1: Add Domain in Resend
1. Dashboard → Domains → Add Domain → `holilihu.online`
2. Resend provides DNS records. Add them in Cloudflare:

| Type | Name | Value |
|------|------|-------|
| MX | `send.holilihu.online` | `feedback-smtp.us-east-1.amazonses.com` (priority 10) |
| TXT | `send.holilihu.online` | `v=spf1 include:amazonses.com ~all` |
| CNAME | `resend._domainkey.holilihu.online` | _(from Resend dashboard)_ |
| CNAME | `resend2._domainkey.holilihu.online` | _(from Resend dashboard)_ |
| TXT | `_dmarc.holilihu.online` | `v=DMARC1; p=quarantine;` |

3. Wait for verification (usually < 5 minutes with Cloudflare)

## Step 2: Get API Key
1. Dashboard → API Keys → Create API Key
2. Name: `wiii-production`
3. Permission: `Sending access` (Full access not needed)
4. Copy key (starts with `re_`)

## Step 3: Configure .env.production
```bash
ENABLE_MAGIC_LINK_AUTH=true
RESEND_API_KEY=re_xxxxxxxxxxxxx
MAGIC_LINK_BASE_URL=https://wiii.holilihu.online
MAGIC_LINK_FROM_EMAIL=Wiii <noreply@holilihu.online>
```

## Step 4: Verify
```bash
curl -X POST https://wiii.holilihu.online/api/v1/auth/magic-link/request \
  -H "Content-Type: application/json" \
  -d '{"email": "test@gmail.com"}'
```

## Rate Limits
- Per email: 5 requests/hour (`magic_link_max_per_hour`)
- Resend free tier: 100 emails/day, 3,000/month
- Cooldown between resends: 45 seconds (`magic_link_resend_cooldown_seconds`)

## Security (Sprint 224)
- Token: `secrets.token_urlsafe(48)` → SHA-256 hashed in DB
- Expiry: 10 minutes (configurable via `magic_link_expires_seconds`)
- One-time use: atomic DB consume
- WebSocket session verification with 15-min timeout
- Rate limit: 5 per email per hour + 45s cooldown

## Troubleshooting
- **Email not received**: Check Resend dashboard → Logs for delivery status
- **Domain not verified**: DNS propagation can take up to 48h (usually minutes with Cloudflare)
- **401 on verify endpoint**: Token expired or already used (one-time only)

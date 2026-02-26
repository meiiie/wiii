# Wiii Production Deployment Guide

> **Team**: Hong Linh Linh Hung (holilihu.online)
>
> GCP Compute Engine + Caddy (auto-SSL) + Nginx + Docker Compose
>
> Target: 10K+ users, ~380K VND/month (~$15 USD)

---

## Architecture

```
Internet
    │
    ▼
┌──────────────────────────────────────┐
│  Cloudflare DNS (free)               │  DDoS protection, CDN
│  *.holilihu.online → GCP Static IP   │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│  GCP Compute Engine (e2-medium)      │  2 vCPU, 4GB RAM
│  Ubuntu 22.04 LTS                    │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ Caddy (host service)          │  │  Auto-SSL (Let's Encrypt)
│  │ :443 → Nginx :80              │  │  HTTPS termination
│  └────────────────────────────────┘  │
│           │                          │
│  ┌────────────────────────────────┐  │
│  │ docker-compose.prod.yml       │  │
│  │  Nginx → App (API :8000)      │  │  Subdomain routing + SPA
│  │  PostgreSQL  MinIO  Valkey    │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

**Flow**: Cloudflare → Caddy (SSL) → Nginx (routing + SPA) → App (API)

---

## Step 1: Domain (Done!)

Domain `holilihu.online` has been purchased (Hong Linh Linh Hung).

> DNS will be configured after GCP VM is created (Step 5).

---

## Step 2: Create GCP VM

Go to [Google Cloud Console](https://console.cloud.google.com/) → Compute Engine → Create Instance:

| Setting | Value |
|---------|-------|
| Name | `wiii-production` |
| Region | `asia-southeast1` (Singapore — lowest latency to Vietnam) |
| Zone | `asia-southeast1-b` |
| Machine | `e2-medium` (2 vCPU, 4GB RAM) |
| Boot disk | Ubuntu 22.04 LTS, **50GB SSD** |
| Firewall | **Allow HTTP** + **Allow HTTPS** (check both boxes) |

After creation:
1. Go to **VPC Network → External IP addresses**
2. Find your VM's IP → click **Reserve** (makes it static)
3. Note this IP — you'll need it for DNS

**Monthly cost**: ~350K VND ($14), covered by your 26M VND credits (~6 years).

---

## Step 3: Server Setup

SSH into your VM:

```bash
# From Google Cloud Console: click "SSH" button on VM page
# Or from terminal:
gcloud compute ssh wiii-production --zone=asia-southeast1-b
```

Run the setup script:

```bash
# Option A: Run directly from repo (if public)
curl -fsSL https://raw.githubusercontent.com/<your-org>/wiii/main/maritime-ai-service/scripts/deploy/setup-server.sh | bash

# Option B: Copy and run manually
nano setup-server.sh   # Paste contents of scripts/deploy/setup-server.sh
chmod +x setup-server.sh
./setup-server.sh
```

**Important**: Log out and back in after setup for Docker group:
```bash
exit
# SSH back in
```

Verify:
```bash
docker --version      # Docker 27.x+
docker compose version # Docker Compose v2.x+
caddy version         # Caddy v2.x+
```

---

## Step 4: Deploy Application

### 4.1 Clone Repository

```bash
cd /opt/wiii
git clone https://github.com/<your-org>/wiii.git .
# If private repo, use SSH key or personal access token
```

### 4.2 Create Production Environment

```bash
cd /opt/wiii/maritime-ai-service
cp scripts/deploy/.env.production.template .env.production
nano .env.production
```

**Replace ALL `CHANGE_ME_*` values**. Generate secrets with:
```bash
openssl rand -hex 32   # For API_KEY, JWT_SECRET_KEY
openssl rand -hex 16   # For database passwords
```

### 4.3 Configure Caddy

```bash
# Edit domain name if different from holilihu.online
nano /opt/wiii/maritime-ai-service/scripts/deploy/Caddyfile

# Install Caddyfile
sudo cp /opt/wiii/maritime-ai-service/scripts/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

### 4.4 Run Deploy Script

```bash
cd /opt/wiii
chmod +x maritime-ai-service/scripts/deploy/deploy.sh
./maritime-ai-service/scripts/deploy/deploy.sh
```

First deploy takes ~5 minutes (building Docker image). Subsequent deploys ~1-2 minutes.

---

## Step 5: Configure DNS

### Option A: Cloudflare (Recommended — free DDoS protection)

1. Create account at [cloudflare.com](https://cloudflare.com) (free)
2. **Add site** → enter your domain (e.g., `holilihu.online`)
3. Cloudflare gives you **2 nameservers** — update these at your registrar
4. Add DNS records:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `<GCP_STATIC_IP>` | Proxied (orange cloud) |
| A | `*` | `<GCP_STATIC_IP>` | DNS only (grey cloud) — wildcard for org subdomains |

5. SSL/TLS settings → set to **Full (strict)**

### Option B: Direct DNS (at registrar)

At your registrar's DNS panel, add:
```
A    holilihu.online      →  <GCP_STATIC_IP>    TTL: 300
A    *.holilihu.online    →  <GCP_STATIC_IP>    TTL: 300
```

> DNS propagation takes 5 minutes to 24 hours. Check: `dig holilihu.online`

---

## Step 6: Configure Webhooks

### Facebook Messenger

1. Go to [Facebook Developer Dashboard](https://developers.facebook.com/)
2. Your App → Messenger → Settings → Webhooks
3. **Callback URL**: `https://holilihu.online/api/v1/messenger/webhook`
4. **Verify Token**: same as `FACEBOOK_VERIFY_TOKEN` in `.env.production`
5. Subscribe to: `messages`, `messaging_postbacks`

### Zalo OA

1. Go to [Zalo OA Admin](https://oa.zalo.me/)
2. Settings → Webhook Configuration
3. **Callback URL**: `https://holilihu.online/api/v1/zalo/webhook`
4. **Token**: same as `ZALO_WEBHOOK_TOKEN` in `.env.production`

---

## Step 7: Verify

```bash
# 1. Health check
curl https://holilihu.online/api/v1/health/live
# Expected: {"status": "ok"}

# 2. API docs
# Open in browser: https://holilihu.online/docs

# 3. Test chat endpoint
curl -X POST https://holilihu.online/api/v1/chat \
  -H "X-API-Key: your-api-key" \
  -H "X-User-ID: test-user" \
  -H "X-Session-ID: test-session" \
  -H "Content-Type: application/json" \
  -d '{"message": "Xin chào!"}'

# 4. Facebook webhook verification
# Facebook Developer Dashboard → Messenger → Test Callback

# 5. Zalo webhook verification
# Zalo OA Admin → Webhook → Test Connection
```

---

## Common Operations

### View logs
```bash
cd /opt/wiii/maritime-ai-service

# App logs (live)
docker compose -f docker-compose.prod.yml logs -f app

# All services
docker compose -f docker-compose.prod.yml logs -f

# Caddy logs
sudo journalctl -u caddy -f
sudo tail -f /var/log/caddy/holilihu-access.log
```

### Restart services
```bash
cd /opt/wiii/maritime-ai-service

# Restart app only
docker compose -f docker-compose.prod.yml restart app

# Restart everything
docker compose -f docker-compose.prod.yml down && docker compose -f docker-compose.prod.yml up -d
```

### Update deployment
```bash
cd /opt/wiii
./maritime-ai-service/scripts/deploy/deploy.sh
```

### Database access (emergency)
```bash
cd /opt/wiii/maritime-ai-service

# Connect to PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres psql -U wiii wiii_ai

# Run specific migration
docker compose -f docker-compose.prod.yml run --rm app alembic upgrade head
```

### Check disk usage
```bash
df -h                                    # System disk
docker system df                         # Docker disk usage
docker system prune -af --volumes        # Clean unused (CAREFUL!)
```

---

## Troubleshooting

### "SSL certificate not working"
- Caddy needs ports 80+443 open (check: `sudo ufw status`)
- DNS must point to your GCP IP (check: `dig holilihu.online`)
- Cloudflare SSL must be "Full (strict)" if using Cloudflare proxy
- Check Caddy logs: `sudo journalctl -u caddy --since "5 minutes ago"`

### "App not starting"
```bash
# Check app logs
docker compose -f docker-compose.prod.yml logs app --tail 50

# Check if .env.production has all required values
grep "CHANGE_ME" .env.production    # Should return nothing

# Check Docker health
docker compose -f docker-compose.prod.yml ps
```

### "Database connection refused"
```bash
# Check PostgreSQL is running
docker compose -f docker-compose.prod.yml ps postgres

# Check PostgreSQL logs
docker compose -f docker-compose.prod.yml logs postgres --tail 20

# Verify DATABASE_URL uses container hostname (postgres, not localhost)
grep DATABASE_URL .env.production
```

### "Webhook verification fails"
- Ensure callback URL uses HTTPS (not HTTP)
- Check verify token matches `.env.production` exactly
- Caddy must be running with valid SSL: `sudo systemctl status caddy`
- Test endpoint directly: `curl -v https://holilihu.online/api/v1/messenger/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test`

### "Out of memory"
```bash
# Check memory usage
free -h
docker stats --no-stream

# If tight, reduce Gunicorn workers in .env.production
# GUNICORN_WORKERS=2  (instead of 4)
```

---

## Cost Summary

| Item | Monthly Cost | Notes |
|------|-------------|-------|
| GCP e2-medium | ~350K VND | Covered by 26M credits (~6 years) |
| `.online` domain | ~20K VND | ~250K VND/year |
| Cloudflare DNS | Free | Free tier is sufficient |
| Caddy SSL | Free | Let's Encrypt automatic |
| **Total** | **~380K VND/month** | **~$15 USD/month** |

---

## Security Notes

- `.env.production` contains secrets — **never commit to git**
- PostgreSQL and MinIO ports are **not exposed** externally (internal Docker network only)
- Caddy handles all TLS termination — internal traffic is HTTP (within Docker network)
- UFW blocks all ports except 22 (SSH), 80 (HTTP→redirect), 443 (HTTPS)
- Use SSH keys for VM access — disable password auth in `/etc/ssh/sshd_config`
- Rotate secrets regularly: `openssl rand -hex 32`

---

## Neo4j (Optional)

Neo4j is disabled by default since Sprint 165. If you need GraphRAG:

1. Set `ENABLE_NEO4J=true` in `.env.production`
2. The `docker-compose.prod.yml` includes Neo4j — it will start automatically
3. Set a strong `NEO4J_PASSWORD`

> Note: Neo4j adds ~2GB RAM usage. On e2-medium (4GB), consider upgrading to e2-standard-4 (4 vCPU, 16GB) if enabling Neo4j.

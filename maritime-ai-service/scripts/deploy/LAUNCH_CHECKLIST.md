# Wiii Production Launch Checklist

> Domain: holilihu.online | Team: Hong Linh Linh Hung
>
> Use this checklist on launch day. Check off each item.

---

## Pre-Launch (on your local machine)

- [ ] All code committed and pushed to `main`
- [ ] All tests passing: `pytest tests/unit/ -v`
- [ ] `.env.production.template` has no typos
- [ ] `docker-compose.prod.yml` validates: `docker compose -f docker-compose.prod.yml config --services`
- [ ] Domain `holilihu.online` purchased and accessible

---

## GCP VM Setup

- [ ] VM created: `e2-medium`, `asia-southeast1-b`, Ubuntu 22.04, 50GB SSD
- [ ] Firewall: "Allow HTTP" + "Allow HTTPS" checked
- [ ] Static IP reserved and noted: `______________`
- [ ] SSH into VM works: `gcloud compute ssh wiii-production --zone=asia-southeast1-b`

---

## Server Setup (SSH into VM)

- [ ] `setup-server.sh` ran successfully
- [ ] Logged out and back in (docker group)
- [ ] Verify: `docker --version` → 27.x+
- [ ] Verify: `docker compose version` → v2.x+
- [ ] Verify: `caddy version` → v2.x+
- [ ] Verify: `free -h` → shows 2GB swap
- [ ] Verify: `sudo ufw status` → 22, 80, 443 only

---

## Application Deploy

- [ ] Repo cloned: `git clone <url> /opt/wiii`
- [ ] `.env.production` created from template
- [ ] ALL `CHANGE_ME_*` values replaced with real secrets
- [ ] Secrets generated: `openssl rand -hex 32` (for API_KEY, JWT_SECRET_KEY)
- [ ] `GOOGLE_API_KEY` set (Gemini API key)
- [ ] `POSTGRES_PASSWORD` set (strong password)
- [ ] `MINIO_SECRET_KEY` set (strong password)
- [ ] Caddyfile installed: `sudo cp scripts/deploy/Caddyfile /etc/caddy/Caddyfile`
- [ ] Caddy restarted: `sudo systemctl restart caddy`
- [ ] `deploy.sh` ran successfully
- [ ] Health check: `curl http://localhost:8000/api/v1/health/live` → `{"status":"alive"}`
- [ ] Nginx health: `curl http://localhost:80/health` → `{"status":"ok"}`

---

## DNS Configuration

- [ ] Cloudflare account created (free tier)
- [ ] Domain added to Cloudflare
- [ ] Nameservers updated at registrar (can take up to 48h)
- [ ] DNS records added:
  - [ ] `A @ → <GCP_IP>` (Proxied)
  - [ ] `A * → <GCP_IP>` (DNS only — for wildcard subdomains)
- [ ] SSL/TLS mode set to **Full (strict)**
- [ ] DNS propagation confirmed: `dig holilihu.online`
- [ ] HTTPS works: `curl https://holilihu.online/api/v1/health/live`

---

## Webhook Configuration

### Facebook Messenger
- [ ] Facebook Developer account set up
- [ ] App created with Messenger product
- [ ] Webhook configured:
  - URL: `https://holilihu.online/api/v1/messenger/webhook`
  - Verify Token: matches `FACEBOOK_VERIFY_TOKEN` in `.env.production`
- [ ] Subscribed to: `messages`, `messaging_postbacks`
- [ ] Page connected to app
- [ ] Test message sent → response received

### Zalo OA
- [ ] Zalo OA account set up
- [ ] Webhook configured:
  - URL: `https://holilihu.online/api/v1/zalo/webhook`
  - Token: matches `ZALO_WEBHOOK_TOKEN` in `.env.production`
- [ ] Test message sent → response received

---

## Post-Launch Verification

- [ ] API docs accessible: `https://holilihu.online/docs`
- [ ] Chat endpoint works:
  ```bash
  curl -X POST https://holilihu.online/api/v1/chat \
    -H "X-API-Key: <your-key>" \
    -H "X-User-ID: test" \
    -H "X-Session-ID: test" \
    -H "Content-Type: application/json" \
    -d '{"message": "Xin chao!"}'
  ```
- [ ] Streaming works (SSE):
  ```bash
  curl -N https://holilihu.online/api/v1/chat/stream/v3 \
    -H "X-API-Key: <your-key>" \
    -H "X-User-ID: test" \
    -H "X-Session-ID: test" \
    -H "Content-Type: application/json" \
    -d '{"message": "COLREG la gi?"}'
  ```
- [ ] Landing page loads: `https://holilihu.online/`
- [ ] Status dashboard: `./scripts/deploy/status.sh`

---

## Monitoring Setup

- [ ] Backup cron configured:
  ```bash
  sudo crontab -e
  # Add: 0 20 * * * /opt/wiii/maritime-ai-service/scripts/deploy/backup-db.sh
  ```
- [ ] Health check cron configured:
  ```bash
  sudo crontab -e
  # Add: */2 * * * * /opt/wiii/maritime-ai-service/scripts/deploy/health-check.sh
  ```
- [ ] First backup created: `./scripts/deploy/backup-db.sh`
- [ ] (Optional) Discord/Telegram webhook set for alerts
- [ ] (Optional) UptimeRobot monitor on `https://holilihu.online/health`

---

## Security Final Check

- [ ] `grep "CHANGE_ME" .env.production` returns nothing
- [ ] SSH password auth disabled: `sudo sshd -T | grep passwordauthentication` → `no`
- [ ] fail2ban running: `sudo fail2ban-client status sshd`
- [ ] No ports exposed except 22, 80, 443: `sudo ufw status`
- [ ] PostgreSQL not exposed externally (internal Docker network only)
- [ ] `.env.production` NOT committed to git

---

## File Reference

| File | Purpose |
|------|---------|
| `scripts/deploy/setup-server.sh` | One-time server setup |
| `scripts/deploy/Caddyfile` | SSL termination config |
| `scripts/deploy/.env.production.template` | Environment variable template |
| `scripts/deploy/deploy.sh` | Deploy/update application |
| `scripts/deploy/backup-db.sh` | PostgreSQL backup |
| `scripts/deploy/health-check.sh` | Monitoring + alerts |
| `scripts/deploy/status.sh` | Quick status dashboard |
| `scripts/deploy/README.md` | Full deployment guide |
| `nginx/nginx.conf` | Reverse proxy + rate limiting + SPA |
| `nginx/html/index.html` | Landing page |
| `postgres/postgresql.conf` | PostgreSQL tuning for 4GB RAM |
| `docker-compose.prod.yml` | Production Docker stack |

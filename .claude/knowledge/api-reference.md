# API Reference

## Domain Admin API
```
GET /api/v1/admin/domains          # List all registered domains
GET /api/v1/admin/domains/{id}     # Get domain details
GET /api/v1/admin/domains/{id}/skills  # List domain skills
```

## Organization Admin API (Sprint 24, enhanced Sprints 161, 181)
```
GET    /api/v1/organizations              # List orgs (admin: all, user: own)
GET    /api/v1/organizations/{org_id}     # Get org details
POST   /api/v1/organizations              # Create org (admin only)
PATCH  /api/v1/organizations/{org_id}     # Update org (admin only)
DELETE /api/v1/organizations/{org_id}     # Soft-delete org (admin only)
POST   /api/v1/organizations/{org_id}/members        # Add member (admin or org admin)
DELETE /api/v1/organizations/{org_id}/members/{uid}   # Remove member (admin or org admin)
GET    /api/v1/organizations/{org_id}/members         # List members (admin or org admin)
GET    /api/v1/users/me/organizations     # List current user's orgs
GET    /api/v1/organizations/{org_id}/settings        # Org settings (Sprint 161)
PATCH  /api/v1/organizations/{org_id}/settings        # Update org settings (org admin: branding only)
GET    /api/v1/organizations/{org_id}/permissions     # User permissions for org (incl. org_role)
GET    /api/v1/users/me/admin-context     # Admin capabilities (Sprint 181)
```

## Authentication API (Sprints 157-159)
```
GET  /api/v1/auth/google/login        # Initiate Google OAuth
GET  /api/v1/auth/google/callback     # OAuth callback → JWT pair
POST /api/v1/auth/token/refresh       # JWT refresh
POST /api/v1/auth/lms/token           # LMS token exchange (HMAC-signed)
POST /api/v1/auth/lms/token/refresh   # LMS token refresh
GET  /api/v1/auth/lms/health          # LMS connector health
```

## User Management API (Sprint 158)
```
GET   /api/v1/users/me                # Current user profile
PATCH /api/v1/users/me                # Update profile
GET   /api/v1/users/me/identities     # Linked accounts (federated)
DELETE /api/v1/users/me/identities/{id} # Unlink identity
GET   /api/v1/users                   # Admin: list all users
PATCH /api/v1/users/{id}/role         # Admin: change user role
POST  /api/v1/users/{id}/deactivate   # Admin: deactivate user
```

## Context Management API (Sprint 78)
```
GET  /api/v1/chat/context/info     # Token budget, utilization, message count
POST /api/v1/chat/context/compact  # Trigger conversation compaction
POST /api/v1/chat/context/clear    # Clear conversation context for session
```

## Living Agent API (Sprint 170)
```
GET  /api/v1/living-agent/status           # Full status (soul, mood, heartbeat, counts)
GET  /api/v1/living-agent/emotional-state  # Current 4D emotional state
GET  /api/v1/living-agent/journal          # Recent journal entries
GET  /api/v1/living-agent/skills           # All skills with lifecycle status
GET  /api/v1/living-agent/heartbeat        # Heartbeat scheduler info
POST /api/v1/living-agent/heartbeat/trigger # Manually trigger heartbeat cycle
```

## Soul Bridge API (Sprint 213)
```
GET  /api/v1/soul-bridge/status              # Bridge status + peer connection states
GET  /api/v1/soul-bridge/peers               # List connected peers with agent cards
GET  /api/v1/soul-bridge/peers/{peer_id}/card  # Specific peer's agent card
POST /api/v1/soul-bridge/events              # HTTP fallback for receiving events
POST /api/v1/soul-bridge/connect             # Manual peer connection
POST /api/v1/soul-bridge/disconnect          # Manual peer disconnect
WS   /api/v1/soul-bridge/ws                  # WebSocket real-time connection
GET  /.well-known/agent.json                 # Soul identity card (A2A-inspired)
```

## API Authentication

Triple auth: API Key + JWT + LMS Token Exchange (HMAC)
```
X-API-Key: your-api-key
X-User-ID: student-123
X-Session-ID: session-abc
X-Role: student|teacher|admin
X-Organization-ID: lms-hang-hai       # Optional: multi-tenant org context
```

Optional domain/org routing:
```json
{
  "domain_id": "maritime",
  "organization_id": "lms-hang-hai"
}
```

## Domain Plugin Development

### Creating a New Domain
```bash
cp -r app/domains/_template app/domains/my_domain
# Edit domain.yaml → write prompts → add to active_domains → restart
```

# API Contract: Immich for Downstream Consumers

**Feature**: 002-immich-setup | **Date**: 2026-04-04
**Consumers**: 001-ai-story-engine, 003-immich-mcp

## API Key Contract

Downstream services locate the Immich API key at a well-known path. This is the
only contract this setup feature exposes — no custom API is built.

### API Key File

```
Path:        /Volumes/HomeRAID/immich/api-key.txt
Permissions: 600 (owner read-only)
Format:      Single line, no trailing newline
Content:     Raw API key string (alphanumeric, ~32 characters)
```

**Usage by consumers**:

```bash
IMMICH_API_KEY=$(cat /Volumes/HomeRAID/immich/api-key.txt)
curl -H "x-api-key: $IMMICH_API_KEY" http://macmini.local:2283/api/assets
```

### Base URL

```
http://macmini.local:2283/api
```

All Immich REST API endpoints are available under this base URL. Consumers
should refer to the Immich API documentation for endpoint details. This setup
feature guarantees the URL is reachable and the API key grants admin access.

### Health Check

Consumers can verify Immich is up before making requests:

```
GET http://macmini.local:2283/api/server/ping
Expected: HTTP 200, body: {"res":"pong"}
SLA: < 500ms response time (SC-005)
```

### Guarantees Provided by This Setup

| Guarantee | Source Requirement |
|-----------|-------------------|
| API is accessible at `http://macmini.local:2283/api` | FR-008 |
| API key file exists at `/Volumes/HomeRAID/immich/api-key.txt` | FR-010 |
| API key has admin privileges | Decision 5 (research.md) |
| External library is registered and contains icloud-export files | FR-004 |
| Face recognition and CLIP search are enabled | FR-006, FR-007 |

### Not Guaranteed by This Setup

- Specific Immich REST API endpoint shapes (use Immich official docs for v2.6.3)
- Immich uptime SLA beyond "restarts automatically" (no monitoring agent)
- API availability during Docker restart window (typically < 30s)

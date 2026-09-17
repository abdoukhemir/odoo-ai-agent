# MCP Server for Odoo 19.0

AI assistants (Claude, Cursor, VS Code, Claude Code) ko Odoo ERP se securely connect karne ka module. Model Context Protocol (MCP) standard use karta hai.

## Features
- REST API + XML-RPC proxy with MCP permission layer
- Per-model CRUD access control with field-level restrictions
- Bearer Token (API Key) + Basic Auth support
- Rate limiting (configurable per minute)
- IP whitelist for production security
- Full audit logging with duration tracking
- Response caching with configurable TTL
- YOLO mode for development (bypasses permissions)
- LLM-optimized output formatting

## Installation

1. Copy `mcp_server_ai` folder to your Odoo addons path
2. Restart Odoo server
3. Apps > Update Apps List > Search "MCP Server" > Install

## Configuration

### Step 1: Enable MCP Server
Settings > General Settings > scroll to **MCP Server** section > Enable MCP Server

### Step 2: Add Models to Expose
Settings > Technical > MCP Server > Model Access > **New**
- Select model (e.g., Contact / res.partner)
- Set permissions: Read, Write, Create, Delete (toggle each)
- Optional: Set allowed fields (JSON list), cache TTL, allowed groups

### Step 3: Generate API Key
Settings > Users & Companies > Users > Select your user > **API Keys** tab > New API Key
- Copy the key - you'll need it for client configuration
- Scope: `rpc`

### Step 4: Rate Limiting (Optional)
Settings > General Settings > MCP Server:
- Rate Limit: 10 requests/min (default, set 0 to disable)
- Max Records Per Request: 1000

### Step 5: IP Whitelist (Optional)
Settings > General Settings > MCP Server:
- IP Whitelist: One IP per line (empty = allow all)

## API Endpoints

### Public (No Auth Required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/mcp/api/v1/health` | Health check + MCP status |
| GET | `/mcp/api/v1/system/info` | Odoo version, DB, exposed model count |

### Authenticated (Bearer Token or Basic Auth)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/mcp/api/v1/auth/validate` | Validate credentials, return user info |
| GET | `/mcp/api/v1/models` | List all exposed models with permissions |
| GET | `/mcp/api/v1/models/<model>/fields` | Get field metadata for a model |
| POST | `/mcp/api/v1/models/<model>/search` | Search records with domain filter |
| POST | `/mcp/api/v1/models/<model>/read` | Read specific records by IDs |
| POST | `/mcp/api/v1/models/<model>/browse` | Paginated browse with offset/limit |
| POST | `/mcp/api/v1/models/<model>/count` | Count records matching domain |
| POST | `/mcp/api/v1/models/<model>/create` | Create new record |
| POST | `/mcp/api/v1/models/<model>/write` | Update existing records |
| POST | `/mcp/api/v1/models/<model>/unlink` | Delete records |
| POST | `/mcp/api/v1/models/<model>/call` | Call arbitrary model method |

### XML-RPC Endpoints
| Endpoint | Methods |
|----------|---------|
| `/mcp/xmlrpc/2/common` | `version()`, `authenticate(db, login, password)` |
| `/mcp/xmlrpc/2/object` | `execute_kw(db, uid, password, model, method, args, kwargs)` |

## Usage Examples

### Health Check
```bash
curl http://localhost:8069/mcp/api/v1/health
```
Response:
```json
{"status": "ok", "timestamp": "2026-02-09T10:34:06Z", "module_version": "19.0.1.0.0", "mcp_enabled": true}
```

### Validate Auth
```bash
curl -X POST http://localhost:8069/mcp/api/v1/auth/validate \
  -H "Authorization: Bearer YOUR_API_KEY"
```
Response:
```json
{"success": true, "data": {"user_id": 2, "login": "admin", "name": "Administrator", "is_mcp_admin": true}}
```

### Search Partners
```bash
curl -X POST http://localhost:8069/mcp/api/v1/models/res.partner/search \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"domain": [["is_company", "=", true]], "fields": ["name", "email"], "limit": 5}'
```
Response:
```json
{"success": true, "data": [{"id": 1, "name": "My Company", "email": null}], "count": 1, "total": 1}
```

### Browse with Pagination
```bash
curl -X POST http://localhost:8069/mcp/api/v1/models/res.partner/browse \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"domain": [], "fields": ["name"], "limit": 3, "offset": 0}'
```
Response:
```json
{"success": true, "data": [...], "pagination": {"offset": 0, "limit": 3, "count": 3, "total": 4, "has_more": true}}
```

### Create Record
```bash
curl -X POST http://localhost:8069/mcp/api/v1/models/res.partner/create \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"values": {"name": "New Partner", "email": "new@test.com", "is_company": true}}'
```

### Update Record
```bash
curl -X POST http://localhost:8069/mcp/api/v1/models/res.partner/write \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ids": [8], "values": {"name": "Updated Name"}}'
```

### XML-RPC Usage (Python)
```python
import xmlrpc.client

common = xmlrpc.client.ServerProxy('http://localhost:8069/mcp/xmlrpc/2/common')
print(common.version())

uid = common.authenticate('mydb', 'admin', 'admin', {})

models = xmlrpc.client.ServerProxy('http://localhost:8069/mcp/xmlrpc/2/object')
partners = models.execute_kw('mydb', uid, 'admin',
    'res.partner', 'search_read', [[]],
    {'fields': ['name', 'email'], 'limit': 5})
```

### Claude Desktop Configuration

**Config file location:**
- Linux: `~/.config/claude/claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python3",
      "args": ["/full/path/to/mcp_server_ai/mcp_bridge.py"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_API_KEY": "your-api-key-here",
        "ODOO_DB": "your-database-name"
      }
    }
  }
}
```

> **Note:** `ODOO_DB` is **required for production** servers with multiple databases. It sends the `X-Odoo-Database` header (Odoo 19 native). For single-database setups it can be omitted.

After saving, restart Claude Desktop completely.

### Claude Code (CLI / VS Code)
```bash
claude mcp add-json odoo '{
  "command": "python3",
  "args": ["/full/path/to/mcp_server_ai/mcp_bridge.py"],
  "env": {
    "ODOO_URL": "http://localhost:8069",
    "ODOO_API_KEY": "your-api-key-here",
    "ODOO_DB": "your-database-name"
  }
}' -s user
```

After running, restart Claude Code and type `/mcp` to verify connection.

### Cursor IDE

**Config file:** `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python3",
      "args": ["/full/path/to/mcp_server_ai/mcp_bridge.py"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_API_KEY": "your-api-key-here",
        "ODOO_DB": "your-database-name"
      }
    }
  }
}
```

## Error Responses

| HTTP Code | Error Code | Meaning |
|-----------|------------|---------|
| 401 | AUTH_INVALID | Missing/invalid credentials |
| 403 | BLOCKED_MODEL | Model is security-blocked |
| 403 | OPERATION_DENIED | Operation not allowed on model |
| 404 | MODEL_NOT_FOUND | Model not exposed via MCP |
| 429 | RATE_LIMITED | Rate limit exceeded |
| 500 | INTERNAL_ERROR | Server error |

## Security Best Practices
- Always use HTTPS in production
- Generate unique API keys per integration
- Enable IP whitelist for production environments
- Set appropriate rate limits
- Only expose necessary models with minimum required permissions
- Use field-level restrictions to hide sensitive fields
- Review audit logs regularly (Settings > Technical > MCP Server > Audit Logs)
- Never enable YOLO mode in production

## Audit Logs
Settings > Technical > MCP Server > Audit Logs

Every MCP API call is logged with:
- User, IP address, user agent
- Model, operation, method name
- Response status (success/error/denied)
- Duration in milliseconds
- Endpoint type (REST/XML-RPC)

Auto-cleanup: Logs older than 90 days are automatically deleted (configurable).

## Technical Details
- **Version:** 19.0.1.0.0
- **License:** LGPL-3
- **Dependencies:** base, mail
- **Python:** 3.10+
- **Models:** `mcp.model.access`, `mcp.audit.log`
- **Security Groups:** MCP User, MCP Administrator

# MCP Server — How to Use

This guide explains how and where to use the Odoo MCP Server module to connect AI assistants with your Odoo ERP.

---

## Table of Contents

1. [What Is This?](#1-what-is-this)
2. [Prerequisites](#2-prerequisites)
3. [Odoo Setup (One-Time)](#3-odoo-setup-one-time)
4. [Platform Integration](#4-platform-integration)
   - [Claude Desktop App](#41-claude-desktop-app)
   - [Claude Code (VS Code / CLI)](#42-claude-code-vs-code--cli)
   - [Cursor IDE](#43-cursor-ide)
   - [REST API (Any HTTP Client)](#44-rest-api-any-http-client)
   - [XML-RPC (Drop-in Odoo Replacement)](#45-xml-rpc-drop-in-odoo-replacement)
5. [Real-World Use Cases](#5-real-world-use-cases)
6. [What You Can Ask the AI](#6-what-you-can-ask-the-ai)
7. [Quick Start (5 Minutes)](#7-quick-start-5-minutes)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. What Is This?

The MCP Server acts as a **secure bridge between AI assistants and your Odoo ERP**. It allows AI tools like Claude, Cursor, and ChatGPT to:

- **Search** customers, orders, invoices, products — any Odoo model
- **Read** specific records by ID
- **Create** new records (customers, quotations, tasks, etc.)
- **Update** existing records
- **Delete** records
- **Call** ORM methods (name_search, etc.)

All operations go through permission checks, rate limiting, IP whitelisting, and audit logging — your data stays safe.

```
┌─────────────────┐      ┌─────────────┐      ┌──────────────┐
│  AI Assistant    │      │  MCP Bridge  │      │  Odoo Server │
│  (Claude/Cursor) │─────▶│  (Python)    │─────▶│  (REST API)  │
│                  │ MCP  │              │ HTTP │              │
│  "Show me all   │      │  Translates  │      │  Permission  │
│   customers"    │      │  AI requests │      │  checks,     │
│                  │◀─────│  to API calls│◀─────│  audit logs  │
└─────────────────┘      └─────────────┘      └──────────────┘
```

---

## 2. Prerequisites

### On Your Machine (where AI tool runs)

```bash
pip install "mcp[cli]" httpx
```

### On Odoo Server

- Odoo 19.0 with `mcp_server_ai` module installed
- Module enabled in Settings

---

## 3. Odoo Setup (One-Time)

### Step 1: Enable MCP Server

1. Go to **Settings** (top menu).
2. Scroll to **MCP Server** section (or search "MCP" in settings).
3. Toggle **Enable MCP Server** to ON.
4. Click **Save**.

### Step 2: Add Users to MCP Group

Users who will access the API must be in the MCP group:

1. Go to **Settings > Users & Companies > Users**.
2. Select the user (e.g., `admin`).
3. Under groups, add **MCP User** (or **MCP Administrator** for config access).
4. Click **Save**.

### Step 3: Expose Models

By default, no models are exposed. You must explicitly add each model:

1. Go to **Settings > MCP Server > Model Access** (or use the Quick Links in MCP settings).
2. Click **New**.
3. Select a **Model** (e.g., `Contact` for `res.partner`).
4. Toggle permissions:
   - **Read** — allow searching and reading records
   - **Write** — allow updating records
   - **Create** — allow creating new records
   - **Delete** — allow deleting records
5. Optionally set **Allowed Fields** to restrict which fields are returned:
   ```json
   ["name", "email", "phone", "city", "country_id"]
   ```
6. Click **Save**.

**Common models to expose:**

| Model | Technical Name | Typical Permissions |
|-------|---------------|-------------------|
| Contacts | `res.partner` | Read, Write, Create |
| Countries | `res.country` | Read only |
| Products | `product.template` | Read only |
| Sale Orders | `sale.order` | Read, Write, Create |
| Invoices | `account.move` | Read only |
| Tasks | `project.task` | Read, Write, Create |
| Employees | `hr.employee` | Read only |

### Step 4: Generate API Key (Recommended)

API keys are more secure than passwords:

1. Go to **Settings > Users > [Your User]**.
2. Go to the **API Keys** tab (or **Preferences > Account Security > API Keys**).
3. Click **New API Key**.
4. Enter a description (e.g., "MCP Claude Desktop").
5. Set scope to `rpc`.
6. Copy the generated key — you'll need it for configuration.

### Step 5: Configure Security (Optional)

In **Settings > MCP Server**:

| Setting | Recommended Value | Description |
|---------|-------------------|-------------|
| Rate Limit | 30 | Requests per user per minute |
| Max Records | 500 | Max records per response |
| IP Whitelist | *(empty)* | Leave empty to allow all, or set `127.0.0.1` for local only |
| Audit Logging | ON | Track all API activity |
| Log Retention | 90 days | Auto-cleanup old logs |

---

## 4. Platform Integration

### 4.1 Claude Desktop App

**Config file location:**
- Linux: `~/.config/claude/claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**Using API Key (Recommended):**

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python3",
      "args": ["/full/path/to/mcp_server_ai/mcp_bridge.py"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_API_KEY": "your_odoo_api_key_here",
        "ODOO_DB": "your_database_name"
      }
    }
  }
}
```

> **Note:** `ODOO_DB` is **required for production** servers with multiple databases. The bridge sends it as the `X-Odoo-Database` header (Odoo 19 native). For single-database setups it can be omitted.

**Using Login/Password:**

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python3",
      "args": ["/full/path/to/mcp_server_ai/mcp_bridge.py"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_LOGIN": "admin",
        "ODOO_PASSWORD": "your_password",
        "ODOO_DB": "your_database_name"
      }
    }
  }
}
```

**After saving:** Restart Claude Desktop. You'll see "Odoo MCP Server" in the tools list (hammer icon).

---

### 4.2 Claude Code (VS Code / CLI)

**Use the `claude mcp add-json` command** — this is the most reliable method:

```bash
claude mcp add-json odoo '{
  "command": "python3",
  "args": ["/full/path/to/mcp_server_ai/mcp_bridge.py"],
  "env": {
    "ODOO_URL": "http://localhost:8069",
    "ODOO_API_KEY": "your_odoo_api_key_here",
    "ODOO_DB": "your_database_name"
  }
}' -s user
```

> **Scope options:**
> - `-s user` — available in **all your projects** (recommended)
> - `-s local` — only in current project (private to you)
> - `-s project` — shared via `.mcp.json` (for team sharing)

**After running:** Restart Claude Code (exit with `Ctrl+C` and reopen). Then type `/mcp` to verify the connection shows **"Connected"**.

**To remove or update later:**
```bash
claude mcp remove odoo -s user
claude mcp list                   # verify current servers
```

---

### 4.3 Cursor IDE

**Config file:** `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python3",
      "args": ["/full/path/to/mcp_server_ai/mcp_bridge.py"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_API_KEY": "your_odoo_api_key_here",
        "ODOO_DB": "your_database_name"
      }
    }
  }
}
```

**After saving:** Restart Cursor. The Odoo tools will appear in the AI assistant's tool list.

---

### 4.4 REST API (Any HTTP Client)

No bridge needed. Call the API directly from Python, JavaScript, Postman, or any HTTP client.

**Python example:**

```python
import requests

BASE = "http://localhost:8069/mcp/api/v1"
HEADERS = {
    "Authorization": "Bearer your_odoo_api_key",
    "Content-Type": "application/json",
}

# Health check (no auth needed)
r = requests.get(f"{BASE}/health")
print(r.json())

# List exposed models
r = requests.get(f"{BASE}/models", headers=HEADERS)
print(r.json())

# Search partners
r = requests.post(f"{BASE}/models/res-partner/search", json={
    "domain": [["is_company", "=", True]],
    "fields": ["name", "email", "phone"],
    "limit": 10,
}, headers=HEADERS)

for partner in r.json()["data"]:
    print(f"{partner['name']} — {partner['email']}")
```

**cURL examples:**

```bash
# Health check
curl http://localhost:8069/mcp/api/v1/health

# Search partners
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"domain":[],"fields":["name","email"],"limit":5}' \
  http://localhost:8069/mcp/api/v1/models/res-partner/search

# Create a partner
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"values":{"name":"John Doe","email":"john@example.com"}}' \
  http://localhost:8069/mcp/api/v1/models/res-partner/create

# Count records
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"domain":[["is_company","=",true]]}' \
  http://localhost:8069/mcp/api/v1/models/res-partner/count
```

**JavaScript (Node.js / Browser):**

```javascript
const BASE = "http://localhost:8069/mcp/api/v1";
const API_KEY = "your_odoo_api_key";

const resp = await fetch(`${BASE}/models/res-partner/search`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    domain: [["is_company", "=", true]],
    fields: ["name", "email", "country_id"],
    limit: 10,
  }),
});

const data = await resp.json();
data.data.forEach((p) => {
  console.log(`${p.name} (${p.country_id?.name || "N/A"})`);
});
```

---

### 4.5 XML-RPC (Drop-in Odoo Replacement)

If you have existing Odoo XML-RPC scripts, just change the URL prefix from `/xmlrpc/` to `/mcp/xmlrpc/` — everything else stays the same, but now MCP permission checks are applied.

```python
import xmlrpc.client

DB = "your_database"
LOGIN = "admin"
PASSWORD = "admin"  # or API key

# Standard Odoo URL:  http://localhost:8069/xmlrpc/2/common
# MCP Proxy URL:      http://localhost:8069/mcp/xmlrpc/2/common

common = xmlrpc.client.ServerProxy("http://localhost:8069/mcp/xmlrpc/2/common")
models = xmlrpc.client.ServerProxy("http://localhost:8069/mcp/xmlrpc/2/object")

# Check version
version = common.version()
print(f"Odoo {version['server_version']}, MCP {version['mcp_version']}")

# Authenticate
uid = common.authenticate(DB, LOGIN, PASSWORD, {})
print(f"Logged in as UID: {uid}")

# Search + Read
partners = models.execute_kw(DB, uid, PASSWORD,
    "res.partner", "search_read",
    [[["is_company", "=", True]]],
    {"fields": ["name", "email", "phone"], "limit": 5}
)
for p in partners:
    print(f"  {p['name']} — {p['email']}")

# Count
count = models.execute_kw(DB, uid, PASSWORD,
    "res.partner", "search_count", [[]]
)
print(f"Total partners: {count}")

# Create
new_id = models.execute_kw(DB, uid, PASSWORD,
    "res.partner", "create",
    [{"name": "New Customer", "email": "new@example.com"}]
)
print(f"Created partner ID: {new_id}")

# Update
models.execute_kw(DB, uid, PASSWORD,
    "res.partner", "write",
    [[new_id], {"phone": "+1 555-0001"}]
)

# Delete
models.execute_kw(DB, uid, PASSWORD,
    "res.partner", "unlink", [[new_id]]
)
```

---

## 5. Real-World Use Cases

### Customer Support AI
> "Show me the last 5 orders for customer john@example.com"

The AI searches `res.partner` by email, then searches `sale.order` by partner ID, and summarizes the results.

### Sales Assistant
> "Create a quotation for Azure Interior with 10 units of Product A"

The AI looks up the partner and product, then creates a `sale.order` with the right `order_line` values.

### Data Analysis
> "How many invoices are unpaid this month? Break down by customer."

The AI counts `account.move` records with domain filters, aggregates, and presents a summary.

### Developer Copilot
> "What fields does the sale.order model have?"

While developing Odoo modules, the AI reads live field schemas from your running instance.

### Inventory Check
> "Is Product X in stock? How many units?"

The AI queries `stock.quant` or `product.product` to check availability.

### HR Self-Service
> "Show me all employees in the Engineering department"

The AI searches `hr.employee` with a department filter.

### Automated Reports
> "Give me a summary of this week's sales"

The AI browses `sale.order` with date filters and uses the built-in summary generator.

---

## 6. What You Can Ask the AI

Once connected, you can use natural language. The AI translates your request into API calls automatically.

### Search & Read
- "Show me all company partners"
- "Find customers in the United States"
- "Get details for partner ID 14"
- "List all products with price above 100"
- "How many draft sale orders are there?"

### Create
- "Create a new customer named John Doe with email john@test.com"
- "Add a new product called Widget Pro priced at $49.99"

### Update
- "Update partner 14's phone number to +1 555-0200"
- "Change the email of John Doe to newemail@test.com"

### Delete
- "Delete partner with ID 99"

### Schema
- "What fields does res.partner have?"
- "Show me the field types for sale.order"
- "What models are available?"

---

## 7. Quick Start (5 Minutes)

```
1. Install Python dependencies
   pip install "mcp[cli]" httpx

2. Enable MCP in Odoo
   Settings > MCP Server > Enable ✓ > Save

3. Add your user to MCP group
   Settings > Users > admin > Add "MCP User" group > Save

4. Expose a model
   Settings > MCP Server > Model Access > New
   → Select "Contact" (res.partner) > Toggle Read ✓ > Save

5. Test the API
   curl http://localhost:8069/mcp/api/v1/health

6. Configure your AI tool
   Add mcp_bridge.py to Claude/Cursor/VS Code config (see Section 4)

7. Start chatting!
   "Show me all contacts in Odoo"
```

---

## 8. Troubleshooting

### "MCP Server is disabled" (503)
- Go to **Settings > MCP Server** and enable it.
- Make sure you clicked **Save** after toggling.

### "Missing or invalid Authorization header" (401)
- Check your API key or login/password in the config.
- Ensure the API key scope is set to `rpc`.
- If using Basic auth, verify the credentials work for Odoo login.

### "User is not a member of MCP User group" (403)
- Go to **Settings > Users > [Your User]** and add the **MCP User** group.

### "Model 'xxx' is not exposed via MCP" (404)
- Go to **Settings > MCP Server > Model Access** and add the model.
- Make sure the access record is **Active** (not archived).

### "Operation 'write' is not allowed" (403)
- The model access config only has **Read** enabled. Toggle **Write** in Model Access.

### "IP address not whitelisted" (403)
- Check **Settings > MCP Server > IP Whitelist**. Clear it to allow all IPs, or add your IP.

### "Rate limit exceeded" (429)
- Wait for the retry period (shown in error message).
- Increase the rate limit in **Settings > MCP Server > Rate Limit**.

### Claude Desktop doesn't show Odoo tools
- Verify the config file path is correct for your OS.
- Check that `python3` is in your PATH.
- Run `python3 mcp_bridge.py` manually to check for import errors.
- Ensure `mcp` and `httpx` packages are installed: `pip install mcp httpx`.

### Bridge connects but requests fail
- Verify Odoo is running: `curl http://localhost:8069/mcp/api/v1/health`
- Check `ODOO_URL` in your config — it must be reachable from where the bridge runs.
- Check Odoo logs for error details: **Settings > MCP Server > Audit Logs**.

### Remote Odoo server
- Replace `http://localhost:8069` with your server URL (e.g., `https://myodoo.example.com`).
- If using HTTPS, ensure certificates are valid.
- Add your machine's IP to the IP Whitelist if configured.

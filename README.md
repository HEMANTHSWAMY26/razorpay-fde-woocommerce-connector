# WooCommerce Private MCP Connector

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP SDK v2](https://img.shields.io/badge/MCP%20SDK-v2.3.0-green.svg)](https://modelcontextprotocol.io/)
[![Tests](https://img.shields.io/badge/tests-64%20passed-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A private, read-only Model Context Protocol (MCP) connector designed for the **Razorpay Forward-Deployed Engineer (FDE) / Agent Studio** assignment. 

This connector provides controlled, privacy-preserving, and resilient access to WooCommerce store data for AI agents and MCP clients.

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Why This Connector Exists](#2-why-this-connector-exists)
3. [Architecture](#3-architecture)
4. [Key Features](#4-key-features)
5. [MCP Tools Implemented](#5-mcp-tools-implemented)
6. [Authentication](#6-authentication)
7. [Quick Start & Setup](#7-quick-start--setup)
8. [Environment Variables](#8-environment-variables)
9. [Running the Server](#9-running-the-server)
10. [Running Tests](#10-running-tests)
11. [Running Live Smoke Test](#11-running-live-smoke-test)
12. [Validation Results](#12-validation-results)
13. [MCP Inspector & Client Testing](#13-mcp-inspector--client-testing)
14. [Example Tool Invocations](#14-example-tool-invocations)
15. [Error Handling & Reliability](#15-error-handling--reliability)
16. [Security Controls & PII Protection](#16-security-controls--pii-protection)
17. [Capabilities & Limitations Summary](#17-capabilities--limitations-summary)
18. [Production Considerations](#18-production-considerations)

---

## 1. Project Overview

The **WooCommerce Private MCP Connector** enables autonomous AI agents (such as Claude Desktop, Cursor, or custom Agent Studio applications) to query order histories and product catalogs securely without granting arbitrary database or write access.

By standing between the AI agent and the store's REST API, the connector enforces:
* **Read-only security boundaries by construction** (no write tools exist).
* **Strict parameter validation** before sending requests upstream.
* **Customer PII minimization** (removing physical addresses, billing details, phone numbers, and emails).
* **Automatic retry with exponential backoff and jitter** for transient upstream failures and HTTP 429 rate limits.

---

## 2. Why This Connector Exists

Directly granting an AI agent access to raw e-commerce APIs or databases introduces severe security and reliability hazards:
1. **Prompt Injection & Accidental Mutations**: An LLM might be manipulated into issuing `POST`/`PUT`/`DELETE` calls, altering prices, or cancelling valid orders.
2. **Data Privacy Leaks**: WooCommerce order payloads contain sensitive Personally Identifiable Information (PII) like customer phone numbers, home addresses, and credit card gateway tokens.
3. **Flaky Upstream Stores**: Self-hosted WordPress instances can be slow, intermittent, or subject to aggressive Web Application Firewall (WAF) rate limits.

This connector acts as a hardened, resilient mediation layer solving each of these concerns.

---

## 3. Architecture

The connector is built using a clean, layered pipeline:

```
AI Agent / MCP Client (Claude Desktop / Inspector)
         │
         ▼
MCP Server (mcp.server.MCPServer — Python SDK v2)
         │
         ▼
Controlled MCP Tools (6 Read-Only Tools)
         │
         ▼
Validation Layer (validation.py)
         │
         ▼
Service & Normalization Layer (normalization.py + pii.py)
         │
         ▼
WooCommerce Client & Retry Engine (client.py + retry.py)
         │
         ▼
HTTPX AsyncClient (TLS / HTTP Basic Auth)
         │
         ▼
WooCommerce REST API v3 (/wp-json/wc/v3/*)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full architectural details and Mermaid diagrams.

---

## 4. Key Features

* **Official MCP Python SDK v2**: Implemented using `MCPServer`, providing JSON schema generation and structured output support.
* **Dual Transports**: Supports modern **Streamable HTTP** (`/mcp`) for containerized deployment and **stdio** for local agent integration.
* **Health Check**: Native `GET /health` endpoint for Docker and Kubernetes liveness/readiness probes.
* **Resilient Retry Policy**: Automatic handling for HTTP 429 (respecting `Retry-After`), 500, 502, 503, 504, and network timeouts.
* **Data Minimization**: Automatically strips customer billing, shipping, IP, and personal notes.
* **Zero Bloat**: No PostgreSQL, Redis, Celery, or vector databases. Direct, minimal, and fast.

---

## 5. MCP Tools Implemented

The connector exposes **strictly 6 read-only tools**:

### Orders
1. **`list_orders`**: Retrieve a paginated list of orders with optional status filtering.
2. **`get_order`**: Retrieve normalized details of a specific order by ID.
3. **`search_orders`**: Search and filter orders using query strings, status, and ISO 8601 dates (`after`, `before`).

### Products
4. **`list_products`**: Retrieve a paginated list of catalog products.
5. **`get_product`**: Retrieve catalog details and inventory for a specific product by ID.
6. **`search_products`**: Search products by keyword across title, content, or SKU.

> **Security Note**: Write tools (`create_order`, `update_order`, `delete_order`, `create_product`, etc.) and generic endpoint callers (`raw_http_request`) **do not exist**.

For full input/output schemas and examples, see [docs/TOOL_SPEC.md](docs/TOOL_SPEC.md).

---

## 6. Authentication

The connector authenticates with the WooCommerce REST API v3 using **HTTP Basic Authentication over HTTPS**.

```
Authorization: Basic base64(WOOCOMMERCE_CONSUMER_KEY:WOOCOMMERCE_CONSUMER_SECRET)
```

### Security Guarantees:
* Credentials are never logged or exposed in tool outputs.
* Credentials are never appended to URL query parameters.
* String representations of settings mask secrets (`ck_mock...***`).

---

## 7. Quick Start & Setup

### Prerequisites
* Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.13, 3.14)
* pip or virtualenv

### Complete Quick Start Sequence

```bash
# 1. Clone repository
git clone https://github.com/HEMANTHSWAMY26/razorpay-fde-woocommerce-connector.git
cd razorpay-fde-woocommerce-connector

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows (PowerShell / Command Prompt):
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 4. Install dependencies in editable mode
pip install -e ".[dev]"

# 5. Create local environment configuration from template
# Windows:
copy .env.example .env
# Linux/macOS:
cp .env.example .env

# 6. Configure WooCommerce credentials in .env
# Set WOOCOMMERCE_URL, WOOCOMMERCE_CONSUMER_KEY, and WOOCOMMERCE_CONSUMER_SECRET

# 7. Start the MCP server (Streamable HTTP on port 8000)
woocommerce-mcp --transport streamable-http --port 8000

# 8. Verify the health endpoint (in another terminal)
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"woocommerce-mcp-connector","version":"1.0.0"}

# 9. Run automated offline test suite
pytest -v
# Expected: 64 passed
```

---

## 8. Environment Variables

Create your `.env` configuration file from the provided template:

```bash
cp .env.example .env
```

Configure the following variables in `.env`:

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `WOOCOMMERCE_URL` | **Yes** | — | Base URL of WooCommerce store (e.g., `https://mystore.example.com`). |
| `WOOCOMMERCE_CONSUMER_KEY` | **Yes** | — | WooCommerce REST API Consumer Key (starts with `ck_`). |
| `WOOCOMMERCE_CONSUMER_SECRET` | **Yes** | — | WooCommerce REST API Consumer Secret (starts with `cs_`). |
| `MCP_SERVER_HOST` | No | `0.0.0.0` | Host binding for Streamable HTTP server. |
| `MCP_SERVER_PORT` | No | `8000` | Port for Streamable HTTP server. |
| `WOOCOMMERCE_TIMEOUT_SECONDS` | No | `15.0` | HTTP request timeout in seconds. |
| `WOOCOMMERCE_MAX_RETRIES` | No | `3` | Maximum retry attempts for transient errors. |
| `WOOCOMMERCE_RETRY_BACKOFF_BASE` | No | `0.5` | Exponential backoff base multiplier. |
| `WOOCOMMERCE_RETRY_BACKOFF_MAX` | No | `10.0` | Maximum backoff delay cap in seconds. |

---

## 9. Running the Server

### Option A: Streamable HTTP (Default, Recommended)
Starts an ASGI HTTP server with Streamable HTTP transport at `/mcp` and health check at `/health`:

```bash
woocommerce-mcp --transport streamable-http --port 8000
```
Or via module execution:
```bash
python -m woocommerce_connector.server --transport streamable-http --port 8000
```

* **MCP Endpoint**: `http://localhost:8000/mcp` (Streamable HTTP for network-connected MCP clients)
* **Health Endpoint**: `http://localhost:8000/health` (Liveness / readiness probe for container orchestrators)

Verify health check:
```bash
curl http://localhost:8000/health
```
Expected response:
```json
{"status":"ok","service":"woocommerce-mcp-connector","version":"1.0.0"}
```

### Option B: stdio Transport
For direct integration with local desktop agents (e.g., Claude Desktop, MCP Inspector) that launch the connector process directly:

```bash
woocommerce-mcp --transport stdio
```

---

## 10. Running Tests

The test suite runs entirely offline using mocked HTTP transports and in-process MCP testing. **No active store credentials are required to run tests.**

```bash
pytest -v
```

### Test Coverage Highlights (64 Passing Tests):
* **Unit Tests**: Validation policies, positive integer IDs, pagination safety, status checks, date checks, PII minimization, and log sanitization.
* **Mocked Upstream HTTP**: Status codes 200, 400, 401, 403, 404, 429, 500, 502, 503, 504, network timeouts, connection drops, and malformed JSON.
* **Transient Retry Tests**: 500 twice then succeed, retry exhaustion, and 429 with `Retry-After`.
* **MCP Integration**: Discovery of all 6 tools, schema correctness, in-process invocation, rejection of invalid inputs, and verification that no write tools exist.

---

## 11. Running Live Smoke Test

To verify connectivity and operations against a real WooCommerce store:

1. Configure `.env` with valid store credentials.
2. Run the smoke test:
   ```bash
   python scripts/smoke_test.py
   ```

If credentials are not configured, the script exits gracefully with setup instructions.

---

## 12. Validation Results

All functional boundaries, reliability policies, and security mechanisms have been validated against an active local WooCommerce test store (`https://razorpay-woocommerce-test.wp.local`):

* **64/64 automated tests passing**: Complete offline unit and mocked integration test coverage.
* **Strictly 6 read-only MCP tools exposed**: `list_orders`, `get_order`, `search_orders`, `list_products`, `get_product`, `search_products`.
* **Zero write tools**: Prohibits creation, modification, or deletion of orders, inventory, or products.
* **WooCommerce live authentication & connection verified**: HTTP Basic Auth over HTTPS verified.
* **Product catalog listing verified**: Retrieves normalized products with pagination metadata.
* **Single product retrieval verified**: Direct ID lookup returns normalized `ProductSummary`.
* **Product search verified**: Search queries and REST v3 `search_fields` (`name`, `sku`, etc.) verified.
* **Order listing and search verified**: Date-range filtering (`after`/`before`) and status filters verified.
* **Connector-side input validation verified**: Positive integer IDs, limit caps (1–100), ISO 8601 timestamps, and status whitelists enforced.
* **Error handling & normalization verified**: Upstream 404s map cleanly to `NOT_FOUND`; validation errors to `INVALID_INPUT`.
* **Retry & rate-limit resilience verified**: Automatic bounded retries with exponential backoff and jitter on 429, 500, 502, 503, 504, and network timeouts.
* **Upstream `Retry-After` header honored**: Parses both integer seconds and RFC HTTP dates.
* **Native OS TLS trust store validation verified**: Seamlessly trusts local WordPress Studio root CA via Windows CryptoAPI / macOS Keychain using `truststore` (no `verify=False`).
* **MCP Streamable HTTP connection verified**: Tested over `http://127.0.0.1:8000/mcp`.
* **Health endpoint verified**: `GET /health` returns HTTP 200 with service metadata.

---

## 13. MCP Inspector & Client Testing

### Using MCP Inspector
To inspect tool schemas and interactively invoke tools using the official MCP Inspector:

```bash
npx @modelcontextprotocol/inspector woocommerce-mcp --transport stdio
```

### Configuring in Claude Desktop
Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "woocommerce": {
      "command": "python",
      "args": [
        "-m",
        "woocommerce_connector.server",
        "--transport",
        "stdio"
      ],
      "env": {
        "WOOCOMMERCE_URL": "https://your-store.example.com",
        "WOOCOMMERCE_CONSUMER_KEY": "ck_...",
        "WOOCOMMERCE_CONSUMER_SECRET": "cs_..."
      }
    }
  }
}
```

---

## 14. Example Tool Invocations

### 1. `list_orders`
```json
{
  "page": 1,
  "limit": 10,
  "status": "processing"
}
```

### 2. `get_order`
```json
{
  "order_id": 1042
}
```

### 3. `search_products`
```json
{
  "query": "backpack",
  "page": 1,
  "limit": 5
}
```

### 4. `get_product` (Verified Live Store Example)
**Request**:
```json
{
  "product_id": 13
}
```
**Response**:
```json
{
  "success": true,
  "data": {
    "id": 13,
    "name": "Razorpay Test USB-C Hub",
    "slug": "razorpay-test-usb-c-hub",
    "sku": "RP-USB-01",
    "price": "29.99",
    "regular_price": "34.99",
    "sale_price": "29.99",
    "on_sale": true,
    "status": "publish",
    "stock_status": "instock",
    "stock_quantity": 40,
    "categories": [
      {
        "id": 15,
        "name": "Accessories",
        "slug": "accessories"
      }
    ],
    "created_at": "2026-03-20T14:30:00"
  },
  "pagination": null,
  "error": null
}
```

---

## 15. Error Handling & Reliability

All errors are returned in a predictable, standardized envelope:

```json
{
  "success": false,
  "data": null,
  "pagination": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "Order 1042 was not found."
  }
}
```

| HTTP Status / Event | Connector Error Code | Retry Policy |
| :--- | :--- | :--- |
| Invalid Input | `INVALID_INPUT` | No retry (rejected locally) |
| HTTP 400 | `UPSTREAM_ERROR` | No retry |
| HTTP 401 | `AUTHENTICATION_FAILED` | No retry |
| HTTP 403 | `PERMISSION_DENIED` | No retry |
| HTTP 404 | `NOT_FOUND` | No retry |
| HTTP 429 | `RATE_LIMITED` | Bounded retry (honors `Retry-After`) |
| HTTP 500 | `UPSTREAM_ERROR` | Bounded retry |
| HTTP 502 / 503 | `UPSTREAM_UNAVAILABLE` | Bounded retry |
| HTTP 504 / Timeout | `TIMEOUT` | Bounded retry |
| Connection Error | `UPSTREAM_UNAVAILABLE` | Bounded retry |

---

## 16. Security Controls & PII Protection

1. **Read-Only by Construction**: No mutating HTTP methods (POST, PUT, PATCH, DELETE) are ever executed against WooCommerce.
2. **Input Whitelisting**: Page limits are capped at 100, IDs must be positive integers, and search fields are strictly validated.
3. **No Arbitrary HTTP Proxies**: Only predefined WooCommerce endpoints (`/orders`, `/products`) can be called.
4. **Data Minimization**: Strips customer personal information (`billing`, `shipping`, `customer_ip_address`, `customer_note`) from responses.
5. **Log Redaction**: Credentials, tokens, and PII are masked before entering console or file logs.

---

## 17. Capabilities & Limitations Summary

* Detailed capabilities: [docs/CAPABILITIES.md](docs/CAPABILITIES.md)
* Boundary analysis & omitted features: [docs/LIMITATIONS.md](docs/LIMITATIONS.md)
* Complete tool specifications: [docs/TOOL_SPEC.md](docs/TOOL_SPEC.md)

---

## 18. Production Considerations

For enterprise production deployment:
1. **Multi-Tenancy**: Integrate with AWS Secrets Manager or Vault to resolve per-store credentials dynamically based on incoming MCP OAuth tokens.
2. **Distributed Cache**: Introduce Redis caching with TTL for catalog queries (`list_products`, `get_product`) to decrease load on WooCommerce.
3. **Rate Limiting Ingress**: Implement token bucket rate limiting on the MCP server to protect against runaway client loops.
4. **Telemetry**: Export OpenTelemetry metrics and traces to Datadog or Prometheus.

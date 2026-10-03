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
   * [MCP Interface](#mcp-interface)
   * [Validation Evidence](#validation-evidence)
   * [Engineering Decisions & Trade-offs](#engineering-decisions--trade-offs)
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
    * [Threat Model & Mitigations](#threat-model--mitigations)
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

## MCP Interface

The connector exposes six read-only MCP tools. The official MCP Python SDK exposes their structured input schemas to an MCP client:

* **`list_orders`**: Retrieve paginated order collection with status/date filters.
* **`get_order`**: Lookup single order by integer ID.
* **`search_orders`**: Search orders by text query, status, customer ID, or date ranges.
* **`list_products`**: Retrieve paginated product catalog.
* **`get_product`**: Lookup single product by integer ID.
* **`search_products`**: Search products by keyword, category, SKU, stock status, and targeted search fields.

### Representative Tool Contract: `search_products`

The MCP client discovers each tool's schema directly through protocol negotiation. Below is a readable representation of the input schema for `search_products`:

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search text to match against products"
    },
    "category_id": {
      "type": "integer",
      "description": "Filter by product category ID (positive integer)"
    },
    "sku": {
      "type": "string",
      "description": "Filter by product SKU"
    },
    "stock_status": {
      "type": "string",
      "description": "Filter by stock status ('instock', 'outofstock', 'onbackorder')"
    },
    "status": {
      "type": "string",
      "description": "Filter by product status ('publish', 'draft', 'pending', 'private')"
    },
    "search_fields": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["name", "sku", "global_unique_id", "description", "short_description"]
      },
      "description": "Optional list of fields to target for search matching"
    },
    "page": {
      "type": "integer",
      "default": 1,
      "minimum": 1
    },
    "limit": {
      "type": "integer",
      "default": 20,
      "minimum": 1,
      "maximum": 100
    }
  }
}
```

*Validation Rule:* At least one search criterion must be supplied (`query`, `category_id`, `sku`, `stock_status`, or `status`). IDs must be strictly positive integers ($> 0$), `page` must be $\ge 1$, and `limit` is bounded between 1 and 100.

### Example Tool Invocation

An MCP client invokes the tool with structured arguments:

```json
{
  "query": "backpack",
  "search_fields": ["name"],
  "page": 1,
  "limit": 20
}
```

**Execution Pipeline:**
`MCP client` $\rightarrow$ `MCP tool (search_products)` $\rightarrow$ `connector validation` $\rightarrow$ `WooCommerce REST API v3` $\rightarrow$ `normalized response envelope`.

### Example Normalized Response Shape

The response returns a standardized `BaseResponse` envelope. *(Note: Minimal illustrative response envelope based on connector response models)*:

```json
{
  "success": true,
  "data": [],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_items": 0,
    "total_pages": 0,
    "has_next_page": false
  },
  "error": null
}
```

### Design Boundary

* MCP clients can call only the explicitly registered tools.
* The connector does not expose arbitrary WooCommerce endpoints.
* The connector does not expose arbitrary HTTP methods.
* All six tools are read-only.

---

## Validation Evidence

### Automated Tests
- 64 tests passed / 0 failed.
- Covers validation, client behavior, retries, error mapping, pagination, PII minimization, and MCP behavior.
- `git diff --check` passes.

### Live WooCommerce Validation
- `list_products`, `get_product`, and `search_products` validated against the local HTTPS WooCommerce test store.
- `search_products` with `search_fields=["name"]` validated.
- `list_orders` returned an empty structured result when no orders existed.
- Invalid inputs were rejected before upstream requests.
- Non-existent product/order IDs returned structured `NOT_FOUND` errors.

### MCP Protocol Validation
- Streamable HTTP endpoint `/mcp` validated.
- Exactly six registered tools verified.
- Structured tool schemas/invocations validated through the official MCP Python SDK.
- No write/mutation or arbitrary endpoint tools exposed.

### Security Validation
- Credentials loaded from environment variables and excluded from responses/logs.
- Customer billing/shipping PII removed from normalized order responses.
- TLS certificate and hostname verification enabled.
- No `verify=False` or disabled TLS verification.

---

## Engineering Decisions & Trade-offs

The following table summarizes the core architectural decisions, their concrete implementations, and the associated trade-offs:

| Decision | Implementation Choice | Trade-off & Rationale |
| :--- | :--- | :--- |
| **1. Read-Only Design** | Exposes exclusively read (`GET`) operations for orders and products. No create, update, or delete tools exist. | **Trade-off:** The connector cannot create orders, update inventory, or mutate store state.<br/>**Rationale:** For an AI-agent-facing connector, the read-only capability boundary prevents agent instructions from directly causing store mutations through this connector. |
| **2. Stateless / No Database** | Operates as a stateless translation proxy without local persistence, databases, or cache layers. | **Trade-off:** Every MCP query triggers an upstream HTTP request to WooCommerce.<br/>**Rationale:** The required list/get/search primitives map directly to WooCommerce REST API v3 endpoints. Adding a database introduces state synchronization and cache invalidation complexity not required for this connector MVP. |
| **3. No Arbitrary Endpoint Proxy** | Whitelisted, discrete MCP tools only. Rejects arbitrary endpoints and arbitrary HTTP methods. | **Trade-off:** MCP clients cannot access unexposed WooCommerce or WordPress REST endpoints without explicit tool additions.<br/>**Rationale:** Constrains the capability surface and prevents the connector from acting as an unrestricted authenticated HTTP proxy across internal WordPress routes. |
| **4. Pre-Request Validation** | Validates pagination bounds (`page >= 1`, `1 <= limit <= 100`), positive IDs, status enums, ISO dates, and search fields before dispatching network calls. | **Trade-off:** Requires maintaining local validation rules aligned with WooCommerce parameter constraints.<br/>**Rationale:** Rejects malformed queries locally with `INVALID_INPUT`, avoiding unnecessary upstream HTTP calls and conserving store rate limits. |
| **5. Retry Strategy** | Bounded exponential backoff with full jitter for 429, 5xx, timeouts, and network errors. Parses and honors `Retry-After`. Fails immediately on 400, 401, 403, and 404. | **Trade-off:** Transient failures introduce bounded latency while awaiting backoff windows.<br/>**Rationale:** Because all exposed tools are read-only `GET` operations, retries are idempotent and cannot cause duplicate mutations. Fast-failing deterministic 4xx errors prevents wasteful retry cycles. |
| **6. PII Minimization** | Strips sensitive customer data during normalization, including billing/shipping street addresses, phone numbers, email addresses, customer IP, user agent, and customer notes. | **Trade-off:** MCP clients cannot retrieve customer contact info or full delivery addresses.<br/>**Rationale:** Protects customer privacy. The connector's defined list/get/search use cases do not require direct customer contact information or full delivery addresses, so these fields are excluded from the MCP response. |
| **7. TLS Verification via `truststore`** | Injects host OS certificate trust store into HTTPX via `truststore.SSLContext`. Preserves `CERT_REQUIRED` and hostname verification without `verify=False`. | **Trade-off:** Relies on host OS certificate store integration; not necessary for standard public HTTPS domains with public CAs.<br/>**Rationale:** Resolves TLS verification for the local WordPress Studio development environment (which issues local root CAs to the host OS) while strictly preserving TLS validation. |
| **8. Normalized Response Contract** | Maps raw WooCommerce payloads into defined Pydantic models (`OrderSummary`, `ProductSummary`) wrapped in a standardized `BaseResponse`. | **Trade-off:** Upstream schema changes require updating connector normalization models.<br/>**Rationale:** Prevents raw upstream API structures from leaking into the MCP contract, guarantees predictable response formats, and enforces PII sanitization in the pipeline. |
| **9. Exactly Six Tools** | Constrains scope to exactly six primitives: `list_orders`, `get_order`, `search_orders`, `list_products`, `get_product`, `search_products`. | **Trade-off:** Does not cover secondary resources such as coupons, refunds, taxes, or customer profile records.<br/>**Rationale:** Provides the full set of required list/get/search primitives for orders and products within the defined assignment scope without unnecessary surface area. |

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

## Threat Model & Mitigations

The following threat model outlines specific failure modes, potential threat vectors relevant to an AI-agent-facing integration, and the concrete mitigations implemented in this connector:

| Threat / Failure Mode | Mitigation | Evidence |
| :--- | :--- | :--- |
| **Agent attempts store mutation** | The connector cannot perform store mutations because no mutation tools are exposed. All six tools are read-only `GET` primitives. No create, update, or delete tools exist. | [`server.py`](src/woocommerce_connector/server.py), [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) |
| **Agent requests arbitrary WooCommerce / WordPress endpoint** | Constrains the capability surface to discrete, explicitly implemented tools. The connector does not accept arbitrary endpoints or arbitrary HTTP methods, preventing use as a generic authenticated proxy. | [`server.py`](src/woocommerce_connector/server.py), [`client.py`](src/woocommerce_connector/client.py) |
| **Invalid or malicious input** | Enforces connector-side validation on pagination bounds (`page >= 1`, `1 <= limit <= 100`), positive integer IDs, order status enums, ISO 8601 timestamps, and search fields. Rejects invalid requests locally before network dispatch. | [`validation.py`](src/woocommerce_connector/validation.py), [`tests/test_validation.py`](tests/test_validation.py) |
| **Customer PII exposure** | Sanitization pipeline explicitly strips customer billing/shipping street addresses, phone numbers, email addresses, customer IP (`customer_ip_address`), user agent (`customer_user_agent`), and customer notes (`customer_note`). | [`pii.py`](src/woocommerce_connector/pii.py), [`normalization.py`](src/woocommerce_connector/normalization.py), [`tests/test_pii.py`](tests/test_pii.py) |
| **Credential exposure** | Credentials are loaded exclusively via environment variables. `Settings.__repr__` and logger filters mask Consumer Keys and Secrets (`ck_...***`). Credentials are never passed in query parameters, logged, or returned in tool outputs. `.env` is excluded via `.gitignore`. | [`config.py`](src/woocommerce_connector/config.py), [`.gitignore`](.gitignore), [`tests/test_config.py`](tests/test_config.py) |
| **TLS / Man-in-the-Middle (MitM) risk** | Requires HTTPS with certificate validation (`CERT_REQUIRED`) and hostname verification enabled. Uses `truststore` to resolve the local WordPress Studio root CA via the host OS trust store without disabling certificate checks or using `verify=False`. | [`client.py`](src/woocommerce_connector/client.py#L42-L56), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| **WooCommerce rate limiting (HTTP 429)** | Intercepts HTTP 429 and parses `Retry-After` header (integer seconds and RFC HTTP dates). Applies bounded exponential backoff with full randomized jitter to reduce upstream pressure. | [`retry.py`](src/woocommerce_connector/retry.py), [`tests/test_retry.py`](tests/test_retry.py) |
| **Transient upstream failures & network drops** | Automatically retries idempotent `GET` requests on HTTP 500, 502, 503, 504, connect errors, and timeouts up to `WOOCOMMERCE_MAX_RETRIES`. Fails immediately on deterministic 4xx client errors (400, 401, 403, 404). | [`retry.py`](src/woocommerce_connector/retry.py), [`client.py`](src/woocommerce_connector/client.py) |
| **Sensitive upstream error leakage** | Maps upstream exceptions to a structured `BaseResponse(success=False, error=ErrorInfo(...))` envelope. Shields internal stack traces and raw HTTP response bodies from the MCP client. | [`models.py`](src/woocommerce_connector/models.py), [`client.py`](src/woocommerce_connector/client.py), [`server.py`](src/woocommerce_connector/server.py) |
| **Accidental expansion of connector capabilities** | Strictly bounds the MCP tool registry to six defined primitives (`list_orders`, `get_order`, `search_orders`, `list_products`, `get_product`, `search_products`), preventing unintended exposure of secondary store resources. | [`server.py`](src/woocommerce_connector/server.py), [`docs/TOOL_SPEC.md`](docs/TOOL_SPEC.md) |

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

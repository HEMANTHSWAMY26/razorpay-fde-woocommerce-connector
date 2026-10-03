# WooCommerce MCP Connector — Limitations & Boundary Analysis

This document explicitly defines the boundaries, deliberate omissions, and production gaps of the WooCommerce Private MCP Connector.

---

## Summary of Omissions

| Capability Area | Supported | Deliberately Omitted / Not Supported |
| :--- | :---: | :---: |
| Read-Only Operations (Orders & Products) | ✓ | |
| Write Operations (Create, Update, Delete) | | ✗ |
| Arbitrary Endpoints / Raw HTTP Access | | ✗ |
| Webhook Real-Time Synchronization | | ✗ |
| Persistent Database Storage | | ✗ |
| Distributed Cache (e.g. Redis) | | ✗ |
| Multi-Tenant Secret Management (e.g. HashiCorp Vault, AWS Secrets Manager) | | ✗ |
| Universal Upstream Rate Limit Guarantees | | ✗ |

---

## Detailed Analysis of Limitations

### 1. No Write Operations (`create`, `update`, `delete`)
* **What is missing**: MCP tools such as `create_order`, `update_order`, `delete_order`, `create_product`, `update_product`, `delete_product`.
* **Why it is outside MVP scope**: This connector is built as a strictly **read-only** integration by design. Permitting write operations through an AI agent MCP interface presents substantial risk of unintended inventory adjustments, price tampering, order cancellations, or data loss caused by model hallucinations.
* **What is needed for production**:
  1. Fine-grained RBAC and tool-level permissions.
  2. Human-in-the-loop (HITL) confirmation flows with cryptographic signatures before write execution.
  3. Audit trail capturing user prompt ID, model token footprint, and exact state delta.
  4. Idempotency keys to prevent duplicate charge/order creation on retry.

---

### 2. No Arbitrary Endpoints or Raw HTTP Access
* **What is missing**: Generic MCP tools like `call_woocommerce_api`, `get_raw_url`, or arbitrary method invocation.
* **Why it is outside MVP scope**: Exposing arbitrary endpoints breaks the controlled security perimeter. An LLM agent could prompt-inject or traverse to WordPress administration endpoints (`/wp-json/wp/v2/users`, `/wp-json/wp/v2/settings`) and exfiltrate sensitive configuration.
* **What is needed for production**: Continued strict restriction to explicit, vetted, schema-validated tools.

---

### 3. No Webhook Synchronization or Push Notifications
* **What is missing**: Webhook listeners to receive asynchronous event payloads (e.g., `order.created`, `product.updated`) pushed from WooCommerce.
* **Why it is outside MVP scope**: Webhook ingestion requires public ingress, durable queueing (e.g., SQS, Kafka), signature verification secrets, and webhook subscription management on the WordPress host. The connector operates on a client-pull model when the AI agent queries data.
* **What is needed for production**:
  1. An HTTPS webhook endpoint verifying HMAC signatures (`X-WC-Webhook-Signature`).
  2. Dead-letter queue (DLQ) and outbox pattern to process webhook bursts asynchronously.
  3. Change data capture (CDC) or local read-cache indexing.

---

### 4. No Persistent Database
* **What is missing**: Local database storage (e.g., PostgreSQL, SQLite, MongoDB).
* **Why it is outside MVP scope**: The connector is designed as a stateless middleware layer bridging the MCP client and the WooCommerce store. Adding a database introduces schema migrations, connection pooling, data synchronization drift, and unnecessary architectural complexity.
* **What is needed for production**: A persistent cache or relational store is only required if the business requires historical analytics, audit logging of agent conversations, or offline analytical querying.

---

### 5. No Distributed Caching
* **What is missing**: Distributed Redis or Memcached caching for product catalogs or frequently accessed orders.
* **Why it is outside MVP scope**: The assignment focuses on direct, reliable API integration and bounded retries. Adding Redis would violate the prompt's mandate against adding unnecessary infrastructure.
* **What is needed for production**: Redis cluster with cache eviction policies (`TTL`, cache-invalidation hooks on product updates) to reduce load on the WooCommerce PHP/MySQL backend for high-frequency queries.

---

### 6. No Production-Grade Multi-Tenant Secret Management
* **What is missing**: Per-tenant credential isolation, dynamic secret rotation, or KMS integration.
* **Why it is outside MVP scope**: The current connector targets a single store environment defined via standard environment variables (`WOOCOMMERCE_URL`, `WOOCOMMERCE_CONSUMER_KEY`, `WOOCOMMERCE_CONSUMER_SECRET`).
* **What is needed for production**:
  1. Integration with AWS Secrets Manager, GCP Secret Manager, or HashiCorp Vault.
  2. Multi-tenant context extraction from incoming MCP authentication tokens (OAuth 2.0 / Bearer tokens).
  3. Tenant isolation preventing cross-store query execution.

---

### 7. No Guaranteed Universal WooCommerce REST API Rate Limit
* **What is missing**: A fixed platform-wide rate limit formula.
* **Why it is outside MVP scope**: WooCommerce is a self-hosted WordPress plugin installed on vastly different hosting environments (shared cPanel hosting, managed Cloudways, dedicated VPS, enterprise VIP, Cloudflare / Wordfence WAFs). Each host enforces different throttling algorithms or none at all.
* **What is needed for production**: The connector implements adaptive defensive handling: honoring standard `Retry-After` headers when returned (HTTP 429), backing off exponentially with jitter, and remaining configurable per deployment via `WOOCOMMERCE_MAX_RETRIES` and `WOOCOMMERCE_RETRY_BACKOFF_BASE`.

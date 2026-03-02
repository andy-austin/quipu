# Quipu Roadmap

> 11 validated items across 4 phases. 4 ideas killed during engineering challenge (premature/vanity).

## Effort Legend

| Size | Meaning | Rough Duration |
|------|---------|---------------|
| **S** | Small — single file, < 1 day | hours |
| **M** | Medium — 2-4 files, 1-3 days | days |
| **L** | Large — cross-cutting, 3-7 days | week |

---

## Phase 0 — Foundation

Harden the existing system before adding features. Everything here unblocks Phase 1.

| # | Item | Effort | Touches | Depends On |
|---|------|--------|---------|------------|
| 0.1 | **Connection pooling** — Pool Supabase DB connections in Hands instead of connect-per-call | S | `hands/tools/db_tools.py` | — |
| 0.2 | **CORS configuration** — Add configurable CORS middleware to Brain | S | `brain/server.py` | — |
| 0.3 | **Input validation** — Pydantic models for all Brain request bodies | S | `brain/server.py`, `brain/models.py` | — |
| 0.4 | **LangGraph loop limits** — Cap tool-call loops to prevent runaway agents | S | `brain/graph.py` | — |
| 0.5 | **User data isolation** — Pass `user_id` through the graph and filter all DB queries by it | M | `brain/server.py`, `brain/graph.py`, `hands/tools/db_tools.py` | 0.3 |
| 0.6 | **CI gates** — GitHub Actions: lint, typecheck, test on every PR | S | `.github/workflows/ci.yml` (new) | — |
| 0.7 | **Test coverage** — Unit tests for graph, tools, dependencies; integration test for SSE flow | M | `brain/tests/`, `hands/tests/` | — |
| 0.8 | **Structured logging** — Replace `print()` calls with `structlog` JSON logging | S | `brain/server.py`, `brain/graph.py`, `hands/server.py` | — |
| 0.9 | **Rate limiting** — Per-user request throttling on Brain endpoints | S | `brain/server.py` | 0.3 |
| 0.10 | **MCP reconnection** — Retry logic + health check for Brain→Hands SSE connection | S | `brain/server.py` | — |

---

## Phase 1 — Core Product

Transform from a scraping demo into a general-purpose agent platform.

| # | Item | Effort | Touches | Depends On |
|---|------|--------|---------|------------|
| 1.1 | **General-purpose chat agent** — New LangGraph graph that handles open-ended conversations, not just scraping | M | `brain/graph.py`, `brain/server.py` | 0.4, 0.5 |
| 1.2 | **Conversation persistence** — Store message history in Supabase keyed by `user_id` + `conversation_id` | M | `hands/tools/db_tools.py`, `brain/graph.py`, `migrations/` | 0.1, 0.5 |
| 1.3 | **Structured data extraction** — Agent that returns typed JSON (via Pydantic) from unstructured web content | M | `brain/graph.py`, `brain/models.py` | 1.1 |
| 1.4 | **Vertical agents** — Pluggable agent definitions (system prompt + tool subset) selectable per request | L | `brain/agents/` (new), `brain/graph.py`, `brain/server.py` | 1.1 |
| 1.5 | **Results API** — GET endpoints to retrieve past agent runs and extracted data | M | `brain/server.py`, `hands/tools/db_tools.py` | 1.2 |

---

## Phase 2 — Growth

Open the platform to more users and use cases.

| # | Item | Effort | Touches | Depends On |
|---|------|--------|---------|------------|
| 2.1 | **BYOK (Bring Your Own Key)** — Users provide their own LLM API keys, stored encrypted in Supabase | M | `brain/server.py`, `brain/models.py`, `hands/tools/db_tools.py` | 0.5, 1.1 |
| 2.2 | **File & document tools** — Upload, parse, and chunk PDFs/CSVs/text files via Hands | L | `hands/tools/file_tools.py` (new), `hands/server.py` | 1.1 |
| 2.3 | **Notification & webhook tools** — Send emails, Slack messages, HTTP callbacks from Hands | M | `hands/tools/notification_tools.py` (new), `hands/server.py` | 1.4 |
| 2.4 | **Webhook-triggered runs** — Inbound webhooks that kick off agent runs (e.g., on new email, cron) | M | `brain/server.py`, `brain/webhooks.py` (new) | 1.1, 0.9 |
| 2.5 | **Additional LLM providers** — Add OpenAI, Anthropic, and Mistral to `models.py` provider registry | S | `brain/models.py` | — |

---

## Phase 3 — Scale

Architecture changes for production load and enterprise use.

| # | Item | Effort | Touches | Depends On |
|---|------|--------|---------|------------|
| 3.1 | **Multi-Hands architecture** — Route tool calls to multiple Hands instances by capability | L | `brain/server.py`, `brain/graph.py`, `hands/` | 1.4, 2.2 |
| 3.2 | **On-prem Hands** — Let users run their own Hands instance behind a firewall, Brain connects via MCP | L | `hands/`, `brain/server.py`, `docs/` | 3.1 |
| 3.3 | **Agent workflow builder** — Visual DAG editor for chaining agents into multi-step workflows | L | `brain/workflows/` (new), frontend (new) | 1.4, 1.5 |

---

## Dependency Graph

```
Phase 0 (Foundation)                Phase 1 (Core)              Phase 2 (Growth)         Phase 3 (Scale)
========================           ==================          ==================       ==================

0.1 Connection pooling ─────────┐
0.2 CORS ──────────┐            │
0.3 Input valid. ──┤            │
0.4 Loop limits ───┤            │
                   ├──► 1.1 Chat agent ──┬──► 1.3 Extraction      2.1 BYOK
0.5 User isolat. ──┘──► 1.2 Persistence  │──► 1.4 Vert. agents ──┬──► 2.3 Notifications
                        │                │    │                   │──► 3.1 Multi-Hands ──► 3.2 On-prem
                        └──► 1.5 Results  │   └──────────────────────► 3.3 Workflow builder
                                          └──► 2.2 File tools ───────►│
0.6 CI gates                              └──► 2.4 Webhooks
0.7 Tests                                      2.5 More LLMs
0.8 Logging
0.9 Rate limiting ────────────────► 2.4 Webhooks
0.10 MCP reconnect
```

---

## Killed Ideas (Engineering Challenge)

These were cut as premature or vanity:

1. **Admin dashboard** — No users to monitor yet
2. **Plugin marketplace** — Vertical agents (1.4) must prove value first
3. **Custom model fine-tuning** — BYOK (2.1) handles the real need
4. **Real-time collaboration** — Single-user foundation not built yet

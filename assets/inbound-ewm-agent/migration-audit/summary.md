# Migration to Cloud Foundry — Summary

**Status: COMPLETE**  
**Deployed at:** 2026-10-16T02:01:52Z  
**Route:** https://inbound-ewm-agent.cfapps.us10.hana.ondemand.com

---

## What was done

### Code migration (Phases 3–5)
- **`app/ewm_actions_client.py`** — new BTP Destination-backed REST client for EWM_ACTIONS
- **`app/tools.py`** — 9 async LangChain `@tool` functions exported as `ALL_TOOLS`
- **`app/aicore.py`** — CF LLM factory wrapping `gen_ai_hub.proxy.langchain.init_models.init_llm`
- **`app/agent.py`** — refactored to own tool loading; dual-mode import block gates litellm/MCP/sap_cloud_sdk behind `JOULE_RUNTIME`; model getters read from env vars on CF
- **`app/agent_executor.py`** — simplified to only import `SampleAgent`
- **`app/main.py`** — exposes `application = _build_app()` for gunicorn; no click dependency
- **`requirements.txt`** — CF-only deps (langchain 1.4.6, sap-ai-sdk-gen[all], gunicorn, uvicorn[standard])
- **`requirements-joule.txt`** — Joule/Kyma additions (litellm, langchain-litellm, langchain-mcp-adapters, sap-cloud-sdk)
- **`manifest.yml`**, **`Procfile`**, **`runtime.txt`**, **`.cfignore`** — CF deployment artefacts
- **`tests/`** — 9 unit tests (6 client tests + 3 structural tool tests)

### Deploy (Phase 6)
- CF login: `ulises.marin@sap.com` → org `COENAMFGLIVE_manu-joule-studio-7i9npdqq` / space `SCM_DEV`
- Services bound: `manu-joule-studio-destination-service`, `aiCore`
- Env vars: `JOULE_RUNTIME=0`, `AICORE_RESOURCE_GROUP=default`, `AGENT_LLM_MODEL=gpt-4o`, `AGENT_SUMMARIZATION_MODEL=gpt-4o`

---

## Issues resolved during deploy

| Error | Fix |
|-------|-----|
| `Env cannot set PORT` | Removed `PORT: "8080"` from manifest `env:` — CF reserves PORT |
| `pip ResolutionImpossible` (langchain==1.3.10 vs sap-ai-sdk-gen) | Bumped to langchain==1.4.6, langchain-core==1.6.11, langgraph==1.2.15 |
| `ModuleNotFoundError: No module named 'botocore'` | Changed `sap-ai-sdk-gen` → `sap-ai-sdk-gen[all]` (installs boto3, langchain-aws, google-genai) |
| `GenAIHubProxyClient: No credentials found` | Added `aiCore` service binding to manifest services |
| `Missing header parameter 'AI-Resource-Group'` | Added `AICORE_RESOURCE_GROUP: "default"` to manifest env |
| `No deployment found with: deployment.model_name == sap/anthropic--claude-4.5-sonnet` | Made `get_model_name()` read from `AGENT_LLM_MODEL` env var; set to `gpt-4o` (gen_ai_hub uses bare model names, not litellm `sap/` prefix) |

---

## Runtime architecture

```
CF (JOULE_RUNTIME=0)              Joule/Kyma (JOULE_RUNTIME=1)
─────────────────────────         ──────────────────────────────
gen_ai_hub → AI Core (aiCore)     ChatLiteLLM → litellm → AI Core
MemorySaver (in-memory)           sap_cloud_sdk checkpointer
No MCP tools                      MCP tools via mcp_providers.agw
No JWTContextMiddleware           JWTContextMiddleware
gunicorn + uvicorn worker         platform-managed
```

---

## Smoke test

```
POST https://inbound-ewm-agent.cfapps.us10.hana.ondemand.com/
→ HTTP 200, task.status.state = "completed"
Agent replied with EWM inbound warehouse greeting ✓
```

---

## Joule deployment (BLOCKED — separate issue)

The `jl a2a message` returning 502 is a platform issue unrelated to this migration.  
**Action required:** An admin must complete one-time CIS authorization at  
`https://agyxede4o.accounts400.ondemand.com/admin` for tenant `inbound-ewm-agent-tn7te`.

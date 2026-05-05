# Valura AI

[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/SHM9MYZJ)

**Video:** _[TODO: add link]_

This project is a FastAPI service that answers retail-investor questions over Server-Sent Events. The request path is simple: block clearly unsafe finance queries locally, classify the safe ones with one structured LLM call, route them through a thin registry, and let the target agent respond in a predictable format.

The important part is not that it uses agents. The important part is where I chose to keep things deterministic. Anything that must be right for trust reasons, especially portfolio math, is computed in Python. I only use the LLM where language helps more than arithmetic: routing broad financial intents and turning pre-computed facts into plain-English observations.

Currently the system has one real agent, `portfolio_health`. `market_research` is an explicitly registered stub, and the rest of the taxonomy still falls back to a structured `not_implemented` response. The code is organized to make adding new agents easy and low-risk.

## How the system works

### 1. Safety runs first, locally

Every `/chat` request goes through a in house pre-trained, warm-loaded TF-IDF + logistic regression safety model before any LLM call happens. if the query is clearly unsafe, the system returns a category-specific refusal SSE event and stops there.

I stayed with a small local model because it is easy to reason about, fast enough to be effectively free in the request budget, and easier to tune than adding another LLM call just to say no. The main issue I hit was false positives on legitimate finance phrasing, not lack of model capacity. The fix was raising the block threshold to `0.58` after trial and error and adding safe examples that reuse the same vocabulary in training data the model was overreacting to.

That tradeoff is deliberate: a lightweight model like this is not robust to every paraphrase, but for this assignment it gives a good balance of recall, latency, and debuggability.

To load the pickle file for this model we need scikit-learn, which is a heavier dependency just for the safety model. I considered converting the model to a pure NumPy implementation or re-training with a smaller library, but in the end I decided that the convenience of using scikit-learn for this part outweighed the cost of adding it as a dependency.

### 2. One classifier call does routing and extraction

If safety passes, the classifier makes a single structured-output OpenAI call. It returns:

- the target agent
- a short intent label
- extracted entities like tickers, benchmark hints, amounts, and horizons
- an informational safety verdict

I chose one structured call over a rule-based router because the surface area is too broad for brittle keyword logic. The classifier has to resolve not just agent selection, but also finance entities that show up in messy natural language. One LLM pass is the simplest place to pay that complexity cost and keep the latency low.

There are still guardrails around that call. The classifier sees only the last 3 user turns for follow-up resolution, not the full session transcript. That keeps context useful without letting history bloat the prompt which can increase latency and we dont have much room to work with (6 seconds). There is also a 5-minute process-local dedupe cache. If the same query arrives with the same last 3 user turns, the system reuses the previous classifier result and skips the LLM call entirely.

On an ordinary API or model failure, classification degrades to `general_query` instead of dropping the request. I preferred graceful degradation over making the whole pipeline brittle.

### 3. The router stays dumb on purpose

The router does not contain business logic. It converts classifier output into a shared `AgentRequest`, looks up the handler in a registry, and returns a structured fallback when the handler does not exist.

That sounds unremarkable, but it matters for extension. The taxonomy lives in one place, the registry lives in one place, and the HTTP layer does not need to know how individual agents work. Adding a new agent is meant to be additive work, not another round of rewriting dispatch logic.

In the current repo that looks like this:

- `portfolio_health` is fully wired and implemented
- `market_research` is registered as an explicit stub
- the remaining categories still route to a structured `not_implemented` payload instead of throwing an error

### 4. Portfolio health is compute-first, not LLM-first

This is the main implementation decision.

An earlier version asked the model to fetch data and do portfolio arithmetic. Soon realised older LLM models are bad at math. The model got signs wrong, copied misleading intermediate percentages, and produced inconsistent numbers for equivalent questions. Once I saw that, I changed the architecture.
The current `portfolio_health` agent works in three clear phases:

1. Fetch the needed market inputs deterministically.
2. Compute all portfolio metrics in Python.
3. Ask the LLM only to explain what those numbers mean in plain language.

The classifier already extracts focus tickers and an optional benchmark hint, and the user fixture already stores a preferred benchmark. So the agent does not ask the LLM a second time what to fetch. It fetches prices and benchmark history directly with `yfinance`, in parallel, and caches those results.

Then Python computes the metrics that actually matter:

- concentration risk using current market value
- total return
- annualized return when purchase dates exist
- benchmark comparison and alpha

Only after those numbers exist does the LLM get involved. It receives an authoritative metrics block and writes 1-5 observations for a novice investor audience. That is a much narrower job, and it is the right place to use a model.

The tradeoff is one less flashy architecture. There is no agentic tool loop here anymore. In this version of the system, that would be unnecessary overhead because the classifier has already done the hard selection work and the portfolio agent mostly follows a fixed compute path. An agentic loop would make more sense if the system had to choose among multiple live tools at runtime, for example market signals, current news, web search, filings, or other external research sources, and then decide which results to trust or combine before answering. In that kind of setup, the extra orchestration cost could buy real capability. Here, it would mostly buy latency.

### 5. Sessions and streaming are intentionally pragmatic

Session history is stored in a process-local, thread-safe in-memory store with a 1-hour TTL and a 10-turn cap. That is not production infrastructure, and I am not pretending it is. I did not use a database here because the assignment only needs short-lived conversational memory for follow-up resolution inside a single service instance. A database would add setup, persistence, schema decisions, and operational complexity without improving the core things this project is trying to prove: safe gating, correct routing, deterministic portfolio analysis, and observable SSE behavior. For this scope, in-memory state is the simplest thing that supports follow-up questions well enough.

Two choices matter here:

- only successful agent responses are persisted
- internal observability data is stripped before assistant payloads enter history

That keeps follow-up context useful instead of polluting it with stub responses or token accounting.

The API always responds over SSE, but not because the model is streaming tokens in real time. The LLM calls are still blocking because both the classifier and the portfolio observation step use structured outputs. In this setup, I need the full response before I can validate that it matches the expected schema and safely route or render it. That makes progressive token streaming a poor fit for the current path, streaming works well for free-form text. I used SSE mainly so the client gets useful progress updates early: stage metadata first, then a `progress` event before agent execution, and finally the completed message and metrics. For a request path that can take several seconds, that is much better than leaving the user with a silent spinner.

## Why I made these tradeoffs

### Deterministic where trust is fragile

Finance users will forgive a stubbed capability faster than they forgive obviously wrong numbers. That is why I moved arithmetic out of the LLM and into `src/tools/metrics.py`. If a value should be verifiable, I want it computed in code.

### Thin infrastructure over premature abstraction

This repo uses a small registry, a simple in-memory session store, and in-memory TTL caches. That is not because Redis, Celery, or a larger orchestration layer are bad ideas. It is because the current assignment does not need them to prove the important spine of architecture.

### Why I skipped most of the stretch goals

The assignment lists four optional stretches. I implemented one and deliberately skipped the other three.

**Dedupe cache — implemented.** The classifier has a 5-minute process-local cache keyed on the query and the last 3 user turns. Repeated or near-identical requests skip the LLM entirely. This was cheap to build and directly helps with both latency and cost, so it was worth doing.

**Embedding-based pre-classifier — skipped.** This would add a second model to load and maintain, and the routing accuracy from the single structured LLM call is already above the required threshold. The latency savings would only matter for the subset of queries where embedding confidence is high enough to skip the LLM, and I did not have enough data to calibrate that threshold reliably. I would rather ship one classifier that works well than two that need careful coordination.

**Per-tenant model selection — skipped.** The plumbing for this is straightforward — read a model override from the user profile and pass it through — but it is not a meaningful architectural decision. It is a config flag. I would rather spend the time on things that actually test the system's design, like making the portfolio agent produce trustworthy numbers.

**Multi-tenant rate limiting — skipped.** Rate limiting matters in production but it is an infrastructure concern, not an AI architecture concern. Adding it here would mean pulling in Redis or a token-bucket library, writing middleware, and testing concurrency — all real work, but none of it exercises the safety, routing, or agent contracts that this assignment is actually evaluating.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add your OpenAI key to .env
uvicorn src.main:app --reload --port 8000
```

## Environment variables

`OPENAI_API_KEY` is required at runtime for LLM-backed behavior. Without it, the server still starts, but `/chat` returns an `llm_unavailable` error event.

`OPENAI_MODEL` defaults to `gpt-4o-mini`. `gpt-4.1` is supported too; it is more expensive and can shift latency in either direction depending on provider-side variance.

`APP_ENV` can be `development`, `production`, or `test`. In production, the OpenAI key is validated at startup. In development, CORS is open to localhost.

Other configs such as `PIPELINE_TIMEOUT_S`, `SAFETY_BLOCK_THRESHOLD`, `SESSION_MAX_TURNS`, `SESSION_TTL_SECONDS`, and `MARKET_DATA_MAX_WORKERS` are centralized in `src/config/settings.py` and can be overridden through environment variables.

One real deployment caveat: `src/main.py` still allows `"*"` CORS in production for evaluator convenience. I would lock that down before shipping this anywhere real.

## Testing

```bash
pytest tests/ -v
```

The tests are split by what they can honestly prove.

Mock-based tests always run and cover:

- safety behavior on the gold pairs
- classifier parsing and fallback behavior
- session-history prompt construction
- portfolio health response structure
- end-to-end SSE event flow

Live OpenAI tests are present for routing accuracy and conversation-follow-up behavior, but they skip cleanly when `OPENAI_API_KEY` is not set.

That split is intentional. I did not want tests that only assert that mocks return the answers I manually fed them.

## Libraries

I used `fastapi` because the assignment requires it and it is a good fit for a small streaming API. `sse-starlette` handles the SSE response layer cleanly. `openai` is the official SDK and supports the structured output flow used by both the classifier and the observation-generation step. `pydantic` and `pydantic-settings` keep the codebase typed. `yfinance` gives live market data without forcing an evaluator to provision another API key. `scikit-learn` is enough for the small safety classifier.

I intentionally did not add heavier infrastructure libraries just to make the stack look more serious. The simple cache and session layers are small enough to inspect and reason about directly.

## Scripts and benchmark artifacts

The `scripts/` folder is for evaluation and developer tooling, not request-path logic. Right now it contains one file, `scripts/measure_latency.py`, which is the benchmark harness I used to measure the SSE endpoint in a repeatable way.

That script does four things that make the benchmark files worth keeping in the repo:

- it warms the server before measurement so startup noise does not dominate the numbers
- it records client-observed timing and server-reported timing separately
- it writes every request as a JSONL row instead of just summary stats, so the raw data is preserved for later analysis or if questions arise about how the numbers were generated
- it appends a final summary row with p50, p95, mean, min, and max

The `benchmark/` folder contains the raw outputs from that harness:

- `benchmark/latency-gpt-4o-mini.jsonl`
- `benchmark/latency-gpt-4-1.jsonl`

They are the direct JSONL outputs of the script, including failures. That matters because it means the benchmark preserves the ugly parts too. For example, the `gpt-4o-mini` run contains 1 timeout out of 100 requests instead of quietly dropping it from the artifact.

## Performance

I measure latency with `scripts/measure_latency.py`, which sends repeated `/chat` requests, parses the SSE stream, and writes JSONL output for later analysis.

For this project, I treat “streaming first-token latency” as time to the first answer-bearing SSE event the client can use, not literal model token streaming. That distinction matters because the service streams pipeline events, but the OpenAI calls themselves are still blocking.

The benchmark artifacts are sequential, warm-server runs of 100 requests against the same `/chat` path. They are useful because they answer slightly different questions:

- `benchmark/latency-gpt-4o-mini.jsonl` shows the default cheap path under the model I actually use in the service by default
- `benchmark/latency-gpt-4-1.jsonl` shows the more expensive evaluation path under a stronger model

Summary of the committed artifacts:

| Run | Requests ok | First useful message p50 | First useful message p95 | Server e2e p50 | Server e2e p95 | Mean cost |
| --- | --- | --- | --- | --- | --- | --- |
| `gpt-4o-mini` | 99 / 100 | 5.539 s | 8.627 s | 5.536 s | 8.624 s | about $0.0002 per request in the raw rows |
| `gpt-4.1` | 100 / 100 | 2.656 s | 6.800 s | 2.653 s | 6.799 s | about $0.003 per request |

So the read is:

- both runs stay far under the $0.05 cost budget
- the default `gpt-4o-mini` run clears the 6-second target at p50 but not p95
- the committed `gpt-4.1` run is faster in this snapshot, but costs roughly an order of magnitude more
- one `gpt-4o-mini` request timed out

One small artifact caveat is worth calling out directly: the summary row in `benchmark/latency-gpt-4o-mini.jsonl` shows `estimated_cost_usd` rounded to `0.0`. That is a formatting artifact from the script's 3-decimal summary rounding, not a claim that the requests were free. The per-request rows in the same file preserve the actual values, which are around `$0.00019` to `$0.00023`.

The remaining p95 problem is still mostly on the observation LLM call, not on the local parts of the pipeline. That is why the timeout is set to 12 seconds: it is long enough to survive typical tail latency, but still bounded enough to fail fast when upstream latency gets unreasonable.

I have not load-tested concurrency yet. The current benchmark is sequential and warm-server only, which is good enough for assignment reporting but not enough to make production claims.

## Known limits

- Only `portfolio_health` is implemented end to end today.
- Session memory is in-process only and does not survive restarts.
- Market data is best-effort `yfinance` data with caching layered on top.
- Multi-currency portfolios are reported approximately because there is no FX normalization yet.
- Timeout handling is user-friendly at the SSE layer, but Python threads started through `asyncio.to_thread` are not truly cancellable.

## What I would do next

If I had more time, here is where I would spend it.

**Fix the p95 latency.** Most of the tail latency comes from the observation LLM call. I would add a cheap pre-classifier to short-circuit obvious intents, make the observation path async, and consider streaming free-form text instead of waiting for a full structured response where schema validation is not critical.

**Move sessions out of process memory.** Sessions vanish on restart and cannot be shared across instances. I would move them to Redis with TTL expiry, which also unblocks horizontal scaling. I would also add a summarization step for older turns instead of hard-truncating them.

**Add real observability.** Right now the system logs structured data but has no telemetry pipeline. I would wire up OpenTelemetry for per-stage latency breakdowns, cost tracking, and alerting on things like safety false-positive spikes or classifier fallback rates — both early signs that something needs retraining.

**Build out more agents.** `market_research` and `financial_calculator` are next. The interesting part is when an agent needs multiple live sources — news, filings, web search — because that is where a tool-use loop actually earns its complexity. The routing contracts already support it; the agent internals would just look different from the deterministic path `portfolio_health` uses.

**Harden the safety model.** The current model handles common cases but is not robust to adversarial rephrasing. I would add a second-pass LLM check for borderline scores, run periodic red-team evaluations, and add per-user rate limits as a backstop.

**Auth and multi-tenancy.** There is no authentication or tenant isolation right now. Production would need JWT auth, per-user request budgets, and isolated session namespaces.

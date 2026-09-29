# Study: LiteChat Core Functionality and MVP Scope

- **Status:** v4, ready for the planning step. This version adds the instructor's constraints, the local environment, auth and stack analysis, and a same-day MVP scope.
- **Date:** 2026-09-29
- **Reference app:** https://litechat.ai
- **Course proxy:** https://proxy.litechat.ai (BUILD LLM Proxy)
- **Nature of this document:** analysis only. No application code exists. **The recommended scope in §9 is a study conclusion, not an approved requirement.** The plan will turn it into a checklist.

---

## 0. How to read this study

The document keeps four kinds of statement apart:

| Kind | Where | Meaning |
|---|---|---|
| **Observed facts** | §3, §4 | What we saw in LiteChat, the repo or the environment. Each carries an evidence tag. |
| **Technical findings** | §5, §6 | What the proxy docs and live calls showed, and what that implies technically. |
| **Assumptions** | §11 | Things we are treating as true without proof. Each says what happens if it's wrong. |
| **Decisions needed** | §12 | Choices the plan must make. Each has options and a recommendation. |

Evidence tags:

| Tag | Source |
|---|---|
| **[CONF]** | Confirmed by the instructor, as relayed by the student on 2026-09-29 |
| **[BRIEF]** | The ITENT 45 midterm brief |
| **[SS]** | Screenshots of the logged-in litechat.ai app, taken 2026-09-29 |
| **[OBS]** | Fetched from litechat.ai without logging in (HTML, headers, API responses) |
| **[CSS]** | litechat.ai's public stylesheet. It shows that an element exists, not how it behaves. |
| **[DOCS]** | The proxy documentation, revision 2026-09-19 · 3 |
| **[API]** | Live proxy calls made 2026-09-29 (§5.3) |
| **[ENV]** | Inspection of this machine and repository |
| **[INF]** | Our inference |
| **[UNK]** | Unknown |

---

## 1. Executive summary

- **What LiteChat is.** "Metered, *a la carte* access to LLMs from various providers" for regular users who won't pay for subscriptions. [BRIEF] In the real app:
  - Users have **billing accounts with dollar credit**.
  - They start each chat by choosing a **billing account and a model** from many providers, each labeled Value / Standard / Premium.
  - They chat in saved, renamable, deletable sessions.
  - Settings include a global system prompt, memories and thinking effort. [SS]
- **What we're given.** A proxy with three provider-native interfaces (OpenAI, Anthropic, Google), **one model each**, all running DeepSeek Flash behind the scenes. [DOCS] It works, reports token usage on every reply, and has **no billing or pricing**. [API]
- **Constraints:** any stack, any coding harness, any reasonable login approach (Google login not required), and **deliverables are due today**. [CONF]
- **Recommendation:** **Django + SQLite with server-rendered templates.** It's the instructor's own teaching stack (§4.3), already familiar to the student, and it provides login, sessions, CSRF protection, the database, an admin site and a test runner. That leaves today's time for the LiteChat-specific parts.
- **Recommended same-day MVP** (§9):
  - Username/password login.
  - Billing accounts with credit.
  - New chat: choose a billing account and one of the **three** provider models.
  - Chat through a **server-side adapter per provider**.
  - Session list, rename and delete.
  - **Token usage priced and deducted** from the account, with sending **blocked when credit runs out**.
  - Everything else is excluded or kept as stretch goals (§9.3). Streaming is the first stretch goal.

---

## 2. Constraints

| # | Constraint | Source |
|---|---|---|
| C1 | Replicate LiteChat's **core** functionality. Deciding what "core" means is "part of the test". | [BRIEF] |
| C2 | Grading is on "how well you can convince me that you can drive an agentically-coded project". | [BRIEF] |
| C3 | Deliverables: coding-session transcripts and the GitHub repo. Other management artifacts are optional. | [BRIEF] |
| C4 | **No required tech stack.** | [CONF] |
| C5 | **Coderange is not required.** Any coding harness is fine. | [CONF] |
| C6 | **Any reasonable login approach is acceptable.** Google login is not required. | [CONF] |
| C7 | **The deadline is today (2026-09-29).** | [CONF] |
| C8 | Keys must never appear in code, docs, git history or client-side code. | CLAUDE.md, [DOCS] |
| C9 | Follow the study → plan → execute → rendezvous → sync docs workflow, with conventional commits and feature branches. | CLAUDE.md |

**What C7 means:** scope must be cut hard. Anything not needed to show *metered, multi-provider chat* waits. Because of C2 and C3, a smaller app with a clean process (docs, plan checklist, focused commits, tests) is better than a larger app built in a rush. [INF]

---

## 3. Observed facts: LiteChat

### 3.1 Access [OBS][SS]
- `/login` has USERNAME and PASSWORD fields, LOG-IN, "OR", and **Login with Google**. There is **no sign-up and no password reset**.
- Login sends JSON to `POST /api/login` with a CSRF token header. The server sets an auth cookie. Unauthenticated API calls get `401 {"message":"Unauthenticated"}`. `/app` redirects to `/login` when logged out.
- The student's account has username `758668b7-…` (a UUID), user ID 80 and "member since" today. [SS] This suggests Google login creates accounts automatically. [INF]
- Logout is an icon at the top of the sidebar. [SS]

### 3.2 Main layout and chat [SS]
- **Sidebar:**
  - APPS: SimGen ↗ (external link) and CHAT
  - ACCOUNT: My Profile
  - SESSIONS: a **+** button and the session list
- **Empty state (`/chat`):** a large dashed **+** and "Start a New Conversation".
- **+ opens "Select a Model":**
  - A **BILLING ACCOUNT** dropdown with the text "*Costs for this session will be charged to the selected account.*"
  - Models are grouped by provider. Each shows a name, a description and a **tier** (Value / Standard / Premium).
  - Two views: Cards and Compact (a table with ☆ favorites and sortable columns).
  - **No prices are visible.**
- **After the first message:**
  - The session appears as **"Untitled session"** with its date, a ✎ rename icon and a 🗑 delete icon.
  - User bubbles are on the right, assistant bubbles on the left.
  - The options bar shows **Model** (a read-only-looking pill), **Include Memories** (a toggle, on), **Tools**, and **Thinking effort: Low**.
  - The input says "Type a message or drop files here…" and has 📎 and send buttons.
  - **No cost or balance is shown in the chat.**

### 3.3 Profile (`/profile`) [SS]
- **User Profile:** display name, username, user ID, member since.
- **Global System Prompt:** "applies to all chat sessions". A textarea with a Save button.
- **Memories:** a type dropdown (e.g. "Preference"), content, and "Add Memory Item".
- **Default App:** SimGen / **Ask** / Chat.
- **Billing Accounts:** "[Personal] HANS LIAM YU", an **ACTIVE** badge and **AVAILABLE CREDIT $2.00**.

### 3.4 Models listed in LiteChat [SS] (partial list)
| Provider | Model | Tier |
|---|---|---|
| Anthropic | Claude Haiku 4.5 | Value |
| Anthropic | Claude Sonnet 5 | Standard |
| Anthropic | Claude Opus 5 | Premium |
| DeepSeek | DeepSeek V4.1 Flash | Value |
| Minimax | MiniMax M3 | Value |
| Moonshot AI | Kimi K2.6 / K2.7 Code / K3 | Value / Value / Standard |
| OpenAI | GPT-5.6 Luna / Terra / Sol | Value / (not visible) / Premium |

### 3.5 Other apps [SS][CSS]
- **SimGen** is linked externally (↗). **Ask** appears only in the Default App setting.
- Both are **separate apps sharing the LiteChat account**, not features of Chat. [INF]

### 3.6 Unknown about LiteChat [UNK]
- Behavior when credit runs out.
- Whether replies stream.
- Whether the model can be changed mid-session.
- The thinking-effort options and the contents of the Tools menu.
- The price per model, and whether the HELLO exchange visibly reduced the $2.00.
- What SimGen and Ask do.

None of these block the MVP. The plan will choose our own behavior and document it.

---

## 4. Observed facts: repository and environment

### 4.1 Repository [ENV]
- `github.com/Liam-Yu12/midterm`, branch `main`, one commit (`5ef4c30 Add files via upload`) containing `CLAUDE.md`.
- **Uncommitted:** `.gitignore` (ignores `.env*` except `.env.example`), `.env.example` (the three key names), `doc/{study,plan,wiki}/README.md`, and this study.
- `.env` holds `BUILD_OPENAI_KEY`, `BUILD_ANTHROPIC_KEY` and `BUILD_GOOGLE_KEY`, all set. It is **git-ignored** (`git check-ignore` confirms). No key value appears in any other repo file.
- **No application code, dependencies or stack yet.**

### 4.2 Machine [ENV]
| Tool | Status |
|---|---|
| Python | `/Applications/anaconda3/bin/python3.13` (3.13.5), `/usr/local/bin/python3.11` (3.11.14), system `python3` (3.9.6) |
| PyPI access | Works (a test `pip download flask` succeeded) |
| SQLite | 3.43.2 (CLI and Python module) |
| Go | 1.25.3 |
| Ruby | 2.6.10 (system). Rails not installed. |
| Homebrew | 4.6.17 |
| Node.js / npm | **Not installed** |
| `gh` CLI, Docker | Not installed |

### 4.3 The instructor's reference stack [ENV]
`~/digitalcafe-2024` is the instructor's own ITMGT teaching walkthrough, which the student has worked through. Its README explains **why he moved students from Flask/Mongo to Django + SQLite**:
- Django's structure "almost forces you to use practices that are well-understood".
- SQLite "comes with Python", so students don't need to install a database server.

That project uses Django apps, models and migrations, templates, the **admin site**, users/login, and `tests.py`.

---

## 5. Technical findings: the proxy

### 5.1 Interfaces [DOCS]
| Provider | Endpoint | Auth header | Only model | Env var |
|---|---|---|---|---|
| OpenAI (Chat Completions) | `POST https://proxy.litechat.ai/openai/v1/chat/completions` | `Authorization: Bearer …` | `gpt-5.6-luna` | `BUILD_OPENAI_KEY` |
| Anthropic (Messages) | `POST https://proxy.litechat.ai/anthropic/v1/messages` + `anthropic-version: 2023-06-01` | `x-api-key: …` | `claude-haiku-4-5-20251001` | `BUILD_ANTHROPIC_KEY` |
| Google (Gemini) | `POST https://proxy.litechat.ai/google/v1beta/models/gemini-3.8-flash:generateContent` | `x-goog-api-key: …` | `gemini-3.8-flash` | `BUILD_GOOGLE_KEY` |

The OpenAI Responses interface (`/openai/v1/responses`) also exists. Chat Completions is simpler, so we'll ignore Responses.

"BUILD LLM Proxy uses DeepSeek Flash for all three provider interfaces." [DOCS]

### 5.2 How the interfaces differ [DOCS][API]
| Concern | OpenAI | Anthropic | Gemini |
|---|---|---|---|
| History | `messages[]` roles `system/user/assistant` | `messages[]` roles `user/assistant` | `contents[]` roles `user/model`, text in `parts[]` |
| System prompt | a `system` message | top-level `system` | `systemInstruction.parts[]` |
| Output limit | `max_tokens` | `max_tokens` (required) | `generationConfig.maxOutputTokens` |
| Disable reasoning | `reasoning_effort: "none"` | `thinking: {type: "disabled"}` | `thinkingConfig.thinkingBudget: 0` |
| Answer text | `choices[0].message.content` | `content[]` where `type == "text"` | `candidates[0].content.parts[].text` |
| Finish | `finish_reason` `stop` / `length` | `stop_reason` `end_turn` / `max_tokens` | `finishReason` `STOP` / `MAX_TOKENS` / `SAFETY` |
| Usage | `usage.prompt_tokens`, `completion_tokens` | `usage.input_tokens`, `output_tokens` | `usageMetadata.promptTokenCount`, `candidatesTokenCount` |
| Stream | SSE deltas, then a usage chunk (needs `stream_options.include_usage`), then `[DONE]` | `message_start` … `message_delta` (with usage) … `message_stop` | `:streamGenerateContent?alt=sse`. Last chunk has usage. No `[DONE]`. |

Shared rules [DOCS]:
- **Stateless:** keep the history in your app.
- **Keys stay on the backend.**
- **Errors:** 400 means fix the request. 401/403 means a bad, wrong-provider or expired key. 429 means back off with a bounded delay. 502/504 means an upstream failure. 503 means contact the admin.
- "Do not automatically retry after partial output arrives. Usage can be unknown after a failure."
- **Not supported:** hosted search, code execution, audio/video, stored responses.
- **Files** expire after 1 hour.

### 5.3 Live checks (9 tiny requests, 2026-09-29) [API]
| Request | Result | Time |
|---|---|---|
| OpenAI chat + system | 200. `"ok"`, `stop`, prompt 187 / completion 1 | 1.6 s |
| Anthropic messages + system | 200. `"ok"`, `end_turn`, input 186 / output 1 | **30.4 s** |
| Gemini generateContent + systemInstruction | 200. `"ok"`, `STOP`, prompt 187 / candidates 1 | 6.9 s |
| OpenAI stream + include_usage | 200. Deltas, then `stop`, then a usage chunk (`choices: []`), then `[DONE]` | 1.5 s |
| Anthropic stream | 200. Usage in `message_start` and the final `message_delta` | 1.5 s |
| Gemini stream | 200. Final chunk has `finishReason` and `usageMetadata` | 12.8 s |
| `GET /openai/v1/models` | 200. Only `gpt-5.6-luna` (`owned_by: exam-proxy`) | 19.7 s |
| OpenAI with `gpt-5.6-sol` | **400** `unknown model` | 0.8 s |
| OpenAI with the Anthropic key | **401** `invalid or inactive provider key` | 35.7 s |

### 5.4 What follows from these findings
1. **The docs are accurate**, so adapters can be written from §5.2 and tested against recorded fixtures.
2. **Usage is available on every interface and in every mode**, so metering is feasible, including with streaming later.
3. **About 175 hidden prompt tokens are added per request.** A ~10-token prompt was counted as 182–187. Charging by reported tokens gives every message a small fixed overhead.
4. **Only three models can be offered.** Others return 400. LiteChat's larger catalog can't be reproduced. Our catalog is **seeded by us**.
5. **Keys are provider-scoped.** A 401 means a configuration problem, not a user error.
6. **Latency ranges from 0.8 to 36 s.** We need long server-side timeouts (≥ 90 s), a visible "waiting" state, and no automatic retry after partial output.
7. There are **no rate-limit or cost headers**. Extra non-standard usage fields (e.g. `prompt_cache_hit_tokens`) should be ignored.

---

## 6. Analysis

### 6.1 Authentication options
| Option | Effort today | Fit | Notes |
|---|---|---|---|
| **A. Django built-in auth** (username/password, session cookie, CSRF, `login_required`) | **Very low**: built in | Matches LiteChat's username/password form [SS] | Users are created in the admin or with a seed command. Passwords are hashed by Django. |
| B. A + a simple sign-up page | Low | LiteChat has no sign-up [SS] | Makes the demo easier (no admin needed). Must auto-create a personal billing account. |
| C. Google OAuth (e.g. `django-allauth`) | Medium–high | LiteChat has it [SS] | Needs a Google Cloud OAuth client, redirect URIs and secret handling. **Not required.** [CONF] |
| D. Hand-rolled auth | Medium, riskier | – | No benefit over A. |

**Recommendation:** **A**. B is optional if time allows. Exclude C.

### 6.2 Billing and metering

This is the requirement that separates LiteChat from a generic chat app, based on the brief's "metered, a la carte" [BRIEF]. The proxy provides **token counts only**. [API]

**Observed LiteChat behavior to copy** [SS]:
- Billing accounts with a name, kind ("Personal"), status (ACTIVE) and dollar credit.
- The account is chosen per session in the model picker.
- Credit is shown on the profile page.

**Proposed mechanics** [INF]:
1. **Price per model:** `input_price` and `output_price` per 1M tokens, stored in the catalog.
2. **Before calling the proxy:** refuse if the session's account is not active or its credit is ≤ 0. Show a clear "insufficient credit" message.
3. **After a successful reply:** `cost = in_tokens × in_price / 1e6 + out_tokens × out_price / 1e6`. In **one database transaction**, save the assistant message, write a usage record and subtract the cost from the account, locking the account row.
4. **On failure** (error, timeout): save nothing billable, show an error, keep the user's message (or let them retry). This follows "usage can be unknown after a failure". [DOCS]
5. **Money type:** `Decimal`, stored with sub-cent precision (e.g. 6 decimal places), because one message costs fractions of a cent. Display rounded to cents.
6. **Credit top-up:** through the Django admin only. There are no payments.
7. **Overdraft:** checking "> 0" before the call means the last message can push the balance slightly negative. That's acceptable and should be documented. The alternative, estimating cost first, is more complex.

### 6.3 Model selection and sessions
- **Catalog:** three seeded rows, one per proxy model. Each has a provider, the proxy's model ID, a display name (e.g. "GPT-5.6 Luna", "Claude Haiku 4.5", "Gemini 3.8 Flash"), a short description, a tier and prices. LiteChat marks Luna and Haiku 4.5 as **Value** [SS]. Gemini's tier wasn't seen.
- **Picker:** a "New conversation" page or modal with a billing account dropdown, then models grouped by provider with name, description and tier. This matches LiteChat's Cards view. [SS] Compact view and favorites are left out.
- **Session:** it belongs to one user, one billing account and one model, all fixed at creation. **Switching the model mid-session is out of scope.** It's unknown in LiteChat, and leaving it out keeps the history-to-provider mapping simple.
- **Session list:** newest first, with name and date. Rename happens in place or on a small form. Delete asks for confirmation. The default name is "Untitled session".
- **History:** send the full session history each turn. Trimming long histories is out of scope for today. The risk is low for a demo.

### 6.4 Stack options
| Option | Pros | Cons for today |
|---|---|---|
| **Django 5.2 LTS + SQLite + templates** (+ a little vanilla JS) | Auth, sessions, CSRF, ORM, migrations, **admin** (for seeding and top-ups), test runner all built in. **The instructor's own teaching stack**, which the student already knows. Python 3.13 is installed. | Multi-page, so a less "app-like" UI. Streaming needs extra work. |
| Flask + SQLite | Quick to start | We'd hand-build auth, CSRF, admin and migrations. The instructor explicitly moved away from it. |
| FastAPI + JS frontend | Good for streaming | Auth, admin and templates are extra. More moving parts. |
| Node/Next.js | Common for chat UIs | **Node isn't installed.** Everything would be built from scratch. |
| Rails (the reference's stack) | Matches LiteChat | Only Ruby 2.6 is present. Installing Rails is risky today. |
| Go | Go 1.25 is installed | No batteries included for auth, admin or ORM. Slow to build today. |

**Recommendation:** Django 5.2 + SQLite with server-rendered templates. Make HTTP calls with `requests` or `httpx`, using a 90 s+ timeout. Use a little vanilla JS only to disable the send button and show "thinking…" while the form posts. It isn't needed for streaming in the MVP.

### 6.5 Provider adapter design (technical)
- One function per provider behind a common interface:
  ```
  complete(model, system_prompt, history[(role, text)]) → Result(text, status, input_tokens, output_tokens)
  ```
  `status` is one of `complete`, `truncated`, or an error kind.
- The mapping follows §5.2. Reasoning is **disabled** in every request, which keeps latency and tokens low, and `max_tokens` is bounded (e.g. 1024).
- Keys are read from the environment at call time and never logged. 401 becomes "service misconfigured", 429 becomes "busy, try again", and 5xx or timeout becomes "provider unavailable".
- **Testing:** unit tests mock the HTTP layer with fixtures shaped like the §5.3 responses, so no real calls are made. Plus one manual smoke test per provider.

### 6.6 Streaming: in the MVP or not?
- **For:** latency of up to 30 s or more makes waiting on a full page load feel broken. [API]
- **Against:** it means three SSE parsers, async or streaming responses in Django, JS for incremental rendering, and billing on stream completion. That's roughly as much work as the rest of the chat feature.
- **Recommendation:** **not in the MVP.** A disabled button with a "thinking…" indicator softens the wait. Streaming is **stretch goal #1**.

---

## 7. Feature classification

| Feature | Evidence | Class | MVP today? |
|---|---|---|---|
| Username/password login, logout, protected pages | [SS][OBS] | Core | **Yes** |
| Seeded users (admin / command) | [CONF] C6 | Core (our approach) | **Yes** |
| Billing accounts (name, kind, status, credit) | [SS] | Core | **Yes** |
| Credit visible to the user | [SS] | Core | **Yes** (profile page or sidebar) |
| New session: pick billing account + model | [SS] | Core | **Yes** |
| Models from 3 providers with name, description, tier | [SS][BRIEF][API] | Core | **Yes** |
| Send / receive via proxy with history | [SS][DOCS] | Core | **Yes** |
| Per-provider adapters | [API] | Core (technical) | **Yes** |
| Session list, open, rename, delete; "Untitled session" | [SS] | Core | **Yes** |
| Usage × price deducted; ledger; insufficient-credit block | [BRIEF][API][INF] | Core | **Yes** |
| Truncated / failed reply marked; friendly errors | [DOCS] | Core (robustness) | **Yes** |
| Admin top-up of credit | [INF] | Supporting | **Yes** (Django admin, near-free) |
| Streaming | [API] | Supporting | Stretch 1 |
| Global system prompt | [SS] | Supporting | Stretch 2 |
| Per-message tokens and cost display | – | Supporting | Stretch 3 |
| Markdown rendering | [CSS] | Supporting | Stretch 4 |
| Self sign-up (with auto personal account) | – | Supporting | Stretch 5 |
| Memories + include toggle | [SS] | Supporting | Excluded today |
| Thinking effort | [SS] | Supporting | Excluded today |
| Profile details (member since, etc.) | [SS] | Supporting | Minimal only |
| Google login | [SS] | Optional [CONF] | Excluded |
| Tools / multi-turn tool loop | [SS][CSS] | Optional | Excluded |
| File uploads | [SS] | Optional | Excluded |
| Web search, research mode, image generation | [CSS] | Optional, and the proxy doesn't support them | Excluded |
| SimGen, Ask, Default App | [SS] | Separate apps | Excluded |
| Cards/Compact views, favorites, sorting | [SS] | Optional | Excluded |
| Mid-session model switch | [UNK] | Unknown | Excluded |
| Payments / top-up UI | – | Optional | Excluded |
| Landing page, mobile polish, deployment | [OBS] | Optional | Excluded |

---

## 8. Data model (proposed)

| Entity | Fields | Notes |
|---|---|---|
| `User` | Django built-in | display name = `first_name`/`last_name`, or `username` |
| `BillingAccount` | name, kind (`personal`/`shared`), status (`active`/`suspended`), `credit` (Decimal, 6 dp), created_at | |
| `BillingAccount.members` | M2M to User | A user sees only accounts they belong to |
| `LLMModel` | provider (`openai`/`anthropic`/`google`), `api_model` (e.g. `gpt-5.6-luna`), display_name, description, tier (`value`/`standard`/`premium`), `input_price_per_mtok`, `output_price_per_mtok` (Decimal), is_active | Seeded by a data migration or command |
| `ChatSession` | user, billing_account, llm_model, name (default "Untitled session"), created_at, updated_at | Model and account fixed at creation |
| `Message` | session, role (`user`/`assistant`), content, status (`complete`/`truncated`/`error`), input_tokens, output_tokens, cost, created_at | Token and cost fields only on assistant messages |
| `UsageCharge` | billing_account, message (1:1), llm_model, input_tokens, output_tokens, cost, created_at | Audit trail. Could be merged into `Message` if time is short (see D6). |

---

## 9. Recommended MVP (study conclusion, **not approved**)

### 9.1 In scope today
1. **Project skeleton:** Django 5.2 on Python 3.13 in a `.venv`, SQLite, settings that read keys from `.env`, and `requirements.txt`.
2. **Auth:** login and logout pages, `login_required` everywhere, and a seed command that creates a demo user with a personal billing account holding **$2.00**, like LiteChat's [SS].
3. **Billing accounts:** model, admin registration (for top-ups), and a balance display (sidebar or profile).
4. **Model catalog:** three seeded models with tier and prices.
5. **New conversation:** a picker with a billing account dropdown and models grouped by provider. It creates a session.
6. **Chat page:** history, a message form, a "thinking…" state, and marking of truncated or failed replies.
7. **Provider adapters:** OpenAI, Anthropic and Gemini, as in §6.5.
8. **Metering:** credit check before the call, and after it one transaction that saves the reply, records the charge and deducts the balance. A clear insufficient-credit message.
9. **Sessions:** a sidebar list (newest first), open, rename and delete.
10. **Tests:** adapters (mocked HTTP), cost calculation and deduction, the insufficient-credit block, auth protection, and ownership (users can't see others' sessions or accounts).
11. **Verification:** a manual end-to-end chat with each of the three providers against the real proxy, checking that the balance goes down.
12. **Docs:** a `doc/wiki/` page on architecture, setup/run steps, the billing policy and proxy caveats, and a README with how to run it.

### 9.2 Stretch goals (only after 9.1 is done, verified and merged), in order
1. Streaming replies
2. Global system prompt
3. Per-message tokens and cost display
4. Markdown rendering of replies
5. Self sign-up with an automatic personal billing account

### 9.3 Explicitly excluded from the MVP because of the deadline
- Google login (not required [CONF])
- Memories and the include toggle, thinking effort, tools, file uploads
- Web search, research mode, image generation (also unsupported by the proxy [DOCS])
- SimGen, Ask, Default App setting
- Changing the model or billing account mid-session
- Model favorites, compact view, sorting
- Payments and self-service top-ups
- Context-window trimming for long histories
- Landing page, mobile-specific layout, visual parity with LiteChat, deployment/hosting (the deliverables are the repo and transcripts [BRIEF])

### 9.4 Time budget
This is a rough estimate. The real pace depends on the session.

| Block | Estimate |
|---|---|
| Plan document | 15–20 min |
| Skeleton, auth, models, admin, seed | ~45 min |
| Adapters and tests | ~45 min |
| Picker, chat, sessions UI | ~60 min |
| Metering and tests | ~30 min |
| End-to-end verification, fixes, rendezvous | ~30 min |
| Wiki and README sync | ~20 min |
| **Total** | **~4–4.5 h** |

If time runs short, the **cut line** is: keep 9.1 items 1–9 and 11. Reduce tests to the adapters and metering. Keep the wiki minimal.

---

## 10. Risks and tradeoffs

| Risk / tradeoff | Impact | Mitigation |
|---|---|---|
| **Same-day deadline** | Unfinished or broken app | Strict MVP, a cut line (§9.4), merge only working increments |
| Grader disagrees with our "core" | Lower grade | This study ties each scope item to the brief or evidence. Exclusions are explicit. |
| Proxy latency of 30 s+ | Page seems frozen; request timeouts | 90 s+ server timeout, a "thinking…" indicator, streaming as stretch #1 |
| Three provider formats | Adapter bugs | Common interface, fixture tests, one live smoke test per provider |
| Only three models, all DeepSeek Flash | Model choice looks cosmetic | Different prices per model if D3 allows it. Document the caveat in the wiki. |
| Hidden ~175-token overhead | Each message costs slightly more than expected | Documented pricing policy. Prices set so $2.00 lasts many messages. |
| Billing concurrency or failures | Wrong balance | Transaction with a row lock. Charge only on success. Allow a small documented overdraft. |
| Proxy outage or key expiry near the deadline | Can't demo live | Automated tests don't depend on the proxy. Record the smoke-test results. Clear 401/5xx messages. |
| Tests that call the real proxy | Spend credit, flaky, slow | Mock HTTP in all automated tests |
| Key leakage | Violates C8 | `.env` git-ignored, keys read only on the server, never logged. Run a pre-commit check. |
| Non-streaming UX differs from LiteChat | Less polished | Accepted tradeoff for the deadline |
| Django multi-page UI vs LiteChat's single-page feel | Visual difference | Replicate function, not visuals (CLAUDE.md) |

---

## 11. Assumptions

| # | Assumption | If wrong |
|---|---|---|
| A1 | Running locally (`runserver`) is enough; no deployment is expected. | Add a deployment task. Scope would need cutting elsewhere. |
| A2 | Seeded users (no sign-up) are a "reasonable login approach". [CONF] C6 suggests yes. | Stretch 5 (sign-up) becomes required. |
| A3 | Charging by proxy-reported tokens × our own prices counts as "metered". | Adjust the pricing model. The ledger still works. |
| A4 | Offering the three proxy models under their provider names is an acceptable stand-in for LiteChat's larger catalog. | Add more display entries mapped to the same models. That's misleading, so not recommended. |
| A5 | Blocking at credit ≤ 0 with a small possible overdraft copies LiteChat well enough. LiteChat's actual behavior is unknown. | Switch to a pre-estimate check. |
| A6 | The proxy's behavior on 2026-09-29 stays stable through the deadline. | Fixtures keep the tests valid, but the live demo is at risk. |
| A7 | The proxy has spending limits of its own that we can't see. There are no headers about them. | Keep real calls to a minimum. |

---

## 12. Decisions needed (for the plan)

| # | Decision | Options | Study recommendation |
|---|---|---|---|
| D1 | Stack | Django / Flask / FastAPI / other | **Django 5.2 + SQLite + templates, Python 3.13** |
| D2 | Auth | built-in / + sign-up / Google | **Built-in username/password with seeded users.** Sign-up is stretch. |
| D3 | Prices and tiers for the 3 models | copy LiteChat's tiers (Luna and Haiku = Value) / differentiate | Keep LiteChat's observed tier for Luna and Haiku (Value), assume Value for Gemini, and give each model a slightly different price per 1M tokens so metering differences show. Exact numbers go in the plan and are documented as ours. |
| D4 | Billing on failure / overdraft | charge nothing / charge partial; hard block / allow small overdraft | **Charge only on success. Check credit > 0 before the call, and allow the final overdraft.** |
| D5 | Streaming in MVP | yes / no | **No. It's stretch #1.** |
| D6 | Separate `UsageCharge` table vs fields on `Message` | separate / merged | **Separate** if time allows, because it's a cleaner audit trail. Merge if we fall behind. |
| D7 | UI shape | one page with a sidebar / several pages | **One chat layout (sidebar + main) rendered by Django**, with a new-conversation page and a profile page |
| D8 | Max output tokens per reply | e.g. 512 / 1024 / 2048 | **1024**, with truncated replies marked |
| D9 | Branching | one feature branch for the MVP / several | One `feat/mvp` branch with small conventional commits. Merge to `main` at rendezvous. |

---

## 13. Remaining open questions (non-blocking)

These are about LiteChat details we didn't observe (§3.6). The plan will pick our own behavior for each. There are **no remaining blocking questions** for the instructor.

---

## Appendix A: Evidence log

| Source | Result |
|---|---|
| `GET https://litechat.ai/` | 200. Landing page. Checks the profile and redirects. `via: Caddy`, `x-runtime` (Rails) |
| `GET /app`, `/app.js` | 302 → `/login` |
| `GET /login` | 200. Username/password form, Google SSO, `anti-forgery-token` |
| `GET /api/my-profile/v1/read-profile` | 401 `{"message":"Unauthenticated"}` |
| `POST /api/login` without CSRF | 422 (Rails `public/422.html`) |
| `GET /css/styles.css` | 200, 62,723 bytes |
| Screenshots (8), 2026-09-29 | Login, empty `/chat`, picker Cards and Compact, chat after "HELLO", `/profile` top and bottom |
| Proxy `/`, `/docs`, 4 interface pages | 200. Summarized in §5 |
| Proxy live checks (9) | §5.3 |
| `~/digitalcafe-2024/README.md` | Instructor's reasoning for Django + SQLite |
| Tool/version checks | §4.2 |
| Instructor clarifications (relayed) | §2, C4–C7 |
| Web search | litechat.ai is an Ateneo JGSOM student venture, unrelated to github.com/DimitriGilbert/LiteChat |

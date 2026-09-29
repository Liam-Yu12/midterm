# Plan: LiteChat MVP (same-day)

- **Based on:** [doc/study/litechat-core-functionality.md](../study/litechat-core-functionality.md) (v4)
- **Date:** 2026-09-29. **Deadline: today.**
- **Goal:** a working Django app that demonstrates LiteChat's core: *metered, a la carte access to LLMs from various providers*. Users log in, choose a billing account and one of three provider models, chat through the course proxy, and pay per token from their credit.
- **Not the goal:** a full clone. Section 14 lists what is deliberately excluded.
- **Status:** MVP complete and merged to `main` (see 12.6). Phases 0–4 and 5 complete. **4b is open:** its code and offline tests are committed, but the live smoke test (4b.10) is on hold until the proxy keys are reissued (they were exposed in a session transcript by a test bug; see 4b.9). Phases 6–11 are complete. **Phase 12: local verification passed.** The real-proxy check (12.3) and the merge (12.6) are **on hold** until fresh keys are issued (see 4b.10). Tick items as they are completed.

---

## 0. Decisions adopted from the study

These close the study's open decisions (§12). Changing any of them means updating this plan first.

| # | Decision |
|---|---|
| D1 | **Django 5.2 LTS + SQLite + server-rendered templates**, on Python 3.13 (`/Applications/anaconda3/bin/python3.13`), in a `.venv`. |
| D2 | **Django built-in username/password auth.** Users are created with a management command or the admin. No sign-up, no Google login. |
| D3 | Seeded catalog of 3 models, all tier **Value**, with our own prices (per 1M tokens, USD): **GPT-5.6 Luna** $0.40 in / $1.60 out · **Claude Haiku 4.5** $1.00 in / $5.00 out · **Gemini 3.8 Flash** $0.30 in / $2.50 out. These prices are ours, not LiteChat's, and will be documented as such. |
| D4 | **Charge only on success.** Check credit > 0 and account active *before* the call. The final message may overdraw slightly, and this is documented. If the call fails, nothing is saved or charged, and the user's draft is kept. |
| D5 | **No streaming in the MVP.** Instead, the send button is disabled and a "Thinking…" indicator is shown while waiting. |
| D6 | **Separate `UsageCharge` table** as the audit trail. Fallback: fold it into `Message` if we fall behind. |
| D7 | **One layout** (sidebar + main) with pages for chat home, new conversation, session and profile. |
| D8 | `max_tokens` = **1024** per reply. Reasoning **disabled** on all providers. Proxy timeout **120 s**. |
| D9 | Docs are committed on `main`. All code goes on the branch **`feat/litechat-mvp`**, which is merged at rendezvous. |

## 0.1 Target layout (what the plan will create)

```
midterm/
├── manage.py
├── requirements.txt            # Django 5.2.x, requests, python-dotenv
├── .env / .env.example         # BUILD_*_KEY, DJANGO_SECRET_KEY, DJANGO_DEBUG
├── litechat/                   # Django project: settings.py, urls.py, wsgi.py, asgi.py
├── billing/                    # BillingAccount, UsageCharge, metering services, profile view
│   ├── models.py  admin.py  services.py  views.py  urls.py
│   ├── management/commands/seed_demo.py
│   └── tests/
├── llm/                        # LLMModel catalog + provider adapters (proxy client)
│   ├── models.py  admin.py  providers.py
│   ├── migrations/000X_seed_models.py
│   └── tests/ (+ fixtures/*.json)
├── chat/                       # ChatSession, Message, chat views/services
│   ├── models.py  admin.py  services.py  views.py  urls.py  forms.py
│   └── tests/
├── templates/
│   ├── base.html  app_layout.html
│   ├── registration/login.html
│   ├── chat/{home,new_session,session_detail,session_confirm_delete}.html
│   └── billing/profile.html
└── static/{css/app.css, js/chat.js}
```

### Routes

| URL | Method | View | Purpose |
|---|---|---|---|
| `/` | GET | redirect | → `/chat/` |
| `/login/` | GET/POST | `auth_views.LoginView` | Log in |
| `/logout/` | POST | `auth_views.LogoutView` | Log out (Django 5 requires POST) |
| `/chat/` | GET | `chat.views.home` | Sidebar + "Start a New Conversation" empty state |
| `/chat/new/` | GET/POST | `chat.views.new_session` | Picker: billing account + model; creates the session |
| `/chat/<id>/` | GET | `chat.views.session_detail` | History + message form |
| `/chat/<id>/send/` | POST | `chat.views.send_message` | Send a message: meter, call the proxy, save |
| `/chat/<id>/rename/` | POST | `chat.views.rename_session` | Rename |
| `/chat/<id>/delete/` | GET/POST | `chat.views.delete_session` | Confirm and delete |
| `/profile/` | GET | `billing.views.profile` | User info + billing accounts + available credit |
| `/admin/` | – | Django admin | Users, accounts, credit top-ups, catalog |

All routes except `/login/` require login. Every session and billing-account lookup is **scoped to the current user**, and anything else returns 404.

---

## Implementation order and dependencies

```
Phase 0 (docs commit)
  └─ 1 Setup ─┬─ 2 Auth ─┬─ 3 Billing ─┐
              │          │             ├─ 5 New conversation ─ 6 Chat via proxy ─ 7 Metering ─┬─ 8 History
              └──────────┴─ 4 Catalog ─┘        ▲                                             ├─ 9 Rename
                          4b Adapters ──────────┘ (6 needs 4b)                             ├─ 10 Delete
                                                                                              └─ 11 Errors
  12 Verification + rendezvous → 13 Sync docs
```

Tests are written **inside each phase**, not saved for the end. Phase 12 runs the whole suite and does the manual end-to-end check.

---

## Phase 0: Commit study and setup files (on `main`)

- [x] 0.1 Add `.venv/`, `db.sqlite3`, `__pycache__/`, `*.pyc`, `staticfiles/` to `.gitignore`. (The unused Node entries were replaced.)
- [x] 0.2 Commit the documentation structure and env template: `chore: set up docs structure and env template` (`.gitignore`, `.env.example`, `doc/*/README.md`).
- [x] 0.3 Commit the study: `docs: add LiteChat core functionality study`.
- [x] 0.4 Commit this plan: `docs: add LiteChat MVP implementation plan`.
- [x] 0.5 Create the branch `feat/litechat-mvp` from `main`. It was created from `main` at `f8f4bfe`. The student ran the Phase 0 git commands by hand while the agent's shell permission check was failing.

**Verify:** `git status` is clean. `git log` shows conventional commits. `git ls-files` **does not** include `.env`.

---

## Phase 1: Project / Django setup
*Depends on: Phase 0.*

- [x] 1.1 Create `.venv` with Python 3.13. Write `requirements.txt` (`Django>=5.2,<5.3`, `requests`, `python-dotenv`) and install it.
  - *Deviation:* only `Django` and `python-dotenv` were installed, following the instruction to install only Phase 1 dependencies. `requests` moves to 4b.1. Installed: Django 5.2.17, python-dotenv 1.2.3 (+ asgiref, sqlparse).
- [x] 1.2 `django-admin startproject litechat .` and `startapp billing`, `startapp llm`, `startapp chat`. Register the apps in `INSTALLED_APPS`.
  - *Note:* the generated per-app `tests.py` stubs were removed, because later phases use `tests/` packages and both cannot coexist. The generated hard-coded `SECRET_KEY` was removed (see 1.3).
- [x] 1.3 `litechat/settings.py`:
  - Load `.env` with `python-dotenv`.
  - Read `SECRET_KEY` from `DJANGO_SECRET_KEY` and `DEBUG` from `DJANGO_DEBUG`. The app fails loudly if `SECRET_KEY` is missing and DEBUG is off.
  - Add `TEMPLATES` dirs and `STATIC` settings.
  - Set `LOGIN_URL = "/login/"`, `LOGIN_REDIRECT_URL = "/chat/"`, `LOGOUT_REDIRECT_URL = "/login/"`.
  - Add app settings: `LITECHAT_PROXY_BASE_URL = "https://proxy.litechat.ai"`, `LITECHAT_PROXY_TIMEOUT = 120`, `LITECHAT_MAX_OUTPUT_TOKENS = 1024`.
- [x] 1.4 Add `DJANGO_SECRET_KEY` and `DJANGO_DEBUG` to `.env.example` (names only), and add real values to the local `.env`. A random key was generated into `.env` without printing it.
- [x] 1.5 `templates/base.html` with a minimal `static/css/app.css`. Simple and clean; no pixel-matching.
- [x] 1.6 `litechat/urls.py` with admin, `/` redirecting to `/chat/`, and includes for `chat`, `billing` and the auth views.
  - *Deviation:* the auth views are left for Phase 2 (2.1 wires them). `chat/urls.py` and `billing/urls.py` exist with empty route lists, so `/chat/` returns 404 until Phase 5.
- [x] 1.7 Commit: `chore: scaffold Django project and apps`.

**Tests:** *(added at the user's request)* `litechat/tests.py` has 7 smoke tests: apps installed, proxy and auth settings, base template links the stylesheet, the stylesheet is findable, `/` redirects to `/chat/`, and the admin login loads.

**Result (2026-09-29):** `check` shows no issues. `makemigrations --check` shows no changes. `migrate` OK. Tests: 7/7 pass. `runserver`: `/` gives 302 → `/chat/`, `/admin/login/` gives 200, `/static/css/app.css` gives 200. With `DJANGO_DEBUG=False` and no key, the app raises `ImproperlyConfigured`.
**Verify:** `python manage.py check` passes. `python manage.py migrate` succeeds. `runserver` starts, and `/admin/` loads.

---

## Phase 2: Authentication
*Depends on: 1.*

- [x] 2.1 Wire `/login/` (`LoginView`) and `/logout/` (`LogoutView`, POST) in `litechat/urls.py`. `redirect_authenticated_user=True`, so logged-in users visiting `/login/` go to `/chat/`.
- [x] 2.2 `templates/registration/login.html`: "Welcome!", Username, Password, and a LOG-IN button, as in LiteChat [SS]. Show an error when login fails.
- [x] 2.3 `templates/app_layout.html`, which every logged-in page extends:
  - A sidebar with the LiteChat name, a logout button (a POST form), "New conversation", the session list (filled in Phase 8), and a My Profile link.
  - A main content block.
  - *Note:* the "New conversation" (`/chat/new/`) and "My Profile" (`/profile/`) links are hard-coded, and return 404 until Phases 5 and 3. The session list is a placeholder until Phase 8.
- [x] 2.4 Protect every app view with `@login_required`.
  - *Deviation:* a bare, login-protected `chat.views.home` (`/chat/`, `templates/chat/home.html`) was added now, so that login has a page to land on. Phase 5.4 replaces its content with the empty state.
- [x] 2.5 Tests in `chat/tests/test_auth.py`:
  - An anonymous `GET /chat/`, `/chat/new/` and `/profile/` redirects to `/login/?next=…`.
  - A valid login redirects to `/chat/`.
  - A bad password shows an error.
  - Logout (POST) ends the session.
  - *Deviation:* `/chat/new/` and `/profile/` don't exist yet, so their anonymous-redirect checks moved to 5.5 and 3.6. `PROTECTED_URLS` in `test_auth.py` gets those URLs then. Extra tests were added: login page content, `next` handling, logged-in users skip `/login/`, logout by GET is refused (405), and `/chat/` uses the app layout.
- [x] 2.6 Commit: `feat: add login and logout`.

**Verify:** tests pass. In the browser, `/chat/` goes to `/login/`, logging in lands on `/chat/`, and logout returns to `/login/`.

**Result (2026-09-29):** `check` shows no issues. `chat.tests.test_auth`: 9/9 pass. Full suite: 16/16 pass. Against `runserver` with a temporary user (since deleted): anonymous `/chat/` gives 302 → `/login/?next=/chat/`, a bad password gives 200 with the error, a good login gives 302 → `/chat/`, `/chat/` gives 200 "Signed in as …", POST `/logout/` gives 302 → `/login/`, and `/chat/` afterwards gives 302 → login.

---

## Phase 3: Billing accounts and credit
*Depends on: 1, 2.*

- [x] 3.1 `billing/models.py`:
  - `BillingAccount` with `name`, `kind` (`personal`/`shared`), `status` (`active`/`suspended`), `credit` (`DecimalField(max_digits=12, decimal_places=6)`), `members` (M2M → User) and `created_at`. Its `__str__` is `"[Personal] NAME"`, as in LiteChat [SS].
  - (`UsageCharge` is created in Phase 7, because it references `chat.Message`.)
- [x] 3.2 `billing/admin.py`: register `BillingAccount` with list display (name, kind, status, credit) and `filter_horizontal` members. **Admins top up credit by editing this field.**
- [x] 3.3 `billing/management/commands/seed_demo.py`: `seed_demo --username U --password P [--credit 2.00]`.
  - Creates or updates the user and a `[Personal]` active account with the given credit, and links them.
  - It is idempotent.
  - **Passwords come from arguments. None are hard-coded or committed.**
  - *Addition:* if `--password` is omitted, the command prompts for it, which keeps demo passwords out of shell history and the session transcripts. The account name is the user's full name (or username) in capitals, as in LiteChat. A re-run resets credit to `--credit` and reactivates the account.
- [x] 3.4 `billing/views.py` `profile` plus `templates/billing/profile.html`:
  - A User Profile section (display name, username, member since).
  - A Billing Accounts list for **the user's accounts only**, with name, status badge and **AVAILABLE CREDIT** shown as `$X.XX`.
  - *Implementation:* `billing/templatetags/money.py` has a `usd` filter (rounds half-up to cents, shows negatives as `-$0.01`). The sidebar "My Profile" link now uses `{% url 'billing:profile' %}`.
- [ ] 3.5 Show the selected or first account's balance in the sidebar footer. This is optional; skip it if short on time.
  - *Skipped* (cut line item 1). The balance is on `/profile/`.
- [x] 3.6 Tests in `billing/tests/`:
  - `seed_demo` creates the user and account with $2.00, and running it twice doesn't duplicate anything.
  - The profile page shows only the logged-in user's accounts and credit.
  - Another user's account is not listed.
  - Anonymous `GET /profile/` redirects to `/login/?next=/profile/` (add to `PROTECTED_URLS` in `chat/tests/test_auth.py`; moved from 2.5).
  - *Added:* model defaults and `__str__`, sub-cent precision, the `usd` filter, seed re-run reset and prompt, invalid credit rejected, suspended status shown, a user with no accounts, and an **admin top-up via the change form**.
- [x] 3.7 Commit: `feat: add billing accounts, credit and profile page`.

**Verify:** after `seed_demo`, `/profile/` shows "[Personal] … ACTIVE … $2.00". Changing the credit in the admin changes the value shown on the profile.

**Result (2026-09-29):** migration `billing/0001_initial` (BillingAccount + members M2M). `billing` + auth tests: 26/26 pass. Full suite: 33/33 pass. `makemigrations --check`: no changes. Manual run against `runserver` with a temporary user (since deleted): `seed_demo` run twice → one user and one account. `/profile/` shows `[Personal] PHASE3CHECK`, Active, `$2.00`. Setting credit to 12.345 → `$12.35`. Anonymous `/profile/` → 302 to login.

---

## Phase 4: Model catalog (the 3 proxy models)
*Depends on: 1.*

- [x] 4.1 `llm/models.py` `LLMModel` with these fields:
  - `provider` (`openai`/`anthropic`/`google`)
  - `api_model` (unique)
  - `display_name`, `description`
  - `tier` (`value`/`standard`/`premium`)
  - `input_price_per_mtok`, `output_price_per_mtok` (Decimal)
  - `is_active`, `sort_order`
- [x] 4.2 A data migration `llm/migrations/000X_seed_models.py` seeds the three rows from D3:
  - `gpt-5.6-luna`: "GPT-5.6 Luna", openai
  - `claude-haiku-4-5-20251001`: "Claude Haiku 4.5", anthropic
  - `gemini-3.8-flash`: "Gemini 3.8 Flash", google
  - Each gets a one-line description and tier Value.
- [x] 4.3 `llm/admin.py`: register `LLMModel`.
- [x] 4.4 Tests in `llm/tests/test_catalog.py`: after migrations, exactly the 3 active models exist, with the correct provider and model ID pairs and prices greater than 0.
- [x] 4.5 Commit: `feat: add model catalog with three proxy models`.

**Verify:** the admin lists the 3 models with tiers and prices.

**Result (2026-09-29):** migrations `llm/0001_initial` and `0002_seed_models` (reversible). Catalog tests 6/6 pass, including the admin list. Commit `a192881`. The unused `llm/views.py` stub was removed.

## Phase 4b: Provider adapters (proxy client)
*Depends on: 4. Can be done alongside 3 and 5.*

- [x] 4b.0 Add `requests` to `requirements.txt` and install it (moved here from 1.1).
- [x] 4b.1 `llm/providers.py`:
  - `Turn(role: "user"|"assistant", content: str)`
  - `CompletionResult(text, status: "complete"|"truncated", input_tokens, output_tokens)`
  - `ProviderError(kind, user_message)` with kinds `auth`, `rate_limited`, `bad_request`, `upstream`, `timeout`, `bad_response`
- [x] 4b.2 `complete(llm_model, turns, system_prompt=None) -> CompletionResult` dispatches on `llm_model.provider`.
- [x] 4b.3 `_openai`: `POST {base}/openai/v1/chat/completions` with header `Authorization: Bearer $BUILD_OPENAI_KEY` and body `{model, messages, max_tokens, reasoning_effort:"none"}`.
  - Parse `choices[0].message.content`, `finish_reason` (`length` → truncated) and `usage.prompt_tokens/completion_tokens`.
- [x] 4b.4 `_anthropic`: `POST {base}/anthropic/v1/messages` with headers `x-api-key` and `anthropic-version: 2023-06-01`, and body `{model, messages, max_tokens, thinking:{type:"disabled"}}` (+ `system`).
  - Join the `text` blocks. Parse `stop_reason` (`max_tokens` → truncated) and `usage.input_tokens/output_tokens`.
- [x] 4b.5 `_google`: `POST {base}/google/v1beta/models/{api_model}:generateContent` with header `x-goog-api-key`.
  - Roles map `assistant` → `model`, and text goes in `parts`.
  - Body includes `generationConfig{maxOutputTokens, thinkingConfig{thinkingBudget:0}}` (+ `systemInstruction`).
  - Join the `parts[].text`. Parse `finishReason` (`MAX_TOKENS` → truncated) and `usageMetadata.promptTokenCount/candidatesTokenCount`.
- [x] 4b.6 Error handling:
  - Map HTTP status to kind: 401/403 → `auth`, 429 → `rate_limited`, 400 → `bad_request`, 5xx → `upstream`. `requests.Timeout` and `ConnectionError` → `timeout`/`upstream`. Missing fields → `bad_response`.
  - **No automatic retries.**
  - **Never include keys or request headers in exceptions or logs.**
- [x] 4b.7 Keys are read from `os.environ` at call time. A missing key raises `ProviderError("auth", …)`.
- [x] 4b.8 Fixtures in `llm/tests/fixtures/`: `openai_ok.json`, `anthropic_ok.json`, `google_ok.json`, `openai_length.json`, `openai_error_401.json`, `openai_error_400.json`. They are based on the study's live responses and contain **no keys**.
- [x] 4b.9 Tests in `llm/tests/test_providers.py`, with `requests.post` mocked and dummy env keys:
  - For each provider: the correct URL, the correct auth header *name*, and a request body with the history, system prompt, `max_tokens` and reasoning disabled.
  - For each provider: text and token parsing works.
  - Truncation is detected.
  - 401 → `auth`, 429 → `rate_limited`, 500 → `upstream`, timeout → `timeout`, malformed JSON → `bad_response`.
  - Gemini maps `assistant` to `model`.
- [ ] 4b.10 **(ON HOLD: wait for reissued keys)** Manual smoke test from `python manage.py shell`: one `complete()` per provider against the real proxy. Record the result, but **not keys**.
- [x] 4b.11 Commit: `feat: add provider adapters for OpenAI, Anthropic and Gemini proxy interfaces`.

**Verify:** all adapter tests pass without network access. The manual smoke test returns text and token counts for all three providers.

**Result so far (2026-09-29):** `llm` tests 35/35 pass offline, including a run with sockets blocked (0 connection attempts). Commit `91399a2`.

**Incident:** the first test run printed the real proxy keys in failure output. A class-level `mock.patch.dict` didn't apply to subclass tests, so the real keys loaded from `.env` were used. No request was sent, and nothing was written to files or git. **Fixes:** dummy keys are patched in `setUp` (`DummyKeysMixin`); header assertions never echo values; tests run with placeholder `BUILD_*_KEY` env vars and output passes through a redaction filter. **Follow-up:** the keys must be reissued by the proxy admin, and must not be used for live calls until then.

`openai_length.json` is the recorded OK response with `finish_reason` set to `length` (no real truncated response was captured). A Gemini `SAFETY` finish is treated as `complete`, since the plan defines only complete and truncated.

---

## Phase 5: New conversation (billing account + model selection)
*Depends on: 2, 3, 4.*

- [x] 5.1 `chat/models.py`:
  - `ChatSession` with `user` (FK), `billing_account` (FK, PROTECT), `llm_model` (FK, PROTECT), `name` (default `"Untitled session"`), `created_at` and `updated_at`, ordered by `-updated_at`.
  - `Message` with `session` (FK, CASCADE), `role` (`user`/`assistant`), `content`, `status` (`complete`/`truncated`), `input_tokens`, `output_tokens`, `cost` (nullable, used for assistant messages) and `created_at`, ordered by `created_at`.
- [x] 5.2 `chat/forms.py` `NewSessionForm`:
  - `billing_account` is limited to the user's **active** accounts.
  - `llm_model` is limited to active models.
- [x] 5.3 `chat.views.new_session` + `templates/chat/new_session.html` ("Select a Model"):
  - A **Billing account** dropdown with the help text "Costs for this session will be charged to the selected account."
  - Models **grouped by provider** as cards (radio buttons) with display name, description and a tier badge. Prices are shown as a small line under each card.
  - Submitting creates the session and redirects to `/chat/<id>/`.
- [x] 5.4 `chat.views.home` + `templates/chat/home.html`: a "Start a New Conversation" empty state with a big **+** that links to `/chat/new/`.
- [x] 5.5 Tests in `chat/tests/test_new_session.py`:
  - GET lists only the user's active accounts and the 3 models.
  - A valid POST creates a session named "Untitled session" with the chosen account and model, and redirects.
  - Choosing another user's account, or a suspended account, is rejected.
  - A user with no active account sees a clear message.
  - Anonymous `GET /chat/new/` redirects to login (add to `PROTECTED_URLS`; moved from 2.5).
- [x] 5.6 Commit: `feat: add new conversation with billing account and model selection`.

**Verify:** in the browser, + leads to the picker, and choosing an account and model opens an empty session page showing the model and account.

*Deviation:* a minimal `chat.views.session_detail` (`/chat/<id>/`, `templates/chat/session_detail.html`) was added so that 5.3's redirect has a target. It is owner-scoped (404 for others), shows the name, model, billing account and a "No messages yet" list, and has **no message form**. Phase 6.3 adds messaging to it. The view passes messages as `chat_messages`, to avoid clashing with Django's `messages` framework.

**Result (2026-09-29):** migration `chat/0001_initial` (ChatSession, Message). `chat` tests 23/23 pass. Full suite 82/82 pass (run with placeholder keys). Manual run on `runserver` with a temporary user (deleted afterwards): `/chat/` shows the empty state with + → `/chat/new/`. The picker lists OpenAI, Anthropic and Google groups, `[Personal] …` and 3 × "Value tier". POST → 302 `/chat/1/`, which shows "Untitled session", "Model: Gemini 3.8 Flash", the billing account, and "No messages yet." No proxy calls were made.

---

## Phase 6: Chat through the LiteChat proxy
*Depends on: 4b, 5.*

- [x] 6.1 `chat/services.py` `build_turns(session)`: the stored messages in order, as `Turn`s. In the MVP there's no system prompt; the parameter exists for later.
- [x] 6.2 `chat/services.py` `send_message(session, text)`:
  - Validate the text: not blank, maximum length (e.g. 8,000 chars).
  - Build the turns plus the new user turn.
  - Call `llm.providers.complete`.
  - Hand the result to metering (Phase 7). **The user message and assistant reply are saved together only on success.**
- [x] 6.3 `chat.views.session_detail` + `templates/chat/session_detail.html`:
  - A header with the session name, a model pill ("Model: GPT-5.6 Luna") and the billing account.
  - Message bubbles: user on the right, assistant on the left. Truncated replies show a "(reply cut off: token limit)" note.
  - A message form at the bottom.
- [x] 6.4 `chat.views.send_message` (POST only):
  - Call the service.
  - On success, **redirect** (POST-redirect-GET) to `/chat/<id>/`.
  - On failure, re-render with the error and the **draft kept in the textarea**.
- [x] 6.5 `static/js/chat.js`: on submit, disable the button, show "Thinking…", and scroll to the bottom on load. This is the MVP's substitute for streaming.
- [x] 6.6 Bump `session.updated_at` on every successful exchange so the sidebar order reflects recent use.
- [x] 6.7 Tests in `chat/tests/test_chat.py`, with `llm.providers.complete` mocked:
  - Sending saves the user message and the assistant reply, then redirects.
  - The second message includes the first exchange in `turns` (multi-turn).
  - A blank message is rejected.
  - Another user's session returns 404 on GET and on send.
- [x] 6.8 Commit: `feat: chat through proxy adapters with saved history`.

**Verify:** a real message in a Luna session gets a reply, and a follow-up question that depends on the first answer is answered in context.

**Result (2026-09-29):** `chat.tests.test_chat` 17/17 pass. Full suite 99/99 pass (placeholder keys; `llm.providers.complete` is mocked, and `requests.post` is patched to fail if reached).

- **Real-proxy check: pending** until the keys are reissued (same hold as 4b.10). It's covered by 12.3.
- **Substitute check:** `runserver` pointed at a **local fake proxy** (scratch files outside the repo; a settings override sets `LITECHAT_PROXY_BASE_URL=http://127.0.0.1:8799`; placeholder keys). The fake proxy is stateless and answers in each provider's response shape.
  - For Luna, Haiku and Gemini: "My name is Hans." then "What is my name?" → "Your name is Hans." Prompt tokens rose 181 → 183, showing the full history was sent.
  - A fake 429 showed "The AI service is busy…", kept the draft, and saved nothing.
  - Credit was unchanged ($2.00). Metering is Phase 7.

*Notes:*
- `send_message` validates input (blank, and a maximum of 8,000 chars), calls the adapter with the full history, and saves the user and assistant messages plus a `updated_at` bump in one transaction only on success.
- The token counts are stored on the assistant message now. `cost` stays empty until Phase 7.
- `ProviderError.user_message` is already shown to the user. Phase 11 reviews the wording.
- `chat.js` sets the textarea to `readOnly` (not `disabled`) so the text is still submitted.

---

## Phase 7: Token-based metering and credit deduction
*Depends on: 3, 6. Tightly coupled to 6.2.*

- [x] 7.1 `billing/services.py` `calculate_cost(llm_model, input_tokens, output_tokens) -> Decimal`: `in × in_price / 1_000_000 + out × out_price / 1_000_000`, quantized to 6 dp.
- [x] 7.2 `billing/services.py` `ensure_can_spend(account)`:
  - Raises `AccountInactive` if the account isn't active.
  - Raises `InsufficientCredit` if `credit <= 0`.
- [x] 7.3 `billing/services.py` `record_charge(account, message, llm_model, in_tok, out_tok)`:
  - Inside `transaction.atomic()`, re-fetch the account with `select_for_update()`, subtract the cost, and create a `UsageCharge`.
  - Negative balances are allowed only as the result of the final message (D4).
- [x] 7.4 Wire into `send_message`:
  1. Call `ensure_can_spend` **before** the proxy call.
  2. On success, in one `transaction.atomic()`, save the user message and the assistant message (with tokens and cost), then call `record_charge`.
  3. On `ProviderError`, save nothing and charge nothing.
- [x] 7.5 `billing/models.py` `UsageCharge` with these fields, plus a migration:
  - `billing_account` (FK, PROTECT)
  - `message` (1:1 → `chat.Message`, `on_delete=SET_NULL`, nullable)
  - `session_label` (text snapshot of the session ID and name)
  - `llm_model` (FK, PROTECT)
  - `input_tokens`, `output_tokens`
  - `cost` (Decimal, 6 dp)
  - `created_at`

  Register it in the admin as read-only.
- [x] 7.6 UI: (the optional per-message tokens and cost line was **skipped**; it is a stretch item)
  - Blocked sends show "Insufficient credit in [Personal] NAME. Ask an administrator to top up." or "This billing account is not active."
  - The profile page shows the updated balance.
  - A small "N tokens · $0.000123" line under each assistant bubble is optional and done only if trivial (it's a stretch item).
- [x] 7.7 Tests in `billing/tests/test_metering.py` and `chat/tests/test_chat.py`:
  - `calculate_cost` is exact for known inputs, for each model's prices.
  - A successful send deducts exactly the calculated cost and creates one `UsageCharge` linked to the assistant message.
  - With credit = 0, the send is **blocked, the proxy is not called** (mock asserts not called), and nothing is saved.
  - A suspended account is blocked.
  - A `ProviderError` means no charge, no messages saved, and an unchanged balance.
  - Two sessions on the same account both deduct from the same balance.
- [x] 7.8 Commit: `feat: meter token usage and deduct credit per reply`.

**Verify:**
- Note the balance, send a message, and check that the balance dropped by the recorded `UsageCharge.cost`, visible in the admin.
- Set credit to 0 in the admin. Sending is then blocked with a clear message, and no proxy call is made.

**Result (2026-09-29):** migration `billing/0002_usagecharge`. `billing.tests.test_metering` + `chat.tests.test_chat`: 39/39 pass. Full suite 121/121 pass (placeholder keys, provider mocked). `makemigrations --check`: no changes. Commit `fd1888d`.

Manual run on `runserver` + the **local fake proxy** (placeholder keys; the real-proxy check is pending, as with 4b.10), with a temporary user and admin (deleted afterwards):
- Haiku session, 2 sends: charges of 181+11 tok = $0.000236 and 183+4 tok = $0.000203. Balance 2.000000 → 1.999561 (exactly −0.000439). The profile shows `$2.00` (rounded to cents). The admin lists 2 usage charges, and its add page gives 403 (read-only).
- Credit set to 0: the send gave "Insufficient credit in [Personal] … Ask an administrator to top up.", the draft was kept, and the fake proxy received **no** new request.

*Notes:*
- Truncated replies are charged (their tokens were consumed).
- The cost is rounded half-up to 6 dp.
- The deduction is `credit = F('credit') - cost` on a `select_for_update()`-locked row, inside the same `transaction.atomic()` as saving both messages and the `updated_at` bump. A failure anywhere rolls back everything (tested by forcing `UsageCharge.objects.create` to fail).
- `ensure_can_spend` re-reads the account from the DB rather than trusting the in-memory object.

---

## Phase 8: Saved conversation / session history
*Depends on: 5, 6.*

- [x] 8.1 A context processor or template tag supplies the sidebar session list for `request.user`, newest first by `updated_at`. Each item shows the name and date (e.g. "Sep 29, 2026") and links to `/chat/<id>/`. The current session is highlighted.
- [x] 8.2 Opening an older session shows its full history, and further sends continue that conversation (history comes from the DB, since the proxy is stateless).
- [x] 8.3 Tests:
  - The sidebar shows only the user's sessions, in `updated_at` order.
  - Reopening a session renders every stored message in order.
  - Data persists across logout and login (same DB).
- [x] 8.4 Commit: `feat: list saved sessions in sidebar`.

**Verify:** create two sessions with different providers, log out and back in, and both are listed with their histories intact.

**Result (2026-09-29):** `chat/context_processors.py` `sidebar_sessions` (registered in settings) supplies the list to `app_layout.html`. Items show the name and `M j, Y` date. The open session gets `active` + `aria-current`. There's no pagination (LiteChat's infinite scroll is out of scope). Commit `49ec43c`. Manual check (dev server + local fake proxy, placeholder keys): Luna and Gemini sessions are listed newest first, survive logout/login with their history, and the current one is highlighted.

---

## Phase 9: Session rename
*Depends on: 8.*

- [x] 9.1 `chat.views.rename_session` (POST `name`):
  - Trim it and cap it at 100 chars. A blank name is rejected (the old name is kept).
  - Scoped to the owner.
  - Redirect back.
- [x] 9.2 UI: a ✎ button in the session header reveals an inline form (a small JS toggle, or a plain `<details>` element).
- [x] 9.3 Tests: the owner can rename; a blank name is rejected; another user gets 404; GET is not allowed (405).
- [x] 9.4 Commit: `feat: rename chat sessions`.

**Verify:** a session renamed in the browser shows the new name in both the header and the sidebar.

**Result (2026-09-29):** a ✎ `<details>` toggle in the header opens the inline form. The name is trimmed, cut to 100 chars, and blank names are rejected with a message. Renaming does **not** change `updated_at` (so it doesn't reorder the list). Commit `64caefb`. Manual check: the header and sidebar show "Trip planning", and a blank rename kept it.

*Deviation:* `app_layout.html` now renders Django `messages` (flash). This is needed for the blank-name rejection and delete confirmation, and is the only Phase 11-adjacent UI added.

---

## Phase 10: Session deletion
*Depends on: 8.*

- [x] 10.1 `chat.views.delete_session`: GET shows `session_confirm_delete.html` ("Delete 'NAME'? This cannot be undone."). POST deletes the session and redirects to `/chat/`. Scoped to the owner.
- [x] 10.2 **Billing records are kept.** Deleting a session deletes its messages. `UsageCharge.message` uses `SET_NULL` and keeps `session_label` (from 7.5), so the charge history survives.
- [x] 10.3 UI: a 🗑 button in the session header (and/or on sidebar items) leads to the confirm page.
- [x] 10.4 Tests:
  - The owner can delete, and the session and its messages are gone.
  - `UsageCharge` rows remain and the balance is unchanged.
  - Another user gets 404.
- [x] 10.5 Commit: `feat: delete chat sessions`.

**Verify:** after deleting in the browser, the session disappears from the sidebar and its charges are still visible in the admin.

**Result (2026-09-29):** 🗑 links appear in the header **and** on each sidebar item (as in LiteChat [SS]), leading to the confirm page. POST deletes the session and redirects to `/chat/` with "Deleted '…'." Commit `63f9f94`. Manual check: after deleting the Gemini session, only "Trip planning" remains. Charges were 2 before and 2 after (the deleted one has `message=NULL` and label `#10 Untitled session`), and the balance was unchanged.

*Note:* `UsageCharge.session_label` is a snapshot taken at charge time, so it doesn't follow later renames.

**Tests (Phases 8–10):** `chat.tests.test_sessions` 24/24 pass. Full suite 145/145 pass. `makemigrations --check`: no changes. All run with placeholder keys and a guard that fails any test reaching the proxy.

---

## Phase 11: Basic error handling
*Depends on: 6, 7. Mostly finishes work started there.*

- [x] 11.1 Map each `ProviderError` kind to a friendly message in the chat view:
  - `auth`: "The AI service rejected our credentials. Please contact the administrator."
  - `rate_limited`: "The AI service is busy. Please try again in a moment."
  - `timeout`: "The AI service took too long to respond. Please try again."
  - `upstream` / `bad_response`: "The AI service is unavailable right now."
  - `bad_request`: "The request could not be processed."
  - *Already done in 4b:* the messages live in `ProviderError.DEFAULT_MESSAGES` (word for word as above), and the chat view shows them through `SendError` (Phase 6). This is not duplicated in the view. **Phase 11 fix:** an unsupported provider showed "Unsupported provider: <name>". It now shows the generic `bad_request` message and logs the detail.
- [x] 11.2 Server-side logging records the kind and HTTP status only. **No headers, keys or full bodies.**
  - *Already done in 4b* for logs. **Phase 11 gap found and fixed:** with `DEBUG=True` (the local `.env`), Django's debug error page showed frame locals, including the key, if an unexpected exception escaped `complete()`. Fixes:
    - `@sensitive_variables()` (all locals) on `complete`. Frames below it, in `requests`/`mock`, hold the headers under other names such as `kwargs`.
    - `@sensitive_variables('key')` on the builders.
    - `litechat/debug.py` `AlwaysSafeExceptionReporterFilter` (`DEFAULT_EXCEPTION_REPORTER_FILTER`). Django only applies masking when DEBUG is off.
- [x] 11.3 Validation messages for a blank message, an overlong message, a blank rename, and "no active billing account".
  - *Already done:* blank and overlong message (Phase 6), blank rename (Phase 9), no active account (Phases 5 and 7). No change.
- [x] 11.4 404 for other users' sessions everywhere (already covered by the tests in 6, 9 and 10). Custom `404.html` is optional. *(Skipped: optional.)*
- [x] 11.5 Tests: for each `ProviderError` kind, the rendered page shows its message, the draft is kept, and nothing is charged.
  - `chat/tests/test_errors.py` (9 tests):
    - every `ProviderError` kind at page level
    - the real adapter with 400/401/403/429/500/502/503/504 on all three providers, plus timeout, connection error, malformed 200, and missing key (no request made). For each: the message is shown, the draft kept, nothing saved or charged, and no key or upstream detail appears in the page.
    - logs hold the kind and status only
    - the generic unsupported-provider message
    - error pages hide keys with DEBUG on and off, including `request.META`
    - a guard proving the masking depends on the decorator
- [x] 11.6 Commit: `fix: show clear errors for proxy failures and invalid input` (`d1f858b`).

**Verify:** temporarily set a wrong key in the environment. The chat shows the credentials message, no charge is made, and restoring the key fixes it.

**Result (2026-09-29):** `chat.tests.test_errors` 9/9 pass. Full suite 154/154 pass. `makemigrations --check`: no changes. Secret scan: 81 working files and the full git history hold no keys, and `.env`/`db.sqlite3` are untracked.

The verify step was done against the **local fake proxy** (the real keys must not be used), which rejects keys containing "wrong" with the real proxy's 401 body:
- With `BUILD_OPENAI_KEY=wrong-placeholder-key`: the page showed "The AI service rejected our credentials…", the draft was kept, 0 messages, 0 charges, credit $2.00. The server log held `kind=auth status=401` only, with no key and no proxy detail.
- Restarted with a good placeholder: the send worked (2 messages, 1 charge, credit $1.999908).

---

## Phase 12: Tests, verification and rendezvous
*Depends on: 1–11.*

- [x] 12.1 `python manage.py test` passes, with **no network calls** (the adapters are mocked everywhere).
- [x] 12.2 `python manage.py check` passes, and `python manage.py makemigrations --check` reports no missing migrations.
- [ ] 12.3 **(REAL PROXY: ON HOLD, waiting for reissued keys)** Manual end-to-end check against the real proxy, from a fresh DB (`migrate` + `seed_demo`):
  - *Substitute done:* every sub-step below was run against the **local fake proxy** from a clean clone (see Result). The real-proxy run is still required before 12.6.
  - [ ] Log in, and the empty state is shown.
  - [ ] New conversation: [Personal] account + **GPT-5.6 Luna**. Two turns; the second relies on the first.
  - [ ] New conversation with **Claude Haiku 4.5**, one turn.
  - [ ] New conversation with **Gemini 3.8 Flash**, one turn.
  - [ ] The profile balance went down from $2.00, and the `UsageCharge` rows match the replies.
  - [ ] Rename one session, delete another. The sidebar is correct and the charges are kept.
  - [ ] Set credit to 0 in the admin. The send is blocked with a clear message.
  - [ ] Log out, log back in, and the sessions and history are intact.
- [x] 12.4 Security check:
  - A grep of the repo for each key value finds it only in `.env`.
  - `git ls-files` doesn't include `.env` or `db.sqlite3`.
  - No key is in any template or static file.
- [x] 12.5 Quick review of the diff for leftover debug code and unrelated changes.
- [ ] 12.6 Tick this checklist, then merge `feat/litechat-mvp` into `main` (`git merge --no-ff`) **only if 12.1–12.4 pass**.
  - **Approved by the user (2026-09-29)** to merge with the real-proxy part of 12.3 still on hold. Local checks 12.1, 12.2, 12.4 and 12.5 pass, and the QA fix is in.

**Verify:** `main` has a working app, and a fresh clone + setup steps + `runserver` gives a working demo.

**Result (2026-09-29, QA review; no live proxy calls, the exposed keys were never used):**

| # | Check | Result |
|---|---|---|
| 12.1 | Full suite with sockets blocked | **154/154 pass, 0 network connection attempts** (litechat 7, billing 31, llm 35, chat 81) |
| 12.2 | `check` / `makemigrations --check` / `showmigrations` | no issues / no changes / all 5 app migrations applied |
| — | `check --deploy` (informational) | 4 HTTPS-only warnings (HSTS, SSL redirect, secure cookies). No deployment is planned (study A1). |
| Clean clone | `git clone` of the branch → new `.venv` → `pip install -r requirements.txt` → `.env` from `.env.example` with **placeholder** keys → `migrate` on a fresh DB | OK. 3 models seeded, `check` clean, **154/154** tests pass, `git status` clean |
| 12.3 (substitute) | Scripted browser-style walkthrough on the clean clone against the **local fake proxy** (`qa_settings`: local base URL, 3 s timeout) | **44/44 checks pass** (details below) |
| Debug page | Real 500 from inside `complete()` with `DEBUG=True` | Debug page rendered with the `llm/providers.py` frame. **No placeholder key and no `Bearer` header in the page.** 90 masked values. |
| 12.4 | Secret scan (3 proxy keys + Django secret key; values never printed) | none in 81 tracked files, untracked files, templates/static, or **26 commits (all refs)**. The only file holding them is `.env` (ignored, untracked). `db.sqlite3` and `.venv` are untracked. The generated `django-insecure` key was never committed. `.env.example` has empty values. |
| 12.5 | Diff review `main..feat/litechat-mvp` (75 files) | no `print`/`pdb`/`breakpoint`/`console.log`/TODO. No files outside the planned layout. CLAUDE.md and the study are unchanged. `DEBUG` defaults to off. |

The 44 walkthrough checks:
- **Auth:** anonymous `/chat/`, `/chat/new/`, `/profile/` → login. Bad password → error. Login → `/chat/` empty state. Logout by GET → 405. Logout by POST ends the session.
- **Billing:**
  - `[Personal] QA`, Active, `$2.00`.
  - 5 replies → 5 charges. Balance 2.00 → 1.999439 (exactly −0.000561). Each charge matches its reply's cost and tokens.
  - The admin set credit to 0 → send blocked with "Insufficient credit…", draft kept, **fake proxy not called**.
  - Charges are listed in the read-only admin.
- **Model selection:** the account dropdown with help text. Providers OpenAI/Anthropic/Google. 3 models, 3 × "Value tier".
- **Chat:**
  - Luna, two turns: "What is my name?" → "Your name is Hans." (the stateless fake proxy can only know this from the history).
  - Haiku and Gemini, one turn each.
  - Continuing the older Luna session sent 5 messages of history.
- **Sessions:**
  - The sidebar lists 3, most recent first, with the current one highlighted.
  - Rename shows in the header and sidebar. A blank rename is rejected.
  - Delete confirms, removes the session and its sidebar item, and keeps the charges and balance.
  - Sessions and history are intact after logout/login.
  - Another user gets 404 on view and delete.
- **Errors:** 400, 401, 403, 429, 500, 502, 503, 504, timeout, and connection failure (fake proxy stopped). Each showed the planned friendly message, kept the draft, saved and charged nothing, and showed no upstream detail or key. The server log held only `kind=… status=…` lines. The only traceback in the log was Django's standard entry for the **intentional** 403 on the read-only admin add page.

**Still pending (needs reissued keys):** 4b.10, and the 12.3 run against the real proxy (the three providers' real response shapes, real usage numbers, real latency). Then 12.6 (merge).

**QA finding (not fixed; no new features in this phase):** `send_message` checks that the billing account is active and has credit, but does **not** re-check that the user is still a member. If an admin removes a user from a *shared* account, that user's existing sessions can still charge it. The MVP demo is unaffected (personal accounts only). It's a small follow-up fix if wanted.

**QA finding fixed (user-approved, 2026-09-29):** `chat.views.send_message` now re-checks membership before the credit check and the proxy call. A removed member gets **403** with "You are no longer a member of …", the draft is kept, and there's no proxy call and no charge. History stays readable. 4 tests were added (`BillingMembershipTests`). Full suite 158/158 pass. Commit `07e2803`.

---

## Phase 13: Sync docs
*Depends on: 12.*

- [x] 13.1 `README.md`: what the project is, setup (venv, `pip install -r requirements.txt`, `.env` from `.env.example`, `migrate`, `seed_demo`, `runserver`), how to run the tests, and links to `doc/`.
- [x] 13.2 `doc/wiki/architecture.md`: the apps (`billing`, `llm`, `chat`), the models, the request flow (send → credit check → adapter → proxy → atomic save + charge), and the routes.
- [x] 13.3 `doc/wiki/billing-and-models.md`:
  - Pricing per model (ours, D3) and the cost formula.
  - The charge-on-success policy and possible final overdraft (D4).
  - Admin top-ups.
  - Proxy caveats: 3 models only, all DeepSeek Flash, ~175 hidden prompt tokens per request, latency.
- [x] 13.4 `doc/wiki/README.md`: an index of the wiki pages.
- [x] 13.5 Note in this plan any deviations made during execution.
- [x] 13.6 Commit: `docs: add wiki and README for LiteChat MVP` (`e25a78a`).
  - *Deviation:* committed on `feat/litechat-mvp` **before** the merge, at the user's request (docs, then merge), so it reaches `main` through the merge rather than as a commit on `main`.

**Verify:** the docs describe the code as it actually is, and the setup steps work when followed literally.

**Result (2026-09-29):**
- **Docs match the code:** no broken relative links. The timeout and max tokens match settings, all 3 catalog rows match the DB, and all documented routes resolve.
- **Setup works literally:** in a fresh clone following the README (placeholder keys), `pip install`, `cp .env.example .env`, `migrate` (3 models), `seed_demo` ($2.00 [Personal]), `runserver` (`/` → `/chat/`, `/login/` 200, `/admin/login/` 200), `test` 158/158, `check` clean, `makemigrations --check` clean, and `git status` clean.

**Deviations recorded during execution (13.5):**
- **1.1** `requests` moved to 4b.0.
- **1.2** App `tests.py` stubs removed. The generated `SECRET_KEY` was removed before the first commit.
- **1.6** Auth views were wired in 2.1.
- **2.4 / 5.3** Minimal placeholder views were added early (`/chat/` home, session page) so that redirects had targets.
- **2.5** Redirect tests for pages not yet built moved to 3.6 and 5.5.
- **3.3** `seed_demo` prompts for the password when `--password` is omitted. 3.5 (sidebar balance) skipped.
- **4b** Test bug exposed the real keys in a transcript. Fixed in the tests; keys must be reissued; **4b.10 on hold**.
- **6 / 7 / 11 / 12.3** Browser-level checks used a local fake proxy, not the real one.
- **7.6** Per-message cost line skipped (stretch).
- **8–10** Django flash messages added to the layout. Delete links are also on sidebar items. Renaming doesn't reorder.
- **11** Messages stay in `ProviderError.DEFAULT_MESSAGES` (not duplicated in the view). The debug-page key leak with DEBUG on was fixed (`sensitive_variables()` + `AlwaysSafeExceptionReporterFilter`).
- **12** QA finding (membership re-check) fixed.
- **12.6** Merged with the real-proxy part of 12.3 still pending, at the user's explicit approval.
- **13.6** Docs were committed on the branch before the merge.

---

## 14. Out of scope for the MVP

Keep these out **unless Phases 0–13 are done and substantial time remains**:

- Google login
- Sign-up
- Memories
- Global system prompt
- SimGen, Ask, Default App
- Web search, research mode, image generation (the proxy doesn't support them)
- Tools and multi-turn tool loops
- Streaming
- A large model catalog (only the 3 proxy models)
- Pixel-perfect UI recreation, including the Cards/Compact toggle, favorites and sorting
- File uploads, thinking effort, changing the model or account mid-session, payments/top-up UI, context trimming, deployment

If time remains, the order to consider is: streaming → global system prompt → per-message cost display. Each one would need a short plan addendum before starting.

---

## 15. Time budget and cut line

| Phase | Estimate |
|---|---|
| 0 Docs commit + branch | 5 min |
| 1 Setup | 20 min |
| 2 Auth | 20 min |
| 3 Billing | 30 min |
| 4 + 4b Catalog + adapters | 50 min |
| 5 New conversation | 30 min |
| 6 + 7 Chat + metering | 60 min |
| 8–10 History, rename, delete | 30 min |
| 11 Errors | 15 min |
| 12 Verification + merge | 25 min |
| 13 Docs | 20 min |
| **Total** | **≈ 5 h** |

**Cut line if behind schedule**, applied in this order:
1. Skip 3.5 (sidebar balance) and the optional part of 7.6 (per-message cost).
2. Fold `UsageCharge` into `Message` (D6 fallback). Deletion then removes charge history, and that must be documented.
3. Use a simpler rename UI (a separate small form page).
4. Reduce tests to adapters (4b.9), metering (7.7) and ownership/auth. Everything else is verified manually in 12.3.

**Never cut:** metering, the insufficient-credit block, key safety, the manual end-to-end check, or the merge-only-if-working rule.

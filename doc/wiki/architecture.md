# Architecture

A Django 5.2 project (`litechat`) with three apps. Pages are server-rendered. The only JavaScript is `static/js/chat.js`, which scrolls the chat and shows "Thinking…" while a reply is pending. The database is SQLite.

## Apps

| App | Responsibility | Key files |
|---|---|---|
| `billing` | Billing accounts and credit, pricing and charging replies, sign-up and profile pages, demo seeding | `models.py`, `services.py`, `views.py`, `management/commands/seed_demo.py`, `templatetags/money.py` |
| `llm` | The model catalog, and adapters that talk to the BUILD LLM Proxy's three provider interfaces | `models.py`, `migrations/0002_seed_models.py`, `providers.py` |
| `chat` | Chat sessions and messages, sending a message, the session sidebar, rename and delete | `models.py`, `services.py`, `views.py`, `forms.py`, `context_processors.py` |
| `litechat` | Settings, URLs, and the exception-report filter that hides secrets | `settings.py`, `urls.py`, `debug.py` |

## Data model

```
User (django.contrib.auth)
  │ M2M members
  ▼
BillingAccount ── name, kind (personal/shared), status (active/suspended), credit (Decimal, 6 dp)
  ▲ PROTECT                                  ▲ PROTECT
  │                                          │
ChatSession ── user, billing_account, llm_model, name ("Untitled session"), created_at, updated_at
  │ CASCADE                                  │ PROTECT
  ▼                                          ▼
Message ── role (user/assistant), content,   LLMModel ── provider, api_model, display_name,
           status (complete/truncated),                   description, tier, input/output price
           input/output tokens, cost                      per 1M tokens, is_active, sort_order
  ▲ SET_NULL (1:1)
  │
UsageCharge ── billing_account, message, session_label (snapshot), llm_model, tokens, cost, created_at
```

- A session's billing account and model are **fixed when it's created**.
- The sidebar is ordered by `updated_at`, which only a successful send changes. Renaming doesn't.
- Deleting a session deletes its messages. Each `UsageCharge` keeps its `session_label`, and its `message` link becomes `NULL`, so billing history survives.

## Sending a message

`POST /chat/<id>/send/` → `chat.views.send_message` → `chat.services.send_message`:

1. **Ownership:** the session must belong to the user (404 otherwise).
2. **Membership:** the user must still be a member of the session's billing account (403 otherwise). This is checked in the view.
3. **Validation:** the text can't be blank and can be at most 8,000 characters.
4. **Credit check** (`billing.services.ensure_can_spend`): the account, re-read from the DB, must be active with credit > 0. Otherwise the request is refused **before** any proxy call.
5. **Proxy call** (`llm.providers.complete`): the full stored history plus the new message goes to the session model's provider interface. No retries.
6. **Save and charge, in one `transaction.atomic()`:**
   1. create the user message
   2. create the assistant message
   3. `billing.services.record_charge`: lock the account row, then `credit = F('credit') - cost`, set `Message.cost`, and create the `UsageCharge`
   4. bump `session.updated_at`

   If any step fails, everything rolls back.
7. Redirect back to the session (POST-redirect-GET).

If a step fails before step 6, nothing is saved or charged. The page is re-rendered with a friendly error and the user's draft.

## Provider adapters (`llm/providers.py`)

`complete(llm_model, turns, system_prompt=None) -> CompletionResult(text, status, input_tokens, output_tokens)`

| Provider | Endpoint (under `LITECHAT_PROXY_BASE_URL`) | Auth header | Key env var |
|---|---|---|---|
| `openai` | `/openai/v1/chat/completions` | `Authorization: Bearer …` | `BUILD_OPENAI_KEY` |
| `anthropic` | `/anthropic/v1/messages` (+ `anthropic-version: 2023-06-01`) | `x-api-key` | `BUILD_ANTHROPIC_KEY` |
| `google` | `/google/v1beta/models/<model>:generateContent` | `x-goog-api-key` | `BUILD_GOOGLE_KEY` |

Each adapter has a request builder and a response parser:
- The builder maps roles (Gemini uses `model` for the assistant), puts the system prompt where that provider expects it, sets `max_tokens` (`LITECHAT_MAX_OUTPUT_TOKENS` = 1024), and disables reasoning.
- The parser reads the text, the finish reason (`length`, `max_tokens` or `MAX_TOKENS` → `truncated`) and the token counts.

Failures raise `ProviderError(kind)`:

| Cause | Kind | Message shown to the user |
|---|---|---|
| 401/403, or a missing key (no request is made) | `auth` | The AI service rejected our credentials. Please contact the administrator. |
| 429 | `rate_limited` | The AI service is busy. Please try again in a moment. |
| Other 4xx, unknown provider | `bad_request` | The request could not be processed. |
| 5xx, connection error | `upstream` | The AI service is unavailable right now. |
| Timeout (`LITECHAT_PROXY_TIMEOUT` = 120 s) | `timeout` | The AI service took too long to respond. Please try again. |
| Unexpected response shape | `bad_response` | The AI service is unavailable right now. |

## Secrets

- Keys are read from `os.environ` (loaded from `.env` by `python-dotenv`) only when a call is made.
- Logs record only the provider, the failure kind and the HTTP status.
- `complete()` is decorated with `@sensitive_variables()`, and `litechat.debug.AlwaysSafeExceptionReporterFilter` applies that masking **even with `DEBUG=True`** (Django's default only masks when DEBUG is off). So debug pages and error reports never show a key.

## Routes

| URL | Method | View | Notes |
|---|---|---|---|
| `/` | GET | redirect | → `/chat/` |
| `/login/`, `/logout/` | GET/POST, POST | Django `LoginView` / `LogoutView` | Logged-in users visiting `/login/` go to `/chat/`. Logout is POST only. |
| `/signup/` | GET/POST | `billing.views.signup` | Public. Django's `UserCreationForm`. In one transaction it creates the user and `ensure_personal_account(user, LITECHAT_SIGNUP_CREDIT)`, then logs in → `/chat/`. Logged-in users go to `/chat/`. |
| `/chat/` | GET | `chat.views.home` | "Start a New Conversation" empty state |
| `/chat/new/` | GET/POST | `chat.views.new_session` | Picker: the user's active billing accounts and the active models, grouped by provider |
| `/chat/<id>/` | GET | `chat.views.session_detail` | History and message form (owner only) |
| `/chat/<id>/send/` | POST | `chat.views.send_message` | See "Sending a message" |
| `/chat/<id>/rename/` | POST | `chat.views.rename_session` | Trimmed, cut to 100 chars, blank rejected |
| `/chat/<id>/delete/` | GET/POST | `chat.views.delete_session` | Confirmation page, then delete → `/chat/` |
| `/profile/` | GET | `billing.views.profile` | User info, billing accounts and available credit |
| `/admin/` | – | Django admin | Accounts (credit top-ups), usage charges (read-only), models |

Every page except login and sign-up requires login. Sessions are always looked up with `user=request.user`, so other users' sessions return 404.

The sidebar session list comes from the `chat.context_processors.sidebar_sessions` context processor.

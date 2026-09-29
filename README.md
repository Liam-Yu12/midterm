# LiteChat MVP

A replication of the core of [LiteChat](https://litechat.ai) for the ITENT 45 midterm: **metered, à la carte access to LLMs from several providers.** Users log in and start a conversation by picking a billing account and a model (OpenAI, Anthropic or Google). They chat through the course's BUILD LLM Proxy, and each reply's token usage is priced and deducted from their dollar credit.

- **Stack:** Python 3.13, Django 5.2, SQLite, server-rendered templates with a little vanilla JS, `requests` for the proxy calls.
- **Scope:** the study explains why these features count as "core", and the plan lists what was built and in what order:
  - [doc/study/litechat-core-functionality.md](doc/study/litechat-core-functionality.md)
  - [doc/plan/litechat-mvp.md](doc/plan/litechat-mvp.md)
- **How it works:** [doc/wiki/](doc/wiki/README.md) (architecture, billing and models).

## What it does

- Username/password login and logout. Every app page requires login.
- Billing accounts with dollar credit, shown on **My Profile**. Admins top up credit in the Django admin.
- **New conversation:** choose a billing account and one of three models, grouped by provider, with tier and price.
- Chat with the full history sent on every turn. Replies cut off by the token limit are marked.
- **Metering:**
  - Credit is checked before each request.
  - Each successful reply is charged (tokens × model price), and the reply, the charge record and the deduction are saved in one transaction.
  - Failed requests are never charged.
- A sidebar of sessions (most recently used first) with rename and delete. Deleting a session keeps its billing records.
- Friendly errors for proxy failures (401/403, 429, 400, 5xx, timeout, connection). The draft is kept, and no key or upstream detail is shown.

Deliberately **not** included in the MVP (see plan §14): Google login, sign-up, memories, global system prompt, streaming, tools, file uploads, web search, SimGen, and a large model catalog.

## Prerequisites

- Python **3.10+** (developed on 3.13.5)
- The three BUILD LLM Proxy keys issued for the course (OpenAI, Anthropic, Google). They're only needed to chat for real. The tests don't use them.

## Setup

```bash
git clone https://github.com/Liam-Yu12/midterm.git
cd midterm

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment (`.env`)

Copy the template and fill it in. **`.env` is git-ignored. Never commit it.**

```bash
cp .env.example .env
```

| Variable | Value |
|---|---|
| `BUILD_OPENAI_KEY` | Your proxy key for the OpenAI interface |
| `BUILD_ANTHROPIC_KEY` | Your proxy key for the Anthropic interface |
| `BUILD_GOOGLE_KEY` | Your proxy key for the Google Gemini interface |
| `DJANGO_SECRET_KEY` | A random secret. Generate one with `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"` |
| `DJANGO_DEBUG` | `True` for local development |

The keys are only read on the server, when a request is made. They never reach the browser, logs, or error pages.

### Database

```bash
python manage.py migrate
```

This creates `db.sqlite3` (git-ignored) and seeds the three models the proxy supports: GPT-5.6 Luna, Claude Haiku 4.5 and Gemini 3.8 Flash.

Next, create a demo user. They get an active **[Personal]** billing account with **$2.00** credit. Leave out `--password` to be prompted for it, which keeps it out of your shell history:

```bash
python manage.py seed_demo --username demo
# options: --password P   --credit 5.00   (re-running resets the credit and reactivates the account)
```

Optionally, create an admin to view charges and top up credit:

```bash
python manage.py createsuperuser
```

## Run

```bash
python manage.py runserver
```

- App: <http://127.0.0.1:8000/>. Log in with the demo user.
- Admin: <http://127.0.0.1:8000/admin/>. Billing accounts (edit `credit` to top up), usage charges (read-only), and the model catalog.

Replies aren't streamed. The proxy can take up to about 30 s, and the send button shows "Thinking…" while you wait.

## Tests

```bash
python manage.py test
```

- 158 tests covering the settings, auth, billing and metering, the model catalog, the provider adapters, chat, sessions, and error handling.
- **The proxy is always mocked.** No test makes a network call or needs real keys, and the adapter tests replace any keys with dummies.
- Useful checks before committing:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Status: live proxy checks on hold

Everything above has been verified locally. Verification used the automated suite, a clean-clone setup, and a scripted walkthrough against a local stand-in for the proxy.

**Checks against the real proxy are on hold** (plan steps **4b.10** and **12.3**). The originally issued keys were exposed in a coding-session transcript and must be reissued before any live call. Once new keys are in `.env`, the remaining check is one real conversation per provider, confirming that the balance goes down by the recorded charges.

## Project layout

```
litechat/   settings, URLs, error-report filter (keys hidden from debug pages)
billing/    BillingAccount, UsageCharge, metering services, profile page, seed_demo
llm/        LLMModel catalog (+ seed migration) and the proxy adapters (llm/providers.py)
chat/       ChatSession, Message, the chat/session views and send service
templates/  app layout, login, chat pages, profile
static/     app.css, chat.js
doc/        study, plan, wiki
```

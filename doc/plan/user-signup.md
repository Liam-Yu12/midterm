# Plan: User Sign-up

- **Based on:** [doc/study/user-signup.md](../study/user-signup.md)
- **Date:** 2026-09-29
- **Goal:** anyone evaluating the app, such as the instructor, can create an account in the browser and start chatting with $2.00 credit, with no terminal command.
- **Out of scope:** Google login, email/verification, password reset, CAPTCHA and rate limiting (study §5).
- **Status:** not started. Waiting for approval to execute.

## Decisions

| # | Decision |
|---|---|
| S1 | Username/password sign-up at `/signup/`, using Django's `UserCreationForm` and the existing password validators. No Google login. |
| S2 | On success: user + active **[Personal]** billing account in one transaction, then log in and redirect to `/chat/`. |
| S3 | Starting credit comes from the new setting `LITECHAT_SIGNUP_CREDIT` (default `Decimal('2.00')`; `0` disables free credit). |
| S4 | Account creation is shared: `billing.services.ensure_personal_account(user, credit)` is used by `seed_demo` and sign-up. |
| S5 | Work happens on branch `feat/signup` from `main`, with conventional commits, merged with `--no-ff` after verification. |

## Checklist

### 0. Branch
- [x] 0.1 Commit the study and this plan on `main`: `docs: add user sign-up study and plan`.
- [ ] 0.2 Create `feat/signup` from `main`.

### 1. Shared account creation (refactor)
*Depends on: 0.*
- [ ] 1.1 `billing/services.py` `ensure_personal_account(user, credit)`:
  - Get the user's personal account, or create it (name = full name or username, in capitals).
  - Set it active with `credit`, add the user as a member, and return `(account, created)`.
- [ ] 1.2 `seed_demo` uses it. Its behaviour and output are unchanged.
- [ ] 1.3 Tests: `billing/tests/test_metering.py` or a new `test_accounts.py` covers create, update/reactivate and naming. **The existing `seed_demo` tests pass unchanged.**
- [ ] 1.4 Commit: `refactor: share personal account creation between seed_demo and sign-up`.

### 2. Sign-up page
*Depends on: 1.*
- [ ] 2.1 `litechat/settings.py`: `LITECHAT_SIGNUP_CREDIT = Decimal('2.00')`.
- [ ] 2.2 `billing/views.py` `signup` (or a small `accounts`-style view in `billing`, which owns user-facing account pages):
  - GET renders the form. A logged-in user is redirected to `/chat/`.
  - A valid POST, inside `transaction.atomic()`: save the user, then `ensure_personal_account(user, settings.LITECHAT_SIGNUP_CREDIT)`. Then `login()` and redirect to `/chat/`.
- [ ] 2.3 URL `/signup/` (name `signup`) in `litechat/urls.py`, next to login/logout.
- [ ] 2.4 `templates/registration/signup.html`:
  - The login card style, a "Create your account" heading, username / password / confirm fields, and field errors plus Django's help text (e.g. "no spaces").
  - A "CREATE ACCOUNT" button and a "Have an account? Log in" link.
- [ ] 2.5 `templates/registration/login.html`: add "Don't have an account? Create one" → `/signup/`.
- [ ] 2.6 Tests in `billing/tests/test_signup.py`:
  - GET renders. The login page links to sign-up.
  - A valid sign-up creates the user and a `[Personal] USERNAME` active account with $2.00. The user is logged in and redirected to `/chat/`, and `/profile/` shows $2.00.
  - The new user can start a conversation (the picker lists their account).
  - Duplicate username, password mismatch, a weak/common/short password, and a username with a space are each rejected with an error. **No user or account is created.**
  - A logged-in user visiting `/signup/` is redirected to `/chat/`.
  - `LITECHAT_SIGNUP_CREDIT=0` → the account is created with $0.00, and sending is blocked with the insufficient-credit message.
  - Atomicity: if account creation fails, no user is left behind.
- [ ] 2.7 Commit: `feat: add self-service sign-up with a personal billing account`.

### 3. Verification (rendezvous)
*Depends on: 2.*
- [ ] 3.1 Full suite passes (placeholder keys, network blocked). `check` and `makemigrations --check` are clean.
- [ ] 3.2 Manual check on `runserver` (local fake proxy, no real keys):
  - `/login/` → "Create one" → sign up → land on `/chat/`.
  - Profile shows `[Personal] … $2.00`.
  - New conversation → a message gets a reply → the balance goes down.
  - Log out, then log in with the new credentials.
- [ ] 3.3 Secret scan of the changed files and history. Review the diff.
- [ ] 3.4 Merge `feat/signup` into `main` (`--no-ff`). The full suite passes on `main`.

### 4. Sync docs
*Depends on: 3.*
- [ ] 4.1 `README.md`:
  - "Create an account at `/signup/`" is the primary way in; `seed_demo` becomes an alternative.
  - Document `LITECHAT_SIGNUP_CREDIT` and the local-only abuse note.
  - Remove sign-up from the "not included" list.
- [ ] 4.2 `doc/wiki/architecture.md`: the `/signup/` route and flow. `doc/wiki/billing-and-models.md`: accounts are created on sign-up with the starting credit.
- [ ] 4.3 Tick this plan, record any deviations, and commit: `docs: document user sign-up`.

## Time estimate
About 45–60 minutes in total.

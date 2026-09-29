# Study: User Sign-up

- **Status:** complete. The decision was confirmed by the student on 2026-09-29.
- **Date:** 2026-09-29
- **Related:** [litechat-core-functionality.md](litechat-core-functionality.md) (§3.1, §6.1, constraint C6), [plan/litechat-mvp.md](../plan/litechat-mvp.md) (stretch item "self sign-up", §9.2 #5 of the study)
- **Nature:** analysis only. The implementation checklist is in [plan/user-signup.md](../plan/user-signup.md).

## 1. The problem

The merged MVP has no way to create an account from the app. Accounts come only from `python manage.py seed_demo` or the Django admin. Someone who clones the repo to evaluate it, such as **the instructor**, must run a terminal command before they can log in. [OBS: README "Database" section]

Grading is on "how well you can convince me" [BRIEF], so the person grading should be able to **create an account and start chatting from the browser** right after setup.

## 2. What LiteChat does

- LiteChat's login page has **no sign-up link**, only username/password and "Login with Google". [SS]
- The student's LiteChat account had a UUID username and was "member since" the same day. This suggests **accounts are created automatically on first Google login**, each with a **[Personal] billing account** ($2.00 in the student's case). [SS][INF]

So LiteChat does let new users in from the browser, through Google. Our replication needs *some* browser-based way in. Its exact mechanism doesn't have to match. [INF]

## 3. Constraints

| # | Constraint | Source |
|---|---|---|
| C6 | Any reasonable login approach is acceptable. Google login is not required. | Instructor, via the study |
| C8 | No credentials in the repo, docs, history or client code. | CLAUDE.md |
| — | Must work on a fresh clone with **no extra external setup**. | This request (the instructor evaluating locally) |
| — | Student decision: **sign-up only, no Google login.** | Student, 2026-09-29 |

## 4. Options

| Option | Works right after cloning? | Setup and secrets | Matches LiteChat | Effort |
|---|---|---|---|---|
| A. Keep seed/admin only (current) | Needs a terminal command | none | Partly | 0 |
| **B. Username/password sign-up page** | **Yes** | **none** | Same outcome: new user + personal account | ~30–45 min |
| C. Google OAuth (e.g. `django-allauth`) | **No.** Every machine needs a Google Cloud OAuth client and its secret in `.env` | A client secret must not be committed, so the instructor would have to create one or be sent one | Closest in mechanism | 1.5–2 h + external setup |

**Decision: B.** C is rejected for this project: it can't work out of the box without sharing a secret, and the student chose sign-up only.

## 5. Proposed design (option B)

**Route:** `/signup/` (GET form, POST create). It's public, and logged-in users are redirected to `/chat/`, as `/login/` already does.

**Form:** Django's built-in `UserCreationForm`:
- username, password, and password confirmation
- Django's username rules (letters, digits and `@ . + - _`; **no spaces**)
- the four password validators already enabled in settings: similarity, minimum length 8, common, numeric
- a clear error for a duplicate username

**On success:**
1. Create the user.
2. Create an active **[Personal]** billing account for them, named after the username in capitals, with the **starting credit**.
3. **Log them in** and redirect to `/chat/`.

Steps 1–2 run in one transaction, so there's never a user without an account.

**Starting credit:** a new setting `LITECHAT_SIGNUP_CREDIT`, default **$2.00**. That's LiteChat's observed starting balance [SS] and the same as `seed_demo`.

**Shared logic:** move "create or update a personal account" out of `seed_demo` into `billing.services.ensure_personal_account(user, credit)`, used by both `seed_demo` and sign-up. This avoids two copies of the account-creation rules.

**UI:**
- The login page gets "Don't have an account? **Create one**".
- The sign-up page uses the same card style as login: a "Create your account" heading and a "Have an account? Log in" link.

**Not included:** email, email verification, password reset, display-name fields, CAPTCHA and rate limiting. None of these are needed for a local demo.

## 6. Risks and tradeoffs

| Risk | Impact | Mitigation |
|---|---|---|
| Anyone who can reach the server can sign up and get $2.00 of credit, spent on the course proxy keys | Proxy usage by strangers | The app runs locally only (study A1; no deployment). `LITECHAT_SIGNUP_CREDIT` can be set to `0`, so new users must be topped up by an admin. Documented in the README. |
| Weak passwords | Account takeover on a shared machine | Django's password validators are already enabled |
| Refactoring `seed_demo` breaks it | Setup instructions fail | The existing `seed_demo` tests must keep passing unchanged |
| Username confusion (spaces, as happened with "liam yu") | Failed sign-up | Show Django's username help text and field errors |

## 7. Evidence and uncertainty

- **Observed:** LiteChat has no sign-up link, and new (Google) users get a personal account. [SS]
- **Inferred:** automatic account creation on first Google login. It doesn't change the design.
- **Unknown:** LiteChat's actual starting credit policy for every new user ($2.00 was seen for one account). We use $2.00 and make it configurable.

## 8. Recommendation

Implement **option B** on a feature branch, following [plan/user-signup.md](../plan/user-signup.md). Then update the README (setup and the "create an account" path) and the wiki (routes, accounts).

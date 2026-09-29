# Billing and models

## Model catalog

The course proxy (BUILD LLM Proxy) accepts **exactly three model IDs**. Any other ID returns `400 unknown model`, so the catalog, seeded by `llm/migrations/0002_seed_models.py`, contains only these:

| Model | Provider interface | Proxy model ID | Tier | Input $/1M tokens | Output $/1M tokens |
|---|---|---|---|---|---|
| GPT-5.6 Luna | OpenAI | `gpt-5.6-luna` | Value | 0.40 | 1.60 |
| Claude Haiku 4.5 | Anthropic | `claude-haiku-4-5-20251001` | Value | 1.00 | 5.00 |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | Value | 0.30 | 2.50 |

- **The prices are ours**, not LiteChat's; LiteChat shows no prices in its picker. They're set so that $2.00 of credit covers many messages, and they differ per model so that metering is visible. Change them in the admin (**LLM models**).
- The tier follows LiteChat's label for Luna and Haiku 4.5, both "Value". Gemini's tier wasn't visible in LiteChat, so it's also set to Value.
- `is_active=False` hides a model from the new-conversation picker.

### Proxy caveats (from the study)

- **All three interfaces are served by DeepSeek Flash** behind provider-shaped APIs. Choosing a model changes the price and the API format, not the answer quality.
- The proxy appears to add **about 175 hidden prompt tokens to every request**. A ~10-token prompt was counted as 182–187. We charge for the tokens the proxy reports, so every reply has a small fixed cost.
- **Latency is 1–36 s.** Replies aren't streamed, and the server waits up to 120 s.
- The proxy stores no conversation state. The app sends the full history on every turn.

## Cost formula

```
cost = input_tokens × input_price / 1,000,000  +  output_tokens × output_price / 1,000,000
```

This is computed with `Decimal` and rounded half-up to 6 decimal places (`billing.services.calculate_cost`). For example, a Luna reply with 187 input and 9 output tokens costs 0.0000748 + 0.0000144 = **$0.000089**.

Credit and costs are stored to 6 decimal places. The UI shows credit rounded to cents, so a balance of $1.999439 displays as **$2.00**.

## Charging policy

1. **Before** calling the proxy, the session's billing account must be **active** with **credit > 0**, and the user must still be a **member** of it. Otherwise the send is refused, the proxy is not called, and the draft is kept:
   - "Insufficient credit in [Personal] NAME. Ask an administrator to top up."
   - "This billing account is not active."
   - 403 "You are no longer a member of …"
2. **After** a successful reply, the actual cost is charged. The charge, both messages and the deduction are saved in one transaction.
3. **Truncated** replies (token limit reached) are charged, because their tokens were used.
4. **Failed** requests (any proxy error, timeout or connection failure) are **not charged** and nothing is saved.
5. **Final overdraft:** credit is only checked for > 0 before the call, so the last reply can take the balance slightly negative, e.g. $0.00005 → −$0.000039. The next send is then blocked. This is a deliberate, documented choice (plan decision D4).

Each charge is recorded as a `UsageCharge` row with the account, model, token counts, cost, the reply it paid for, and a `session_label` (for example `#9 Trip planning`, as it was when charged). Charges are **read-only** in the admin and survive session deletion.

## Accounts and top-ups

- **Sign-up** (`/signup/`) gives every new user an active **[Personal]** account (named after the username, in capitals) holding `LITECHAT_SIGNUP_CREDIT` (settings; default **$2.00**, and `0` means admins must top up first).
- `python manage.py seed_demo --username U [--password P] [--credit 2.00]` creates or updates a user with an active **[Personal]** account. Re-running it resets the credit and reactivates the account.
- Both use `billing.services.ensure_personal_account(user, credit)`, which creates the personal account if missing, or reactivates it and resets its credit.
- **Top-ups:** in the admin, go to **Billing accounts** → an account → edit **Credit**. There is no payment flow.
- **Shared accounts:** set **Kind** to Shared and add several **Members**. Every member can start sessions on it, and they all draw from one balance.
- **Suspending:** set **Status** to Suspended. The account disappears from the picker, and existing sessions on it can't send.

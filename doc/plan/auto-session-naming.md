# Plan: Automatic session naming and rename control

- **Date:** 2026-09-29
- **Request:** the student's spec (2026-09-29). It's a small follow-up to the merged MVP, so there's no separate study. The findings are recorded here.
- **Branch:** `feat/auto-session-naming`. **Do not merge or push until approved.**

## Findings (before changes)

- **Naming:** `ChatSession.name` defaults to "Untitled session" and changes only through `chat.views.rename_session`. Nothing records whether a name was chosen by the user.
- **Sending:** `chat.services.send_message` saves both messages, the charge and the `updated_at` bump in one transaction, and only after the provider call succeeds. A failed send saves nothing. **This transaction is the smallest clean place for automatic naming.** Failures can never rename the session, and the name change is atomic with the first exchange.
- **Header:** ✎ (a `<details>` element) and 🗑 sit next to each other when closed. When rename is **open**, the inline form appears *between* them: ✎ jumps up and 🗑 is pushed away (screenshot taken before the change).

## Decisions

| # | Decision |
|---|---|
| N1 | The name is derived **locally** from the first message (`chat/naming.py`). No extra proxy call. |
| N2 | Auto-name only when **all** hold: (a) the session had no stored messages before this exchange, (b) `name_set_by_user` is false, (c) the name is still the default. |
| N3 | New field `ChatSession.name_set_by_user` (default False), set by the rename view. Existing sessions: false. (c) still protects any existing non-default names. |
| N4 | Heuristic: first sentence → strip a leading filler phrase ("what are some", "help me", "can you", …) → drop low-information words (a, an, the, my, some, good, …) → at most 6 words, with no dangling "to/for/and/…" → at most 60 characters. Capitalise only if a prefix was stripped (so "hello" stays "hello"). Fall back to the raw first words, then to "Untitled session". |
| N5 | ✎ and 🗑 go in one `.session-actions` group. The rename form becomes a dropdown under ✎ (same `<details>`, same form and view). The sidebar is unchanged (🗑 on hover only). |

## Checklist

- [ ] 1. `chat/naming.py` `suggest_session_name(text)`, plus unit tests (the spec's examples, whitespace, long input, fallbacks).
- [ ] 2. `ChatSession.name_set_by_user` + migration `chat/0002`.
- [ ] 3. `send_message`: auto-name inside the success transaction (N2).
- [ ] 4. `rename_session`: set `name_set_by_user=True` on a successful rename. Blank rejection and the 100-char cap are unchanged.
- [ ] 5. Header: the `.session-actions` group and the dropdown rename form (CSS).
- [ ] 6. Tests:
  - New sessions are "Untitled session".
  - The first successful message names the session.
  - Later messages don't rename.
  - A failed first message doesn't rename.
  - A manual rename is never overwritten.
  - A long first message gives a short, valid name.
  - Rename still works, and a blank rename is still rejected.
  - ✎ and 🗑 are adjacent.
- [ ] 7. Full suite, plus a browser check of the header (closed and open) and of naming.
- [ ] 8. Commit: `feat: add automatic chat naming and rename control`.
- [ ] 9. After approval and merge: sync `doc/wiki/architecture.md` (naming rule, new field).

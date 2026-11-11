# Decisions

Back to the [README](../README.md).

Agreed by Brahim and Sarah on November 10, 2026, unless another date is given. They replace the original plan in [PRD.md](../PRD.md) where it differed; the code in `main` follows them.

| Topic | Decision | Why |
| --- | --- | --- |
| What an issue is linked to | One or more clients, or **All clients** (including clients added later); optionally the milestone it delays, which also links that milestone's client | One issue often affects several clients; no duplicates. The milestone shows *what* the issue holds back; blocking still goes through the client |
| Readiness states | Not Ready, At Risk, In Progress, Ready, always with a reason in plain words | More useful than Ready / Not Ready alone |
| Incomplete milestone | In Progress; a late milestone makes the client At Risk; only a Blocked milestone makes it Not Ready | Unfinished work is not a crisis |
| Critical issue with no link | Fail-safe: it blocks every client until triaged; Medium and Low issues never block ([triage rules](triage-rules.md)) | A Critical issue must never drop out of readiness because it is not linked yet |
| Triage deadline | Same business day; weekends and holidays skipped, in the agency's time zone ([triage rules](triage-rules.md#overdue-for-triage)) | Keeps false blocks short without flagging issues over a weekend |
| Frontend layout | One page with two tabs | Simpler navigation, no duplicated UI |
| Data access | Built-in `sqlite3`, no SQLAlchemy | Enough for this scope, no extra dependency |
| Interface language (November 11, 2026) | English everywhere: interface, stored values, demo data and Claude's answers. Older French databases are converted on startup. Code comments, test names and [PRD.md](../PRD.md) stay in French, as they were written before the switch | The Showcase audience reads English |

The original plan linked issues to milestones and had two readiness states only; the team replaced it with the rules above on November 10, 2026.

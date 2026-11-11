# Testing

Back to the [README](../README.md).

Run the automated tests with `python -m pytest` (34 tests). Each test uses a temporary database, never `data/careops.db`. Test names are in French because they were written before the interface switched to English.

## Presentation demo

Sarah proposed a demo that shows both workspaces working together. Click **Reset demo** first. The demo data then starts in three different states, one per client:

- **Horizon Home Care: Not Ready.** The reason names the issue and the milestone it delays (EVV export, milestone “State EVV test”).
- **CareFirst Brooklyn: At Risk.** One milestone is late.
- **Queens Wellness Care: Ready.** The walkthrough below starts here.

| Step | Who and where | Action | Expected result |
| --- | --- | --- | --- |
| 1 | Sarah, Implementation | Add the milestone “Final go-live check” to Queens Wellness Care, due in the coming days | Queens: **In Progress** (1 milestone left) |
| 2 | Brahim, Product | Create a Critical issue “Duplicate clock-ins in the caregiver portal”, feature Caregiver Portal, and choose that milestone under **Milestone it delays** | Queens Wellness Care is linked automatically |
| 3 | Sarah, Implementation | Look at Queens | **Not Ready**, and the reason names the issue and the milestone |
| 4 | Brahim, Product | Set the issue to **Resolved** | Queens: **In Progress** (the milestone is still open) |
| 5 | Sarah, Implementation | Set the milestone to **Done** | Queens: **Ready** |
| 6 | Both | Refresh the page | Everything is still there |

`test_demo_de_presentation` in `tests/test_tickets.py` runs the same steps against the API.

## End-to-end test plan

Brahim and Sarah run this workflow with a fictional client. Pass criterion: it runs without changing readiness by hand, without data loss, and without affecting implementations that a linked issue does not touch.

| # | Step | Expected result | Run 2026-11-05 |
| --- | --- | --- | --- |
| 1 | Sarah creates an implementation for a client and adds its required milestones | In Progress | ✅ |
| 2 | Sarah marks every required milestone Done | Ready (no blocker) | ✅ |
| 3 | Brahim creates an issue in the Product workspace: severity Critical, status Open, linked to the client | Saved | ✅ |
| 4 | Back in Sarah's workspace | Not Ready automatically, with the issue as the reason; other implementations unchanged | ✅ |
| 5 | Brahim moves the issue from Open to Resolved | Saved | ✅ |
| 6 | Readiness checked again | Ready again: all milestones Done, no unresolved Critical issue | ✅ |
| 7 | Edge case: Brahim creates a general Critical issue with no client | Shown as **To triage** and blocks **every** implementation until it is linked or resolved ([triage rules](triage-rules.md)) | ✅ |
| 8 | Both workspaces refreshed | All changes saved; readiness unchanged | ✅ |
| 9 | Invalid client link, and calls straight to the API without the interface | Unknown client rejected (400); invalid severity rejected (400); readiness cannot be forced, the backend always computes it | ✅ |

**Step 7, corrected.** The first version of this plan expected a general Critical issue to stay visible *without* blocking. That would let a client go live while a Critical issue waits for triage, which breaks the core promise. We kept the fail-safe rule: when the scope is unknown, the issue blocks everyone.

**Still to do:** rerun the plan with Sarah driving the Implementation workspace. The 2026-11-05 run was done by Brahim alone.

## Milestone link test (November 10, 2026)

An issue can point to the milestone it delays. Client A = Queens Wellness Care (all milestones Done), client B = CareFirst Brooklyn.

| # | Test | Result |
| --- | --- | --- |
| 1 | Open Critical issue linked to A's milestone “State EVV test” | A Not Ready, and the reason names the milestone; the issue is linked to A automatically ✅ |
| 2 | Client B | Unchanged (At Risk, for its own late milestone) ✅ |
| 3 | Issue resolved | A Ready again ✅ |
| 4 | Page refreshed | Issue, milestone link and readiness preserved ✅ |

Run in the browser and as automated tests (`test_probleme_lie_a_une_etape_plan_en_quatre_tests`). Deleting the milestone keeps the issue linked to the client, so the block does not disappear; an unknown milestone is rejected (400).

## Issue creation (November 4, 2026)

The **+ New issue** form sends `POST /api/issues`; the backend validates the fields (Pydantic) and stores the issue in SQLite.

| Step | Result |
| --- | --- |
| Create in the interface | `POST /api/issues` → `201 Created` |
| Stored in the database | Row present in `issues`, affected client in `issue_clients` |
| Displayed in the list | Shown exactly once |
| Page refresh | Still shown once, severity and status preserved |
| Server restart | Still present |

## Claude features (tested November 4, 2026)

Claude never changes data: a person reviews every suggestion. Outputs are plain text with dates written out, because they are shown in text boxes and copied into emails.

| Feature | Where | Result of the live test |
| --- | --- | --- |
| Severity suggestion | Product, new issue form | Weekend EVV export rejected with no workaround → **Critical**, with a one-sentence justification (valid JSON, 3.4 s) |
| Readiness summary | Implementation | 4 sentences matching the data: blocker, go-live risk, next action and owner |
| Client update email | Implementation | Starts with a subject line, honest about the go-live date, no internal jargon |

These tests were run in French; on November 11, 2026, one severity suggestion was checked again in English.

## Fresh-clone check (November 11, 2026)

The installation steps in the README were followed in an empty folder: the page and `/docs` load, the demo data appears, the tests pass, and without a key the Claude buttons answer “AI unavailable: ANTHROPIC_API_KEY is missing from .env.”

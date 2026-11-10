# CareOps Hub

CareOps Hub is a lightweight healthcare implementation management platform designed to connect technical issue tracking with implementation project progress.

Built as a two-week MVP for the Pursuit L2 Cycle 4 Capstone Project, CareOps Hub helps implementation teams identify blockers, track milestones, and assess deployment readiness through a shared system. The project is inspired by the "Project Manager, Client Implementations" role at HHAeXchange.

## Project Team

| Partner | Workspace |
| --- | --- |
| Sarah | Implementation Workspace |
| Brahim | Product Workspace |

## Problem Statement

Healthcare software implementation teams often manage implementation milestones and technical issues in separate systems. This can create communication gaps, delay decisions, and make it difficult to determine whether a deployment is truly ready.

CareOps Hub provides a shared view of:

- Product issues
- Implementation milestones
- Technical blockers
- Deployment readiness

By connecting these areas, teams can better understand how unresolved issues impact implementation progress.

## Business Case

**Value claimed:** no client goes live with an unresolved critical issue.

When milestones and bugs live in separate tools, the "ready / not ready" call is made by hand, and a critical bug can slip through to go-live. In home care, that means missed visits, rejected EVV exports and billing errors for the agency, and a costly rollback and loss of trust for the vendor.

**Where this value shows up in the product today:**

| Value | Where it shows up | How we know it works |
| --- | --- | --- |
| The go/no-go rule is automatic | `app/readiness.py` (`compute_readiness`): any open Critical issue linked to a client sets it to **Not Ready**, and an open Critical issue linked to no client yet blocks **every** client until it is triaged (see [Untriaged issues](#untriaged-issues-fail-safe)). Readiness is computed on every request and never stored, so it cannot go stale. | `tests/test_tickets.py`: creating a Critical issue makes the client Not Ready, and it survives a page refresh; an untriaged Critical issue makes every client Not Ready |
| Blockers are visible in one place | Readiness cards at the top of both workspaces show the status and the reason, e.g. *Horizon Soins à Domicile*: Not Ready, "1 open critical issue (EVV export rejected by the State aggregator)" | Seeded demo scenario |
| Product and Implementation share one view | When the Product workspace resolves an issue, the Implementation workspace's card updates on its own within 4 seconds | Manual end-to-end test in the browser |
| Faster client communication | Claude drafts the readiness summary and the client email from the same data; a person reviews before anything is sent | Tested live against the API on November 4, 2026 |

**Where the value is not proven yet:**

- **Speed is not measured.** The target "find what blocks a client in under 30 seconds" (see Success Metrics) has not been timed with real testers.
- **Severity scale is unvalidated.** With three levels (assumption A1), a serious issue with a costly workaround is either invisible in readiness (Medium) or wrongly blocks it (Critical).
- **One rule, agreed but not yet tested together.** On November 10, 2026, Brahim and Sarah agreed on the client-based rule in `main` (see [Decisions](#decisions)). Sarah's earlier branch `Implementation-Workplace` (old milestone-based model) was deleted on November 10, and her work now goes through `main`; the end-to-end test still has to be rerun with Sarah.

## Product Vision

CareOps Hub provides a single source of truth for:

- Product Managers tracking technical issues
- Implementation Project Managers tracking deployment progress

The platform surfaces blockers and calculates implementation readiness using deterministic business rules.

## User Stories

1. **Report an issue.** As a Product Manager, I want to log a technical issue with its severity, feature and affected clients, so that the implementation team immediately sees its impact.
   - Acceptance: Claude can suggest a severity; I confirm or change it before saving.
2. **Track resolution.** As a Product Manager, I want to update an issue's status (Open, In Progress, Resolved), so that the readiness of affected clients updates without manual work.
3. **Manage milestones.** As an Implementation Project Manager, I want to manage a client's milestones (due date, owner, status, blocker), so that I know what remains before go-live.
   - Acceptance: a milestone past its due date is flagged as late.
4. **Know if a client is ready.** As an Implementation Project Manager, I want to see each client's readiness with the reason behind it, so that we never deploy with an unresolved Critical issue.
5. **Communicate with the client.** As an Implementation Project Manager, I want Claude to draft a readiness summary and a client update email, so that I can inform the client quickly and honestly.
   - Acceptance: nothing is sent automatically; I review and edit before sending.

## MVP Features

### Product Workspace (Brahim)

- Create and manage product features
- Create and track technical issues
- Assign issue severity: Low, Medium, Critical
- Update issue status: Open, In Progress, Resolved
- Associate issues with features
- Link issues to the affected clients, to **All clients**, or leave them **To triage**
- Optionally link an issue to the milestone it delays (its client is linked automatically)

### Implementation Workspace (Sarah)

- View implementation project details
- Create and edit milestones
- Assign milestone owners
- Set milestone due dates
- Track milestone progress
- View linked technical issues
- Identify implementation blockers (a Blocked milestone must state its cause)
- Display implementation readiness

## Severity Levels and Statuses

The interface is in French; each value is shown below with its French label.

| Severity | French label | Definition | Effect on readiness |
| --- | --- | --- | --- |
| Critical | Critique | Blocks an essential function (visits, EVV, billing, compliance) with no workaround, or creates a regulatory risk | **Not Ready** until resolved |
| Medium | Moyenne | Real impact, but a workaround exists, even if costly | None |
| Low | Faible | Minor or cosmetic defect | None |

| Status | French label | Meaning | Counts as unresolved? |
| --- | --- | --- | --- |
| Open | Ouvert | Reported, nobody working on it yet | Yes |
| In Progress | En cours | Fix in progress | Yes |
| Resolved | Résolu | Fix delivered and verified | No |

Defaults: severity Medium, status Open. Any other value is rejected by the API (HTTP 400) and by the database (`CHECK` constraint). There is no "Closed" or "Rejected" status in the MVP: an issue created by mistake is deleted.

## Readiness Rules

**Not Ready** when an unresolved Critical issue affects the client, OR a milestone is Blocked. A milestone can only be set to Blocked with its cause written (enforced by the API, HTTP 400 otherwise), so the reason shown always says what to unblock. An unresolved Critical issue affects:

- the clients it is linked to (linking a milestone links its client, and the reason names the milestone);
- every client, when it is marked **All clients** or linked to no client yet (**To triage**, see [below](#untriaged-issues-fail-safe)).

An open Critical issue therefore always blocks at least one client. Medium and Low issues never block.

**Ready** only when no unresolved Critical issue affects the client, AND all milestones are Completed.

Otherwise the client is **At Risk** (a milestone is late) or **In Progress**. This rule is computed in `app/readiness.py` and proven by `tests/test_tickets.py`. The original plan linked issues to milestones and had two states only; the team replaced it on November 10, 2026 (see [Decisions](#decisions)).

### Untriaged issues (fail-safe)

A product teammate can log an issue before knowing which clients it affects (a general bug found in internal testing, for example). Leaving **Affected clients** empty saves it as **To triage** (À trier).

| Untriaged issue | Effect on readiness |
| --- | --- |
| Open **Critical** | **Every** client is Not Ready, with the reason "critical issue not triaged, to link to affected clients" |
| Medium, Low, or Resolved | No effect |

When in doubt, the rule blocks: an unknown scope never lets a client go live. Once the issue is linked to clients, only those clients stay blocked. The same applies if the last client of an open Critical issue is unlinked or deleted: the issue goes back to To triage and blocks everyone, so the blocker never disappears silently.

For an issue that affects everyone (a login outage, for example), tick **All clients** (Tous les clients) instead of each client one by one. The issue then counts for every client, including clients added later, and is shown as triaged.

The cost is a false block until triage, so the team agreed on a deadline (November 10, 2026): **a Critical issue is triaged within the same business day.** Triage means identifying the affected clients, not fixing the issue; only resolving a Critical issue removes its block, and relinking it never removes the block silently.

### Important Note

Readiness is an informational indicator only. The system does not authorize or automate healthcare software go-live decisions. Final deployment approval remains the responsibility of a human project manager.

## Assumptions and Validation

### A1: Three severity levels are enough

| | |
| --- | --- |
| **Assumption** | Technical issues can be classified into three severity levels: Low, Medium and Critical. |
| **Why we made it** | Three levels are enough to build and test the issue workflow. The decision that matters for deployment is binary: does the issue block go-live (Critical) or not? Fewer levels also means less hesitation when classifying an issue. |
| **Risk** | We have not validated that real healthcare implementation teams prioritize this way. A middle level may be missing, for example a serious issue with a costly workaround that should raise an alert without blocking. Without it, such an issue is either classified Medium and invisible in readiness, or Critical and wrongly blocks deployment. Escalation rules (who to notify, how fast) are not modeled either. |
| **How we will validate it** | 1. Ask 2 or 3 people working in healthcare implementation or support how they classify tickets and whether three levels are enough. 2. Have them classify our 6 demo issues and compare with our choices. 3. Note the issues they would want flagged without blocking deployment. 4. Compare with common support-tool levels (often four, P1 to P4). |
| **What would change** | If feedback shows that teams need different severity categories or escalation rules, we add a level (for example "High", which would mark a client At Risk) or an escalation rule, and update the PRD, database and tests. |
| **Status** | Not validated. Used for the MVP. |

## Technology Stack

| Layer | Choice | Status |
| --- | --- | --- |
| Frontend | HTML, CSS, JavaScript | Done |
| Backend | Python, FastAPI | Done |
| Database (local development) | SQLite | Done |
| Database (production) | PostgreSQL or SQLite | To decide with the Render deployment |
| Data access | Python's built-in `sqlite3` | Done; SQLAlchemy dropped (decided November 10, 2026) |
| AI | Anthropic API (Claude), server-side only | Done, tested against the live API (Nov 4, 2026) |
| Source control | GitHub | Done |
| Deployment | Render | Planned |

## Architecture

```
┌──────────────────────┐        ┌──────────────────────────┐
│  Product Workspace   │        │ Implementation Workspace │
└──────────┬───────────┘        └────────────┬─────────────┘
           │                                 │
           └───────────────┬─────────────────┘
                           ▼
                ┌──────────────────────┐
                │   FastAPI Backend    │──── Anthropic API (Claude)
                └──────────┬───────────┘
                           ▼
                ┌──────────────────────┐
                │ SQLite / PostgreSQL  │
                └──────────────────────┘
```

Both workspaces use the same backend and database to ensure data consistency.

## Project Structure

Current layout:

```
careops-hub/
├── app/
│   ├── main.py          # FastAPI routes (data, AI) and static frontend
│   ├── db.py            # SQLite schema, demo data, reads and writes
│   ├── models.py        # Field validation (Pydantic)
│   ├── readiness.py     # Deployment readiness rules
│   ├── business_days.py # Agency time zone, weekends and holidays
│   └── ai.py            # Claude calls (summary, severity, email)
├── public/              # index.html, styles.css, app.js (both workspaces as tabs)
├── data/seed.json       # Fictional demo data
├── tests/               # pytest
├── scripts/check-secrets.sh
├── .githooks/pre-commit
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── PRD.md               # Product requirements (French)
└── README.md
```

`.env` and the SQLite database (`data/careops.db`) exist only locally and are never committed.

## Installation

```bash
git clone https://github.com/BMbuild/CareOps-Hub.git
cd CareOps-Hub
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # then add your own API key
git config core.hooksPath .githooks
uvicorn app.main:app --reload
```

- Application: http://localhost:8000
- API documentation: http://localhost:8000/docs
- Tests: `python -m pytest` (each test uses a temporary database, never `data/careops.db`)

The database is created on first start with fictional demo data. The **Reset demo** button (Réinitialiser la démo) restores it.

## Environment Variables

Create a `.env` file in the project root from `.env.example`:

```
ANTHROPIC_API_KEY=your_api_key_here
# Optional: the agency's time zone for dates (default America/New_York)
CAREOPS_TZ=America/New_York
```

Without a key the application works normally; only the Claude buttons return an error. `CAREOPS_TZ` sets the time zone used for "today" and for issue creation dates, whatever the server's own time zone (Render runs in UTC). `DATABASE_URL` will be added when we move to PostgreSQL.

## Security

### Never commit secrets

- `.gitignore` excludes `.env`, `.env.*` (except `.env.example`), `secrets.json`, `credentials.json`, `*.pem`, `*.key` and all database files.
- A `pre-commit` hook ([scripts/check-secrets.sh](scripts/check-secrets.sh)) blocks any commit that contains a `.env` file or a known key format (Anthropic, Slack, GitHub, AWS, Google, private keys, secrets.pursuit.org links). Enable it once per clone with `git config core.hooksPath .githooks`.
- The API key stays on the server. The browser never calls the Anthropic API directly.
- Keys are never shared through Git, Slack or email: each partner creates their own `.env`.
- All data is fictional.

To check your clone: `git check-ignore -v .env` must print a line from `.gitignore`, and `sh scripts/check-secrets.sh` must pass.

### If an API key is accidentally committed

1. Revoke the exposed key immediately.
2. Generate a new key.
3. Remove it from Git history. Deleting it from the code is not enough, because it stays in the history.

## Component 1: Technical Issue Creation (Product Workspace)

The **+ New issue** form (+ Nouveau problème) sends `POST /api/issues` to the FastAPI backend, which validates the fields (Pydantic) and stores the issue in SQLite. The list is read back from the database.

**Success criterion:** an issue is created, stored, displayed, and retrieved after a page refresh, without duplication.

**Verification (November 4, 2026):**

| Step | Result |
| --- | --- |
| Create in the interface | `POST /api/issues` → `201 Created` |
| Stored in the database | Row present in `issues`, affected client in `issue_clients` |
| Displayed in the list | Shown exactly once |
| Page refresh | Still shown once, severity and status preserved |
| Server restart | Still present |

`tests/test_tickets.py` replays this scenario automatically.

## AI Features (tested November 4, 2026)

All three run server-side with `claude-opus-5-5`. Claude never changes data: a person reviews every suggestion.

| Feature | Where | Result of the live test |
| --- | --- | --- |
| Severity suggestion | Product, new issue form | Weekend EVV export rejected with no workaround → **Critical**, with a one-sentence justification (valid JSON, 3.4 s) |
| Readiness summary | Implementation | 4 sentences matching the data: blocker, go-live risk, next action and owner |
| Client update email | Implementation | Starts with a subject line, honest about the go-live date, no internal jargon |

Outputs are plain text (no Markdown) with dates written out in full, because they are shown in text areas and copied into emails.

## Core User Journey

1. Product Manager creates a Critical technical issue.
2. Issue is linked to the affected client (the plan said a milestone; see [Decisions](#decisions)).
3. Implementation Workspace displays the issue as a blocker.
4. Readiness becomes Not Ready.
5. Product Manager resolves the issue.
6. Remaining milestones are completed.
7. Readiness recalculates automatically.
8. Status changes to Ready.

## Acceptance Criteria

### Product Workspace

- Create features
- Create technical issues
- Update issue severity
- Update issue status
- Link issues to affected clients (or All clients)
- Persist data

### Implementation Workspace

- View implementation project
- Create milestones
- Update milestones
- Assign owners
- Assign due dates
- View blockers
- View readiness status

### Integration

- Critical issue causes Not Ready
- Untriaged Critical issue (no client yet) causes Not Ready for every client
- Resolving critical issue removes blocker
- Incomplete milestones prevent Ready
- Completed milestones and no critical blockers produce Ready
- Data remains consistent across both workspaces

## End-to-End Test Plan

Brahim and Sarah run this workflow with a fictional healthcare client before merging. Pass criterion: the workflow runs without manually changing readiness, without data loss, and without affecting implementations that a linked issue does not touch. If a step fails, we document the incident, fix it, and rerun the test before merging.

| # | Step | Expected result | Run 2026-11-05 |
| --- | --- | --- | --- |
| 1 | Sarah creates an implementation for a client and adds its required milestones | In Progress | ✅ |
| 2 | Sarah marks every required milestone Completed | Ready (no blocker) | ✅ |
| 3 | Brahim creates an issue in the Product workspace: severity Critical, status Open, linked to the client | Saved | ✅ |
| 4 | Back in Sarah's workspace | Not Ready automatically, with the issue as the reason; other implementations unchanged | ✅ |
| 5 | Brahim moves the issue from Open to Resolved | Saved | ✅ |
| 6 | Readiness checked again | Ready again: all milestones Completed, no unresolved Critical issue | ✅ |
| 7 | Edge case: Brahim creates a general Critical issue with no client | Visible as **To triage** (À trier) and blocks **every** implementation until it is linked to the affected clients or resolved ([fail-safe rule](#untriaged-issues-fail-safe)) | ✅ |
| 8 | Both workspaces refreshed | All changes saved; readiness unchanged | ✅ |
| 9 | Invalid client link, and calls straight to the API without the interface | Unknown client rejected (400); invalid severity rejected (400); readiness cannot be forced, it is always computed by the backend | ✅ |

**Step 7, corrected.** The first version of this plan expected a general Critical issue to stay visible *without* blocking. That would let a client go live while a Critical issue waits for triage, which breaks the core promise. We kept the fail-safe rule: when the scope is unknown, the issue blocks everyone. "Without affecting other implementations" applies to issues linked to clients.

### Milestone link test (November 10, 2026)

An issue can now point to the milestone it delays. Client A = Bien-Être Queens (all milestones Completed), client B = CareFirst Brooklyn. Pass criterion: all four pass without changing readiness by hand.

| # | Test | Result |
| --- | --- | --- |
| 1 | Open Critical issue linked to A's milestone "Test EVV avec l'État" | A Not Ready, reason "Export EVV refusé, étape « Test EVV avec l'État »"; the issue is linked to A automatically ✅ |
| 2 | Client B | Unchanged (At Risk, for its own late milestone) ✅ |
| 3 | Issue resolved | A Ready again ✅ |
| 4 | Page refreshed | Issue, milestone link and readiness preserved ✅ |

Run in the browser and as automated tests (`test_probleme_lie_a_une_etape_plan_en_quatre_tests`). Deleting the milestone keeps the issue linked to the client, so the block does not disappear; an unknown milestone is rejected (400).

**Still to do:** rerun the plan with Sarah driving the Implementation workspace on `main`. The 2026-11-05 run was done by Brahim alone.

## Presentation Demo

Sarah proposed a fresh demo that shows both workspaces working together. Click **Réinitialiser la démo** first. The demo data then starts in three different states, one per client:

- **Horizon Soins à Domicile: Non prêt.** The reason names the issue and the milestone it delays (Export EVV, step « Test EVV avec l'État »).
- **CareFirst Brooklyn: À risque.** One milestone is late.
- **Bien-Être Queens: Prêt.** The walkthrough below starts here.

| Step | Who and where | Action | Expected result |
| --- | --- | --- | --- |
| 1 | Sarah, Implementation | Add the milestone « Vérification finale avant go-live » to Bien-Être Queens, due in the coming days | Queens: **En cours** (1 étape restante) |
| 2 | Brahim, Product | Create a Critical issue « Pointages en double sur le portail aidants », feature Portail aidants, and choose that milestone under **Étape concernée** | Bien-Être Queens is linked automatically |
| 3 | Sarah, Implementation | Look at Queens | **Non prêt**, and the reason names the issue and the milestone |
| 4 | Brahim, Product | Set the issue to **Résolu** | Queens: **En cours** (the milestone is still open) |
| 5 | Sarah, Implementation | Set the milestone to **Terminé** | Queens: **Prêt** |
| 6 | Both | Refresh the page | Everything is still there |

`test_demo_de_presentation` in `tests/test_tickets.py` runs the same steps against the API.

## Non-Goals

The MVP does not include:

- Real patient data
- EHR integrations
- AI-generated deployment decisions (Claude only drafts text and suggests a severity; a person decides)
- Automated go-live approvals
- Advanced analytics
- Email or SMS notifications (the client email is a draft to copy, never sent by the app)
- Enterprise authentication
- Multi-facility implementations
- Real-time collaboration

## Success Metrics

| Metric | Target |
| --- | --- |
| Usability | 3/3 testers complete core workflow |
| Blocker Visibility | 3/3 testers identify blockers in under 30 seconds |
| Readiness Accuracy | 10/10 readiness scenarios pass |
| Data Persistence | 10/10 persistence tests pass |
| Deployment Reliability | Successful hosted demo |

## Definition of Done

CareOps Hub is complete when:

- Both workspaces function independently
- Both workspaces connect to the shared backend
- Issue-to-client linking works, including All clients and To triage
- Readiness rules behave correctly
- Data persists after restart
- Acceptance criteria pass
- Application is deployed
- Public demo URL is available
- Final demonstration workflow succeeds

## Decisions

Agreed by Brahim and Sarah on November 10, 2026. They replace the original plan where it differed; the code in `main` already follows them.

| Topic | Decision | Why |
| --- | --- | --- |
| What an issue is linked to | One or more clients, or **All clients** (including clients added later); optionally the milestone it delays | One issue often affects several clients; no duplicates. The milestone shows *what* the issue holds back; blocking still goes through the client |
| Readiness states | Not Ready, At Risk, In Progress, Ready, always with a reason in French | More useful than Ready / Not Ready alone |
| Incomplete milestone | In Progress; a late milestone makes the client At Risk; only a Blocked milestone makes it Not Ready | Unfinished work is not a crisis |
| Critical issue with no link | Fail-safe: it blocks every client until triaged; Medium and Low issues never block | A Critical issue must never drop out of readiness because it is not linked yet |
| Triage deadline | Same business day (weekends and holidays skipped, agency time zone; see the table below); triage identifies the affected clients, only resolving removes the block | Keeps false blocks short |
| Frontend layout | One page with two tabs | Simpler navigation, no duplicated UI |
| Data access | Built-in `sqlite3`, no SQLAlchemy | Enough for this scope, no extra dependency |
| Interface language | French in the interface; code, database columns and identifiers in English | Matches the users; keeps the code maintainable |

Built by Sarah (PR #1, November 10): an open Critical issue still linked to no client is flagged **En retard de triage** next to **À trier**, in both workspaces. The server computes the flag (`overdueForTriage` in `/api/state`).

**Overdue triage counts business days** (agreed with Sarah, November 10). The deadline is the end of the business day the issue was created; an issue created on a weekend or a holiday is due on the next business day. The flag appears on the next business day after the deadline, never on a weekend or a holiday, so an issue is never flagged too early:

| Created | Due by the end of | Flagged from |
| --- | --- | --- |
| Monday to Thursday | the same day | the next business day |
| Friday | Friday | Monday |
| Saturday or Sunday | Monday | Tuesday |
| Friday before a Monday holiday (May 28, 2027) | Friday | Tuesday |
| Wednesday before Thanksgiving (Nov 25, 2026) | Wednesday | Friday |

- **Holidays:** US federal holidays (observed dates) for 2026 and 2027, listed in `app/business_days.py`. The list still has to be confirmed with Sarah: a home-care agency may work on some of them.
- **Time zone:** dates use the agency's time zone (`CAREOPS_TZ`, default `America/New_York`), not the server's. An issue created at 11:59 p.m. in New York is dated that day, even on a UTC server, and a Thursday issue is not flagged at 7 p.m. New York time just because it is already Friday in UTC.

Tests: `test_retard_de_tri_en_jours_ouvres`, `test_retard_de_tri_saute_les_jours_feries`, `test_dates_dans_le_fuseau_de_l_agence`, `test_api_date_les_problemes_dans_le_fuseau_de_l_agence`.

## Progress and Next Steps

### Where we stopped (November 10, 2026)

- [x] Shared repository, both partners connected, secrets guard in place
- [x] PRD and README (user stories, assumptions and validation)
- [x] Component 1: technical issue creation, verified end to end
- [x] Readiness rules and both workspaces working on FastAPI + SQLite
- [x] Three Claude features tested against the live API
- [x] Layout works on phone width (no horizontal scroll)
- [x] Fail-safe rule for untriaged Critical issues and the **All clients** option, with tests
- [x] End-to-end test plan run on `main` (9/9 steps)
- [x] Brahim and Sarah agreed on the [Decisions](#decisions)
- [x] Overdue triage counts business days, skips US federal holidays and uses the agency's time zone; presentation demo scripted and covered by a test (31 pass)
- [x] Sarah's old branch `Implementation-Workplace` is not needed: its demo data predates the current model

### Next steps

1. Rehearse the [Presentation Demo](#presentation-demo) together, with Sarah driving the Implementation workspace; it doubles as the end-to-end rerun.
2. Prepare the Render deployment (and decide whether production needs PostgreSQL or stays on SQLite).
3. Run the validation plan for assumption A1 (severity levels) with 2 or 3 testers.
4. Confirm with Sarah which holidays the agency observes, and extend the list beyond 2027.

## License

This project was created for educational purposes as part of the Pursuit Software Engineering Fellowship and is not intended for production healthcare use.

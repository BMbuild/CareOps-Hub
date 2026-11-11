# CareOps Hub

When a home-care agency moves to new software, an implementation project manager has to decide when it is ready to **go live** (start using the software for real visits). Today that call is made by hand, from two separate places: the milestones in the project plan, and the technical issues in the product team's tracker. A critical bug, such as a rejected **EVV** export (Electronic Visit Verification: the record of each caregiver visit that the state requires), can slip through to go-live, and the agency pays for it in missed visits and billing errors.

CareOps Hub puts both in one place. The Product team logs issues and links them to the clients they affect, the Implementation team tracks each client's milestones, and every client gets a readiness status (Not Ready, At Risk, In Progress or Ready) with the reason in plain words. No client goes live with an open critical issue.

Built by Brahim and Sarah as a two-week minimum viable product (MVP) for the final group project of [Pursuit](https://www.pursuit.org)'s L2 program (Cycle 4). It is inspired by the "Project Manager, Client Implementations" role at [HHAeXchange](https://www.hhaexchange.com), a company that makes home-care software.

## Key Features

- **Issue tracking (Product workspace):** log technical issues with a severity and link them to the clients they affect, or to **All clients**. An issue whose clients are not known yet is saved as **To triage** (see [How readiness works](#how-readiness-works)). An issue can also name the milestone it delays.
- **Milestone tracking (Implementation workspace):** each client's go-live milestones with owner, due date and status; a Blocked milestone must state its cause.
- **Readiness status with a reason:** every client is **Not Ready**, **At Risk**, **In Progress** or **Ready**, recomputed on every change and always explained, for example “1 open critical issue (EVV export rejected by the State aggregator…)”.
- **Go-live guard:** an open Critical issue keeps its clients from Ready; if nobody knows yet which clients it affects, it blocks every client until it is linked.
- **AI drafts, a person decides:** Claude suggests a severity, summarizes readiness and drafts the client update email; a person reviews before anything is saved or sent.

## Demo

![CareOps Hub, Product workspace: readiness cards show Horizon Home Care as Not Ready because of an open critical EVV issue on the milestone “State EVV test”, CareFirst Brooklyn as At Risk because of a late milestone, and Queens Wellness Care as Ready; below, the technical issues table with severity, state and affected clients](docs/screenshots/readiness-product.png)

*Product workspace (Brahim): every client shows a readiness status with its reason. Horizon is **Not Ready** because a critical issue, a rejected EVV export, delays its “State EVV test” milestone; CareFirst is **At Risk** because a milestone is late; Queens is **Ready**.*

![CareOps Hub, Implementation workspace for Horizon Home Care: a red Not Ready banner lists the open critical issue and the blocked milestone, followed by the milestone table with owner, status and blocker, and the read-only list of technical issues affecting this client](docs/screenshots/implementation.png)

*Implementation workspace (Sarah), same data: the banner explains why Horizon is not ready, the blocked milestone states its cause, and the issues logged by Product appear read-only.*

Captured on November 11, 2026 from the demo data. The step-by-step presentation demo is in [docs/testing.md](docs/testing.md#presentation-demo).

## Run it locally

You need Git and Python 3.10 or newer (we tested with Python 3.14).

**macOS or Linux**

```bash
git clone https://github.com/BMbuild/CareOps-Hub.git
cd CareOps-Hub
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

**Windows:** run the same commands, with two changes: activate with `.venv\Scripts\activate`, and copy the settings file with `copy .env.example .env`.

**Claude API key (optional).** The app works fully without one; only the three Claude buttons then show “AI unavailable”. To turn them on, put your own Anthropic key after `ANTHROPIC_API_KEY=` in `.env`.

**What you should see.** Open http://localhost:8000: three client cards at the top, one Not Ready (Horizon Home Care), one At Risk (CareFirst Brooklyn) and one Ready (Queens Wellness Care). The **Reset demo** button restores this demo data at any time. If port 8000 is taken, add `--port 8001` to the last command and open that port instead.

- API documentation: http://localhost:8000/docs
- Tests: `python -m pytest` (48 tests)
- Contributors: `git config core.hooksPath .githooks` turns on the hook that blocks committed secrets.

## How readiness works

The rules are checked in this order; the first one that applies sets the status. They live in `app/readiness.py`, and `test_tableau_de_decision_du_readme` checks this table row by row.

| Status | When |
| --- | --- |
| **Not Ready** | An unresolved Critical issue (Open or In Progress) affects the client, or one of its milestones is Blocked |
| **At Risk** | Otherwise, a milestone is past its due date |
| **Ready** | Otherwise, every milestone is Done |
| **In Progress** | Anything else (milestones still to do, or no milestones yet) |

**Which clients an issue affects:** the clients it is linked to (choosing a milestone links that milestone's client), or every client when it is marked **All clients**. Medium and Low issues never change readiness.

**To triage:** a Critical issue linked to no client yet blocks **every** client until someone links it to the affected clients. When nobody knows who is affected, the rule blocks. It must be triaged the same business day, or it is flagged **Overdue for triage**. Details, including weekends, holidays and time zones: [docs/triage-rules.md](docs/triage-rules.md).

Readiness is an indicator only. The app never approves a go-live: a project manager makes that decision.

## Glossary

| Term | Meaning |
| --- | --- |
| EVV | Electronic Visit Verification: the record of each home-care visit (who, when, where) that the state requires |
| State aggregator | The state's system that receives EVV records from agencies |
| Go-live | The day an agency starts using the new software for real visits |
| Readiness | Whether a client can go live, computed from its milestones and open issues |
| Milestone | A step before go-live, such as data migration or staff training |
| Triage | Deciding which clients an issue affects and linking it to them |
| Severity | Critical blocks an essential function with no workaround; Medium has a workaround; Low is minor |

## Technology

| Layer | Choice |
| --- | --- |
| Frontend | Plain HTML, CSS and JavaScript (ES modules), no framework or build step; one page with two tabs |
| Backend | Python, FastAPI, served by Uvicorn |
| Validation | Pydantic v2 (`app/models.py`) |
| Database | SQLite through Python's built-in `sqlite3`, no ORM |
| AI | Anthropic Claude API through the official Python SDK (`anthropic`), called server-side only (`app/ai.py`); model `claude-opus-5-5` by default, configurable with `CAREOPS_MODEL` |
| Tests | pytest with FastAPI's `TestClient` |

## Configuration

Settings live in `.env` (copied from `.env.example`; never committed):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | empty | Turns on the Claude features |
| `CAREOPS_MODEL` | `claude-opus-5-5` | Claude model to use |
| `CAREOPS_TZ` | `America/New_York` | The agency's time zone for "today" and issue dates |
| `CAREOPS_HOLIDAYS` | US federal holidays | Holidays skipped by the triage deadline ([details](docs/triage-rules.md#overdue-for-triage)) |

## Project structure

```
CareOps-Hub/
├── app/
│   ├── main.py          # FastAPI routes (data, AI) and the frontend files
│   ├── db.py            # SQLite schema, demo data, reads and writes
│   ├── models.py        # Field validation (Pydantic)
│   ├── readiness.py     # Readiness rules
│   ├── business_days.py # Agency time zone, weekends and holidays
│   └── ai.py            # Claude calls (severity, summary, email)
├── public/              # index.html, styles.css, app.js (both workspaces as tabs)
├── data/seed.json       # Fictional demo data
├── docs/                # Business case, decisions, triage rules, testing, screenshots
├── tests/               # pytest
├── scripts/check-secrets.sh
├── PRD.md               # Original product requirements (in French)
└── README.md
```

The interface, data and documentation are in English. Code comments, test names and the original PRD are in French, because they were written before the interface switched to English on November 11, 2026.

## Security

- `.env` and the local database (`data/careops.db`) are never committed; `.gitignore` excludes them.
- The pre-commit hook ([scripts/check-secrets.sh](scripts/check-secrets.sh)) blocks commits that contain a `.env` file or a known key format.
- The API key stays on the server; the browser never calls the Anthropic API.
- All data is fictional. If a key is ever committed: revoke it, create a new one, and remove it from the Git history.

## More documentation

- [Business case](docs/business-case.md): the value claimed, where it is proven and where it is not yet, user stories, assumptions and success metrics
- [Decisions](docs/decisions.md): what Brahim and Sarah agreed and why
- [Triage rules](docs/triage-rules.md): untriaged issues and the overdue deadline
- [Testing](docs/testing.md): the presentation demo, the end-to-end plan and the other checks
- [PRD.md](PRD.md): the original product requirements (in French; the decisions above replace it where they differ)

## Team

| Partner | Workspace |
| --- | --- |
| Brahim Maouloud | Product |
| Sarah Dykes | Implementation |

## Status and next steps (November 11, 2026)

Done: both workspaces on FastAPI and SQLite, the readiness and triage rules, the three Claude features, the English interface, and the presentation demo, all covered by 48 automated tests.

1. Rehearse the [presentation demo](docs/testing.md#presentation-demo) together, with Sarah driving the Implementation workspace; it doubles as the end-to-end rerun.
2. Deploy on Render, and decide whether production uses PostgreSQL or stays on SQLite.
3. Validate the three severity levels with 2 or 3 testers ([assumption A1](docs/business-case.md#assumption-a1-three-severity-levels-are-enough)).
4. Confirm who triages Critical issues and which holidays apply, then set `CAREOPS_HOLIDAYS`.

## License

Created for educational purposes as part of the Pursuit Software Engineering Fellowship. Not intended for production healthcare use.

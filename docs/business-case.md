# Business Case

Back to the [README](../README.md).

## Value claimed

**No client goes live with an unresolved critical issue.**

When milestones and bugs live in separate tools, the "ready / not ready" call is made by hand, and a critical bug can slip through to go-live. In home care, that means missed visits, rejected EVV exports and billing errors for the agency, and a costly rollback and loss of trust for the vendor.

### Where this value shows up in the product today

| Value | Where it shows up | How we know it works |
| --- | --- | --- |
| The go/no-go rule is automatic | `app/readiness.py` (`compute_readiness`) applies the [readiness rules](../README.md#how-readiness-works) on every request; readiness is never stored, so it cannot go stale | `tests/test_tickets.py`: a Critical issue makes its client Not Ready and survives a page refresh; an untriaged Critical issue makes every client Not Ready |
| Blockers are visible in one place | Readiness cards at the top of both workspaces show the status and the reason, for example *Horizon Home Care*: Not Ready, “1 open critical issue (EVV export rejected by the State aggregator, milestone “State EVV test”)” | Demo data |
| Product and Implementation share one view | When the Product workspace resolves an issue, the Implementation workspace's card updates on its own within 4 seconds | Manual end-to-end test in the browser |
| Faster client communication | Claude drafts the readiness summary and the client email from the same data; a person reviews before anything is sent | Tested against the live API on November 4, 2026 |

### Where the value is not proven yet

- **Speed is not measured.** The target "find what blocks a client in under 30 seconds" (see [Success metrics](#success-metrics)) has not been timed with real testers.
- **Severity scale is unvalidated.** With three levels (assumption A1 below), a serious issue with a costly workaround is either invisible in readiness (Medium) or wrongly blocks it (Critical).
- **Not yet tested together.** The end-to-end test still has to be rerun with Sarah driving the Implementation workspace.

## User stories

1. **Report an issue.** As a Product Manager, I want to log a technical issue with its severity, feature and affected clients, so that the implementation team immediately sees its impact.
   - Acceptance: Claude can suggest a severity; I confirm or change it before saving.
2. **Track resolution.** As a Product Manager, I want to update an issue's status (Open, In Progress, Resolved), so that the readiness of affected clients updates without manual work.
3. **Manage milestones.** As an Implementation Project Manager, I want to manage a client's milestones (due date, owner, status, blocker), so that I know what remains before go-live.
   - Acceptance: a milestone past its due date is flagged as late.
4. **Know if a client is ready.** As an Implementation Project Manager, I want to see each client's readiness with the reason behind it, so that we never deploy with an unresolved Critical issue.
5. **Communicate with the client.** As an Implementation Project Manager, I want Claude to draft a readiness summary and a client update email, so that I can inform the client quickly and honestly.
   - Acceptance: nothing is sent automatically; I review and edit before sending.

## Assumption A1: three severity levels are enough

| | |
| --- | --- |
| **Assumption** | Technical issues can be classified into three severity levels: Low, Medium and Critical. |
| **Why we made it** | The decision that matters for deployment is binary: does the issue block go-live (Critical) or not? Fewer levels also means less hesitation when classifying an issue. |
| **Risk** | Real implementation teams may need a middle level, for example a serious issue with a costly workaround that should raise an alert without blocking. Escalation rules (who to notify, how fast) are not modeled either. |
| **How we will validate it** | 1. Ask 2 or 3 people working in healthcare implementation or support how they classify tickets. 2. Have them classify our 6 demo issues and compare with our choices. 3. Note the issues they would flag without blocking deployment. 4. Compare with common support-tool levels (often four, P1 to P4). |
| **What would change** | Add a level (for example "High", which would mark a client At Risk) or an escalation rule, and update the PRD, database and tests. |
| **Status** | Not validated. Used for the MVP. |

## Success metrics

| Metric | Target | Result so far |
| --- | --- | --- |
| Usability | 3/3 testers complete the core workflow | Not run yet |
| Blocker visibility | 3/3 testers find what blocks a client in under 30 seconds | Not run yet |
| Readiness accuracy | 10/10 readiness scenarios pass | Covered by automated tests (48 pass); not yet run as a 10-scenario session with testers |
| Data persistence | 10/10 persistence checks pass | Refresh and restart checks pass in the automated tests and the end-to-end plan |
| Deployment reliability | A hosted demo works | Not deployed yet (Render planned) |

## Not in the MVP

- Real patient data or EHR integrations
- AI-made deployment decisions or automated go-live approvals (Claude only drafts text and suggests a severity; a person decides)
- Email or SMS notifications (the client email is a draft to copy, never sent by the app)
- Enterprise authentication, multi-facility implementations, advanced analytics

## Definition of done

- Both workspaces work and share one backend
- Issue-to-client linking works, including All clients and To triage
- Readiness rules behave correctly and data persists after a restart
- The [test plans](testing.md) pass
- The application is deployed with a public demo URL
- The final demonstration workflow succeeds

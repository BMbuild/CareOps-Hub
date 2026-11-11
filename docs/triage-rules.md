# Triage Rules

Back to the [README](../README.md#how-readiness-works).

**Triage** means deciding which clients an issue affects and linking it to them. It does not mean fixing the issue.

## Issues with no client yet (fail-safe)

A product teammate can log an issue before knowing which clients it affects (a general bug found in internal testing, for example). Leaving **Affected clients** empty saves it as **To triage**.

| Untriaged issue | Effect on readiness |
| --- | --- |
| Open **Critical** | **Every** client is Not Ready, with the reason “untriaged critical issue, to be linked to the affected clients” |
| Medium, Low, or Resolved | No effect |

When in doubt, the rule blocks: an unknown scope never lets a client go live. Once the issue is linked to clients, only those clients stay blocked. The same applies if the last client of an open Critical issue is unlinked or deleted: the issue goes back to To triage and blocks everyone, so the blocker never disappears silently.

For an issue that affects everyone (a login outage, for example), tick **All clients** instead of each client one by one. The issue then counts for every client, including clients added later, and is shown as triaged.

The cost is a false block until triage, so the team agreed on a deadline (November 10, 2026): **a Critical issue is triaged within the same business day.** Only resolving a Critical issue removes its block; relinking it never removes the block silently.

## Overdue for triage

An open Critical issue still linked to no client is flagged **Overdue for triage** next to **To triage**, in both workspaces, once its deadline has passed. Sarah built this flag (PR #1, November 10, 2026). The server computes it (`overdueForTriage` in `/api/state`).

The deadline counts business days. It is the end of the business day the issue was created; an issue created on a weekend or a holiday is due on the next business day. The flag appears on the next business day after the deadline, never on a weekend or a holiday, so an issue is never flagged too early:

| Created | Due by the end of | Flagged from |
| --- | --- | --- |
| Monday to Thursday | the same day | the next business day |
| Friday | Friday | Monday |
| Saturday or Sunday | Monday | Tuesday |
| Friday before a Monday holiday (May 28, 2027) | Friday | Tuesday |
| Wednesday before Thanksgiving (Nov 25, 2026) | Wednesday | Friday |

- **Holidays:** by default, US federal holidays (observed dates) for 2026 and 2027, listed in `app/business_days.py`. The deadline should follow the calendar of whoever triages, so this is a setting: if the agency works on federal holidays and expects triage that day, set `CAREOPS_HOLIDAYS=` (empty) and only weekends are skipped; if it closes on a few days only, list them (`CAREOPS_HOLIDAYS=2026-11-26,2026-12-25`). An invalid date stops the server at startup with a clear message. Which holidays apply is still to confirm.
- **Time zone:** dates use the agency's time zone (`CAREOPS_TZ`, default `America/New_York`), not the server's. An issue created at 11:59 p.m. in New York is dated that day, even on a UTC server such as Render.
- **The active setting is visible:** `/api/state` returns it as `triageCalendar`, and the **Overdue for triage** tooltip states it (for example “weekends and US federal holidays skipped; dates in America/New_York time”), so two machines set differently are easy to spot.

Tests: `test_retard_de_tri_en_jours_ouvres`, `test_retard_de_tri_saute_les_jours_feries`, `test_dates_dans_le_fuseau_de_l_agence`, `test_api_date_les_problemes_dans_le_fuseau_de_l_agence`, `test_jours_feries_reglables`, `test_api_affiche_le_calendrier_de_tri_actif`.

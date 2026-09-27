# Synthetic seed data

**All people in these files are fictional.** Never add real PHI to this repo.

| Persona | Member ID | Name | DOB | ZIP | Employer/group | Subscriber | Plan | Status | Used by |
|---|---|---|---|---|---|---|---|---|---|
| P1 | ABC100000001 | Jane Doe | 1985-03-04 | 95814 | Acme Corp | self | Silver PPO 2500 | active | S01 S02 S05 S07 S08, R* |
| P2 | ABC100000002 | Robert Chen | 1972-11-20 | 94107 | Globex Inc | self | Gold HMO 1000 | active | S03 (lockout) |
| P3 | ABC100000003 | Maria Garcia | 1990-07-15 | 95630 | Initech | self | Bronze HDHP 6000 | active | S04 S10 |
| P4 | ABC100000004 | Katherine Nguyen | 1988-02-28 | 95670 | Umbrella Health | Tom Nguyen (spouse) | Silver PPO 2500 | active | dependent flows |
| P5 | ABC100000005 | Samuel Okafor | 1965-09-09 | 95819 | Stark Logistics | self | Silver PPO 3000 | **terminated 2026-06-30** | S09 |
| P6 | ABC999999999 | *(not in DB)* | — | — | — | — | — | not found | S06, R04 |
| P7 | ABC100000007 | Priya Raman | 1995-12-01 | 95035 | Wayne Analytics | self | Gold PPO 1500 | active, deductible met | policy display |

In the eval scenarios, the placeholder `{answer:challenge}` is filled with the correct answer to whichever challenge question was asked, and `{answer:wrong}` is filled with a deliberately wrong value.

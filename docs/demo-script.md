# Cost Estimation Engine - Demo Script

Spoken narration for a live walkthrough. Audience: business / SME stakeholders.
Estimated run time: 8-10 minutes. Read the **[SAY]** lines aloud; the **[DO]**
lines are your on-screen actions.

---

## 0. Before you start (setup, off-camera)

- Run the app with mock data so nothing depends on a live connection:
  `DATA_SOURCE=mock streamlit run app.py`
- Have the browser full-screen on the welcome screen.
- Keep a real business estimate in mind as the "story" (e.g. a Gulf Coast
  reconfiguration project) so the numbers feel concrete.

---

## 1. Opening (the problem)

**[SAY]**
"Every capital project starts with a detailed cost estimate - the ADR. That
estimate is built for one location and one point in time. But projects move:
they get re-sited, they slip a few quarters, and suddenly the original numbers
no longer reflect today's market. Re-pricing all of that by hand is slow and
error-prone.

The Cost Estimation Engine solves exactly that. It takes an existing ADR
estimate and re-prices it for any location and time period you choose, using our
EMMA market factors - and it shows you, side by side, what changed and by how
much. Let me show you."

**[DO]** Point at the welcome screen.

---

## 2. Welcome screen

**[SAY]**
"This is the landing screen. The whole tool is just three steps: pick a project,
choose where and when, and read the results. No training required."

**[DO]** Click **▶ Start**.

---

## 3. Step 1 - Pick a project

**[SAY]**
"First, we choose the project we want to re-estimate. These are real ADR
projects, each identified by its PlanView ID and name. I can search by either -
the ID number or by any part of the name."

**[DO]** Type a few characters in the search box to filter, then pick a project
from the dropdown

**[SAY]**
"Notice the tool automatically uses the latest snapshot of the estimate - the
most mature stage-gate we have on file. So we're always re-pricing the newest
version of the numbers, not an outdated draft. Here are the project details it
found."

**[DO]** Point at the project detail card. Click **Next / Continue**.

---

## 4. Step 2 - Choose location and time period

**[SAY]**
"Now the interesting part. This is where we tell the engine the new scenario:
which location and which time period we want to re-price for."

**[DO]** Open the Location dropdown, then the Time Period dropdown.

**[SAY]**
"An important detail for accuracy: the tool only offers combinations where we
have both the labor factors and the material factors. That guarantees every
estimate you run is backed by real market data - it will never quietly give you
a half-priced answer.

Before we even run it, the tool gives us a coverage preview: it tells us how
many of this project's material items have a matching market factor for the
scenario we picked. That's our confidence check up front."

**[DO]** Point at the MFC coverage preview. Select a Location + Period.

**[SAY]**
"Let's run it."

**[DO]** Click **Estimate** (a spinner runs briefly).

---

## 5. Step 3 - Results (the payoff)

**[SAY]**
"And here's the answer. At the top we have the headline totals - the original
estimate versus the updated estimate, for both cost and hours - with the change
called out as a number and a percentage. Green means it came down, red means it
went up. In one glance you know the direction and the size of the impact."

**[DO]** Point at the top-line total cost and total hours comparison.

**[SAY]**
"Below that, we break it down by category so you can see *where* the change came
from - the labor categories re-priced by the market labor factor, and the
material categories re-priced by the per-commodity material factors. The charts
show original versus updated side by side, so a stakeholder can immediately see
which part of the estimate is driving the difference."

**[DO]** Scroll through the per-category breakdown and the grouped bar charts.

**[SAY]**
"And it's fully transparent at the line level. Here's every line item with its
original and updated values. If a material item didn't have a market factor for
this scenario, we don't hide it and we don't guess - we keep the line, leave its
cost unchanged, and flag it clearly. So you always know exactly which numbers
moved and which didn't, and why."

**[DO]** Scroll the line-level detail table; point at a flagged line if visible.

---

## 6. Export

**[SAY]**
"Finally, everything you see is one click away from a spreadsheet. There's a
summary export for the headline comparison, and a full line-level export with
every item and every flag"

**[DO]** Click the CSV download buttons.

---

## 7. Closing

**[SAY]**
"So that's the Cost Estimation Engine. it takes an existing
estimate, re-prices it for a new location and time period using our own market
data, and gave us a clear, auditable before-and-after - with a spreadsheet to
back it up.

I'm happy to run it again with any project or scenario you'd like to see."

**[DO]** Optionally restart (returns to the welcome screen) and take a
suggestion from the room.

---

## Quick reference - key talking points

- **Three steps**: project -> location & period -> results.
- **Latest snapshot auto-selected**: always re-prices the newest estimate.
- **Only fully-covered scenarios are offered**: no half-backed estimates.
- **Coverage preview up front**: confidence check before you run.
- **Original vs updated, colour-coded**: direction and size at a glance.
- **Missing factors are flagged, never hidden**: full transparency and audit.
- **Two CSV exports**: summary + full line-level detail.

## Glossary (if asked)

- **ADR** - the existing detailed project cost estimate we start from.
- **EMMA** - the market-factor reference data used to re-price.
- **Material factor (MFC)** - re-prices material costs, per commodity code.
- **Labor factor (LRC)** - re-prices labor hours and cost, per location/period.
- **Snapshot / stage-gate** - the maturity stage of the estimate (Screen ->
  Gate 1 ... -> Gate 3); the tool uses the most mature one.

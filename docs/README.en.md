# Territorial Doctrine — Victoria 3 1.13

Version **0.6.1-alpha.1** adds four territorial doctrine laws and individual claim, admission and lost-claim relinquishment bills.

**The design goal is domestic bargaining over expansion and admission.** The revised [design and effect audit](DESIGN.md) distinguishes the new specification from the running 0.6.1 prototype. Concrete group interests, funded commitments and accountability should drive the process. Current fixed doctrine bonuses are experimental effects scheduled for replacement, not quantified historical findings; a doctrine name alone cannot make factories more efficient or residents more loyal. The complete general bargaining flow is not implemented yet.

**The system starts disabled.** Take **Enable National Territorial Doctrine** in the decisions menu to activate it for every country in this save. The enable decision and the permanently visible mod-status decision indicate that the mod is loaded. AI cannot activate it. This alpha has no disable decision; use a new test save.

Game language settings select the text. English is the canonical default, Simplified Chinese is translated, and French, German, Spanish, Polish, Russian, Brazilian Portuguese, Japanese, Korean and Turkish catalogs currently contain English fallback text. This does not change the game's language setting or claim translations into those languages.

Each doctrine now supplies native law modifiers, with distinct political beneficiaries and national tradeoffs:

| Doctrine | Interest-group political strength | National effects |
|---|---|---|
| Status Quo | Intelligentsia, Trade Unions, Rural Folk +10% each; Armed Forces −10% | Bureaucracy +5%, prestige −5%, infamy decay +15% |
| Historical Rights | Petty Bourgeoisie +15%; Landowners and Devout +10% each | Authority +25, infamy generation −10%, infamy decay +5% |
| Strategic Frontiers | Armed Forces +15%, Industrialists +10%, Rural Folk −10% | Diplomatic play maneuvers +10, military goods cost +5%, infamy generation +10% |
| Imperial Expansion | Armed Forces +20%, Industrialists +15%, Landowners +10%; Intelligentsia, Trade Unions and Rural Folk −10% each | Prestige +10%, military goods cost +10%, bureaucracy −5%, infamy generation +25% |

Additional industrial and state development effects:

| Doctrine | Industry throughput within newly acquired states | New-state construction / migration attraction |
|---|---|---|
| Status Quo | Paper, food and textiles +5% | +5% / +15% |
| Historical Rights | Agriculture and logging +5% | +10% / +10% |
| Strategic Frontiers | Steel, tools, arms, munitions and shipyards +5% | +15% / +5% |
| Imperial Expansion | Twelve specified military supply-chain industries +10% | +20% / +10% |

The imperial list covers coal, iron, lead and sulfur mines, steel mills, tooling workshops, chemical plants, motor industries, arms industries, munition plants, war machine industries and shipyards. Throughput increases inputs as well as outputs. All industrial, construction, migration and ongoing local political effects are attached to ordinary states newly acquired after activation. Every original owned state is registered when enabling, including original non-homelands, and remains excluded even if later lost and recovered. Separate owned portions of a shared state region remain independent. Treaty ports and foreign military occupation do not qualify. Administrative incorporation does not remove an acquired state’s eligibility. Changing doctrine replaces the state's old bonus. Migration laws still apply.

Legitimacy is earned from territorial results. Actually acquiring territory with an approved target bill and a still-valid claim grants +6 under Historical Rights, +8 under Strategic Frontiers or +12 under Imperial Expansion. Status Quo earns no acquisition credit. Completing an individual one-year admission grants +3 under any doctrine. All rewards share a 36-month window, never stack or renew within it, and disappear early if the credited state is lost; the window remains locked. Passing a claim or declaring war alone earns no credit. Higher imperial infamy, administration costs and local resistance remain the price of expansion.

Local population politics:

| Doctrine | Radicals from discrimination | Radicals from falling living standards | Loyalists from rising living standards | One-time acquisition radicals / loyalists |
|---|---:|---:|---:|---:|
| Status Quo | −15% | −10% | +15% | 0% / +2% |
| Historical Rights | −5% | 0% | +10% | +1% / +2% |
| Strategic Frontiers | +5% | +5% | +5% | +3% / +1% |
| Imperial Expansion | +20% | +10% | −10% | +5% / 0% |

The first three columns modify the named source rates, not total radical/loyalist counts or monthly population shares. Acquisition reactions occur once for a newly acquired state’s owner. A ratified individual admission reduces radicals and adds loyalists in that state by 2% of population, or 3% with the Equal Rights justification, subject to vanilla population caps. The reaction cannot repeat monthly or on a duplicate vote; it does not remove discrimination or change citizenship laws. Ratification itself adds no economic bonus to an original state.

Political strength modifiers change influence rather than granting approval or the same percentage-point share of clout. Colonial policy and humanitarian research still adjust law preferences; they do not change the enacted doctrine's fixed effects. Unique law descriptions explain each policy and its scope. Group descriptions report their current doctrine positions. These are initial balance values awaiting engine testing.

All governments and power structures share a 10% base passage chance. Seven justifications supply institutional adjustments. Countries can browse eligible foreign targets and establish funded focus regions. Distant expansion requires an existing vanilla regional interest and a mature focus. If candidates disappear or browsing finds no eligible state, a safe no-target message replaces the state preview. Claim passage gives a real claim and a target mandate, while acquiring sovereignty still uses vanilla diplomacy.

Owned, unincorporated non-homeland states need a named individual admission amendment. Ratification records the exact owned state, applies one-time local radical relief and loyalty, and automatically starts its one-calendar-year integration if the administrative reserve is affordable. Otherwise the state remains ratified until funded through the integration decision. No prior cultural acceptance threshold applies, and later unrest or a budget deficit does not reset a funded deadline. Completion incorporates only this state. Transfers invalidate approvals and cancel the original owner's project.

For example, Portugal can ratify the Admission Amendment for its owned portion of Western Guangdong. China's portion of the same region and other Portuguese territories receive no approval. If the intended example is the initial Macau treaty port, ordinary territorial sovereignty must be obtained first. The named journal and state modifier show the individual amendment and its integration progress. Cultures and homelands remain unchanged. Lost claims can be relinquished one wholly lost region at a time without changing homelands or sovereignty.

Colonial Resettlement and Colonial Exploitation favor early expansion while making resident admission less attractive. Egalitarianism and Human Rights research reduce expansion support and increase admission support. These affect interest-group bill scores and their stances on national doctrine laws. Colonial administration and stronger rights obligations also increase integration bureaucracy.

For an offensive conquest or annexation, the declaring attacking warleader needs both an expansion doctrine and approved bills with still-valid claims for every target region. A failure adds 2 war exhaustion per month, capped at 20 per war. Defense, pure return-state wars and nonterritorial wars are exempt. Existing wars at activation are not retroactively penalized. Late approval cannot erase an unauthorized start. Only an attacking warleader can establish the initial snapshot; leaving the war stops further extra exhaustion without resetting its saved counter.

**139 offline tests pass. Loading and gameplay in the Victoria 3 1.13 engine have not been tested.** The symbolic runner uses explicit game-scope fixtures; it does not emulate the engine. New regressions execute Portuguese generic claims and admission selection, check humanitarian versus medical/military research, and restore queues, approvals, profiles and war counters through JSON. This tests persisted script state, not a real Vic3 save format or random-number generator. Resources, detailed cultural-population thresholds, a historical registry and great-power risk remain design/model features. Construction pledges still cover only Spain–Al Rif. Extra 1.13 colonial law variants receive neutral policy values until explicitly mapped.

Python 3.10+; no third-party dependencies:

```bash
python3 tools/generate.py --check
python3 -m unittest discover -s tests -v
python3 tools/validate.py
python3 tools/scenario.py
python3 tools/package.py
```

Extract `dist/territorial_doctrine-0.6.1-alpha.1.zip` into your user-data `Victoria 3/mod/` directory and enable the mod in a launcher playset. Then activate the doctrine system using its in-game decision. Alternatively, run `python3 tools/package.py --install-dir "/path/to/your/Victoria 3/mod"`; existing installations are never overwritten. GitHub Actions also saves the packaged ZIP after validation.

Full rules: [Design](DESIGN.md). The six-part delivery and engine boundaries are recorded in [Colonial and war rules](COLONIAL_WAR_RULES.md). All Markdown rules and acceptance documents are now included in the ZIP. Installation and engine checks: [Install](INSTALL.md), [Testing](TESTING.md). Old alpha saves are not a supported migration path; disabled cleanup does not undo earlier sovereignty, culture, incorporation or claim changes.

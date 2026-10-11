# Territorial Doctrine — Victoria 3 1.13

Version **0.5.0-alpha.1** adds four territorial doctrine laws and individual claim, admission and lost-claim relinquishment bills.

**The system starts disabled.** Take **Enable National Territorial Doctrine** in the decisions menu to activate it for every country in this save. The enable decision and the permanently visible mod-status decision indicate that the mod is loaded. AI cannot activate it. This alpha has no disable decision; use a new test save.

Game language settings select the text. English is the canonical default, Simplified Chinese is translated, and French, German, Spanish, Polish, Russian, Brazilian Portuguese, Japanese, Korean and Turkish catalogs currently contain English fallback text. This does not change the game's language setting or claim translations into those languages.

Each doctrine now supplies native law modifiers, with distinct political beneficiaries and national tradeoffs:

| Doctrine | Interest-group political strength | National effects |
|---|---|---|
| Status Quo | Intelligentsia, Trade Unions, Rural Folk +10% each; Armed Forces −10% | Bureaucracy +5%, prestige −5%, infamy decay +15%, base legitimacy +5 |
| Historical Rights | Petty Bourgeoisie +15%; Landowners and Devout +10% each | Authority +25, infamy generation −10%, infamy decay +5%, base legitimacy +5 |
| Strategic Frontiers | Armed Forces +15%, Industrialists +10%, Rural Folk −10% | Diplomatic play maneuvers +10, military goods cost +5%, infamy generation +10%, base legitimacy +2 |
| Imperial Expansion | Armed Forces +20%, Industrialists +15%, Landowners +10%; Intelligentsia, Trade Unions and Rural Folk −10% each | Prestige +10%, military goods cost +10%, bureaucracy −5%, infamy generation +25%, base legitimacy −5 |

Additional industrial and state development effects:

| Doctrine | National industry throughput | Eligible owned-state construction / migration attraction |
|---|---|---|
| Status Quo | Paper, food and textiles +5% | +5% / +15% |
| Historical Rights | Agriculture and logging +5% | +10% / +10% |
| Strategic Frontiers | Steel, tools, arms, munitions and shipyards +5% | +15% / +5% |
| Imperial Expansion | Twelve specified military supply-chain industries +10% | +20% / +10% |

The imperial list covers coal, iron, lead and sulfur mines, steel mills, tooling workshops, chemical plants, motor industries, arms industries, munition plants, war machine industries and shipyards. Throughput increases inputs as well as outputs. Development applies to owned non-homeland states and ordinary states newly acquired after activation; treaty ports and foreign military occupation do not qualify. Changing doctrine replaces the state's old bonus. Migration laws still apply.

Political strength modifiers change influence rather than granting approval or the same percentage-point share of clout. Colonial policy and humanitarian research still adjust law preferences; they do not change the enacted doctrine's fixed effects. Unique law descriptions explain each policy and its scope. Group descriptions report their current doctrine positions. These are initial balance values awaiting engine testing.

All governments and power structures share a 10% base passage chance. Seven justifications supply institutional adjustments. Countries can browse eligible foreign targets and establish funded focus regions. Distant expansion requires an existing vanilla regional interest and a mature focus. Claim passage gives a real claim and a target mandate, while acquiring sovereignty still uses vanilla diplomacy.

Owned, unincorporated non-homeland states need a named individual admission amendment. Ratification records the exact owned state, grants migration attraction +5%, and automatically starts its one-calendar-year integration if the administrative reserve is affordable. Otherwise the state remains ratified until funded through the integration decision. No prior cultural acceptance threshold applies, and later unrest or a budget deficit does not reset a funded deadline. Completion incorporates only this state. Transfers invalidate approvals and cancel the original owner's project.

For example, Portugal can ratify the Admission Amendment for its owned portion of Western Guangdong. China's portion of the same region and other Portuguese territories receive no approval. If the intended example is the initial Macau treaty port, ordinary territorial sovereignty must be obtained first. The named journal and state modifier show the individual amendment and its integration progress. Cultures and homelands remain unchanged. Lost claims can be relinquished one wholly lost region at a time without changing homelands or sovereignty.

Colonial Resettlement and Colonial Exploitation favor early expansion while making resident admission less attractive. Egalitarianism and Human Rights research reduce expansion support and increase admission support. These affect interest-group bill scores and their stances on national doctrine laws. Colonial administration and stronger rights obligations also increase integration bureaucracy.

For an offensive conquest or annexation, the declaring attacking warleader needs both an expansion doctrine and approved bills with still-valid claims for every target region. A failure adds 2 war exhaustion per month, capped at 20 per war. Defense, pure return-state wars and nonterritorial wars are exempt. Existing wars at activation are not retroactively penalized. Late approval cannot erase an unauthorized start.

**111 offline tests pass. Loading and gameplay in the Victoria 3 1.13 engine have not been tested.** The symbolic runner uses explicit game-scope fixtures; it does not emulate the engine. Resources, detailed cultural-population thresholds, a historical registry and great-power risk remain design/model features. Construction pledges still cover only Spain–Al Rif. Extra 1.13 colonial law variants receive neutral policy values until explicitly mapped.

Python 3.10+; no third-party dependencies:

```bash
python3 tools/generate.py --check
python3 -m unittest discover -s tests -v
python3 tools/validate.py
python3 tools/scenario.py
python3 tools/package.py
```

Extract `dist/territorial_doctrine-0.5.0-alpha.1.zip` into your user-data `Victoria 3/mod/` directory and enable the mod in a launcher playset. Then activate the doctrine system using its in-game decision. Alternatively, run `python3 tools/package.py --install-dir "/path/to/your/Victoria 3/mod"`; existing installations are never overwritten. GitHub Actions also saves the packaged ZIP after validation.

Full rules: [Design](DESIGN.md). Installation and engine checks: [Install](INSTALL.md), [Testing](TESTING.md). Old alpha saves are not a supported migration path; disabled cleanup does not undo earlier sovereignty, culture, incorporation or claim changes.

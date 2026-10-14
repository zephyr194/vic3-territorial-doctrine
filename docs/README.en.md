# Territorial Doctrine — Victoria 3 1.13

Version **0.8.0-alpha.1** adds permanently enabled fiscal, recruitment and public-service accounting to domestic territorial bargaining. The system starts disabled: use **Enable National Territorial Doctrine** in decisions. English and Simplified Chinese are translated; nine other game-language catalogs contain complete English fallback text. Game settings select the language.

Select a claim, admission or lost-claim relinquishment target and an argument. Every 90 days the player negotiates a round: review group interests, fund a commitment, proceed or withdraw. Three successes pass; three failures reject. Closing a dialog does not immediately vote, and the negotiation decision reopens it. Engine timeout behavior remains to be tested.

Support reads vanilla clout, group approval and selected leader ideologies, plus explicit argument, colonial, commitment and breach components. The ledger separates these sources. Base affinities and score thresholds are adjustable gameplay parameters, not historical approval measurements.

Railway and naval-base commitments work for all countries’ claim and admission bills. Each pays `max(5000, ceil(target population x0.01))` from gold reserves and reserves 10 bureaucracy. Surveys are nonrefundable; actual buildings, employment and upkeep use vanilla budgets. Railways require railway technology; naval bases require a coast; treaty ports are excluded. Commitments create no free buildings or throughput.

Owned-state commitments retain the exact state and signing baseline, with three years to deliver after ratification. Foreign commitments first bind the target region, waiting at most five years for acquisition, then bind the actual owned state and acquisition baseline for three-year delivery. They cannot be signed early if the actor already owns part of that foreign region; negotiate through the owned portion’s admission amendment instead. Fulfillment grants the relevant group approval +2 for three years; breach grants -5 and a -10 future bargaining component for five years. Same-name feedback is replaced, not stacked. Doctrine changes, transfers and reloads never restart obligations.

Admission remains individual: ratification plus a funded one-calendar-year administrative project incorporates only the owned non-homeland ordinary state. Culture, religion, actual acceptance, radicals and loyalists are not rewritten. The administrative reserve is `ceil((25+25 x population in millions) x (1+0.5 x turmoil+0.5 x devastation))`. A project no longer freezes other bills. This alpha supports one active bill and one funded annual project at a time; each building commitment type has one outstanding slot.

All unconditional industrial, construction, migration, political-strength, legitimacy and population effects are removed. Domestic passage adds no extra infamy. Vanilla diplomacy and warfare remain available, with no additional war exhaustion or war callbacks imposing penalties. Doctrine focus-maturity waits, the five-year doctrine lock, the legitimacy-40 discussion gate and blanket institutional cost multipliers are retired.

Colonial policy still distinguishes acquiring land from admitting residents, and Egalitarianism/Human Rights supply humanitarian argument stages. These alter support estimates, not citizenship or residents’ actual acceptance. Medical/military technology does not increment humanitarian stages. Rights arguments receive extra support only with actual Multiculturalism and Total Separation laws. Population-specific tax burdens, automatic debt financing, long-term tax/service contracts, detailed returns and a complete leader-ideology map remain unimplemented.

**179 offline tests pass, including 32 bargaining/contract and 22 new accounting regressions. Victoria 3 1.13 engine behavior has not been tested.** Tests use explicit engine-data fixtures; JSON roundtrips validate persisted script state, not a real game save or PRNG. Test treasury scopes, UI, building counts, partial-state transfers and timing in a fresh 1.13 save. Old alpha saves are not supported migrations.

Python 3.10+, no third-party dependencies:

```bash
python3 tools/generate.py --check
python3 -m unittest discover -s tests -v
python3 tools/validate.py
python3 tools/scenario.py
python3 tools/package.py
```

Extract `territorial_doctrine-0.8.0-alpha.1.zip` into your user-data `Victoria 3/mod/` directory and enable it in a playset, then activate the system in game. All rule and acceptance documents are included. [Install](INSTALL.md), [Design and scope](DESIGN.md), [Testing](TESTING.md), [Colonial and war rules](COLONIAL_WAR_RULES.md).


After enabling the main system, independently enable Fiscal Accounting, Political Recruitment Response and Public-Service Responsibility Accounting in decisions. Each flag is permanent for all countries in that save; peaceful budgeting never disables it. All mod-owned names and tooltips have one **VTD** prefix in all eleven catalogs. Vanilla localization keys are untouched.

Fiscal accounting observes vanilla weekly balance/expenses and tax law. Deficit/surplus decisions change the actual tax setting one step, with a shared 30-day cooldown and appropriate bounds. Surplus before a tax cut is not a revenue forecast. Increased tax settings against the bill's frozen baseline give specified burden-bearing groups up to -10 bargaining points; unknown laws earn no fabricated allocation. No extra payment duplicates vanilla expenses.

An expansion doctrine with an active claim bill or a three-year approved program marks expansion budgeting. Recruitment additionally requires a ratified program and offensive war leadership. Relative conscription potential changes by `0.10 * clamp((legitimacy-50)/50,-1,1)` using state modifiers, not recruitment speed, percentage points or free troops. Ordinary owned states are eligible, foreign states and treaty ports are excluded. Peace, defense and missing requirements yield zero. This checks a national program and war role, not approval of every war target. Peaceful budgeting can end the temporary program while retaining contracts and permanent flags.

Services observe school/health institution levels and bureaucracy. Pressure is `min(100,100*max(0,-bureaucracy)/max(1,bureaucracy_usage))`, not institution efficiency or population coverage. Actual school cuts affect the intelligentsia, health cuts affect trade unions, and a bureaucracy deficit affects those groups plus the petty bourgeoisie; each service component floors at -10. Restoring capacity removes that opposition without awarding free approval. The mod never automatically cuts an institution simply because the country expands. Inspect these interfaces and state modifiers in a fresh 1.13 save; engine behavior is still untested.

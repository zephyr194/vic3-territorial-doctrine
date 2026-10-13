# Territorial Doctrine — Victoria 3 1.13

Version **0.7.0-alpha.1** implements domestic bargaining instead of doctrine attribute packages and uniform war penalties. The system starts disabled: use **Enable National Territorial Doctrine** in decisions. English and Simplified Chinese are translated; nine other game-language catalogs contain complete English fallback text. Game settings select the language.

Select a claim, admission or lost-claim relinquishment target and an argument. Every 90 days the player negotiates a round: review group interests, fund a commitment, proceed or withdraw. Three successes pass; three failures reject. Closing a dialog does not immediately vote, and the negotiation decision reopens it. Engine timeout behavior remains to be tested.

Support reads vanilla clout, group approval and selected leader ideologies, plus explicit argument, colonial, commitment and breach components. The ledger separates these sources. Base affinities and score thresholds are adjustable gameplay parameters, not historical approval measurements.

Railway and naval-base commitments work for all countries’ claim and admission bills. Each pays `max(5000, ceil(target population x0.01))` from gold reserves and reserves 10 bureaucracy. Surveys are nonrefundable; actual buildings, employment and upkeep use vanilla budgets. Railways require railway technology; naval bases require a coast; treaty ports are excluded. Commitments create no free buildings or throughput.

Owned-state commitments retain the exact state and signing baseline, with three years to deliver after ratification. Foreign commitments first bind the target region, waiting at most five years for acquisition, then bind the actual owned state and acquisition baseline for three-year delivery. They cannot be signed early if the actor already owns part of that foreign region; negotiate through the owned portion’s admission amendment instead. Fulfillment grants the relevant group approval +2 for three years; breach grants -5 and a -10 future bargaining component for five years. Same-name feedback is replaced, not stacked. Doctrine changes, transfers and reloads never restart obligations.

Admission remains individual: ratification plus a funded one-calendar-year administrative project incorporates only the owned non-homeland ordinary state. Culture, religion, actual acceptance, radicals and loyalists are not rewritten. The administrative reserve is `ceil((25+25 x population in millions) x (1+0.5 x turmoil+0.5 x devastation))`. A project no longer freezes other bills. This alpha supports one active bill and one funded annual project at a time; each building commitment type has one outstanding slot.

All unconditional industrial, construction, migration, political-strength, legitimacy and population effects are removed. Domestic passage adds no extra infamy. Vanilla diplomacy and warfare remain available, with no additional war exhaustion or war callbacks imposing penalties. Doctrine focus-maturity waits, the five-year doctrine lock, the legitimacy-40 discussion gate and blanket institutional cost multipliers are retired.

Colonial policy still distinguishes acquiring land from admitting residents, and Egalitarianism/Human Rights supply humanitarian argument stages. These alter support estimates, not citizenship or residents’ actual acceptance. Medical/military technology does not increment humanitarian stages. Rights arguments receive extra support only with actual Multiculturalism and Total Separation laws. Tax, conscription and public-service negotiation clauses, detailed resources/returns and a complete leader-ideology map are not yet implemented.

**157 offline tests pass, including 32 bargaining/contract regressions. Victoria 3 1.13 engine behavior has not been tested.** Tests use explicit engine-data fixtures; JSON roundtrips validate persisted script state, not a real game save or PRNG. Test treasury scopes, UI, building counts, partial-state transfers and timing in a fresh 1.13 save. Old alpha saves are not supported migrations.

Python 3.10+, no third-party dependencies:

```bash
python3 tools/generate.py --check
python3 -m unittest discover -s tests -v
python3 tools/validate.py
python3 tools/scenario.py
python3 tools/package.py
```

Extract `territorial_doctrine-0.7.0-alpha.1.zip` into your user-data `Victoria 3/mod/` directory and enable it in a playset, then activate the system in game. All rule and acceptance documents are included. [Install](INSTALL.md), [Design and scope](DESIGN.md), [Testing](TESTING.md), [Colonial and war rules](COLONIAL_WAR_RULES.md).

# Territorial Doctrine — Victoria 3 1.13

Version **0.9.1-alpha.1** adds paid distribution clauses for all eight interest groups and distinct colonial responses to domestic territorial bargaining. The main system runs with the mod. Its law group is always visible under Laws > Power Structure. The country status decision disappears after acknowledgement. Fiscal, recruitment and service accounting remain separate opt-in modules. English and Simplified Chinese are translated; nine other game-language catalogs contain complete English fallback text. Game settings select the language.

Quick source installation on Windows uses built-in Windows PowerShell 5.1; no Python or additional runtime installation is required:

```bat
git clone https://github.com/zephyr194/vic3-territorial-doctrine.git
cd vic3-territorial-doctrine
vtd.cmd install
vtd.cmd status
vtd.cmd update
vtd.cmd remove
```

Double-click `vtd.cmd` for the menu; type `exit` to close the retained console afterward. In a PowerShell terminal use `.\vtd.cmd`. Linux/macOS keep `python3 vtd.py` or `./vtd.sh` (Python 3.10+, no pip dependencies). The tool discovers the **user-data mod directory**, including Windows Documents redirection, rather than modifying the Steam game files. Override it with `--mod-dir "/path/to/Victoria 3/mod"` or `VTD_MOD_DIR`; explicit arguments take precedence. Proton/custom profiles need an explicit path.

Both entry points print a persistent log path in the system temporary directory (`%TEMP%/vtd-installer-*.log` on Windows), recording progress and errors, including during dry runs. Set `VTD_LOG_FILE` to append to a file in an existing directory. The batch launcher uses a process-local execution policy for the repository script, without changing system policy. Managed device policies can still block scripts before they start. Run `vtd.cmd status` from an existing terminal to see startup errors.

`update` copies the current checkout; run `git pull --ff-only` first for remote changes. Windows checks source identity, required files and links, then copies the checked-in payload without invoking Python. It does not perform the Python source-generation consistency or deep script checks. After editing generator inputs, regenerate in a Python development environment and commit the resulting assets. Python entry points retain full offline source validation and support `update --generate`; Windows rejects `--generate` explicitly. `--dry-run` changes no source or game files but still writes its diagnostic log.

Updates/removals back up the old payload and descriptor under the profile's `vtd-backups/`, preserving local edits. Failed writes attempt rollback, unrelated files/descriptor paths are refused, and legacy ZIP installations are supported. Windows also refuses reparse points within source/backup payloads; use a full local copy if OneDrive placeholders are refused. Saves, other mods and playsets are preserved. Exit the game before changing files and restart the launcher afterward. PowerShell transactions are tested on Linux with optional `pwsh`; native Windows checks are included in CI. See [installation](INSTALL.md#源码安装工具).

Select a claim, admission or lost-claim relinquishment target and an argument. Every 90 days the player negotiates a round: review group interests, fund a commitment, proceed or withdraw. Three successes pass; three failures reject. Closing a dialog does not immediately vote, and the negotiation decision reopens it. Engine timeout behavior remains to be tested.

Support reads vanilla clout, group approval and selected leader ideologies, plus explicit argument, colonial, commitment and breach components. The ledger separates these sources. Base affinities and score thresholds are adjustable gameplay parameters, not historical approval measurements.

Railway and naval-base commitments work for all countries’ claim and admission bills. Each pays `max(5000, ceil(target population x0.01))` from gold reserves and reserves 10 bureaucracy. Surveys are nonrefundable; actual buildings, employment and upkeep use vanilla budgets. Railways require railway technology; naval bases require a coast; treaty ports are excluded. Commitments create no free buildings or throughput.

Owned-state commitments retain the exact state and signing baseline, with three years to deliver after ratification. Foreign commitments first bind the target region, waiting at most five years for acquisition, then bind the actual owned state and acquisition baseline for three-year delivery. They cannot be signed early if the actor already owns part of that foreign region; negotiate through the owned portion’s admission amendment instead. Fulfillment grants the relevant group approval +2 for three years; breach grants -5 and a -10 future bargaining component for five years. Same-name feedback is replaced, not stacked. Doctrine changes, transfers and reloads never restart obligations.

Admission remains individual: ratification plus a funded one-calendar-year administrative project incorporates only the owned non-homeland ordinary state. Culture, religion, actual acceptance, radicals and loyalists are not rewritten. The administrative reserve is `ceil((25+25 x population in millions) x (1+0.5 x turmoil+0.5 x devastation))`. A project no longer freezes other bills. This alpha supports one active bill and one funded annual project at a time; each building commitment type has one outstanding slot.

All unconditional industrial, construction, migration, political-strength, legitimacy and population effects are removed. Domestic passage adds no extra infamy. Vanilla diplomacy and warfare remain available, with no additional war exhaustion or war callbacks imposing penalties. Doctrine focus-maturity waits, the five-year doctrine lock, the legitimacy-40 discussion gate and blanket institutional cost multipliers are retired.

Colonial policy still distinguishes acquiring land from admitting residents, and Egalitarianism/Human Rights supply humanitarian argument stages. These alter support estimates, not citizenship or residents’ actual acceptance. Medical/military technology does not increment humanitarian stages. Rights arguments receive extra support only with actual Multiculturalism and Total Separation laws. Population-specific taxes, automatic financing, actual property/profit/wage/member returns and complete ideology responses remain unimplemented.

**240 offline tests pass with optional PowerShell (2 native Windows batch tests are skipped on Linux), including 35 installer tests, 32 bargaining/contract, 22 accounting and 26 new allocation regressions. Victoria 3 1.13 engine behavior has not been tested.** Tests use explicit engine-data fixtures; JSON roundtrips validate persisted script state, not a real game save or PRNG. Test treasury scopes, UI, building counts, partial-state transfers and timing in a fresh 1.13 save. Old alpha saves are not supported migrations.

Python 3.10+, no third-party dependencies:

```bash
python3 tools/generate.py --check
python3 -m unittest discover -s tests -v
python3 tools/validate.py
python3 tools/scenario.py
python3 tools/package.py
```

Extract `territorial_doctrine-0.9.1-alpha.1.zip` into your user-data `Victoria 3/mod/` directory and enable it in a playset, the main system starts with the mod. All rule and acceptance documents are included. [Install](INSTALL.md), [Design and scope](DESIGN.md), [Testing](TESTING.md), [Colonial and war rules](COLONIAL_WAR_RULES.md).


After loading the mod, independently enable Fiscal Accounting, Political Recruitment Response and Public-Service Responsibility Accounting in decisions. Each flag is permanent for all countries in that save; peaceful budgeting never disables it. All mod-owned names and tooltips have one **VTD** prefix in all eleven catalogs. Vanilla localization keys are untouched.

Fiscal accounting observes vanilla weekly balance/expenses and tax law. Deficit/surplus decisions change the actual tax setting one step, with a shared 30-day cooldown and appropriate bounds. Surplus before a tax cut is not a revenue forecast. Increased tax settings against the bill's frozen baseline give specified burden-bearing groups up to -10 bargaining points; unknown laws earn no fabricated allocation. No extra payment duplicates vanilla expenses.

An expansion doctrine with an active claim bill or a three-year approved program marks expansion budgeting. Recruitment additionally requires a ratified program and offensive war leadership. Relative conscription potential changes by `0.10 * clamp((legitimacy-50)/50,-1,1)` using state modifiers, not recruitment speed, percentage points or free troops. Ordinary owned states are eligible, foreign states and treaty ports are excluded. Peace, defense and missing requirements yield zero. This checks a national program and war role, not approval of every war target. Peaceful budgeting can end the temporary program while retaining contracts and permanent flags.

Services observe school/health institution levels and bureaucracy. Pressure is `min(100,100*max(0,-bureaucracy)/max(1,bureaucracy_usage))`, not institution efficiency or population coverage. Actual school cuts affect the intelligentsia, health cuts affect trade unions, and a bureaucracy deficit affects those groups plus the petty bourgeoisie; each service component floors at -10. Restoring capacity removes that opposition without awarding free approval. The mod never automatically cuts an institution simply because the country expands. Inspect these interfaces and state modifiers in a fresh 1.13 save; engine behavior is still untested.


0.9 provides seven allocation types sharing two slots per claim/admission bill: naval base, railway, religious schooling, public education, health investment, existing landlord-regime maintenance and a low-tax guarantee. Each preparation fee is population x0.01 (minimum 5,000), with 10 reserved bureaucracy. Religious/public schooling is mutually exclusive; school-law prerequisites and institution headroom are required. Land maintenance records Serfdom or Tenant Farmers rather than inventing ownership gains. Low-tax terms require actual low/very-low taxes, fiscal accounting and a nonnegative observed balance at signing.

Institutional delivery requires one real national institution investment level above the frozen baseline and incorporation of the exact bound state. This is not a state-specific school/hospital or proof of population coverage. Maintenance terms hold the actual recorded regime or low-tax threshold for at least a year, with a two-year acceptance window; institutional delivery has three years. Foreign contracts await an ordinary owned portion for at most five years, retaining the paid signing investment baseline: preparatory national investment can count only after the bound state is incorporated. Lost ownership, changes of doctrine and reloads never extend deadlines. A monthly audit checks prerequisites; no claim is made to capture every transient setting change between audits.

Funded terms change the coalition and can create opponents: religious schooling favors Devout and opposes Intelligentsia; public education reverses these; landlord maintenance favors Landowners and opposes Rural Folk. Low tax serves Rural Folk/Petty Bourgeoisie, health serves Trade Unions, and existing base/rail contracts serve Armed Forces/Industrialists. Broken promises affect beneficiaries only; no automatic political-strength rewards. Journals distinguish proposed, waiting and named-state delivery obligations.

Observed foreign market difference plus current access >=50% supplies a commercial opportunity argument; actor-faith share below 50% under Religious Schools supplies a missionary/education argument. Both score +5 and denote opportunities, not realized profit or conversion. Colonial and humanitarian adjustments are group-specific: religious interests no longer receive blanket colonial scores. See DESIGN.md for the exact coefficient table and pending assessments. All 205 tests are offline fixtures; verify institutional caps, scoped faith/market comparisons and legal/state persistence in Victoria 3 1.13.

The 0.9.1 hotfix guards missing variables, hides state-selection internals from tooltip previews, freezes menu targets and bundles replaceable event artwork. Offline checks cannot confirm that the reported 1.13.11 access violation is resolved. See [hotfix notes](HOTFIX_0_9_1.md).

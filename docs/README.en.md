# Territorial Doctrine — Victoria 3 1.13

Version **0.3.0-alpha.1** includes English and Simplified Chinese. Four doctrine laws govern territorial claims, individual admission bills and relinquishing lost claims. All governments and power structures share a 10% base passage chance; selected justifications supply institutional adjustments. Additional claim infamy and integration bureaucracy depend on institutions and local conditions.

Each owned, unincorporated non-homeland state needs its own admission bill. Passage unlocks only that state; changing owners invalidates approval. Lost regions with existing claims or primary-cultural homelands can be relinquished individually without changing cultural homelands or sovereignty. Vanilla diplomatic plays and war goals remain available.

Admission and relinquishment apply to all countries. New claims and construction pledges currently expose only the Spain–Al Rif example. Existing incorporated states are exempt on initialization; new non-homeland acquisitions require admission. Historical registration, general claim selection and expansion AI are pending.

**This is an offline-validated alpha. Loading and gameplay in the Victoria 3 1.13 engine have not been tested.** Use a new test save; v0.2 country-level admissions are not migrated. Former-ruler costs default to neutral where no reliable owner history exists, such as initially owned colonies and some newly split states.

Python 3.10+ with no third-party packages:

```bash
python3 tools/generate.py --check
python3 -m unittest discover -s tests -v
python3 tools/validate.py
python3 tools/scenario.py
python3 tools/package.py
```

Extract `dist/territorial_doctrine-0.3.0-alpha.1.zip` into your **user-data** `Victoria 3/mod/` directory and enable the mod in a launcher playset. Alternatively, run `python3 tools/package.py --install-dir "/path/to/your/Victoria 3/mod"`; existing installs are never overwritten. Switch the game's language to English or Simplified Chinese to select localization.

Use “Process a Non-Homeland State,” browse one candidate, select a justification, and submit that state's bill. After passage, select it for regular incorporation or the one-year fast track. Regular incorporation is started in the vanilla state UI. Use “Relinquish a Lost Territorial Claim” for a wholly lost claimed or homeland region. The mod's reasons apply to its bills; vanilla diplomacy receives no additional reason menu.

Full rules and required engine checks: [Design](DESIGN.md), [Testing](TESTING.md), [Chinese installation guide](INSTALL.md).

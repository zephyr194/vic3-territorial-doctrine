#!/usr/bin/env python3
"""Run deterministic territorial, colonial and war-policy examples offline."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from territorial_doctrine.model import (Bill, Conditions, Integration, Target,
    final_probability, integration_cost, round_probability, colonial_tendencies,
    WarGoal, WarMandate)  # noqa: E402


def main():
    target = Target(1_000_000, focus_ready=True, strategic_site=True)
    assert target.eligible('strategic_frontiers')
    p = round_probability(55, 20, legitimacy=50,
                          reason='security', government='monarchy', power='autocracy')
    print(f'Spain claim fixture: round={p:.1%}, final={final_probability(p):.1%}')
    bill = Bill()
    for day, roll in zip((90, 180, 270, 360, 450), (.1, .8, .2, .7, .3)):
        print(f'Day {day}: {bill.checkpoint(day, p, roll).value}; '
              f'successes={bill.successes}, failures={bill.failures}')
    print('Sovereignty acquisition is external; admission is a separate bill.')
    admission = Bill(started_day=600)
    for day in (690, 780, 870):
        admission.checkpoint(day, .7, .1)
    assert admission.status.value == 'passed'
    cost = integration_cost(1_000_000, 'strategic_frontiers', fast=True)
    eligible = Conditions(True, True, 60, 0, .19, .09, .9, .8)
    project = Integration()
    for _ in range(12):
        project.tick(eligible)
    assert project.status == 'incorporated'
    print(f'Admission passed; fast bureaucracy cost={cost}; '
          f'{project.months} eligible months -> {project.status}. Cultures/religions unchanged.')
    for stage in range(3):
        expansion, acceptance = colonial_tendencies('exploitation', stage)
        print(f'Exploitation stage {stage}: expansion score {expansion:+}; admission score {acceptance:+}')
    mandate = WarMandate('imperial_expansion', (WarGoal('conquer_state', ('A','B')),), {'A'})
    total = sum(mandate.tick() for _ in range(12))
    assert total == 20
    print(f'Only A approved for war targeting A+B: extra exhaustion {total} (capped).')
    authorized = WarMandate('imperial_expansion', (WarGoal('conquer_state', ('A','B')),), {'A','B'})
    assert authorized.tick() == 0
    print('Both targets approved with expansion doctrine: no additional mod exhaustion.')


if __name__ == '__main__':
    main()

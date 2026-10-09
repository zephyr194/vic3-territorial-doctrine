#!/usr/bin/env python3
"""Run a deterministic Spain -> Al Rif reference scenario, without the game."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from territorial_doctrine.model import (Bill, Conditions, Integration, Target,
    final_probability, integration_cost, round_probability)  # noqa: E402


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


if __name__ == '__main__':
    main()

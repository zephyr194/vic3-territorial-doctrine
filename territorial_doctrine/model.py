"""Executable balance specification. This module does not operate on game saves."""
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
import json
from math import ceil
from pathlib import Path

RULES = json.loads(Path(__file__).with_name("rules.json").read_text(encoding="utf-8"))
DOCTRINES = tuple(RULES["doctrines"])


def _range(value: float, low: float, high: float, name: str) -> None:
    if not low <= value <= high:
        raise ValueError(f"{name} must be in [{low}, {high}]")


def political_weight(score: float) -> float:
    """Fraction of IG clout counted, with negative values denoting opposition."""
    if score >= 20:
        return 1.0
    if score >= 5:
        return 0.5
    if score > -5:
        return 0.0
    if score > -20:
        return -0.5
    return -1.0


def group_scores(doctrine: str, *, admission: bool = False,
                 renunciation: bool = False,
                 security: bool = False, scarce_resource: bool = False,
                 compatriots: bool = False, discriminatory: bool = False,
                 conscription: bool = False, great_power_risk: bool = False,
                 pledges: tuple[str, ...] = (),
                 leader_adjustments: dict[str, float] | None = None,
                 broken_pledges: tuple[str, ...] = ()) -> dict[str, float]:
    index = DOCTRINES.index(doctrine)
    if len(pledges) > 2 or len(set(pledges)) != len(pledges):
        raise ValueError("At most two pledges to distinct groups")
    scores = {g: row[index] * 10.0 for g, row in RULES["groups"].items()}
    for g in (*pledges, *broken_pledges, *(leader_adjustments or {})):
        if g not in scores:
            raise ValueError(f"Unknown interest group: {g}")
    if security:
        scores["armed_forces"] += 15
    if scarce_resource:
        scores["industrialists"] += 15
    if compatriots:
        scores["petty_bourgeoisie"] += 15
    if admission:
        scores["intelligentsia"] += 15
        scores["trade_unions"] += 15
    if renunciation:
        for group, value in {'armed_forces': -20, 'landowners': -10,
                             'petty_bourgeoisie': -15, 'intelligentsia': 10,
                             'trade_unions': 10, 'rural_folk': 10}.items():
            scores[group] += value
    if discriminatory:
        scores["intelligentsia"] -= 20
    if conscription:
        scores["rural_folk"] -= 15
    if great_power_risk:
        scores["armed_forces"] -= 15
    for g in pledges:
        scores[g] += 10
    for g in broken_pledges:
        scores[g] -= 10
    for g, adjustment in (leader_adjustments or {}).items():
        scores[g] += adjustment
    return scores


def political_forces(scores: dict[str, float], clout: dict[str, float]) -> tuple[float, float]:
    if set(clout) - set(scores):
        raise ValueError("Clout contains unknown groups")
    for value in clout.values():
        _range(value, 0, 100, "clout")
    if sum(clout.values()) > 100 + 1e-9:
        raise ValueError("Total clout exceeds 100 percent")
    weighted = [political_weight(scores[g]) * v for g, v in clout.items()]
    return sum(max(0, v) for v in weighted), sum(max(0, -v) for v in weighted)


def round_probability(support: float, opposition: float, *, legitimacy: float,
                      reason: str | None = None, government: str = "other",
                      power: str = "other",
                      fiscal_crisis: bool = False, at_war: bool = False,
                      great_power_risk: bool = False,
                      target_population_ratio: float = 0) -> float:
    for value, name in ((support, "support"), (opposition, "opposition"),
                        (legitimacy, "legitimacy")):
        _range(value, 0, 100, name)
    if support + opposition > 100 + 1e-9:
        raise ValueError("Support and opposition exceed total clout")
    if target_population_ratio < 0:
        raise ValueError("Population ratio must be nonnegative")
    bonus = reason_bonus(reason, government, power)
    risk = 5 * (fiscal_crisis + at_war + great_power_risk)
    size = 10 if target_population_ratio >= 0.5 else 5 if target_population_ratio >= 0.2 else 0
    raw = RULES['bill']['base_probability'] + 0.6 * support - 0.4 * opposition + bonus + 0.2 * (legitimacy - 50) - risk - size
    return min(85, max(5, raw)) / 100


def final_probability(p: float) -> float:
    """Exact probability of reaching three successes before three failures."""
    _range(p, 0, 1, "probability")

    @lru_cache(None)
    def solve(success: int, failure: int) -> float:
        if success == 3:
            return 1.0
        if failure == 3:
            return 0.0
        return p * solve(success + 1, failure) + (1 - p) * solve(success, failure + 1)

    return solve(0, 0)


@dataclass(frozen=True)
class Target:
    population: int
    focus_ready: bool = False
    historical_registry: bool = False
    treaty_right: bool = False
    primary_homeland: bool = False
    adjacent: bool = False
    strategic_site: bool = False
    discovered_resource: bool = False
    resource_levels: int = 0
    price_ratio: float = 1
    shortage_months: int = 0
    compatriot_population: int = 0
    foreign: bool = True
    diplomatic_target: bool = True
    renounced: bool = False

    def eligible(self, doctrine: str) -> bool:
        if self.population <= 0 or not self.foreign or not self.diplomatic_target or self.renounced:
            return False
        if doctrine == "status_quo":
            return False
        if doctrine == "historical_rights":
            return self.historical_registry or self.treaty_right or self.primary_homeland
        if doctrine == "imperial_expansion":
            return self.focus_ready
        if doctrine != "strategic_frontiers":
            raise ValueError(f"Unknown doctrine: {doctrine}")
        resource = (self.discovered_resource and self.resource_levels >= 5
                    and self.price_ratio > 1.2 and self.shortage_months >= 3)
        compatriots = (self.compatriot_population >= 50_000
                       and self.compatriot_population / self.population >= 0.2)
        return self.adjacent or self.focus_ready and (self.strategic_site or resource or compatriots)


class BillStatus(str, Enum):
    ACTIVE = "active"
    PASSED = "passed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class Bill:
    """At most one round per due date; RNG rolls are supplied by the caller."""
    started_day: int = 0
    successes: int = 0
    failures: int = 0
    status: BillStatus = BillStatus.ACTIVE
    cooldown_until: int = 0
    next_day: int = field(init=False)

    def __post_init__(self):
        self.next_day = self.started_day + RULES["bill"]["round_days"]

    def checkpoint(self, day: int, p: float, roll: float) -> BillStatus:
        _range(p, 0, 1, "probability")
        if not 0 <= roll < 1:
            raise ValueError("Roll must be in [0, 1)")
        if self.status != BillStatus.ACTIVE or day < self.next_day:
            raise ValueError("Bill is closed or checkpoint is not due")
        self.successes += roll < p
        self.failures += roll >= p
        self.next_day = day + RULES["bill"]["round_days"]
        if self.successes == 3:
            self.status = BillStatus.PASSED
        elif self.failures == 3:
            self.status = BillStatus.REJECTED
            self.cooldown_until = day + RULES["bill"]["cooldown_days"]
        return self.status

    def cancel(self, day: int) -> None:
        if self.status != BillStatus.ACTIVE:
            raise ValueError("Bill is already closed")
        self.status = BillStatus.CANCELLED
        self.cooldown_until = day + RULES["bill"]["cooldown_days"]


def reason_bonus(reason: str | None, government: str, power: str) -> float:
    if government not in ('monarchy', 'republic', 'other') or power not in RULES['regimes']:
        raise ValueError("Unknown government or power structure")
    if reason is None:
        return 0.0
    r = RULES['reasons'][reason]
    return r['government'][government] + r['power'][power]


def claim_infamy(doctrine: str, reason: str, target_power: str) -> int:
    return ceil(RULES['doctrines'][doctrine]['infamy']
                * RULES['reasons'][reason]['cost_multiplier']
                * RULES['regimes'][target_power]['diplomatic_multiplier'])


def integration_cost(population: int, doctrine: str, *, fast: bool,
                     reason: str | None = None, actor_power: str = "other",
                     source_power: str = "other", turmoil: float = 0,
                     devastation: float = 0, accepted_share: float = 1) -> int:
    if population < 0:
        raise ValueError("Population must be nonnegative")
    base = ceil(25 + 25 * population / 1_000_000)
    for value, label in ((turmoil, 'turmoil'), (devastation, 'devastation'), (accepted_share, 'accepted_share')):
        _range(value, 0, 1, label)
    conditions = 1 + .5 * turmoil + .5 * devastation + .25 * (1 - accepted_share)
    return ceil(base * RULES["doctrines"][doctrine]["cost_multiplier"] * (2 if fast else 1)
                * RULES['regimes'][actor_power]['actor_administration_multiplier']
                * RULES['regimes'][source_power]['inherited_administration_multiplier']
                * (RULES['reasons'][reason]['cost_multiplier'] if reason else 1) * conditions)


@dataclass
class OwnedTerritory:
    key: str
    owner: str
    homeland: bool = False
    incorporated: bool = False
    treaty_port: bool = False
    admitted_owner: str | None = None
    source_power: str = 'other'
    reason: str | None = None

    def needs_admission(self, country: str) -> bool:
        return (self.owner == country and not self.homeland and not self.incorporated
                and not self.treaty_port and self.admitted_owner != country)

    def transfer(self, new_owner: str, former_power: str, *, homeland: bool = False) -> None:
        if new_owner == self.owner:
            return
        self.owner = new_owner
        self.source_power = former_power
        self.homeland = homeland
        self.admitted_owner = None
        self.reason = None
        if not homeland and not self.treaty_port:
            self.incorporated = False


@dataclass
class TerritorialAgenda:
    country: str
    active_target: str | None = None
    cooldown_until: int = 0

    def start(self, state: OwnedTerritory, day: int) -> None:
        if self.active_target or day < self.cooldown_until or not state.needs_admission(self.country):
            raise ValueError('Only one eligible owned state may be legislated at a time')
        self.active_target = state.key

    def resolve(self, state: OwnedTerritory, *, passed: bool, day: int, reason: str) -> None:
        if self.active_target != state.key:
            raise ValueError('Resolution must address the active state')
        if not state.needs_admission(self.country):
            passed = False
        if passed:
            state.admitted_owner = self.country
            state.reason = reason
        else:
            self.cooldown_until = day + RULES['bill']['cooldown_days']
        self.active_target = None


@dataclass
class LostTerritory:
    region: str
    owner: str
    claimant: str
    homeland: bool = False
    claimed: bool = False
    renounced: bool = False

    def eligible(self) -> bool:
        return self.owner != self.claimant and (self.claimed or self.homeland) and not self.renounced

    def renounce(self) -> None:
        if not self.eligible():
            raise ValueError('Only an unrenounced lost homeland or claim can be relinquished')
        self.claimed = False
        self.renounced = True
        # Homeland identity and sovereignty remain unchanged.


@dataclass(frozen=True)
class Conditions:
    sovereign_owner: bool
    admitted: bool
    legitimacy: float
    bureaucracy_after_cost: float
    turmoil: float
    devastation: float
    market_access: float
    accepted_population_share: float

    def valid(self) -> bool:
        r = RULES["integration"]
        return (self.sovereign_owner and self.admitted and self.legitimacy >= r["legitimacy"]
                and self.bureaucracy_after_cost >= 0 and self.turmoil < r["turmoil_below"]
                and self.devastation < r["devastation_below"]
                and self.market_access >= r["market_access"]
                and self.accepted_population_share >= r["accepted_share"])


@dataclass
class Integration:
    months: int = 0
    consecutive_invalid: int = 0
    status: str = "fast"

    def tick(self, conditions: Conditions) -> str:
        if self.status != "fast":
            raise ValueError("Integration is no longer on the fast track")
        if not conditions.sovereign_owner:
            self.status = "lost"
        elif conditions.valid():
            self.months += 1
            self.consecutive_invalid = 0
            if self.months == RULES["integration"]["valid_months"]:
                self.status = "incorporated"
        else:
            self.consecutive_invalid += 1
            if self.consecutive_invalid == RULES["integration"]["fallback_months"]:
                self.status = "regular"
        return self.status


@dataclass
class ConstructionPledge:
    """An obligation from a passed bill; first acquisition starts the deadline.

    The reference model uses a 365-day year; native scripts use calendar years.
    """
    group: str
    baseline: int | None = None
    deadline: int | None = None
    status: str = "awaiting_acquisition"
    penalty_until: int = 0

    def tick(self, day: int, *, owns_target: bool, building_levels: int) -> str:
        if self.status in ("fulfilled", "broken"):
            return self.status
        if self.baseline is None and owns_target:
            self.baseline = building_levels
            self.deadline = day + 3 * 365
            self.status = "pending"
        if self.deadline is not None:
            if day >= self.deadline:
                self.status = "broken"
                self.penalty_until = day + 5 * 365
            elif owns_target and building_levels > self.baseline:
                self.status = "fulfilled"
        return self.status

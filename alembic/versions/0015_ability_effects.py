"""ability effects: abilities are built from catalog effects instead of one effect, condition, area and second
condition

Adds abilities.effects (a list of {"key": ...}, see classes/combat/Effects.py), converts the abilities that exist to
the nearest catalog effects, and drops effect, condition, area, secondary and passive. Ability, spell and passive keys
are spelled out here so the migration does not depend on the catalog changing later. A downgrade brings the old columns
back empty (abilities keep their effects column's data only until the downgrade).

Comes before 0023_drop_legacy_combat, which waits until the old tables have been imported.

Revision ID: 0015_ability_effects
Revises: 0014_bad_streak
Create Date: 2026-11-15 22:00:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0015_ability_effects'
down_revision: Union[str, None] = '0014_bad_streak'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (kind, old effect) -> the catalog effect that does the same thing.
MAIN = {
    ("spell", "damage") : "bolt", ("spell", "heal") : "mend", ("spell", "shield") : "ward",
    ("ability", "damage") : "strike", ("ability", "heal") : "first_aid", ("ability", "shield") : "guard",
}
# (kind, condition) -> a catalog effect that applies it with a save (or gives it, for boosts).
CONDITION = {
    ("spell", "stunned") : "hold_person", ("spell", "weakened") : "bane", ("spell", "slowed") : "slow",
    ("spell", "burning") : "immolate", ("spell", "bleeding") : "wither", ("spell", "blinded") : "blinding_light",
    ("spell", "marked") : "evil_eye", ("spell", "silenced") : "deafening_silence",
    ("spell", "inspired") : "divine_favor", ("spell", "regenerating") : "regeneration",
    ("ability", "stunned") : "flashbang", ("ability", "weakened") : "demoralize", ("ability", "slowed") : "caltrops",
    ("ability", "burning") : "firebomb", ("ability", "bleeding") : "caltrops", ("ability", "blinded") : "sand_in_eyes",
    ("ability", "marked") : "expose_weakness", ("ability", "silenced") : "flashbang",
    ("ability", "inspired") : "rally", ("ability", "regenerating") : "rally",
}
AREA = {"spell" : "widened", "ability" : "sweeping"}
# Old passive parts -> a physical passive effect (passives used to be abilities only).
BONUS = {("to_hit", None) : "weapon_training", ("to_hit", "melee") : "brawler", ("to_hit", "ranged") : "keen_eye",
         ("to_hit", "magic") : "weapon_training", ("damage", None) : "brute", ("damage", "melee") : "brute",
         ("damage", "ranged") : "deadeye", ("damage", "magic") : "brute", ("ac", None) : "nimble",
         ("dt", None) : "thick_hide", ("hp", None) : "toughness", ("ap", None) : "quick_reflexes",
         ("sequence", None) : "quick_reflexes"}
IMMUNE = {"stunned" : "steady", "prone" : "sure_footed", "frightened" : "fearless", "poisoned" : "poison_immunity",
          "bleeding" : "bloodless"}
STRONG_HIT = {"prone" : "crushing_blows", "bleeding" : "bleeder", "stunned" : "staggering"}
TRIGGER = {"regenerate" : "regeneration_passive", "last_stand" : "undying", "counter" : "counterattack"}
AURA = {"to_hit" : "commander", "damage" : "war_banner", "ac" : "protector"}
STACKS = {"to_hit" : "fury", "damage" : "vengeance", "ac" : "toughened"}


def active_effects(kind: str, effect: str, condition: str | None, area: bool, secondary: str | None) -> list[dict] :
    kind = kind if kind in ("spell", "ability") else "ability"
    found = []
    key = MAIN.get((kind, effect)) or (CONDITION.get((kind, condition)) if condition else None)
    found.append(key or ("bolt" if kind == "spell" else "strike"))
    if secondary and CONDITION.get((kind, secondary)) :
        found.append(CONDITION[(kind, secondary)])
    if area :
        found.append(AREA[kind])
    return [{"key" : key} for key in dict.fromkeys(found)]


def passive_effects(data: dict) -> list[dict] :
    kind, field, scope = data.get("type"), data.get("field"), data.get("scope")
    lowered = scope.lower() if isinstance(scope, str) else None
    if kind == "bonus" :
        if lowered in (None, "melee", "ranged", "magic") :
            return [{"key" : BONUS.get((field, lowered), "weapon_training")}]
        return [{"key" : "specialist" if field == "damage" else "trained_aim", "target" : scope}]
    if kind == "resist" :
        if lowered == "magic" :
            return [{"key" : "magic_resistance"}]
        if lowered == "physical" :
            return [{"key" : "resistance_physical"}]
        return [{"key" : "resistance_any", "target" : scope}]
    if kind == "immune" :
        return [{"key" : IMMUNE.get(data.get("condition"), "steady")}]
    if kind == "trigger" :
        if data.get("trigger") == "on_strong_hit" :
            return [{"key" : STRONG_HIT.get(data.get("condition"), "bleeder")}]
        return [{"key" : TRIGGER.get(data.get("trigger"), "regeneration_passive")}]
    if kind == "aura" :
        return [{"key" : AURA.get(field, "commander")}]
    if kind == "stacks" :
        entry = {"key" : STACKS.get(field, "vengeance"), "target" : scope or "any"}
        if data.get("limit") :
            entry["limit"] = data["limit"]
        return [entry]
    return []


def upgrade() -> None:
    op.add_column('abilities', sa.Column('effects', sa.JSON(), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT id, kind, effect, condition, area, secondary, activation, passive FROM abilities")).fetchall()
    for row in rows :
        passive = row.passive if isinstance(row.passive, dict) else json.loads(row.passive) if row.passive else {}
        if row.activation == "passive" :
            effects = passive_effects(passive)
        else :
            effects = active_effects(row.kind, row.effect, row.condition, bool(row.area), row.secondary)
        connection.execute(sa.text("UPDATE abilities SET effects = :effects WHERE id = :id"),
                           {"effects" : json.dumps(effects), "id" : row.id})
    op.drop_column('abilities', 'effect')
    op.drop_column('abilities', 'condition')
    op.drop_column('abilities', 'area')
    op.drop_column('abilities', 'secondary')
    op.drop_column('abilities', 'passive')


def downgrade() -> None:
    op.add_column('abilities', sa.Column('passive', sa.JSON(), nullable=True))
    op.add_column('abilities', sa.Column('secondary', sa.String(length=16), nullable=True))
    op.add_column('abilities', sa.Column('area', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('abilities', sa.Column('condition', sa.String(length=16), nullable=True))
    op.add_column('abilities', sa.Column('effect', sa.String(length=16), server_default='damage', nullable=False))
    op.drop_column('abilities', 'effects')

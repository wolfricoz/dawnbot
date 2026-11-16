# Effect balance report

2005 effects, 200 fights each in two scenarios (a duel and a 2-vs-2 team fight, everyone in DT 2 armor). A side that only attacks wins 50% of duels and 49% of team fights. Run `python -m classes.combat.Balance` to make a new one; see classes/combat/Balance.py for the method.

0 too strong, 13 too weak, 363 worse than attacking.

## Cantrip (1561 effects, median win rate 48% / 50% duel / team)

| Effect | Realm | AP | Duel | Team | Verdict |
|---|---|---|---|---|---|
| Gust (`gust`) | magic | 4 | 44% | 43% | worse than attacking |
| Dream Judgement (`dream_judgement`) | magic | 4 | 44% | 43% | worse than attacking |
| Bone Hex (`bone_hex`) | magic | 3 | 44% | 40% | worse than attacking |
| Mirror Grasp (`mirror_grasp`) | magic | 4 | 44% | 39% | worse than attacking |
| Finishing Trident Jab (`trident_finishing`) | physical | 4 | 44% | 43% | worse than attacking |
| Chill Touch (`chill_touch`) | magic | 4 | 38% | 44% | worse than attacking |
| Compel (`compel`) | magic | 3 | 32% | 44% | worse than attacking |
| Ash Mantle (`ash_mantle`) | magic | 3 | 42% | 44% | worse than attacking |
| Lightning Grasp (`lightning_grasp`) | magic | 4 | 40% | 44% | worse than attacking |
| Sand Curse (`sand_curse`) | magic | 3 | 18% | 44% | worse than attacking |
| Sonic Hex (`sound_hex`) | magic | 3 | 18% | 44% | worse than attacking |
| Star Dart (`star_dart`) | magic | 4 | 44% | 44% | worse than attacking |
| Dark Burst (`dark_burst`) | magic | 3 | 17% | 44% | worse than attacking |
| Dream Burst (`dream_burst`) | magic | 3 | 24% | 44% | worse than attacking |
| Rune Mantle (`rune_mantle`) | magic | 3 | 38% | 44% | worse than attacking |
| Card Veil (`card_veil`) | magic | 4 | 44% | 34% | worse than attacking |
| Chain Mantle (`chain_mantle`) | magic | 3 | 38% | 44% | worse than attacking |
| Mirror Curse (`mirror_curse`) | magic | 3 | 20% | 44% | worse than attacking |
| Finishing Flail Swing (`flail_finishing`) | physical | 4 | 44% | 40% | worse than attacking |
| Piercing Javelin Throw (`javelin_piercing`) | physical | 4 | 42% | 44% | worse than attacking |
| Precise Rifle Round (`rifle_precise`) | physical | 4 | 42% | 44% | worse than attacking |
| Sonic Scream (`sonic_scream`) | magic | 4 | 38% | 43% | worse than attacking |
| Slow (`slow`) | magic | 3 | 24% | 43% | worse than attacking |
| Sanctuary (`sanctuary`) | magic | 4 | 43% | 30% | worse than attacking |
| Protection (`protection`) | magic | 3 | 43% | 38% | worse than attacking |
| Blood Frenzy (`blood_frenzy`) | physical | 3 | 40% | 43% | worse than attacking |
| Fire Mantle (`fire_mantle`) | magic | 3 | 41% | 43% | worse than attacking |
| Ash Grasp (`ash_grasp`) | magic | 4 | 41% | 43% | worse than attacking |
| Hellfire Grasp (`hellfire_grasp`) | magic | 4 | 36% | 43% | worse than attacking |
| Ice Dart (`ice_dart`) | magic | 4 | 37% | 43% | worse than attacking |
| Stone Mantle (`stone_mantle`) | magic | 3 | 38% | 43% | worse than attacking |
| Song Mantle (`song_mantle`) | magic | 3 | 43% | 37% | worse than attacking |
| Song Blessing (`song_blessing`) | magic | 3 | 36% | 43% | worse than attacking |
| Dream Dart (`dream_dart`) | magic | 4 | 36% | 43% | worse than attacking |
| Dream Curse (`dream_curse`) | magic | 3 | 18% | 43% | worse than attacking |
| Dream Mantle (`dream_mantle`) | magic | 3 | 42% | 43% | worse than attacking |
| Psychic Dart (`psychic_dart`) | magic | 4 | 37% | 43% | worse than attacking |
| Phantasmal Hex (`phantasm_hex`) | magic | 3 | 23% | 43% | worse than attacking |
| Phantasmal Grasp (`phantasm_grasp`) | magic | 4 | 43% | 41% | worse than attacking |
| Arcane Burst (`arcane_burst`) | magic | 3 | 24% | 43% | worse than attacking |
| Chaos Brand (`chaos_brand`) | magic | 4 | 43% | 42% | worse than attacking |
| Chaos Grasp (`chaos_grasp`) | magic | 4 | 43% | 38% | worse than attacking |
| Primal Hex (`primal_hex`) | magic | 3 | 42% | 43% | worse than attacking |
| Shield Slam (`shield_strike`) | physical | 3 | 39% | 43% | worse than attacking |
| Piercing Bow Shot (`bow_piercing`) | physical | 4 | 42% | 43% | worse than attacking |
| Frostbite (`frostbite`) | magic | 3 | 38% | 42% | worse than attacking |
| Entangle (`entangle`) | magic | 4 | 42% | 40% | worse than attacking |
| Illusion (`illusion`) | magic | 4 | 32% | 42% | worse than attacking |
| Super Speed (`super_speed`) | physical | 3 | 31% | 42% | worse than attacking |
| Fire Grasp (`fire_grasp`) | magic | 4 | 42% | 38% | worse than attacking |
| Acid Hex (`acid_hex`) | magic | 3 | 23% | 42% | worse than attacking |
| Sonic Grasp (`sound_grasp`) | magic | 4 | 40% | 42% | worse than attacking |
| Lunar Wave (`lunar_wave`) | magic | 4 | 42% | 42% | worse than attacking |
| Dread Curse (`dread_curse`) | magic | 3 | 22% | 42% | worse than attacking |
| Blood Dart (`blood_dart`) | magic | 4 | 38% | 42% | worse than attacking |
| Death Curse (`death_curse`) | magic | 3 | 16% | 42% | worse than attacking |
| Death Leech (`death_leech`) | magic | 4 | 42% | 42% | worse than attacking |
| Rapier Feint (`rapier_feint`) | physical | 3 | 14% | 42% | worse than attacking |
| Finishing Fang Bite (`fang_finishing`) | physical | 4 | 42% | 42% | worse than attacking |
| Finishing Horn Gore (`horn_finishing`) | physical | 4 | 42% | 42% | worse than attacking |
| Vanish (`vanish`) | physical | 3 | 18% | 42% | worse than attacking |
| Dirty Trick (`sand_in_eyes`) | physical | 3 | 37% | 42% | worse than attacking |
| Ash Hex (`ash_hex`) | magic | 3 | 30% | 42% | worse than attacking |
| Thunder Wave (`thunder_wave`) | magic | 4 | 41% | 42% | worse than attacking |
| Acid Grasp (`acid_grasp`) | magic | 4 | 38% | 42% | worse than attacking |
| Song Grasp (`song_grasp`) | magic | 4 | 34% | 42% | worse than attacking |
| Dream Brand (`dream_brand`) | magic | 4 | 38% | 42% | worse than attacking |
| Dream Grasp (`dream_grasp`) | magic | 4 | 39% | 42% | worse than attacking |
| Dream Veil (`dream_veil`) | magic | 3 | 34% | 42% | worse than attacking |
| Psychic Grasp (`psychic_grasp`) | magic | 4 | 42% | 38% | worse than attacking |
| Dread Brand (`dread_brand`) | magic | 4 | 41% | 42% | worse than attacking |
| Force Hex (`force_hex`) | magic | 3 | 26% | 42% | worse than attacking |
| Arcane Veil (`arcane_veil`) | magic | 3 | 36% | 42% | worse than attacking |
| Chaos Hex (`chaos_hex`) | magic | 3 | 14% | 42% | worse than attacking |
| Blood Hex (`blood_hex`) | magic | 3 | 40% | 42% | worse than attacking |
| Rot Grasp (`rot_grasp`) | magic | 4 | 42% | 42% | worse than attacking |
| Soul Grasp (`soul_grasp`) | magic | 4 | 42% | 42% | worse than attacking |
| Card Curse (`card_curse`) | magic | 3 | 20% | 42% | worse than attacking |
| Flail Swing (`flail_strike`) | physical | 3 | 41% | 42% | worse than attacking |
| Suppressing Rifle Fire (`rifle_suppressing`) | physical | 3 | 32% | 42% | worse than attacking |
| Ice Shackles (`ice_shackles`) | magic | 4 | 38% | 42% | worse than attacking |
| Wind Wall (`wind_wall`) | magic | 4 | 42% | 40% | worse than attacking |
| Divine Favor (`divine_favor`) | magic | 3 | 36% | 42% | worse than attacking |
| Barkskin (`barkskin`) | magic | 3 | 40% | 42% | worse than attacking |
| Rally (`rally`) | physical | 3 | 42% | 42% | worse than attacking |
| Net (`net`) | physical | 4 | 42% | 42% | worse than attacking |
| Magma Veil (`magma_veil`) | magic | 3 | 35% | 42% | worse than attacking |
| Crystal Hex (`crystal_hex`) | magic | 3 | 38% | 42% | worse than attacking |
| Shadow Hex (`shadow_hex`) | magic | 3 | 25% | 42% | worse than attacking |
| Psychic Burst (`psychic_burst`) | magic | 3 | 28% | 42% | worse than attacking |
| Force Veil (`force_veil`) | magic | 3 | 42% | 37% | worse than attacking |
| Card Grasp (`card_grasp`) | magic | 4 | 42% | 42% | worse than attacking |
| Suppressing Sling Fire (`sling_suppressing`) | physical | 3 | 32% | 42% | worse than attacking |
| Gravity Well (`gravity_well`) | magic | 4 | 41% | 40% | worse than attacking |
| Mirror Image (`mirror_image`) | magic | 4 | 41% | 28% | worse than attacking |
| Frost Hex (`frost_hex`) | magic | 3 | 34% | 41% | worse than attacking |
| Ice Bolt (`ice_bolt`) | magic | 3 | 31% | 41% | worse than attacking |
| Star Grasp (`star_grasp`) | magic | 4 | 36% | 41% | worse than attacking |
| Lunar Grasp (`lunar_grasp`) | magic | 4 | 30% | 41% | worse than attacking |
| Dread Grasp (`dread_grasp`) | magic | 4 | 36% | 41% | worse than attacking |
| Bone Burst (`bone_burst`) | magic | 3 | 28% | 41% | worse than attacking |
| Suppressing Bow Fire (`bow_suppressing`) | physical | 3 | 28% | 41% | worse than attacking |
| Static Field (`static_field`) | magic | 4 | 25% | 40% | worse than attacking |
| Mind Fog (`mind_blank`) | magic | 4 | 30% | 40% | worse than attacking |
| Demoralize (`demoralize`) | physical | 4 | 40% | 40% | worse than attacking |
| Water Curse (`water_curse`) | magic | 3 | 16% | 40% | worse than attacking |
| Crystal Burst (`crystal_burst`) | magic | 3 | 24% | 40% | worse than attacking |
| Iron Mantle (`metal_mantle`) | magic | 3 | 38% | 40% | worse than attacking |
| Sonic Curse (`sound_curse`) | magic | 3 | 18% | 40% | worse than attacking |
| Holy Grasp (`holy_grasp`) | magic | 4 | 38% | 40% | worse than attacking |
| Star Hex (`star_hex`) | magic | 3 | 22% | 40% | worse than attacking |
| Star Veil (`star_veil`) | magic | 3 | 38% | 40% | worse than attacking |
| Blood Grasp (`blood_grasp`) | magic | 4 | 40% | 36% | worse than attacking |
| Death Burst (`death_burst`) | magic | 3 | 20% | 40% | worse than attacking |
| Chain Hex (`chain_hex`) | magic | 3 | 30% | 40% | worse than attacking |
| Ink Hex (`ink_hex`) | magic | 3 | 29% | 40% | worse than attacking |
| Horn Feint (`horn_feint`) | physical | 3 | 20% | 40% | worse than attacking |
| Darkness (`darkness`) | magic | 3 | 32% | 40% | worse than attacking |
| Void Touch (`void_touch`) | magic | 4 | 26% | 40% | worse than attacking |
| Magma Curse (`magma_curse`) | magic | 3 | 20% | 40% | worse than attacking |
| Frost Grasp (`frost_grasp`) | magic | 4 | 36% | 40% | worse than attacking |
| Ice Judgement (`ice_judgement`) | magic | 4 | 40% | 40% | worse than attacking |
| Water Grasp (`water_grasp`) | magic | 4 | 38% | 40% | worse than attacking |
| Thunder Grasp (`thunder_grasp`) | magic | 4 | 36% | 40% | worse than attacking |
| Earth Veil (`earth_veil`) | magic | 3 | 38% | 40% | worse than attacking |
| Wind Curse (`wind_curse`) | magic | 3 | 19% | 40% | worse than attacking |
| Wind Veil (`wind_veil`) | magic | 4 | 40% | 33% | worse than attacking |
| Light Hex (`light_hex`) | magic | 3 | 34% | 40% | worse than attacking |
| Light Veil (`light_veil`) | magic | 3 | 29% | 40% | worse than attacking |
| Holy Hex (`holy_hex`) | magic | 3 | 30% | 40% | worse than attacking |
| Dark Hex (`dark_hex`) | magic | 3 | 28% | 40% | worse than attacking |
| Dark Grasp (`dark_grasp`) | magic | 4 | 38% | 40% | worse than attacking |
| Dark Curse (`dark_curse`) | magic | 3 | 22% | 40% | worse than attacking |
| Phantasmal Dart (`phantasm_dart`) | magic | 4 | 38% | 40% | worse than attacking |
| Arcane Grasp (`arcane_grasp`) | magic | 4 | 37% | 40% | worse than attacking |
| Rune Hex (`rune_hex`) | magic | 3 | 26% | 40% | worse than attacking |
| Chaos Curse (`chaos_curse`) | magic | 3 | 17% | 40% | worse than attacking |
| Thorn Hex (`thorn_hex`) | magic | 3 | 38% | 40% | worse than attacking |
| Life Veil (`life_veil`) | magic | 3 | 40% | 37% | worse than attacking |
| Mirror Hex (`mirror_hex`) | magic | 3 | 28% | 40% | worse than attacking |
| Ice Armor (`ice_armor`) | magic | 3 | 36% | 40% | worse than attacking |
| Wither (`wither`) | magic | 4 | 26% | 40% | worse than attacking |
| Vampire Form (`vampire_form`) | magic | 4 | 33% | 40% | worse than attacking |
| Stone Grasp (`stone_grasp`) | magic | 4 | 37% | 40% | worse than attacking |
| Iron Veil (`metal_veil`) | magic | 3 | 35% | 40% | worse than attacking |
| Wind Hex (`wind_hex`) | magic | 3 | 26% | 40% | worse than attacking |
| Lunar Hex (`lunar_hex`) | magic | 3 | 18% | 40% | worse than attacking |
| Psychic Hex (`psychic_hex`) | magic | 3 | 33% | 40% | worse than attacking |
| Psychic Curse (`psychic_curse`) | magic | 3 | 21% | 40% | worse than attacking |
| Death Grasp (`death_grasp`) | magic | 4 | 39% | 40% | worse than attacking |
| Thread Veil (`thread_veil`) | magic | 4 | 40% | 39% | worse than attacking |
| Chain Veil (`chain_veil`) | magic | 3 | 40% | 37% | worse than attacking |
| Club Feint (`club_feint`) | physical | 3 | 22% | 40% | worse than attacking |
| Fist Feint (`fist_feint`) | physical | 3 | 18% | 40% | worse than attacking |
| Tail Feint (`tail_feint`) | physical | 3 | 18% | 40% | worse than attacking |
| Confusion (`confusion`) | magic | 4 | 32% | 39% | worse than attacking |
| Hex (`hex`) | magic | 3 | 16% | 39% | worse than attacking |
| Corrode (`corrode`) | magic | 3 | 18% | 39% | worse than attacking |
| Hunter's Mark (`hunters_mark`) | physical | 4 | 39% | 39% | worse than attacking |
| Iron Grasp (`metal_grasp`) | magic | 4 | 38% | 39% | worse than attacking |
| Sand Hex (`sand_hex`) | magic | 3 | 30% | 39% | worse than attacking |
| Song Curse (`song_curse`) | magic | 3 | 18% | 39% | worse than attacking |
| Lunar Curse (`lunar_curse`) | magic | 3 | 22% | 39% | worse than attacking |
| Arcane Hex (`arcane_hex`) | magic | 3 | 23% | 39% | worse than attacking |
| Primal Curse (`primal_curse`) | magic | 3 | 20% | 39% | worse than attacking |
| Ink Curse (`ink_curse`) | magic | 3 | 22% | 39% | worse than attacking |
| Fire Curse (`fire_curse`) | magic | 3 | 16% | 38% | worse than attacking |
| Iron Curse (`metal_curse`) | magic | 3 | 20% | 38% | worse than attacking |
| Wind Grasp (`wind_grasp`) | magic | 4 | 38% | 38% | worse than attacking |
| Dread Hex (`dread_hex`) | magic | 3 | 24% | 38% | worse than attacking |
| Phantasmal Curse (`phantasm_curse`) | magic | 3 | 18% | 38% | worse than attacking |
| Force Curse (`force_curse`) | magic | 3 | 14% | 38% | worse than attacking |
| Arcane Curse (`arcane_curse`) | magic | 3 | 24% | 38% | worse than attacking |
| Bone Veil (`bone_veil`) | magic | 3 | 38% | 38% | worse than attacking |
| Thorn Veil (`thorn_veil`) | magic | 3 | 38% | 36% | worse than attacking |
| Card Hex (`card_hex`) | magic | 3 | 38% | 38% | worse than attacking |
| Thread Curse (`thread_curse`) | magic | 3 | 18% | 38% | worse than attacking |
| Suppressing Crossbow Fire (`crossbow_suppressing`) | physical | 3 | 30% | 38% | worse than attacking |
| Suppressing Scattergun Fire (`scattergun_suppressing`) | physical | 3 | 34% | 38% | worse than attacking |
| Martial Feint (`martial_feint`) | physical | 3 | 15% | 38% | worse than attacking |
| Fang Feint (`fang_feint`) | physical | 3 | 24% | 38% | worse than attacking |
| Immolate (`immolate`) | magic | 3 | 26% | 38% | worse than attacking |
| Brace (`brace`) | physical | 3 | 38% | 32% | worse than attacking |
| Magma Hex (`magma_hex`) | magic | 3 | 28% | 38% | worse than attacking |
| Frost Veil (`frost_veil`) | magic | 3 | 38% | 34% | worse than attacking |
| Stone Hex (`stone_hex`) | magic | 3 | 28% | 38% | worse than attacking |
| Stone Veil (`stone_veil`) | magic | 3 | 36% | 38% | worse than attacking |
| Song Hex (`song_hex`) | magic | 3 | 18% | 38% | worse than attacking |
| Psychic Veil (`psychic_veil`) | magic | 3 | 34% | 38% | worse than attacking |
| Death Hex (`death_hex`) | magic | 3 | 18% | 38% | worse than attacking |
| Stoneskin (`stoneskin`) | magic | 3 | 35% | 38% | worse than attacking |
| Backfire (`backfire`) | physical | 2 | 34% | 38% | worse than attacking |
| Dagger Feint (`dagger_feint`) | physical | 3 | 16% | 38% | worse than attacking |
| Suppressing Hatchet Fire (`hatchet_suppressing`) | physical | 3 | 30% | 38% | worse than attacking |
| Bless (`bless`) | magic | 3 | 22% | 37% | worse than attacking |
| Clarity (`clarity`) | magic | 3 | 36% | 37% | worse than attacking |
| Shield Wall (`shield_wall`) | physical | 3 | 37% | 28% | worse than attacking |
| Distract (`distract`) | physical | 3 | 36% | 37% | worse than attacking |
| Wild Magic (`wild_magic`) | magic | 2 | 28% | 37% | worse than attacking |
| Ice Curse (`ice_curse`) | magic | 3 | 14% | 37% | worse than attacking |
| Ice Veil (`ice_veil`) | magic | 3 | 37% | 36% | worse than attacking |
| Holy Veil (`holy_veil`) | magic | 3 | 30% | 37% | worse than attacking |
| Dark Veil (`dark_veil`) | magic | 4 | 12% | 37% | worse than attacking |
| Mirror Veil (`mirror_veil`) | magic | 4 | 36% | 37% | worse than attacking |
| Chain Feint (`chain_feint`) | physical | 3 | 14% | 37% | worse than attacking |
| Trident Feint (`trident_feint`) | physical | 3 | 21% | 37% | worse than attacking |
| Glaive Feint (`glaive_feint`) | physical | 3 | 18% | 37% | worse than attacking |
| Suppressing Shuriken Fire (`shuriken_suppressing`) | physical | 3 | 34% | 37% | worse than attacking |
| Elbow Feint (`elbow_feint`) | physical | 3 | 18% | 37% | worse than attacking |
| Fire Shield (`fire_shield`) | magic | 4 | 24% | 36% | worse than attacking |
| Ash Veil (`ash_veil`) | magic | 4 | 14% | 36% | worse than attacking |
| Light Grasp (`light_grasp`) | magic | 4 | 34% | 36% | worse than attacking |
| Shadow Curse (`shadow_curse`) | magic | 3 | 18% | 36% | worse than attacking |
| Voodoo (`voodoo`) | magic | 4 | 36% | 34% | worse than attacking |
| Hellfire Hex (`hellfire_hex`) | magic | 3 | 28% | 36% | worse than attacking |
| Lightning Veil (`lightning_veil`) | magic | 4 | 28% | 36% | worse than attacking |
| Thunder Curse (`thunder_curse`) | magic | 3 | 16% | 36% | worse than attacking |
| Light Curse (`light_curse`) | magic | 3 | 18% | 36% | worse than attacking |
| Blood Curse (`blood_curse`) | magic | 3 | 19% | 36% | worse than attacking |
| Soul Veil (`soul_veil`) | magic | 3 | 24% | 36% | worse than attacking |
| Scythe Feint (`scythe_feint`) | physical | 3 | 18% | 36% | worse than attacking |
| Staff Feint (`staff_feint`) | physical | 3 | 24% | 36% | worse than attacking |
| Shield Feint (`shield_feint`) | physical | 3 | 18% | 36% | worse than attacking |
| Halberd Feint (`halberd_feint`) | physical | 3 | 20% | 36% | worse than attacking |
| Tentacle Feint (`tentacle_feint`) | physical | 3 | 16% | 36% | worse than attacking |
| Shadow Cloak (`shadow_cloak`) | magic | 4 | 14% | 36% | worse than attacking |
| Regeneration (`regeneration`) | magic | 3 | 33% | 36% | worse than attacking |
| Spell Ward (`spell_ward`) | magic | 4 | 29% | 36% | worse than attacking |
| Rot Curse (`rot_curse`) | magic | 3 | 20% | 36% | worse than attacking |
| Chain Curse (`chain_curse`) | magic | 3 | 22% | 36% | worse than attacking |
| Mace Feint (`mace_feint`) | physical | 3 | 22% | 36% | worse than attacking |
| Suppressing Pistol Fire (`pistol_suppressing`) | physical | 3 | 22% | 36% | worse than attacking |
| Claw Feint (`claw_feint`) | physical | 3 | 15% | 36% | worse than attacking |
| Precognition (`precognition`) | magic | 4 | 35% | 30% | worse than attacking |
| Stimulant (`stimulant`) | physical | 4 | 32% | 35% | worse than attacking |
| Lightning Curse (`lightning_curse`) | magic | 3 | 22% | 35% | worse than attacking |
| Rune Curse (`rune_curse`) | magic | 3 | 16% | 35% | worse than attacking |
| Bone Curse (`bone_curse`) | magic | 3 | 14% | 35% | worse than attacking |
| Spore Curse (`spore_curse`) | magic | 3 | 16% | 35% | worse than attacking |
| Axe Feint (`axe_feint`) | physical | 3 | 15% | 35% | worse than attacking |
| Flail Feint (`flail_feint`) | physical | 3 | 22% | 35% | worse than attacking |
| Wing Feint (`wing_feint`) | physical | 3 | 18% | 35% | worse than attacking |
| Silence (`deafening_silence`) | magic | 4 | 30% | 34% | worse than attacking |
| Nightmare (`nightmare`) | magic | 4 | 28% | 34% | worse than attacking |
| Intimidate (`intimidate`) | physical | 3 | 17% | 34% | worse than attacking |
| Earth Curse (`earth_curse`) | magic | 3 | 15% | 34% | worse than attacking |
| Acid Curse (`acid_curse`) | magic | 3 | 18% | 34% | worse than attacking |
| Greatsword Feint (`greatsword_feint`) | physical | 3 | 22% | 34% | worse than attacking |
| Scimitar Feint (`scimitar_feint`) | physical | 3 | 20% | 34% | worse than attacking |
| Whip Feint (`whip_feint`) | physical | 3 | 22% | 34% | worse than attacking |
| Terror (`terror`) | magic | 4 | 28% | 34% | worse than attacking |
| Expose Weakness (`expose_weakness`) | physical | 3 | 25% | 34% | worse than attacking |
| Lightning Hex (`lightning_hex`) | magic | 3 | 19% | 34% | worse than attacking |
| Phantasmal Veil (`phantasm_veil`) | magic | 4 | 13% | 34% | worse than attacking |
| Tactical Order (`tactical_order`) | physical | 4 | 34% | 25% | worse than attacking |
| Smoke Bomb (`smoke_bomb`) | physical | 3 | 32% | 34% | worse than attacking |
| Blood Price (`blood_price`) | magic | 2 | 13% | 34% | worse than attacking |
| Hellfire Curse (`hellfire_curse`) | magic | 3 | 24% | 34% | worse than attacking |
| Crystal Curse (`crystal_curse`) | magic | 3 | 20% | 34% | worse than attacking |
| Holy Curse (`holy_curse`) | magic | 3 | 12% | 34% | worse than attacking |
| Rune Veil (`rune_veil`) | magic | 4 | 24% | 34% | worse than attacking |
| Tailwind (`tailwind`) | magic | 4 | 26% | 33% | worse than attacking |
| Taunt (`taunt`) | physical | 3 | 28% | 33% | worse than attacking |
| Fire Hex (`fire_hex`) | magic | 3 | 28% | 33% | worse than attacking |
| Ash Curse (`ash_curse`) | magic | 3 | 20% | 33% | worse than attacking |
| Frost Curse (`frost_curse`) | magic | 3 | 19% | 33% | worse than attacking |
| Soul Curse (`soul_curse`) | magic | 3 | 19% | 32% | too weak |
| Haste (`haste`) | magic | 4 | 28% | 32% | worse than attacking |
| Crystal Veil (`crystal_veil`) | magic | 4 | 24% | 32% | worse than attacking |
| Sand Veil (`sand_veil`) | magic | 4 | 14% | 32% | too weak |
| Ink Veil (`ink_veil`) | magic | 4 | 14% | 32% | too weak |
| Overexertion (`overexertion`) | physical | 2 | 10% | 32% | too weak |
| Lunar Veil (`lunar_veil`) | magic | 4 | 14% | 32% | too weak |
| Dream Hex (`dream_hex`) | magic | 3 | 18% | 32% | too weak |
| Blood Veil (`blood_veil`) | magic | 4 | 32% | 28% | worse than attacking |
| Lance Feint (`lance_feint`) | physical | 3 | 17% | 32% | too weak |
| Steam Veil (`steam_veil`) | magic | 4 | 20% | 31% | too weak |
| Hammer Feint (`hammer_feint`) | physical | 3 | 16% | 31% | too weak |
| Spear Feint (`spear_feint`) | physical | 3 | 16% | 31% | too weak |
| Feint (`feint`) | physical | 3 | 19% | 30% | too weak |
| Shadow Veil (`shadow_veil`) | magic | 4 | 16% | 30% | too weak |
| Take Cover (`cover`) | physical | 4 | 18% | 30% | too weak |
| Storm Speed (`storm_speed`) | magic | 4 | 29% | 30% | worse than attacking |
| Stand Firm (`stand_firm`) | physical | 3 | 29% | 28% | worse than attacking |
| Sword Feint (`sword_feint`) | physical | 3 | 20% | 28% | worse than attacking |
| *1276 others within range* | | | | | |

## Weak (375 effects, median win rate 46% / 51% duel / team)

| Effect | Realm | AP | Duel | Team | Verdict |
|---|---|---|---|---|---|
| Suffocate (`suffocate`) | magic | 4 | 44% | 39% | worse than attacking |
| Curse (`curse`) | magic | 5 | 44% | 42% | worse than attacking |
| Crystal Torment (`crystal_torment`) | magic | 5 | 44% | 40% | worse than attacking |
| Moon Moth (`lunar_summon`) | magic | 4 | 44% | 31% | worse than attacking |
| Puppet (`thread_summon`) | magic | 4 | 44% | 40% | worse than attacking |
| Shadow Hound (`shadow_summon`) | magic | 4 | 44% | 34% | worse than attacking |
| Unstoppable (`unstoppable`) | physical | 3 | 40% | 44% | worse than attacking |
| Stone Torment (`stone_torment`) | magic | 5 | 44% | 42% | worse than attacking |
| Iron Torment (`metal_torment`) | magic | 5 | 44% | 43% | worse than attacking |
| Light Wisp (`light_summon`) | magic | 4 | 38% | 44% | worse than attacking |
| Dark Torment (`dark_torment`) | magic | 5 | 42% | 44% | worse than attacking |
| Rune Sentinel (`rune_summon`) | magic | 4 | 42% | 44% | worse than attacking |
| Thorn Creeper (`thorn_summon`) | magic | 4 | 42% | 44% | worse than attacking |
| Mirror Double (`mirror_summon`) | magic | 4 | 44% | 41% | worse than attacking |
| Spear Whirlwind (`spear_whirlwind`) | physical | 4 | 44% | 40% | worse than attacking |
| Spiritual Weapon (`spiritual_weapon`) | magic | 4 | 42% | 43% | worse than attacking |
| Stone Servant (`stone_summon`) | magic | 4 | 43% | 36% | worse than attacking |
| Wind Sprite (`wind_summon`) | magic | 4 | 39% | 43% | worse than attacking |
| Song Torment (`song_torment`) | magic | 5 | 39% | 43% | worse than attacking |
| Chaos Torment (`chaos_torment`) | magic | 5 | 42% | 43% | worse than attacking |
| Bone Torment (`bone_torment`) | magic | 5 | 36% | 43% | worse than attacking |
| Spirit Guide (`soul_summon`) | magic | 4 | 40% | 43% | worse than attacking |
| Raise Dead (`raise_dead`) | magic | 4 | 39% | 42% | worse than attacking |
| Sleep (`sleep`) | magic | 5 | 36% | 42% | worse than attacking |
| Sleeper Dart (`sleeper_dart`) | physical | 5 | 40% | 42% | worse than attacking |
| Frost Sprite (`frost_summon`) | magic | 4 | 42% | 41% | worse than attacking |
| Dream Torment (`dream_torment`) | magic | 5 | 36% | 42% | worse than attacking |
| Card Soldier (`card_summon`) | magic | 4 | 42% | 40% | worse than attacking |
| Thread Torment (`thread_torment`) | magic | 5 | 31% | 42% | worse than attacking |
| Storm Hawk (`thunder_summon`) | magic | 4 | 42% | 35% | worse than attacking |
| Earth Torment (`earth_torment`) | magic | 5 | 40% | 42% | worse than attacking |
| Spectral Hand (`force_summon`) | magic | 4 | 38% | 42% | worse than attacking |
| Rune Torment (`rune_torment`) | magic | 5 | 30% | 42% | worse than attacking |
| Chaos Imp (`chaos_summon`) | magic | 4 | 35% | 42% | worse than attacking |
| Thorn Torment (`thorn_torment`) | magic | 5 | 32% | 42% | worse than attacking |
| Spore Torment (`spore_torment`) | magic | 5 | 38% | 42% | worse than attacking |
| Fungal Creeper (`spore_summon`) | magic | 4 | 42% | 32% | worse than attacking |
| Animated Chains (`chain_summon`) | magic | 4 | 42% | 40% | worse than attacking |
| Flame Sprite (`fire_summon`) | magic | 4 | 38% | 42% | worse than attacking |
| Water Sprite (`water_summon`) | magic | 4 | 38% | 42% | worse than attacking |
| Iron Hound (`metal_summon`) | magic | 4 | 41% | 42% | worse than attacking |
| Echo (`sound_summon`) | magic | 4 | 42% | 40% | worse than attacking |
| Dream Phantom (`dream_summon`) | magic | 4 | 40% | 42% | worse than attacking |
| Rot Ghoul (`rot_summon`) | magic | 4 | 40% | 42% | worse than attacking |
| Scattergun Volley (`scattergun_volley`) | physical | 4 | 36% | 42% | worse than attacking |
| Mud Hound (`earth_summon`) | magic | 4 | 41% | 36% | worse than attacking |
| Spectral Guardian (`holy_summon`) | magic | 4 | 41% | 40% | worse than attacking |
| Shadow Torment (`shadow_torment`) | magic | 5 | 38% | 41% | worse than attacking |
| Gloom Stalker (`dark_summon`) | magic | 4 | 41% | 36% | worse than attacking |
| Phantasmal Double (`phantasm_summon`) | magic | 4 | 40% | 41% | worse than attacking |
| Arcane Familiar (`arcane_summon`) | magic | 4 | 41% | 37% | worse than attacking |
| Death Torment (`death_torment`) | magic | 5 | 41% | 41% | worse than attacking |
| Chain Torment (`chain_torment`) | magic | 5 | 34% | 41% | worse than attacking |
| Ink Torment (`ink_torment`) | magic | 5 | 41% | 40% | worse than attacking |
| Dagger Whirlwind (`dagger_whirlwind`) | physical | 4 | 40% | 41% | worse than attacking |
| Call Beast (`call_beast`) | magic | 4 | 40% | 38% | worse than attacking |
| Volley (`volley`) | physical | 4 | 40% | 38% | worse than attacking |
| Knockout Gas (`knockout_gas`) | physical | 5 | 39% | 40% | worse than attacking |
| Cinder Hound (`magma_summon`) | magic | 4 | 40% | 36% | worse than attacking |
| Spark Sprite (`lightning_summon`) | magic | 4 | 39% | 40% | worse than attacking |
| Star Mote (`star_summon`) | magic | 4 | 36% | 40% | worse than attacking |
| Thought Wisp (`psychic_summon`) | magic | 4 | 40% | 36% | worse than attacking |
| Phantasmal Torment (`phantasm_torment`) | magic | 5 | 35% | 40% | worse than attacking |
| Minor Elemental (`summon_elemental`) | magic | 4 | 38% | 40% | worse than attacking |
| Sand Torment (`sand_torment`) | magic | 5 | 34% | 40% | worse than attacking |
| Dread Wisp (`dread_summon`) | magic | 4 | 40% | 34% | worse than attacking |
| Fang Whirlwind (`fang_whirlwind`) | physical | 4 | 38% | 40% | worse than attacking |
| Lunar Torment (`lunar_torment`) | magic | 5 | 40% | 40% | worse than attacking |
| Force Torment (`force_torment`) | magic | 5 | 40% | 34% | worse than attacking |
| Spirit Wolf (`primal_summon`) | magic | 4 | 40% | 37% | worse than attacking |
| Ink Beast (`ink_summon`) | magic | 4 | 36% | 40% | worse than attacking |
| Drown (`drown`) | magic | 4 | 39% | 39% | worse than attacking |
| Imp (`hellfire_summon`) | magic | 4 | 38% | 39% | worse than attacking |
| Ice Hound (`ice_summon`) | magic | 4 | 39% | 38% | worse than attacking |
| Soul Torment (`soul_torment`) | magic | 5 | 36% | 39% | worse than attacking |
| Venom Torment (`venom_torment`) | magic | 5 | 35% | 39% | worse than attacking |
| Ash Wisp (`ash_summon`) | magic | 4 | 38% | 36% | worse than attacking |
| Acid Ooze (`acid_summon`) | magic | 4 | 37% | 34% | worse than attacking |
| Mirror Torment (`mirror_torment`) | magic | 5 | 32% | 37% | worse than attacking |
| Bodyguard (`bodyguard`) | physical | 4 | 36% | 36% | worse than attacking |
| Ice Torment (`ice_torment`) | magic | 5 | 36% | 36% | worse than attacking |
| Holy Torment (`holy_torment`) | magic | 5 | 36% | 33% | worse than attacking |
| Arcane Torment (`arcane_torment`) | magic | 5 | 34% | 35% | worse than attacking |
| Water Torment (`water_torment`) | magic | 5 | 34% | 34% | worse than attacking |
| Rebound (`mirror_ward`) | magic | 5 | 26% | 32% | worse than attacking |
| *290 others within range* | | | | | |

## Normal (69 effects, median win rate 60% / 61% duel / team)

| Effect | Realm | AP | Duel | Team | Verdict |
|---|---|---|---|---|---|
| Dread Doom (`dread_doom`) | magic | 5 | 44% | 38% | worse than attacking |
| Dark Doom (`dark_doom`) | magic | 5 | 42% | 40% | worse than attacking |
| Blood Doom (`blood_doom`) | magic | 5 | 36% | 42% | worse than attacking |
| Death Mark (`death_mark`) | magic | 5 | 40% | 40% | worse than attacking |
| Shadow Doom (`shadow_doom`) | magic | 5 | 40% | 34% | worse than attacking |
| Hellfire Doom (`hellfire_doom`) | magic | 5 | 39% | 32% | worse than attacking |
| *63 others within range* | | | | | |

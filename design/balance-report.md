# Effect balance report

2005 effects, 200 fights each. A hero that only attacks wins 48% of the time. Run `python -m classes.combat.Balance` to make a new one; see classes/combat/Balance.py for the method.

13 too strong, 9 too weak, 480 worse than attacking.

## Cantrip (1561 effects, median win rate 48%)

| Effect | Realm | AP | Win rate | Rounds | Verdict |
|---|---|---|---|---|---|
| Magic Missile (`magic_missile`) | magic | 4 | 81% | 3.3 | too strong |
| Ricochet (`ricochet`) | physical | 4 | 76% | 4.8 | too strong |
| Earth Barrage (`earth_barrage`) | magic | 4 | 72% | 4.6 | too strong |
| Double Sling Stone (`sling_double`) | physical | 4 | 72% | 4.5 | too strong |
| Sand Barrage (`sand_barrage`) | magic | 4 | 71% | 4.6 | too strong |
| Chain Barrage (`chain_barrage`) | magic | 4 | 70% | 4.6 | too strong |
| Mighty Sling Stone (`sling_mighty`) | physical | 4 | 70% | 4.0 | too strong |
| Ice Shackles (`ice_shackles`) | magic | 4 | 42% | 4.8 | worse than attacking |
| Storm Speed (`storm_speed`) | magic | 4 | 42% | 5.1 | worse than attacking |
| Bless (`bless`) | magic | 3 | 42% | 5.0 | worse than attacking |
| Hex (`hex`) | magic | 3 | 42% | 4.8 | worse than attacking |
| Brace (`brace`) | physical | 3 | 42% | 5.2 | worse than attacking |
| Frost Grenade (`frost_grenade`) | physical | 4 | 42% | 4.8 | worse than attacking |
| Lingering (`lingering_spell`) | magic | 4 | 42% | 4.7 | worse than attacking |
| Fire Curse (`fire_curse`) | magic | 3 | 42% | 5.0 | worse than attacking |
| Ash Veil (`ash_veil`) | magic | 4 | 42% | 4.8 | worse than attacking |
| Frost Bolt (`frost_bolt`) | magic | 3 | 42% | 5.2 | worse than attacking |
| Frost Lance (`frost_lance`) | magic | 4 | 42% | 4.6 | worse than attacking |
| Stone Mantle (`stone_mantle`) | magic | 3 | 42% | 4.9 | worse than attacking |
| Acid Curse (`acid_curse`) | magic | 3 | 42% | 4.9 | worse than attacking |
| Acid Purge (`acid_purge`) | magic | 3 | 42% | 5.2 | worse than attacking |
| Wind Curse (`wind_curse`) | magic | 3 | 42% | 5.0 | worse than attacking |
| Light Bolt (`light_bolt`) | magic | 3 | 42% | 5.3 | worse than attacking |
| Holy Bolt (`holy_bolt`) | magic | 3 | 42% | 5.4 | worse than attacking |
| Holy Blessing (`holy_blessing`) | magic | 3 | 42% | 5.0 | worse than attacking |
| Lunar Hex (`lunar_hex`) | magic | 3 | 42% | 4.8 | worse than attacking |
| Shadow Mantle (`shadow_mantle`) | magic | 3 | 42% | 5.2 | worse than attacking |
| Dread Dart (`dread_dart`) | magic | 4 | 42% | 4.7 | worse than attacking |
| Dread Purge (`dread_purge`) | magic | 3 | 42% | 5.0 | worse than attacking |
| Force Dart (`force_dart`) | magic | 4 | 42% | 4.4 | worse than attacking |
| Rune Burst (`rune_burst`) | magic | 3 | 42% | 5.4 | worse than attacking |
| Death Leech (`death_leech`) | magic | 4 | 42% | 5.0 | worse than attacking |
| Soul Wave (`soul_wave`) | magic | 4 | 42% | 4.8 | worse than attacking |
| Greatsword Riposte (`greatsword_riposte`) | physical | 3 | 42% | 5.0 | worse than attacking |
| Piercing Axe Chop (`axe_piercing`) | physical | 4 | 42% | 4.6 | worse than attacking |
| Dagger Riposte (`dagger_riposte`) | physical | 3 | 42% | 5.0 | worse than attacking |
| Whip Riposte (`whip_riposte`) | physical | 3 | 42% | 5.0 | worse than attacking |
| Hammer Riposte (`hammer_riposte`) | physical | 3 | 42% | 5.1 | worse than attacking |
| Hammer Feint (`hammer_feint`) | physical | 3 | 42% | 4.8 | worse than attacking |
| Piercing Shield Slam (`shield_piercing`) | physical | 4 | 42% | 4.9 | worse than attacking |
| Spear Riposte (`spear_riposte`) | physical | 3 | 42% | 5.1 | worse than attacking |
| Crippling Lance Charge (`lance_crippling`) | physical | 4 | 42% | 4.5 | worse than attacking |
| Toppling Trident Jab (`trident_toppling`) | physical | 4 | 42% | 4.7 | worse than attacking |
| Pinning Trident Jab (`trident_pinning`) | physical | 4 | 42% | 5.0 | worse than attacking |
| Trident Parry (`trident_parry`) | physical | 3 | 42% | 5.0 | worse than attacking |
| Bleeding Glaive Arc (`glaive_bleeding`) | physical | 4 | 42% | 4.5 | worse than attacking |
| Hunter's Bow Shot (`bow_hunters`) | physical | 4 | 42% | 4.6 | worse than attacking |
| Fist Riposte (`fist_riposte`) | physical | 3 | 42% | 5.0 | worse than attacking |
| Fang Feint (`fang_feint`) | physical | 3 | 42% | 4.7 | worse than attacking |
| Wing Parry (`wing_parry`) | physical | 3 | 42% | 5.0 | worse than attacking |
| Thorn Whip (`thorn_whip`) | magic | 4 | 42% | 4.6 | worse than attacking |
| Armor Breaker (`armor_breaker`) | physical | 4 | 42% | 4.6 | worse than attacking |
| Lightning Wave (`lightning_wave`) | magic | 4 | 42% | 4.8 | worse than attacking |
| Thunder Wave (`thunder_wave`) | magic | 4 | 42% | 4.7 | worse than attacking |
| Sand Curse (`sand_curse`) | magic | 3 | 42% | 4.7 | worse than attacking |
| Wind Grasp (`wind_grasp`) | magic | 4 | 42% | 4.8 | worse than attacking |
| Wind Mantle (`wind_mantle`) | magic | 3 | 42% | 5.0 | worse than attacking |
| Sonic Grasp (`sound_grasp`) | magic | 4 | 42% | 5.0 | worse than attacking |
| Sonic Purge (`sound_purge`) | magic | 3 | 42% | 5.2 | worse than attacking |
| Holy Curse (`holy_curse`) | magic | 3 | 42% | 4.9 | worse than attacking |
| Star Purge (`star_purge`) | magic | 3 | 42% | 5.1 | worse than attacking |
| Dream Wave (`dream_wave`) | magic | 4 | 42% | 4.7 | worse than attacking |
| Arcane Mantle (`arcane_mantle`) | magic | 3 | 42% | 5.1 | worse than attacking |
| Chaos Judgement (`chaos_judgement`) | magic | 4 | 42% | 4.5 | worse than attacking |
| Bone Curse (`bone_curse`) | magic | 3 | 42% | 4.8 | worse than attacking |
| Life Veil (`life_veil`) | magic | 3 | 42% | 5.1 | worse than attacking |
| Card Lance (`card_lance`) | magic | 4 | 42% | 4.6 | worse than attacking |
| Hammer Parry (`hammer_parry`) | physical | 3 | 42% | 4.8 | worse than attacking |
| Flail Parry (`flail_parry`) | physical | 3 | 42% | 5.2 | worse than attacking |
| Finishing Trident Jab (`trident_finishing`) | physical | 4 | 42% | 4.5 | worse than attacking |
| Precise Javelin Throw (`javelin_precise`) | physical | 4 | 42% | 4.5 | worse than attacking |
| Precise Rifle Round (`rifle_precise`) | physical | 4 | 42% | 4.4 | worse than attacking |
| Precise Claw Swipe (`claw_precise`) | physical | 4 | 42% | 4.4 | worse than attacking |
| Precise Horn Gore (`horn_precise`) | physical | 4 | 42% | 4.4 | worse than attacking |
| Horn Parry (`horn_parry`) | physical | 3 | 42% | 5.0 | worse than attacking |
| Piercing Wing Buffet (`wing_piercing`) | physical | 4 | 42% | 4.7 | worse than attacking |
| Tentacle Feint (`tentacle_feint`) | physical | 3 | 42% | 4.8 | worse than attacking |
| Hemokinesis (`hemokinesis`) | magic | 4 | 42% | 4.3 | worse than attacking |
| Decoy (`decoy`) | physical | 3 | 42% | 5.1 | worse than attacking |
| Beast Form (`shapeshift`) | magic | 3 | 42% | 5.2 | worse than attacking |
| Expose Weakness (`expose_weakness`) | physical | 3 | 42% | 4.8 | worse than attacking |
| Ash Mantle (`ash_mantle`) | magic | 3 | 42% | 5.2 | worse than attacking |
| Water Veil (`water_veil`) | magic | 3 | 42% | 5.1 | worse than attacking |
| Water Blessing (`water_blessing`) | magic | 3 | 42% | 4.9 | worse than attacking |
| Steam Mantle (`steam_mantle`) | magic | 3 | 42% | 5.0 | worse than attacking |
| Lightning Dart (`lightning_dart`) | magic | 4 | 42% | 4.6 | worse than attacking |
| Lightning Judgement (`lightning_judgement`) | magic | 4 | 42% | 4.5 | worse than attacking |
| Lightning Veil (`lightning_veil`) | magic | 4 | 42% | 5.0 | worse than attacking |
| Earth Mantle (`earth_mantle`) | magic | 3 | 42% | 5.1 | worse than attacking |
| Iron Judgement (`metal_judgement`) | magic | 4 | 42% | 4.4 | worse than attacking |
| Wind Purge (`wind_purge`) | magic | 3 | 42% | 5.3 | worse than attacking |
| Solar Mantle (`solar_mantle`) | magic | 3 | 42% | 5.1 | worse than attacking |
| Shadow Judgement (`shadow_judgement`) | magic | 4 | 42% | 4.5 | worse than attacking |
| Shadow Curse (`shadow_curse`) | magic | 3 | 42% | 4.9 | worse than attacking |
| Dark Judgement (`dark_judgement`) | magic | 4 | 42% | 4.8 | worse than attacking |
| Dream Burst (`dream_burst`) | magic | 3 | 42% | 5.4 | worse than attacking |
| Dread Brand (`dread_brand`) | magic | 4 | 42% | 4.9 | worse than attacking |
| Force Burst (`force_burst`) | magic | 3 | 42% | 5.2 | worse than attacking |
| Rune Lance (`rune_lance`) | magic | 4 | 42% | 4.7 | worse than attacking |
| Blood Mantle (`blood_mantle`) | magic | 3 | 42% | 4.9 | worse than attacking |
| Bone Dart (`bone_dart`) | magic | 4 | 42% | 4.8 | worse than attacking |
| Soul Lance (`soul_lance`) | magic | 4 | 42% | 4.7 | worse than attacking |
| Soul Veil (`soul_veil`) | magic | 3 | 42% | 5.1 | worse than attacking |
| Piercing Scimitar Slash (`scimitar_piercing`) | physical | 4 | 42% | 4.5 | worse than attacking |
| Staff Feint (`staff_feint`) | physical | 3 | 42% | 5.1 | worse than attacking |
| Club Parry (`club_parry`) | physical | 3 | 42% | 5.1 | worse than attacking |
| Shield Parry (`shield_parry`) | physical | 3 | 42% | 5.2 | worse than attacking |
| Glaive Feint (`glaive_feint`) | physical | 3 | 42% | 4.9 | worse than attacking |
| Finishing Scattergun Blast (`scattergun_finishing`) | physical | 4 | 42% | 4.6 | worse than attacking |
| Bleeding Scattergun Blast (`scattergun_bleeding`) | physical | 4 | 42% | 4.5 | worse than attacking |
| Martial Riposte (`martial_riposte`) | physical | 3 | 42% | 5.0 | worse than attacking |
| Wing Riposte (`wing_riposte`) | physical | 3 | 42% | 4.9 | worse than attacking |
| Divine Favor (`divine_favor`) | magic | 3 | 41% | 5.0 | worse than attacking |
| Mind Spike (`mind_spike`) | magic | 3 | 41% | 4.9 | worse than attacking |
| Treat Ailment (`antidote`) | physical | 3 | 41% | 5.2 | worse than attacking |
| Protection (`protection`) | magic | 3 | 41% | 4.9 | worse than attacking |
| Distract (`distract`) | physical | 3 | 41% | 4.9 | worse than attacking |
| Hellfire Purge (`hellfire_purge`) | magic | 3 | 41% | 5.1 | worse than attacking |
| Ice Burst (`ice_burst`) | magic | 3 | 41% | 5.4 | worse than attacking |
| Water Grasp (`water_grasp`) | magic | 4 | 41% | 4.9 | worse than attacking |
| Thunder Curse (`thunder_curse`) | magic | 3 | 41% | 5.0 | worse than attacking |
| Sand Mantle (`sand_mantle`) | magic | 3 | 41% | 5.0 | worse than attacking |
| Acid Brand (`acid_brand`) | magic | 4 | 41% | 4.7 | worse than attacking |
| Shadow Lance (`shadow_lance`) | magic | 4 | 41% | 4.8 | worse than attacking |
| Shadow Purge (`shadow_purge`) | magic | 3 | 41% | 5.0 | worse than attacking |
| Arcane Hex (`arcane_hex`) | magic | 3 | 41% | 4.9 | worse than attacking |
| Blood Veil (`blood_veil`) | magic | 4 | 41% | 5.0 | worse than attacking |
| Bone Mantle (`bone_mantle`) | magic | 3 | 41% | 5.2 | worse than attacking |
| Soul Burst (`soul_burst`) | magic | 3 | 41% | 5.4 | worse than attacking |
| Primal Veil (`primal_veil`) | magic | 3 | 41% | 4.8 | worse than attacking |
| Piercing Dagger Stab (`dagger_piercing`) | physical | 4 | 41% | 4.8 | worse than attacking |
| Piercing Whip Lash (`whip_piercing`) | physical | 4 | 41% | 4.6 | worse than attacking |
| Whip Parry (`whip_parry`) | physical | 3 | 41% | 5.2 | worse than attacking |
| Trident Riposte (`trident_riposte`) | physical | 3 | 41% | 5.0 | worse than attacking |
| Pinning Bow Shot (`bow_pinning`) | physical | 4 | 41% | 4.7 | worse than attacking |
| Crippling Javelin Throw (`javelin_crippling`) | physical | 4 | 41% | 4.7 | worse than attacking |
| Pinning Scattergun Blast (`scattergun_pinning`) | physical | 4 | 41% | 4.7 | worse than attacking |
| Hunter's Scattergun Blast (`scattergun_hunters`) | physical | 4 | 41% | 4.5 | worse than attacking |
| Hunter's Horn Gore (`horn_hunters`) | physical | 4 | 41% | 4.4 | worse than attacking |
| Tentacle Parry (`tentacle_parry`) | physical | 3 | 41% | 5.1 | worse than attacking |
| Tentacle Riposte (`tentacle_riposte`) | physical | 3 | 41% | 4.9 | worse than attacking |
| Stone Spike (`stone_spike`) | magic | 3 | 40% | 5.3 | worse than attacking |
| Void Touch (`void_touch`) | magic | 4 | 40% | 4.9 | worse than attacking |
| Wither (`wither`) | magic | 4 | 40% | 4.8 | worse than attacking |
| Clarity (`clarity`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Spell Ward (`spell_ward`) | magic | 4 | 40% | 4.8 | worse than attacking |
| Enlarge (`enlarge`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Rally (`rally`) | physical | 3 | 40% | 5.0 | worse than attacking |
| Evasion (`evasion`) | physical | 3 | 40% | 5.0 | worse than attacking |
| Acid Flask (`acid_flask`) | physical | 4 | 40% | 4.7 | worse than attacking |
| Ice Bolt (`ice_bolt`) | magic | 3 | 40% | 5.3 | worse than attacking |
| Ice Judgement (`ice_judgement`) | magic | 4 | 40% | 4.6 | worse than attacking |
| Thunder Purge (`thunder_purge`) | magic | 3 | 40% | 5.0 | worse than attacking |
| Earth Curse (`earth_curse`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Earth Purge (`earth_purge`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Stone Veil (`stone_veil`) | magic | 3 | 40% | 4.9 | worse than attacking |
| Crystal Dart (`crystal_dart`) | magic | 4 | 40% | 4.7 | worse than attacking |
| Crystal Judgement (`crystal_judgement`) | magic | 4 | 40% | 4.3 | worse than attacking |
| Crystal Veil (`crystal_veil`) | magic | 4 | 40% | 4.8 | worse than attacking |
| Acid Dart (`acid_dart`) | magic | 4 | 40% | 4.6 | worse than attacking |
| Song Grasp (`song_grasp`) | magic | 4 | 40% | 5.1 | worse than attacking |
| Song Blessing (`song_blessing`) | magic | 3 | 40% | 4.8 | worse than attacking |
| Holy Lance (`holy_lance`) | magic | 4 | 40% | 4.9 | worse than attacking |
| Holy Veil (`holy_veil`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Star Grasp (`star_grasp`) | magic | 4 | 40% | 5.1 | worse than attacking |
| Dream Mantle (`dream_mantle`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Rune Brand (`rune_brand`) | magic | 4 | 40% | 4.7 | worse than attacking |
| Death Lance (`death_lance`) | magic | 4 | 40% | 4.9 | worse than attacking |
| Venom Lance (`venom_lance`) | magic | 4 | 40% | 4.8 | worse than attacking |
| Thread Mantle (`thread_mantle`) | magic | 3 | 40% | 5.0 | worse than attacking |
| Mirror Bolt (`mirror_bolt`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Mirror Mantle (`mirror_mantle`) | magic | 3 | 40% | 5.0 | worse than attacking |
| Sword Cut (`sword_strike`) | physical | 3 | 40% | 4.8 | worse than attacking |
| Bleeding Dagger Stab (`dagger_bleeding`) | physical | 4 | 40% | 4.7 | worse than attacking |
| Finishing Rapier Lunge (`rapier_finishing`) | physical | 4 | 40% | 4.5 | worse than attacking |
| Lance Feint (`lance_feint`) | physical | 3 | 40% | 5.0 | worse than attacking |
| Piercing Glaive Arc (`glaive_piercing`) | physical | 4 | 40% | 4.8 | worse than attacking |
| Toppling Javelin Throw (`javelin_toppling`) | physical | 4 | 40% | 4.7 | worse than attacking |
| Fist Parry (`fist_parry`) | physical | 3 | 40% | 5.0 | worse than attacking |
| Martial Parry (`martial_parry`) | physical | 3 | 40% | 5.1 | worse than attacking |
| Elbow Riposte (`elbow_riposte`) | physical | 3 | 40% | 5.2 | worse than attacking |
| Claw Parry (`claw_parry`) | physical | 3 | 40% | 5.1 | worse than attacking |
| Piercing Horn Gore (`horn_piercing`) | physical | 4 | 40% | 4.8 | worse than attacking |
| Ice Lance (`ice_lance`) | magic | 4 | 40% | 4.6 | worse than attacking |
| Silence (`deafening_silence`) | magic | 4 | 40% | 5.1 | worse than attacking |
| Arcane Blast (`arcane_blast`) | magic | 3 | 40% | 5.0 | worse than attacking |
| Bite (`bite`) | physical | 3 | 40% | 5.3 | worse than attacking |
| Spiked Hide (`spikes`) | physical | 3 | 40% | 5.1 | worse than attacking |
| Blood Frenzy (`blood_frenzy`) | physical | 3 | 40% | 5.2 | worse than attacking |
| Stand Firm (`stand_firm`) | physical | 3 | 40% | 5.0 | worse than attacking |
| Magma Purge (`magma_purge`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Lightning Purge (`lightning_purge`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Light Mantle (`light_mantle`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Lunar Lance (`lunar_lance`) | magic | 4 | 40% | 4.6 | worse than attacking |
| Psychic Brand (`psychic_brand`) | magic | 4 | 40% | 5.0 | worse than attacking |
| Blood Burst (`blood_burst`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Chain Mantle (`chain_mantle`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Ink Lance (`ink_lance`) | magic | 4 | 40% | 4.5 | worse than attacking |
| Ink Mantle (`ink_mantle`) | magic | 3 | 40% | 4.9 | worse than attacking |
| Axe Riposte (`axe_riposte`) | physical | 3 | 40% | 5.2 | worse than attacking |
| Dagger Parry (`dagger_parry`) | physical | 3 | 40% | 5.0 | worse than attacking |
| Hunter's Crossbow Quarrel (`crossbow_hunters`) | physical | 4 | 40% | 4.5 | worse than attacking |
| Precise Pistol Shot (`pistol_precise`) | physical | 4 | 40% | 4.7 | worse than attacking |
| Finishing Fang Bite (`fang_finishing`) | physical | 4 | 40% | 4.5 | worse than attacking |
| Horn Riposte (`horn_riposte`) | physical | 3 | 40% | 4.9 | worse than attacking |
| Tail Riposte (`tail_riposte`) | physical | 3 | 40% | 4.9 | worse than attacking |
| Frostbite (`frostbite`) | magic | 3 | 40% | 5.0 | worse than attacking |
| Static Field (`static_field`) | magic | 4 | 40% | 4.9 | worse than attacking |
| Regeneration (`regeneration`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Water Purge (`water_purge`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Lightning Brand (`lightning_brand`) | magic | 4 | 40% | 4.6 | worse than attacking |
| Lightning Curse (`lightning_curse`) | magic | 3 | 40% | 4.8 | worse than attacking |
| Thunder Grasp (`thunder_grasp`) | magic | 4 | 40% | 5.0 | worse than attacking |
| Sonic Bolt (`sound_bolt`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Song Purge (`song_purge`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Light Veil (`light_veil`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Lunar Bolt (`lunar_bolt`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Dark Veil (`dark_veil`) | magic | 4 | 40% | 5.1 | worse than attacking |
| Dream Veil (`dream_veil`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Phantasmal Curse (`phantasm_curse`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Force Mantle (`force_mantle`) | magic | 3 | 40% | 5.0 | worse than attacking |
| Chaos Purge (`chaos_purge`) | magic | 3 | 40% | 5.1 | worse than attacking |
| Blood Dart (`blood_dart`) | magic | 4 | 40% | 4.6 | worse than attacking |
| Soul Mantle (`soul_mantle`) | magic | 3 | 40% | 5.2 | worse than attacking |
| Card Purge (`card_purge`) | magic | 3 | 40% | 5.0 | worse than attacking |
| Mirror Grasp (`mirror_grasp`) | magic | 4 | 40% | 5.0 | worse than attacking |
| Scythe Riposte (`scythe_riposte`) | physical | 3 | 40% | 4.9 | worse than attacking |
| Piercing Spear Thrust (`spear_piercing`) | physical | 4 | 40% | 4.8 | worse than attacking |
| Spear Feint (`spear_feint`) | physical | 3 | 40% | 5.0 | worse than attacking |
| Halberd Riposte (`halberd_riposte`) | physical | 3 | 40% | 5.2 | worse than attacking |
| Piercing Pistol Shot (`pistol_piercing`) | physical | 4 | 40% | 4.6 | worse than attacking |
| Fang Riposte (`fang_riposte`) | physical | 3 | 40% | 5.3 | worse than attacking |
| Tailwind (`tailwind`) | magic | 4 | 39% | 5.1 | worse than attacking |
| Wind Wall (`wind_wall`) | magic | 4 | 39% | 5.1 | worse than attacking |
| Confusion (`confusion`) | magic | 4 | 39% | 5.0 | worse than attacking |
| Force Lance (`force_lance`) | magic | 4 | 39% | 4.7 | worse than attacking |
| Fire Mantle (`fire_mantle`) | magic | 3 | 39% | 5.1 | worse than attacking |
| Ash Lance (`ash_lance`) | magic | 4 | 39% | 4.7 | worse than attacking |
| Frost Purge (`frost_purge`) | magic | 3 | 39% | 5.0 | worse than attacking |
| Sonic Dart (`sound_dart`) | magic | 4 | 39% | 4.5 | worse than attacking |
| Light Lance (`light_lance`) | magic | 4 | 39% | 4.8 | worse than attacking |
| Dark Purge (`dark_purge`) | magic | 3 | 39% | 5.0 | worse than attacking |
| Dark Ward (`dark_ward`) | magic | 3 | 39% | 5.2 | worse than attacking |
| Dream Dart (`dream_dart`) | magic | 4 | 39% | 4.9 | worse than attacking |
| Arcane Brand (`arcane_brand`) | magic | 4 | 39% | 4.6 | worse than attacking |
| Bone Veil (`bone_veil`) | magic | 3 | 39% | 5.3 | worse than attacking |
| Death Burst (`death_burst`) | magic | 3 | 39% | 5.4 | worse than attacking |
| Rot Purge (`rot_purge`) | magic | 3 | 39% | 5.2 | worse than attacking |
| Primal Mantle (`primal_mantle`) | magic | 3 | 39% | 5.2 | worse than attacking |
| Spore Grasp (`spore_grasp`) | magic | 4 | 39% | 4.9 | worse than attacking |
| Scythe Parry (`scythe_parry`) | physical | 3 | 39% | 5.2 | worse than attacking |
| Chain Parry (`chain_parry`) | physical | 3 | 39% | 5.0 | worse than attacking |
| Hunter's Spear Thrust (`spear_hunters`) | physical | 4 | 39% | 4.7 | worse than attacking |
| Piercing Crossbow Quarrel (`crossbow_piercing`) | physical | 4 | 39% | 4.6 | worse than attacking |
| Hunter's Pistol Shot (`pistol_hunters`) | physical | 4 | 39% | 4.7 | worse than attacking |
| Elbow Parry (`elbow_parry`) | physical | 3 | 39% | 5.2 | worse than attacking |
| Finishing Horn Gore (`horn_finishing`) | physical | 4 | 39% | 4.6 | worse than attacking |
| Blink (`blink`) | magic | 4 | 38% | 5.0 | worse than attacking |
| Thunder Bolt (`thunder_bolt`) | magic | 3 | 38% | 5.3 | worse than attacking |
| Wind Lance (`wind_lance`) | magic | 4 | 38% | 4.7 | worse than attacking |
| Lunar Grasp (`lunar_grasp`) | magic | 4 | 38% | 4.9 | worse than attacking |
| Psychic Lance (`psychic_lance`) | magic | 4 | 38% | 4.8 | worse than attacking |
| Phantasmal Veil (`phantasm_veil`) | magic | 4 | 38% | 5.2 | worse than attacking |
| Force Veil (`force_veil`) | magic | 3 | 38% | 5.2 | worse than attacking |
| Rune Bolt (`rune_bolt`) | magic | 3 | 38% | 5.1 | worse than attacking |
| Bone Judgement (`bone_judgement`) | magic | 4 | 38% | 4.6 | worse than attacking |
| Death Wave (`death_wave`) | magic | 4 | 38% | 4.8 | worse than attacking |
| Thorn Lance (`thorn_lance`) | magic | 4 | 38% | 4.5 | worse than attacking |
| Thorn Purge (`thorn_purge`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Life Mantle (`life_mantle`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Chain Veil (`chain_veil`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Mirror Purge (`mirror_purge`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Finishing Dagger Stab (`dagger_finishing`) | physical | 4 | 38% | 4.4 | worse than attacking |
| Bleeding Horn Gore (`horn_bleeding`) | physical | 4 | 38% | 4.7 | worse than attacking |
| Tail Feint (`tail_feint`) | physical | 3 | 38% | 5.0 | worse than attacking |
| Fire Shield (`fire_shield`) | magic | 4 | 38% | 5.0 | worse than attacking |
| Acid Spit (`acid_spit`) | physical | 4 | 38% | 4.6 | worse than attacking |
| Frost Mantle (`frost_mantle`) | magic | 3 | 38% | 4.9 | worse than attacking |
| Water Mantle (`water_mantle`) | magic | 3 | 38% | 5.3 | worse than attacking |
| Crystal Lance (`crystal_lance`) | magic | 4 | 38% | 5.0 | worse than attacking |
| Wind Veil (`wind_veil`) | magic | 4 | 38% | 5.1 | worse than attacking |
| Sonic Veil (`sound_veil`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Star Bolt (`star_bolt`) | magic | 3 | 38% | 5.2 | worse than attacking |
| Psychic Dart (`psychic_dart`) | magic | 4 | 38% | 4.6 | worse than attacking |
| Force Purge (`force_purge`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Thorn Mantle (`thorn_mantle`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Card Veil (`card_veil`) | magic | 4 | 38% | 4.9 | worse than attacking |
| Thread Purge (`thread_purge`) | magic | 3 | 38% | 5.3 | worse than attacking |
| Ink Veil (`ink_veil`) | magic | 4 | 38% | 5.0 | worse than attacking |
| Piercing Greatsword Cleave (`greatsword_piercing`) | physical | 4 | 38% | 4.5 | worse than attacking |
| Greatsword Parry (`greatsword_parry`) | physical | 3 | 38% | 5.1 | worse than attacking |
| Club Riposte (`club_riposte`) | physical | 3 | 38% | 5.1 | worse than attacking |
| Trident Jab (`trident_strike`) | physical | 3 | 38% | 5.0 | worse than attacking |
| Piercing Fang Bite (`fang_piercing`) | physical | 4 | 38% | 4.7 | worse than attacking |
| Bone Spear (`bone_spear`) | magic | 3 | 38% | 5.4 | worse than attacking |
| Parry (`parry`) | physical | 3 | 38% | 5.3 | worse than attacking |
| Wild Magic (`wild_magic`) | magic | 2 | 38% | 3.1 | worse than attacking |
| Ice Mantle (`ice_mantle`) | magic | 3 | 38% | 4.9 | worse than attacking |
| Ice Veil (`ice_veil`) | magic | 3 | 38% | 5.2 | worse than attacking |
| Holy Mantle (`holy_mantle`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Dark Dart (`dark_dart`) | magic | 4 | 38% | 4.7 | worse than attacking |
| Phantasmal Lance (`phantasm_lance`) | magic | 4 | 38% | 4.8 | worse than attacking |
| Bone Purge (`bone_purge`) | magic | 3 | 38% | 5.1 | worse than attacking |
| Soul Purge (`soul_purge`) | magic | 3 | 38% | 4.9 | worse than attacking |
| Card Mantle (`card_mantle`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Ink Purge (`ink_purge`) | magic | 3 | 38% | 5.0 | worse than attacking |
| Mace Parry (`mace_parry`) | physical | 3 | 38% | 5.0 | worse than attacking |
| Light Blessing (`light_blessing`) | magic | 3 | 37% | 5.0 | worse than attacking |
| Dark Mantle (`dark_mantle`) | magic | 3 | 37% | 5.1 | worse than attacking |
| Psychic Purge (`psychic_purge`) | magic | 3 | 37% | 5.3 | worse than attacking |
| Arcane Bolt (`arcane_bolt`) | magic | 3 | 37% | 5.2 | worse than attacking |
| Chaos Lance (`chaos_lance`) | magic | 4 | 37% | 4.7 | worse than attacking |
| Blood Lance (`blood_lance`) | magic | 4 | 37% | 4.8 | worse than attacking |
| Ink Curse (`ink_curse`) | magic | 3 | 37% | 4.9 | worse than attacking |
| Staff Parry (`staff_parry`) | physical | 3 | 37% | 5.1 | worse than attacking |
| Hunter's Halberd Hack (`halberd_hunters`) | physical | 4 | 37% | 4.3 | worse than attacking |
| Pinning Lance Charge (`lance_pinning`) | physical | 4 | 37% | 4.7 | worse than attacking |
| Chill Touch (`chill_touch`) | magic | 4 | 36% | 4.8 | worse than attacking |
| Feint (`feint`) | physical | 3 | 36% | 5.0 | worse than attacking |
| Stimulant (`stimulant`) | physical | 4 | 36% | 5.0 | worse than attacking |
| Backfire (`backfire`) | physical | 2 | 36% | 3.2 | worse than attacking |
| Ice Dart (`ice_dart`) | magic | 4 | 36% | 4.6 | worse than attacking |
| Iron Grasp (`metal_grasp`) | magic | 4 | 36% | 4.8 | worse than attacking |
| Acid Lance (`acid_lance`) | magic | 4 | 36% | 4.8 | worse than attacking |
| Lunar Burst (`lunar_burst`) | magic | 3 | 36% | 5.2 | worse than attacking |
| Dark Burst (`dark_burst`) | magic | 3 | 36% | 5.3 | worse than attacking |
| Dream Brand (`dream_brand`) | magic | 4 | 36% | 4.6 | worse than attacking |
| Soul Bolt (`soul_bolt`) | magic | 3 | 36% | 5.2 | worse than attacking |
| Soul Dart (`soul_dart`) | magic | 4 | 36% | 4.8 | worse than attacking |
| Piercing Trident Jab (`trident_piercing`) | physical | 4 | 36% | 4.7 | worse than attacking |
| Glaive Riposte (`glaive_riposte`) | physical | 3 | 36% | 5.1 | worse than attacking |
| Piercing Bow Shot (`bow_piercing`) | physical | 4 | 36% | 4.7 | worse than attacking |
| Pinning Horn Gore (`horn_pinning`) | physical | 4 | 36% | 4.7 | worse than attacking |
| Stoneskin (`stoneskin`) | magic | 3 | 36% | 5.0 | worse than attacking |
| Sanctuary (`sanctuary`) | magic | 4 | 36% | 5.1 | worse than attacking |
| Vampire Form (`vampire_form`) | magic | 4 | 36% | 5.0 | worse than attacking |
| Dread Lance (`dread_lance`) | magic | 4 | 36% | 4.8 | worse than attacking |
| Phantasmal Mantle (`phantasm_mantle`) | magic | 3 | 36% | 5.2 | worse than attacking |
| Bone Lance (`bone_lance`) | magic | 4 | 36% | 4.8 | worse than attacking |
| Mirror Lance (`mirror_lance`) | magic | 4 | 36% | 4.8 | worse than attacking |
| Piercing Rapier Lunge (`rapier_piercing`) | physical | 4 | 36% | 4.8 | worse than attacking |
| Piercing Club Bash (`club_piercing`) | physical | 4 | 36% | 4.7 | worse than attacking |
| Shield Riposte (`shield_riposte`) | physical | 3 | 36% | 4.9 | worse than attacking |
| Spear Parry (`spear_parry`) | physical | 3 | 36% | 5.2 | worse than attacking |
| Precise Bow Shot (`bow_precise`) | physical | 4 | 36% | 4.6 | worse than attacking |
| Shadow Cloak (`shadow_cloak`) | magic | 4 | 36% | 5.0 | worse than attacking |
| Piercing Shot (`piercing_shot`) | physical | 4 | 36% | 4.6 | worse than attacking |
| Vanish (`vanish`) | physical | 3 | 36% | 5.0 | worse than attacking |
| Crystal Bolt (`crystal_bolt`) | magic | 3 | 36% | 5.2 | worse than attacking |
| Iron Veil (`metal_veil`) | magic | 3 | 36% | 4.8 | worse than attacking |
| Star Lance (`star_lance`) | magic | 4 | 36% | 4.9 | worse than attacking |
| Star Veil (`star_veil`) | magic | 3 | 36% | 4.9 | worse than attacking |
| Lunar Purge (`lunar_purge`) | magic | 3 | 36% | 5.2 | worse than attacking |
| Force Bolt (`force_bolt`) | magic | 3 | 36% | 5.0 | worse than attacking |
| Bone Bolt (`bone_bolt`) | magic | 3 | 36% | 5.1 | worse than attacking |
| Mirror Veil (`mirror_veil`) | magic | 4 | 36% | 4.9 | worse than attacking |
| Javelin Throw (`javelin_strike`) | physical | 3 | 36% | 5.2 | worse than attacking |
| Fang Bite (`fang_strike`) | physical | 3 | 36% | 5.0 | worse than attacking |
| Haste (`haste`) | magic | 4 | 35% | 5.1 | worse than attacking |
| Magma Veil (`magma_veil`) | magic | 3 | 35% | 4.9 | worse than attacking |
| Shadow Veil (`shadow_veil`) | magic | 4 | 35% | 5.0 | worse than attacking |
| Blood Purge (`blood_purge`) | magic | 3 | 35% | 4.9 | worse than attacking |
| Battle Focus (`battle_focus`) | physical | 2 | 34% | 6.2 | worse than attacking |
| Stone Purge (`stone_purge`) | magic | 3 | 34% | 4.9 | worse than attacking |
| Dread Bolt (`dread_bolt`) | magic | 3 | 34% | 5.1 | worse than attacking |
| Phantasmal Bolt (`phantasm_bolt`) | magic | 3 | 34% | 5.1 | worse than attacking |
| Flail Riposte (`flail_riposte`) | physical | 3 | 34% | 5.0 | worse than attacking |
| Spear Thrust (`spear_strike`) | physical | 3 | 34% | 5.1 | worse than attacking |
| Thunder Lance (`thunder_lance`) | magic | 4 | 34% | 5.0 | worse than attacking |
| Dream Bolt (`dream_bolt`) | magic | 3 | 34% | 5.3 | worse than attacking |
| Death Brand (`death_brand`) | magic | 4 | 34% | 4.8 | worse than attacking |
| Piercing Lance Charge (`lance_piercing`) | physical | 4 | 34% | 4.8 | worse than attacking |
| Bow Shot (`bow_strike`) | physical | 3 | 34% | 5.2 | worse than attacking |
| Shadow Bolt (`shadow_bolt`) | magic | 3 | 34% | 5.2 | worse than attacking |
| Super Speed (`super_speed`) | physical | 3 | 34% | 5.0 | worse than attacking |
| Dark Lance (`dark_lance`) | magic | 4 | 34% | 4.7 | worse than attacking |
| Scattergun Blast (`scattergun_strike`) | physical | 3 | 34% | 5.2 | worse than attacking |
| Rage (`rage`) | physical | 2 | 33% | 5.9 | worse than attacking |
| Blood Bolt (`blood_bolt`) | magic | 3 | 33% | 5.4 | worse than attacking |
| Horn Gore (`horn_strike`) | physical | 3 | 33% | 5.2 | worse than attacking |
| Psychic Bolt (`psychic_bolt`) | magic | 3 | 32% | 5.2 | worse than attacking |
| Chain Purge (`chain_purge`) | magic | 3 | 32% | 5.3 | worse than attacking |
| Piercing Javelin Throw (`javelin_piercing`) | physical | 4 | 32% | 4.7 | worse than attacking |
| Acid Splash (`acid_splash`) | magic | 4 | 32% | 4.7 | worse than attacking |
| Thread Veil (`thread_veil`) | magic | 4 | 32% | 5.0 | worse than attacking |
| Rifle Round (`rifle_strike`) | physical | 3 | 32% | 5.2 | worse than attacking |
| Crossbow Quarrel (`crossbow_strike`) | physical | 3 | 31% | 5.2 | worse than attacking |
| Dream Lance (`dream_lance`) | magic | 4 | 30% | 4.8 | worse than attacking |
| Rapier Lunge (`rapier_strike`) | physical | 3 | 30% | 5.3 | worse than attacking |
| Pistol Shot (`pistol_strike`) | physical | 3 | 30% | 5.4 | worse than attacking |
| Lance Charge (`lance_strike`) | physical | 3 | 30% | 5.0 | worse than attacking |
| Piercing Rifle Round (`rifle_piercing`) | physical | 4 | 30% | 4.8 | worse than attacking |
| Acid Bolt (`acid_bolt`) | magic | 3 | 29% | 5.2 | worse than attacking |
| Dark Bolt (`dark_bolt`) | magic | 3 | 27% | 5.1 | worse than attacking |
| Death Bolt (`death_bolt`) | magic | 3 | 25% | 5.1 | too weak |
| Escape Artist (`escape_artist`) | physical | 2 | 24% | 6.5 | too weak |
| Shake It Off (`shake_it_off`) | physical | 2 | 24% | 6.5 | too weak |
| Blood Price (`blood_price`) | magic | 2 | 20% | 2.7 | too weak |
| Iron Will (`iron_will`) | physical | 2 | 15% | 6.3 | too weak |
| Overexertion (`overexertion`) | physical | 2 | 12% | 2.7 | too weak |
| Widened (`widened`) | magic | 5 | 12% | 6.4 | too weak |
| Sweeping (`sweeping`) | physical | 5 | 12% | 6.8 | too weak |
| *1159 others within range* | | | | | |

## Weak (375 effects, median win rate 48%)

| Effect | Realm | AP | Win rate | Rounds | Verdict |
|---|---|---|---|---|---|
| Ash Nova (`ash_nova`) | magic | 4 | 74% | 3.9 | too strong |
| Solar Nova (`solar_nova`) | magic | 4 | 72% | 3.9 | too strong |
| Spore Nova (`spore_nova`) | magic | 4 | 72% | 4.1 | too strong |
| Water Nova (`water_nova`) | magic | 4 | 71% | 4.4 | too strong |
| Venom Nova (`venom_nova`) | magic | 4 | 70% | 4.4 | too strong |
| Chain Nova (`chain_nova`) | magic | 4 | 70% | 4.4 | too strong |
| Sand Wisp (`sand_summon`) | magic | 4 | 42% | 4.9 | worse than attacking |
| Dread Torment (`dread_torment`) | magic | 5 | 42% | 5.1 | worse than attacking |
| Disarming Scythe Reap (`scythe_disarming`) | physical | 5 | 42% | 6.1 | worse than attacking |
| Stunning Mace Blow (`mace_stunning`) | physical | 5 | 42% | 5.7 | worse than attacking |
| Lance Whirlwind (`lance_whirlwind`) | physical | 4 | 42% | 4.8 | worse than attacking |
| Disarming Martial Kick (`martial_disarming`) | physical | 5 | 42% | 6.2 | worse than attacking |
| Magma Torment (`magma_torment`) | magic | 5 | 42% | 5.3 | worse than attacking |
| Hellfire Torment (`hellfire_torment`) | magic | 5 | 42% | 5.5 | worse than attacking |
| Earth Torment (`earth_torment`) | magic | 5 | 42% | 5.4 | worse than attacking |
| Crystal Familiar (`crystal_summon`) | magic | 4 | 42% | 4.6 | worse than attacking |
| Spectral Singer (`song_summon`) | magic | 4 | 42% | 5.0 | worse than attacking |
| Shadow Smite (`shadow_smite`) | magic | 5 | 42% | 5.6 | worse than attacking |
| Chaos Smite (`chaos_smite`) | magic | 5 | 42% | 5.4 | worse than attacking |
| Chaos Imp (`chaos_summon`) | magic | 4 | 42% | 4.7 | worse than attacking |
| Disarming Horn Gore (`horn_disarming`) | physical | 5 | 42% | 6.4 | worse than attacking |
| Revivify (`revivify`) | magic | 4 | 42% | 4.8 | worse than attacking |
| Spark Sprite (`lightning_summon`) | magic | 4 | 42% | 4.8 | worse than attacking |
| Wind Sprite (`wind_summon`) | magic | 4 | 42% | 4.5 | worse than attacking |
| Holy Torment (`holy_torment`) | magic | 5 | 42% | 5.2 | worse than attacking |
| Disarming Dagger Stab (`dagger_disarming`) | physical | 5 | 42% | 6.1 | worse than attacking |
| Disarming Bow Shot (`bow_disarming`) | physical | 5 | 42% | 6.4 | worse than attacking |
| Disarming Crossbow Quarrel (`crossbow_disarming`) | physical | 5 | 42% | 6.5 | worse than attacking |
| Disarming Pistol Shot (`pistol_disarming`) | physical | 5 | 42% | 6.3 | worse than attacking |
| Raise Dead (`raise_dead`) | magic | 4 | 41% | 4.7 | worse than attacking |
| Ice Hound (`ice_summon`) | magic | 4 | 41% | 4.9 | worse than attacking |
| Chaos Torment (`chaos_torment`) | magic | 5 | 41% | 5.3 | worse than attacking |
| Shield Bash (`shield_bash`) | physical | 5 | 40% | 6.3 | worse than attacking |
| Unstoppable (`unstoppable`) | physical | 3 | 40% | 5.3 | worse than attacking |
| Ash Wisp (`ash_summon`) | magic | 4 | 40% | 4.7 | worse than attacking |
| Iron Torment (`metal_torment`) | magic | 5 | 40% | 5.9 | worse than attacking |
| Shadow Torment (`shadow_torment`) | magic | 5 | 40% | 5.2 | worse than attacking |
| Spirit Wolf (`primal_summon`) | magic | 4 | 40% | 4.8 | worse than attacking |
| Ink Torment (`ink_torment`) | magic | 5 | 40% | 5.5 | worse than attacking |
| Disarming Scimitar Slash (`scimitar_disarming`) | physical | 5 | 40% | 6.3 | worse than attacking |
| Disarming Lance Charge (`lance_disarming`) | physical | 5 | 40% | 6.5 | worse than attacking |
| Javelin Volley (`javelin_volley`) | physical | 4 | 40% | 4.7 | worse than attacking |
| Snuff Magic (`eclipse`) | magic | 4 | 40% | 4.9 | worse than attacking |
| Mud Hound (`earth_summon`) | magic | 4 | 40% | 4.9 | worse than attacking |
| Acid Ooze (`acid_summon`) | magic | 4 | 40% | 4.9 | worse than attacking |
| Chain Torment (`chain_torment`) | magic | 5 | 40% | 5.2 | worse than attacking |
| Turn (`turn_undead`) | magic | 4 | 40% | 4.8 | worse than attacking |
| Knockout Gas (`knockout_gas`) | physical | 5 | 40% | 5.5 | worse than attacking |
| Spectral Hand (`force_summon`) | magic | 4 | 40% | 4.7 | worse than attacking |
| Bone Torment (`bone_torment`) | magic | 5 | 40% | 5.4 | worse than attacking |
| Soul Torment (`soul_torment`) | magic | 5 | 40% | 5.2 | worse than attacking |
| Thorn Torment (`thorn_torment`) | magic | 5 | 40% | 5.3 | worse than attacking |
| Spore Torment (`spore_torment`) | magic | 5 | 40% | 5.2 | worse than attacking |
| Chain Smite (`chain_smite`) | magic | 5 | 40% | 5.7 | worse than attacking |
| Stunning Lance Charge (`lance_stunning`) | physical | 5 | 40% | 5.9 | worse than attacking |
| Disarming Rifle Round (`rifle_disarming`) | physical | 5 | 40% | 6.4 | worse than attacking |
| Rune Torment (`rune_torment`) | magic | 5 | 39% | 5.3 | worse than attacking |
| Ink Smite (`ink_smite`) | magic | 5 | 39% | 5.4 | worse than attacking |
| Shock Baton (`shock_baton`) | physical | 5 | 38% | 6.2 | worse than attacking |
| Light Wisp (`light_summon`) | magic | 4 | 38% | 4.8 | worse than attacking |
| Arcane Smite (`arcane_smite`) | magic | 5 | 38% | 5.4 | worse than attacking |
| Scattergun Volley (`scattergun_volley`) | physical | 4 | 38% | 4.8 | worse than attacking |
| Fang Whirlwind (`fang_whirlwind`) | physical | 4 | 38% | 4.9 | worse than attacking |
| Disarming Tail Lash (`tail_disarming`) | physical | 5 | 38% | 6.1 | worse than attacking |
| Drown (`drown`) | magic | 4 | 38% | 4.9 | worse than attacking |
| Bodyguard (`bodyguard`) | physical | 4 | 38% | 4.8 | worse than attacking |
| Star Mote (`star_summon`) | magic | 4 | 38% | 4.9 | worse than attacking |
| Rune Sentinel (`rune_summon`) | magic | 4 | 38% | 4.9 | worse than attacking |
| Mirror Torment (`mirror_torment`) | magic | 5 | 38% | 5.2 | worse than attacking |
| Water Torment (`water_torment`) | magic | 5 | 38% | 5.2 | worse than attacking |
| Stone Servant (`stone_summon`) | magic | 4 | 38% | 4.7 | worse than attacking |
| Crystal Torment (`crystal_torment`) | magic | 5 | 38% | 5.5 | worse than attacking |
| Rune Smite (`rune_smite`) | magic | 5 | 38% | 5.4 | worse than attacking |
| Soul Smite (`soul_smite`) | magic | 5 | 38% | 5.4 | worse than attacking |
| Smelling Salts (`smelling_salts`) | physical | 4 | 37% | 5.0 | worse than attacking |
| Sleeper Dart (`sleeper_dart`) | physical | 5 | 37% | 6.5 | worse than attacking |
| Last Stand (`last_stand`) | physical | 4 | 37% | 5.1 | worse than attacking |
| Water Sprite (`water_summon`) | magic | 4 | 37% | 4.8 | worse than attacking |
| Ink Beast (`ink_summon`) | magic | 4 | 37% | 5.0 | worse than attacking |
| Rapier Whirlwind (`rapier_whirlwind`) | physical | 4 | 37% | 4.7 | worse than attacking |
| Card Torment (`card_torment`) | magic | 5 | 36% | 5.4 | worse than attacking |
| Force Torment (`force_torment`) | magic | 5 | 36% | 5.2 | worse than attacking |
| Sand Torment (`sand_torment`) | magic | 5 | 35% | 5.2 | worse than attacking |
| Arcane Torment (`arcane_torment`) | magic | 5 | 35% | 5.0 | worse than attacking |
| Bow Volley (`bow_volley`) | physical | 4 | 34% | 4.8 | worse than attacking |
| Rebound (`mirror_ward`) | magic | 5 | 34% | 5.5 | worse than attacking |
| *289 others within range* | | | | | |

## Normal (69 effects, median win rate 63%)

| Effect | Realm | AP | Win rate | Rounds | Verdict |
|---|---|---|---|---|---|
| Shadow Doom (`shadow_doom`) | magic | 5 | 42% | 5.3 | worse than attacking |
| Venom Doom (`venom_doom`) | magic | 5 | 42% | 5.3 | worse than attacking |
| Berserk (`berserk`) | physical | 4 | 41% | 5.1 | worse than attacking |
| Soul Doom (`soul_doom`) | magic | 5 | 40% | 5.0 | worse than attacking |
| Dread Doom (`dread_doom`) | magic | 5 | 40% | 5.3 | worse than attacking |
| Rot Doom (`rot_doom`) | magic | 5 | 40% | 5.3 | worse than attacking |
| Hellfire Doom (`hellfire_doom`) | magic | 5 | 38% | 5.1 | worse than attacking |
| Dark Doom (`dark_doom`) | magic | 5 | 38% | 5.1 | worse than attacking |
| Chaos Doom (`chaos_doom`) | magic | 5 | 38% | 5.2 | worse than attacking |
| Death Mark (`death_mark`) | magic | 5 | 37% | 5.1 | worse than attacking |
| Blood Doom (`blood_doom`) | magic | 5 | 36% | 5.3 | worse than attacking |
| Acid Doom (`acid_doom`) | magic | 5 | 34% | 5.2 | worse than attacking |
| Unravel (`unravel`) | magic | 5 | 33% | 5.3 | worse than attacking |
| Tactical Retreat (`retreat`) | physical | 5 | 0% | 1.0 | too weak |
| *55 others within range* | | | | | |

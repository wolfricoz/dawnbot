---
layout: default
title: Craft
parent: Commands
nav_order: 11
---

<h1>Craft</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Crafting from recipes, projects worked on in downtime, and salvage.


### `recipes`

**Usage:** `/craft recipes <character>`

> Lists the server's recipes. With a character: ✅ can make it now, ❌ misses ingredients (listed), 🔒 locked.

---

### `make`

**Usage:** `/craft make <character> <recipe>`

> Crafts a recipe with your character's ingredients. Recipes that take days set the ingredients aside and start
> a project, worked on one roll per day with /downtime spend activity:craft.

---

### `projects`

**Usage:** `/craft projects <character>`

> Lists the projects your character is working on, with how far along each is.

---

### `salvage`

**Usage:** `/craft salvage <character> <item>`

> Breaks an owned or broken item into the materials its catalog entry lists; each one comes out on a coin flip,
> so about half of them. The item is gone afterwards.

---

### `uncurse`

**Usage:** `/craft uncurse <member> <character> <item>`

> Makes a cursed item a normal one again.
>
> **Permissions:**
> - `Manage Messages`

---

### `recipe add`

**Usage:** `/craft recipe add <name> <result> <ingredients> <amount> <tool> <stat> <dc> <occupation> <occupation_required> <min_level> <days>`

> Adds a recipe. Materials are catalog items of kind material (the fantasy recipe pack brings a set).
>
> **Permissions:**
> - `Manage Messages`

---

### `recipe remove`

**Usage:** `/craft recipe remove <recipe>`

> Removes a recipe; projects using it are abandoned when next worked on.
>
> **Permissions:**
> - `Manage Messages`

---

### `recipe mishap`

**Usage:** `/craft recipe mishap <recipe> <table>`

> Sets (or, without a table, clears) the roll table a bad failure on this recipe rolls.
>
> **Permissions:**
> - `Manage Messages`

---

### `recipe salvage`

**Usage:** `/craft recipe salvage <item> <materials>`

> Sets the materials salvaging an item can give (each comes out on a coin flip).
>
> **Permissions:**
> - `Manage Messages`

---

### `recipe import`

**Usage:** `/craft recipe import <pack>`

> Adds the pack's materials to the catalog, its recipes, and salvage lists for the gear it knows. Import the
> matching gear pack first (/armory import), since recipes make catalog items.
>
> **Permissions:**
> - `Manage Messages`

---


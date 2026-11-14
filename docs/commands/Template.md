---
layout: default
title: Template
parent: Commands
nav_order: 10
---

<h1>Template</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Save a server's categories and channels as a template and apply it to a new server.

Applying a template archives the existing channels (see /archive) and is limited to the server owner, to servers
with at most 10 members, and asks for confirmation twice.


### `register`

**Usage:** `/template register <name>`

> Saves this server's categories and channels (not their messages or permissions) as one of your templates.

**Permissions:**
- `Server Owner`

---

### `apply`

**Usage:** `/template apply <template>`

> Archives every channel that sits in a category, removes those categories and builds the template. Only works
in servers with at most 10 members (bots not counted) and asks for confirmation twice. Archived channels can
be brought back with /archive restore.

**Permissions:**
- `Server Owner`

---

### `list`

**Usage:** `/template list`

> Lists the templates you have registered.

---

### `view`

**Usage:** `/template view <template>`

> Shows the categories and channels of one of your templates.

---

### `delete`

**Usage:** `/template delete <template>`

> Deletes one of your templates.

---


---
layout: default
title: Archive
parent: Commands
nav_order: 2
---

<h1>Archive</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

The archive holds channels set aside by /template restore. Archived channels are named
"<old category>・<channel>" and hidden from everyone until they are restored; /template archivepurge deletes them.


### `restore`

**Usage:** `/archive restore <archive>`

> Moves archived channels back to the category named at the start of their name (recreating it if it is gone),
> gives them their old name and restores who could see them. Restores one archive category, or all of them.
>
> **Permissions:**
> - `Administrator`

---


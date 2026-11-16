---
layout: default
title: Job
parent: Commands
nav_order: 22
---

<h1>Job</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

The job board: post jobs, claim them and get paid when they are done.


### `post`

**Usage:** `/job post <title> <currency> <xp> <items> <slots> <min_level> <faction> <rep_success> <rep_failure> <deadline_hours> <location> <as_character>`

> Opens a form for the job's description and posts it as a thread on the job board with **Claim**,
> **Withdraw**, **Complete** and **Start scene** buttons. Staff post jobs; with JOB_PLAYER_POSTS on, players
> post them as a character and the currency reward (for every slot) is held until the job ends.

---

### `cancel`

**Usage:** `/job cancel <job>`

> Cancels an open job; a player job's held reward goes back. Poster or staff.

---

### `list`

**Usage:** `/job list`

> Lists open and taken jobs with links.

---


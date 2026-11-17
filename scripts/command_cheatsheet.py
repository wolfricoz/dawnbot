"""Build the printable command cheatsheet (docs/command-cheatsheet.pdf) from the cogs themselves.

Imports every module in modules/, collects its slash commands (nested groups included) with their options and who
may use them, renders a four-column landscape A4 page and prints it to PDF with headless Chrome or Edge:

    python scripts/command_cheatsheet.py
    python scripts/command_cheatsheet.py --html docs/command-cheatsheet.html   # also keep the HTML

Set CHROME to a browser executable if neither Chrome nor Edge is found. Dev-only commands are left out. A new cog
must be added to CATEGORIES below, or the script stops and names it.
"""
import argparse
import html
import inspect
import os
import re
import shutil
import subprocess
import sys
import tempfile
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from discord import app_commands  # noqa: E402
from discord.ext import commands  # noqa: E402

from data.env.loader import load_environment  # noqa: E402

# (heading, colour, cogs) in page order; every cog in modules/ except Dev must appear exactly once.
CATEGORIES = [
	("Characters & progression", "#2f6f9f",
	 ["Character", "Sheet", "Species", "Proxy", "Template", "Occupation", "Language", "User", "Experience"]),
	("Rolls & tools", "#7a4f9a", ["Tools", "Check", "Generator", "Table", "Omen"]),
	("Scenes & storytelling", "#a0522d", ["Scene", "Chronicle", "Archive", "Letter", "Rumor", "Job"]),
	("World", "#2e7d5b", ["Location", "Travel", "Time", "Calendar", "Weather", "Faction"]),
	("Combat & magic", "#b03a3a", ["Combat", "Ability", "School", "DamageType", "Bestiary", "Enchant"]),
	("Gear & crafting", "#8a6d1f", ["Gear", "Armory", "Craft", "Downtime", "Stash"]),
	("Economy & trade", "#1f7a8a", ["Currency", "Economy", "Shop", "Merchant", "Market", "Trade", "Lifestyle"]),
	("Staff & setup", "#55606e", ["GM", "Config", "TagRule", "Feedback"]),
]
SKIPPED_COGS = {"Dev", "logs", "__init__"}

BROWSERS = [
	r"C:\Program Files\Google\Chrome\Application\chrome.exe",
	r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
	r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
	r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
	"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


# ============================================================
# Collecting the commands
# ============================================================
def permission_names(obj) -> set[str]:
	"""The permissions a command or group needs through default_permissions."""
	perms = getattr(obj, "default_permissions", None)
	return {name for name, value in perms if value} if perms else set()


def access(cmd: app_commands.Command, inherited: set[str]) -> set[str]:
	"""Who may run a command: default permissions plus has_permissions, gm_only and AccessControl checks."""
	found = permission_names(cmd) or set(inherited)
	for check in cmd.checks :
		name = check.__qualname__
		if "gm_only" in name :
			found.add("gm")
		elif "AccessControl" in name :
			found.add("dev")
		elif "has_permissions" in name :
			for cell in check.__closure__ or () :
				if isinstance(cell.cell_contents, dict) :
					found |= {perm for perm, value in cell.cell_contents.items() if value}
	return found


def walk(cmd, prefix: str, cog: str, inherited: set[str], out: list[dict]) :
	"""Adds a command, or every command under a group, to out."""
	if isinstance(cmd, app_commands.Group) :
		for child in cmd.commands :
			walk(child, f"{prefix} {cmd.name}".strip(), cog, permission_names(cmd) or inherited, out)
		return
	doc = inspect.getdoc(cmd.callback) or ""
	if doc.startswith(("skip", "[skip]")) :
		return
	out.append(dict(cog=cog, path=f"{prefix} {cmd.name}".strip(), desc=cmd.description,
	                params=[dict(name=p.display_name, required=p.required) for p in cmd.parameters],
	                perms=access(cmd, inherited)))


def collect() -> list[dict]:
	"""Every slash command in modules/, in source order."""
	load_environment()
	out = []
	for file in sorted(glob("modules/*.py")) :
		name = Path(file).stem
		if name in SKIPPED_COGS :
			continue
		module = __import__(f"modules.{name}", fromlist=[name])
		for cls in vars(module).values() :
			if not (inspect.isclass(cls) and issubclass(cls, commands.Cog) and cls.__module__ == module.__name__) :
				continue
			# A plain Cog's commands are top level; only a GroupCog puts its name in front of them.
			group = cls.__cog_group_name__ if issubclass(cls, commands.GroupCog) else ""
			# @app_commands.default_permissions on the cog class gates its whole group.
			defaults = (getattr(cls, "__cog_group_default_permissions__", None)
			            or getattr(cls, "__discord_app_commands_default_permissions__", None))
			inherited = {perm for perm, value in defaults if value} if defaults else set()
			for obj in cls.__dict__.values() :
				# Commands made with @some_group.command are class attributes too; reach them through their group.
				if isinstance(obj, (app_commands.Command, app_commands.Group)) and obj.parent is None :
					walk(obj, group, name, inherited, out)
	return [c for c in out if "dev" not in c["perms"]]


# ============================================================
# Rendering
# ============================================================
def level(cmd: dict) -> tuple[int, str]:
	"""Sort order and badge class: everyone, GM, Mod, Admin."""
	perms = cmd["perms"]
	if perms & {"administrator", "manage_guild"} :
		return 3, "admin"
	if "manage_messages" in perms :
		return 2, "mod"
	if "gm" in perms :
		return 1, "gm"
	return 0, ""


def summary(desc: str) -> str:
	"""Discord caps descriptions at 100 characters, so long ones end in an ellipsis; keep whole clauses."""
	text = desc.strip()
	if text.endswith("…") :
		text = text[:-1]
		if not text.endswith(".") :
			# Whole sentences win, then whole clauses, then whole list items.
			cut = text.rfind(". ")
			if cut <= 25 :
				cut = max(text.rfind("; "), text.rfind(": "))
			if cut <= 25 :
				cut = text.rfind(", ")
			text = text[:cut] if cut > 25 else text.rsplit(" ", 1)[0] + "…"
	text = re.sub(r"\s*\((GMs|staff)\)$", "", text).rstrip(".")
	return html.escape(text[:1].upper() + text[1:]).replace("`", "")


def usage(cmd: dict) -> str:
	"""Required options, then up to three optional ones (or how many there are)."""
	required = [p["name"] for p in cmd["params"] if p["required"]]
	optional = [p["name"] for p in cmd["params"] if not p["required"]]
	parts = [f'<span class="req">{html.escape(n)}</span>' for n in required]
	if len(optional) <= 3 :
		parts += [f'<span class="opt">{html.escape(n)}</span>' for n in optional]
	else :
		parts.append(f'<span class="more">+{len(optional)} options</span>')
	return " ".join(parts)


def render(cmds: list[dict], version: str) -> str:
	listed = [cog for _, _, cogs in CATEGORIES for cog in cogs]
	missing = sorted({c["cog"] for c in cmds} - set(listed))
	if missing :
		sys.exit(f"Add these cogs to CATEGORIES in {Path(__file__).name}: {', '.join(missing)}")

	badges = {"gm" : "GM", "mod" : "Mod", "admin" : "Admin"}
	body = []
	for title, colour, cogs in CATEGORIES :
		body.append(f'<h2 style="--c:{colour}">{title}</h2>')
		for cog in cogs :
			items = sorted((c for c in cmds if c["cog"] == cog), key=lambda c : level(c)[0])
			if not items :
				continue
			groups = sorted({c["path"].split(" ")[0] for c in items if " " in c["path"]})
			rows = []
			for cmd in items :
				cls = level(cmd)[1]
				badge = f'<span class="badge {cls}">{badges[cls]}</span>' if cls else ""
				rows.append(f'<div class="cmd"><div class="line"><code>/{html.escape(cmd["path"])}</code> '
				            f'{usage(cmd)}{badge}</div><div class="desc">{summary(cmd["desc"])}</div></div>')
			label = " · ".join("/" + g for g in groups)
			head = f'<h3 style="--c:{colour}">{html.escape(cog)} <span class="g">{label}</span></h3>'
			# The heading travels with its first command so it never sits alone at a column foot.
			body.append(f'<section><div class="keep">{head}{rows[0]}</div>{"".join(rows[1:])}</section>')

	version = html.escape(version)
	return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Dawnbot command cheatsheet</title>
<style>
@page {{ size: A4 landscape; margin: 8mm 9mm 9mm;
  @bottom-left {{ content: "Dawnbot command cheatsheet · v{version}"; font: 6.5pt 'Segoe UI', sans-serif; color: #888; }}
  @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font: 6.5pt 'Segoe UI', sans-serif;
    color: #888; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font: 6.8pt/1.15 'Segoe UI', Arial, sans-serif; color: #1d232b; background: #fff;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
header {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 12px;
  border-bottom: 2px solid #1d232b; padding-bottom: 4px; margin-bottom: 6px; }}
header h1 {{ margin: 0; font-size: 17pt; letter-spacing: -.3px; line-height: 1; }}
header h1 small {{ font-size: 8pt; font-weight: 400; color: #666; margin-left: 6px; letter-spacing: 0; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: center; font-size: 6.6pt; color: #444; }}
.legend .badge {{ float: none; }}
.cols {{ column-count: 4; column-gap: 9px; column-rule: .5px solid #e3e6ea; }}
h2 {{ break-after: avoid; margin: 4px 0 2px; padding: 2px 5px; font-size: 8pt; color: #fff; background: var(--c);
  border-radius: 2px; letter-spacing: .2px; text-transform: uppercase; }}
h2:first-child {{ margin-top: 0; }}
section {{ margin: 0 0 2px; }}
.keep {{ break-inside: avoid; }}
h3 {{ margin: 2px 0 1px; font-size: 7.6pt; color: var(--c); border-bottom: .6px solid var(--c); padding-bottom: 1px; }}
h3 .g {{ font: 400 6.4pt Consolas, monospace; color: #6b7480; margin-left: 3px; }}
.cmd {{ break-inside: avoid; padding: .8px 0 1px; border-bottom: .4px dotted #d7dbe0; }}
.line {{ font-size: 6.6pt; }}
code {{ font: 700 7pt Consolas, 'Cascadia Mono', monospace; color: #111; }}
.req, .opt, .more {{ font: 6.2pt Consolas, monospace; white-space: nowrap; }}
.req {{ color: #2a4f7a; }} .req::before {{ content: "<"; }} .req::after {{ content: ">"; }}
.opt {{ color: #7d8792; }} .opt::before {{ content: "["; }} .opt::after {{ content: "]"; }}
.more {{ color: #7d8792; font-style: italic; }}
.desc {{ color: #4a525c; font-size: 6.4pt; padding-left: 4px; }}
.badge {{ float: right; margin-left: 3px; font: 700 5.4pt 'Segoe UI', sans-serif; padding: 0 3px; border-radius: 2px;
  line-height: 1.5; text-transform: uppercase; letter-spacing: .3px; }}
.badge.gm {{ background: #ede4f6; color: #5e3a86; }}
.badge.mod {{ background: #fdecd8; color: #8a4b0f; }}
.badge.admin {{ background: #fbe0e0; color: #9a2424; }}
</style></head><body>
<header>
  <h1>Dawnbot commands <small>{len(cmds)} slash commands · v{version}</small></h1>
  <div class="legend">
    <span><span class="req">required</span> <span class="opt">optional</span></span>
    <span><span class="badge gm">GM</span> staff or the GM role</span>
    <span><span class="badge mod">Mod</span> Manage Messages</span>
    <span><span class="badge admin">Admin</span> Manage Server</span>
    <span>no badge: everyone</span>
  </div>
</header>
<div class="cols">
{"".join(body)}
</div>
</body></html>"""


def find_browser() -> str | None:
	for candidate in [os.environ.get("CHROME"), *BROWSERS] :
		if candidate and Path(candidate).is_file() :
			return candidate
	for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge") :
		if found := shutil.which(name) :
			return found
	return None


def main() :
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--out", default="docs/command-cheatsheet.pdf", help="where to write the PDF")
	parser.add_argument("--html", help="also keep the HTML page here")
	args = parser.parse_args()

	from project.data import VERSION
	cmds = collect()
	page = render(cmds, VERSION)

	with tempfile.TemporaryDirectory() as tmp :
		source = Path(args.html).resolve() if args.html else Path(tmp) / "cheatsheet.html"
		source.write_text(page, encoding="utf-8")
		browser = find_browser()
		if browser is None :
			kept = Path(args.html or "command-cheatsheet.html").resolve()
			kept.write_text(page, encoding="utf-8")
			sys.exit(f"No Chrome or Edge found (set CHROME). Wrote {kept}; print it to PDF from a browser.")
		out = Path(args.out).resolve()
		subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
		                f"--print-to-pdf={out}", source.as_uri()], check=True, capture_output=True)
	print(f"{len(cmds)} commands -> {out}")


if __name__ == "__main__" :
	main()

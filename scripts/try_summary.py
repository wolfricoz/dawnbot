"""Try a local model on a chronicle transcript before wiring it into the bot.

Sends a chronicle .md file (the one the bot posts when a scene ends) to a local Ollama server, prints the draft
summary and how long each step took. Standard library only, so it runs with the server's own python3:

    python3 scripts/try_summary.py "The Long Night.md"
    python3 scripts/try_summary.py "The Long Night.md" --model qwen3:8b --threads 4
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request

SYSTEM = (
	"You summarise roleplay scenes for a Discord server's timeline. Write one or two short paragraphs, "
	"third person, past tense, about 150 words. Say who was there, where it happened and what changed: decisions, "
	"fights and their outcomes, discoveries, promises, injuries, items gained or lost. Use the character names "
	"exactly as written. Only state what the transcript shows; never invent events, motives or names. "
	"No headings, no lists, no preamble."
)

POST_HEADER = re.compile(r"^\*\*(.+?)\*\* · \d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
OOC = re.compile(r"^\s*(\(\(.*?\)\)|//.*|ooc:.*)\s*$", re.IGNORECASE)


def trim(markdown: str, keep_notes: bool) -> str:
	"""Turns the chronicle Markdown into 'Name: text' lines, dropping timestamps, blank lines and OOC lines."""
	out, name = [], None
	for line in markdown.splitlines():
		line = line.rstrip()
		header = POST_HEADER.match(line)
		if header:
			name = header.group(1)
			continue
		if not line.strip() or OOC.match(line):
			continue
		if line.startswith("> "):
			if keep_notes:
				out.append(f"[{line[2:]}]")
			continue
		if line.startswith("# ") or name is None:
			out.append(line)  # title and the meta line (location, dates, participants)
			continue
		out.append(f"{name}: {line}")
	return "\n".join(out)


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("transcript", help="a chronicle .md file")
	parser.add_argument("--model", default="qwen3:4b-instruct-2507-q4_K_M")
	parser.add_argument("--threads", type=int, default=4, help="CPU threads for the model (default 4)")
	parser.add_argument("--ctx", type=int, default=16384, help="context window in tokens (default 16384)")
	parser.add_argument("--host", default="http://127.0.0.1:11434")
	parser.add_argument("--no-notes", action="store_true", help="drop dice, check and table notes")
	parser.add_argument("--show-input", action="store_true", help="print the trimmed transcript too")
	args = parser.parse_args()

	with open(args.transcript, encoding="utf-8") as handle:
		raw = handle.read()
	text = trim(raw, keep_notes=not args.no_notes)
	if args.show_input:
		print(text, "\n" + "-" * 60)
	print(f"Transcript: {len(raw):,} chars, {len(text):,} after trimming (~{len(text) // 4:,} tokens)")

	body = json.dumps({
		"model": args.model,
		"stream": False,
		"messages": [{"role": "system", "content": SYSTEM},
		             {"role": "user", "content": f"Summarise this scene.\n\n{text}"}],
		"options": {"num_ctx": args.ctx, "num_thread": args.threads, "temperature": 0.3},
	}).encode("utf-8")
	request = urllib.request.Request(f"{args.host}/api/chat", body, {"Content-Type": "application/json"})

	started = time.monotonic()
	try:
		with urllib.request.urlopen(request, timeout=1800) as response:
			result = json.load(response)
	except urllib.error.HTTPError as error:
		print(f"Ollama said {error.code}: {error.read().decode('utf-8', 'replace')}", file=sys.stderr)
		return 1
	except urllib.error.URLError as error:
		print(f"Couldn't reach Ollama at {args.host} ({error.reason}). Is it running? `systemctl status ollama`",
		      file=sys.stderr)
		return 1
	wall = time.monotonic() - started

	def rate(count_key: str, duration_key: str) -> str:
		count, nanos = result.get(count_key, 0), result.get(duration_key, 0)
		return f"{count:,} tokens in {nanos / 1e9:.1f}s ({count / (nanos / 1e9):.1f} tok/s)" if nanos else "n/a"

	print("\n" + result["message"]["content"].strip() + "\n")
	print(f"Load model:  {result.get('load_duration', 0) / 1e9:.1f}s")
	print(f"Read scene:  {rate('prompt_eval_count', 'prompt_eval_duration')}")
	print(f"Write:       {rate('eval_count', 'eval_duration')}")
	print(f"Total:       {wall:.1f}s")
	if result.get("prompt_eval_count", 0) >= args.ctx - 50:
		print(f"Warning: the transcript filled the {args.ctx:,}-token window, so the start was cut. Try --ctx 32768.")
	return 0


if __name__ == "__main__":
	sys.exit(main())

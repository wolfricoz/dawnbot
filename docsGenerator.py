import inspect
import json
import os
import sys
from glob import glob

from discord import app_commands
from discord.ext import commands

from data.env.loader import load_environment
from project.data import CACHE, VERSION
from resources.configs.ConfigMapping import channels, docs, lists, settings, toggles


class DocGenerator():

    def __init__(self):
        self.command_cache = {}
        self.start()
        self.create_cache_File()

    def start(self):
        print("===Generating Documentation===")
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        count = 1

        if os.path.exists('docs/commands/'):
            for f in os.listdir('docs/commands/'):
                os.remove(os.path.join('docs/commands/', f))

        for file in glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules", "*.py")):

            if os.path.basename(file).lower() in ['logs.py', 'dev.py']:
                continue

            self.load_file(file, nav=count)
            count += 1
        # == Generate config docs ==
        self.create_config()

    def load_file(self, file, nav=1):
        name = os.path.splitext(os.path.basename(file))[0]
        document = f"docs/commands/{name}.md"
        if name == "__init__":
            return
        # create the document
        for dirc in ["docs", "docs/commands"]:
            if not os.path.exists(dirc):
                os.mkdir(dirc)

        # add package prefix to name
        module_name = f"modules.{name}"
        module = __import__(module_name, fromlist=[name])

        with open(document, "w", encoding="utf-8") as docfile:

            for member in dir(module):
                # do something with the member named ``member``

                if member == name:
                    tclass = getattr(module, member)
                    if inspect.ismodule(tclass):

                        continue

                    print(f"- Documenting Module: {name}")
                    docfile.write(self.document_header(tclass, name, nav))

                    # The prefix is the cog's app-command group, not the file
                    # name: Forums.py registers its commands under /forum. Note
                    # discord.py sets __cog_group_name__ on every Cog, so only a
                    # GroupCog has a real group - a plain Cog's commands are top
                    # level and take no prefix at all.
                    domain = ""
                    if inspect.isclass(tclass) and issubclass(tclass, commands.GroupCog):
                        domain = getattr(tclass, "__cog_group_name__", "") or ""

                    for function in tclass.__dict__:
                        self.command_line(docfile, function, tclass, domain, )

    def document_header(self, module, module_name: str, nav, parent = "parent: Commands"):

        return f"""---
layout: default
title: {module_name}
{parent}
nav_order: {nav}
---

<h1>{module_name}</h1>
<h6>version: {VERSION}</h6>
<h6>Documentation automatically generated from docstrings.</h6>

{inspect.getdoc(module) if not isinstance(module, str) else module}


"""

    def command_line(self, docfile, function, tclass, domain, cachefile=None):
        if function.startswith("_") or function.startswith('cog') or function.startswith('cog') or function.startswith(
                'before_'):
            return

        func_obj = getattr(tclass, function)
        # Only real commands belong in a command reference. Helper methods on a
        # cog cannot be invoked from Discord, so documenting them invents
        # commands that do not exist.
        if not isinstance(func_obj, (app_commands.Command, commands.Command)):
            return
        # @app_commands.command(name=...) can rename a command away from its
        # method name, and the registered name is what users actually type.
        command_name = func_obj.name
        # A command inside a nested group (such as /gm gear grant) is named after its group too.
        parent = getattr(func_obj, "parent", None)
        if isinstance(parent, app_commands.Group):
            command_name = f"{parent.name} {command_name}"
        docstring = ""
        # Check if it's a decorated command with a callback
        if hasattr(func_obj, 'callback'):
            docstring = inspect.getdoc(func_obj.callback)
        # Check if it's a callable function
        elif callable(func_obj):
            docstring = inspect.getdoc(func_obj)

        if not docstring:
            docstring = "Missing Documentation"
        if docstring.startswith("skip") or docstring.startswith("[skip]"):
            return

        param_string = ""
        try:
            # Use the callback if it exists, otherwise use the function object itself
            target_func = func_obj.callback if hasattr(func_obj, 'callback') else func_obj
            sig = inspect.signature(target_func)
            # Filter out 'self' and 'interaction' from the parameters
            params = [p for p in sig.parameters if p not in ('self', 'interaction')]
            if params:
                # Format parameters like: <param1> <param2>
                param_string = " " + " ".join([f"<{p}>" for p in params])
        except (ValueError, TypeError):
            print("Could not retrieve signature for function:", function)
            # This can happen for objects that are not inspectable
            pass
        self.add_command_to_cache(domain, command_name, docstring)

        usage = f"/{domain.lower()} {command_name}" if domain else f"/{command_name}"
        docfile.write(f"### `{command_name}`\n\n"
                      f"**Usage:** `{usage}{param_string}`\n\n"
                      f"> {docstring}\n\n"
                      f"---\n\n")

    def add_command_to_cache(self, domain, function, docstring):
        # if domain not in self.command_cache :
        # 	self.command_cache[domain] = {}
        # self.command_cache[domain][function] = docstring
        # Keyed by the full command path, so commands with the same name in different groups do not collide.
        self.command_cache[f"{domain} {function}".strip()] = docstring

    def create_cache_File(self):
        print("===Creating command cache file===")
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as cachefile:
            json.dump(self.command_cache, cachefile, indent=4)
        print("===Command cache file created===")

    def create_config(self):
        with open('docs/config.md', 'w', encoding="utf-8") as configfile:
            configfile.write(self.document_header("", "Configuration", 2, ""))
            for title, keys in [("Channel lists", lists), ("Channels", channels), ("Settings", settings),
                                ("Toggles", toggles)]:
                if not keys:
                    continue
                configfile.write(f"\n<h2>{title}</h2>")
                for key in keys:
                    configfile.write(f"\n\n### {key}\n"
                                     f"{docs.get(key, 'This config option is missing documentation, let the devs know!')}")




load_environment()
DocGenerator()
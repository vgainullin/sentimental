#!/usr/bin/env python3
"""Print the CI matrix of author keys: keys=["hilbert", ...].

AUTHORS env (space-separated keys) narrows the list; unknown keys are an error
so a typo in a manual run fails fast instead of silently doing nothing.
"""

import json
import os
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1] if len(sys.argv) > 1 else "authors.yaml")
authors = yaml.safe_load(path.read_text()) or []
known = [a["key"] for a in authors]
if len(set(known)) != len(known):
    sys.exit(f"duplicate author keys in authors.yaml: {known}")
wanted = os.environ.get("AUTHORS", "").split()
bad = [k for k in wanted if k not in known]
if bad:
    sys.exit(f"unknown author keys {bad}; known: {known}")
print("keys=" + json.dumps(wanted or known))

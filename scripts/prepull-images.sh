#!/bin/sh
# Pre-pull the pinned sandbox images onto the runner host.
#
# Run on the Hetzner VM before starting the runner. `docker build` cannot reach a
# daemon, so this must happen on the host. Digests are read straight from
# app_pkg/config.py so the two can never drift.
set -eu

cd "$(dirname "$0")/.."

.venv/bin/python - <<'PY' | while IFS= read -r image; do
import re, pathlib
text = pathlib.Path("app_pkg/config.py").read_text(encoding="utf-8")
for match in re.finditer(r'"([a-z0-9./:-]+@sha256:[a-f0-9]{64})"', text):
    print(match.group(1))
PY
    echo "pulling $image"
    docker pull "$image"
done

echo "done"

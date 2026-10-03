#!/bin/sh
set -eu
package_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v uv >/dev/null 2>&1 || { echo 'Install uv using the official instructions first.' >&2; exit 1; }
exec uv run --python 3.11 --no-project "$package_root/install.py" "$@"

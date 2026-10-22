#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$ROOT/DELETE.txt"
[[ -f "$MANIFEST" ]] || { echo "Error: missing DELETE.txt; refusing to continue." >&2; exit 1; }
while IFS= read -r entry || [[ -n "$entry" ]]; do
  entry="${entry%$'\r'}"
  [[ -z "$entry" || "$entry" == \#* ]] && continue
  case "$entry" in
    /*|..|../*|*/../*|*/..) echo "Error: unsafe deletion path in manifest: $entry" >&2; exit 1 ;;
  esac
  target="$ROOT/$entry"
  if [[ -e "$target" || -L "$target" ]]; then
    rm -rf -- "$target"
    echo "Removed manifest path: $entry"
  fi
done < "$MANIFEST"
echo "Deletion manifest applied. Review the diff before committing."

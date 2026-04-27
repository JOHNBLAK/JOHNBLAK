#!/usr/bin/env bash
set -euo pipefail

# Initialize this folder as a standalone repository named bunker (version 1).
# Run this script from inside bunker/.

git init
git add .
git commit -m "chore: bunker v1 initial release"
git tag -a v1 -m "bunker version 1"

echo "Repository initialized and tagged as v1."
echo "To push to GitHub private repo named bunker, run:"
echo "  gh repo create bunker --private --source=. --remote=origin --push"

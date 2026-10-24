#!/usr/bin/env bash
# Publish the committed Explorer to a Hugging Face Docker Space as one fresh commit.
#
#   bash scripts/deploy_space.sh https://huggingface.co/spaces/<user>/<space>
#
# Git asks for a username (your Hugging Face username) and a password (an access token with
# write permission from https://huggingface.co/settings/tokens). Only the files the app needs are
# published, from HEAD; the Space's previous files are replaced.
set -euo pipefail
SPACE_URL="${1:?usage: bash scripts/deploy_space.sh https://huggingface.co/spaces/<user>/<space>}"
cd "$(dirname "$0")/.."

if [[ -n "$(git status --porcelain -- Dockerfile requirements-explorer.txt src data/synthetic frontend deploy)" ]]; then
  echo "Commit your changes first; the Space is built from the last commit." >&2
  exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git archive HEAD Dockerfile .dockerignore requirements-explorer.txt src data/synthetic frontend deploy/space-README.md \
  | tar -x -C "$work"
mv "$work/deploy/space-README.md" "$work/README.md"
rmdir "$work/deploy"

source_commit="$(git rev-parse --short HEAD)"
cd "$work"
git init -q -b main
git add -A
git -c user.name="$(git -C "$OLDPWD" config user.name || echo MedGuard)" \
    -c user.email="$(git -C "$OLDPWD" config user.email || echo medguard@users.noreply.huggingface.co)" \
    commit -q -m "Deploy MedGuard Explorer from ${source_commit}"
echo "Publishing ${source_commit} to ${SPACE_URL} …"
git push --force "$SPACE_URL" main
echo "Done. The Space rebuilds itself; watch the Logs tab, then open the App tab."

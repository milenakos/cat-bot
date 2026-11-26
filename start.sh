#!/bin/sh
set -eu

: "${GIT_REPO:?Set GIT_REPO to the repository URL}"
: "${GIT_BRANCH:=main}"
APP_DIR=/data/repo

if [ ! -d "$APP_DIR/.git" ]; then
    git clone --branch "$GIT_BRANCH" --single-branch "$GIT_REPO" "$APP_DIR"
else
    git -C "$APP_DIR" fetch origin "$GIT_BRANCH"
    git -C "$APP_DIR" pull --ff-only origin "$GIT_BRANCH"
fi

mkdir -p /data
ln -sf /data/cursor.txt "$APP_DIR/cursor.txt"
mkdir -p "$APP_DIR/config"
ln -sf /data/emojis_cache.json "$APP_DIR/config/emojis_cache.json"
ln -sfn /data/stats.py "$APP_DIR/stats.py"

cd "$APP_DIR"
exec python creator.py

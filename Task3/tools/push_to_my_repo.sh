#!/usr/bin/env bash
# 把本任务（task3/）同步到你个人仓库的 Task3/ 目录并推送。
#
#   bash push_to_my_repo.sh                 # 用默认提交信息
#   bash push_to_my_repo.sh "fix: ..."      # 自定义提交信息
#
# 为什么不能直接 `git push origin main`：
#   本仓库是小组仓库（fullcans），根目录是 README.md / tak2 / task3；
#   你个人仓库的根目录是 Task1 / Task2 / Task3。两者布局和历史都不同，
#   git 远程只能一对一映射整个仓库，没法把 task3/ 映射到 Task3/。
#   所以直接推 origin main 会被拒（历史无关），一旦加 --force 就会把
#   Task1、Task2 整个删掉。这个脚本改成：维护一份你仓库的临时检出，
#   把 task3/ 的内容同步进它的 Task3/，再提交推送。
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK3="$(dirname "$HERE")"
REMOTE="git@github.com:boff868/2026Summer-integrated-robot-grouptask.git"
BRANCH="main"
MIRROR="${TASK3_PUSH_MIRROR:-$HOME/.cache/task3_push_mirror}"

if [ -d "$MIRROR/.git" ]; then
  git -C "$MIRROR" fetch -q origin "$BRANCH"
  git -C "$MIRROR" checkout -q "$BRANCH"
  git -C "$MIRROR" reset -q --hard "origin/$BRANCH"
else
  mkdir -p "$(dirname "$MIRROR")"
  git clone -q "$REMOTE" "$MIRROR"
fi

rsync -a \
  --exclude '.git' --exclude '.DS_Store' --exclude '__pycache__' \
  --exclude '*.pyc' --exclude '*.pyo' \
  --exclude 'build/' --exclude 'install/' --exclude 'log/' \
  "$TASK3/" "$MIRROR/Task3/"

git -C "$MIRROR" add -A
if git -C "$MIRROR" diff --cached --quiet; then
  echo "已是最新，没有需要推送的改动。"
  exit 0
fi

git -C "$MIRROR" commit -q -m "${1:-sync task3 source}"
git -C "$MIRROR" push origin "$BRANCH"
echo "已推送 -> $REMOTE ($BRANCH)"

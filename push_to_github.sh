#!/usr/bin/env bash
set -e
REPO_URL="${1:-}"
if [ -z "$REPO_URL" ]; then
  read -rp "请输入你的 GitHub 公开仓库地址 (例如 https://github.com/你的用户名/electrical-cad-skill.git): " REPO_URL
fi
git init
git add .
git commit -m "feat: initial public release of electrical-cad-skill (IEC/GB + EPLAN baseline)"
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
git push -u origin main

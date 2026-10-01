#!/bin/zsh
# Opens an ISSUE (not a PR) on expressjs/express: their CONTRIBUTING asks for an issue before a bug-fix PR.
# Run: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/submit-express-issue.sh"
set -euo pipefail
ME=$(gh api user -q .login)
[[ "$ME" == "andrewstellman" ]] || { echo "gh is logged in as $ME, expected andrewstellman"; exit 1; }
URL=$(gh issue create --repo expressjs/express \
  --title 'res.cookie sends Max-Age=0 (cookie deleted) for a positive maxAge under 1000 ms' \
  --body-file "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/express-cookie.issue.md")
echo "$URL"
gh issue view "$URL" --json number,url,title,state

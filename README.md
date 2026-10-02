# myproject

## Structure
- data/: raw data (NOT in git)
- proc/: processed data (NOT in git)
- scripts/: code
- results/: figures + outputs
- tables/: tables
- paper/: manuscript

## Sync local → GitHub (step by step)

1) Go to the repo:
```bash
cd ~/work/github/steg_call

git pull --rebase

git status

git add -A

git commit -m "Describe what changed"

git push

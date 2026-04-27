# bunker (Version 1)

`bunker` is a lightweight Python-based system intelligence script.
Current release: **v1** (`VERSION` file = `1`).

## What it does
When you run `bunker.py`, it prints a detailed and visually structured report containing:
- System/OS details
- CPU and memory information
- Disk/filesystem usage
- Network details (local IPs, short routing info, best-effort public IP)
- Toolchain details (`python`, `pip`, `git`)
- A full raw JSON snapshot for machine-readable review

## Run
```bash
python3 bunker.py
```

## Initialize as a separate repository and mark version 1
From inside this folder:
```bash
./init_separate_repo.sh
```

This will:
- initialize a standalone git repository
- commit the current files
- create the `v1` tag

## Push this separate repo to a private GitHub repository called `bunker`
If GitHub CLI is authenticated:
```bash
gh repo create bunker --private --source=. --remote=origin --push
```

If `gh` is not authenticated, run `gh auth login` first.

# Contributing

Use `claude`, `codex/work` or `grok` for the corresponding assistant's development work. `codex/work` uses the existing `codex/` branch namespace. Keep `main` as the shared integration and deployment branch.

1. Fetch the latest `main` and preserve other contributors' changes.
2. Work locally. Keep server backups, tokens, private data and machine-specific files out of Git.
3. Read the current PR reviews before the next push and address relevant findings. Review comments refer to the commit they reviewed; verify whether a later change already fixes them.
4. Run tests appropriate to the change, repository lint and JavaScript checks when relevant. Android changes must pass the signed build and emulator workflow before merge.
5. Open a PR into `main`. Merge only after required checks pass and review findings are addressed. The existing deployment workflow then updates production.

Do not replace the owner's scene, edit setup or service configuration incidentally, or grant one assistant access to another's credentials. Use one shared server identity and task state across communication channels.

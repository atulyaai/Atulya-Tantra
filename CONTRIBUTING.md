# Contributing

Use `antigravity`, `claude`, `codex/work` or `grok` for the corresponding assistant's development work. `codex/work` uses the existing `codex/` branch namespace. Keep `main` as the shared integration and deployment branch.

1. Fetch the latest `main` and preserve other contributors' changes.
2. Work locally. Keep server backups, tokens, private data and machine-specific files out of Git.
3. Read the current PR reviews before the next push and address relevant findings. Review comments refer to the commit they reviewed; verify whether a later change already fixes them.
4. Run tests appropriate to the change, repository lint and JavaScript checks when relevant. Android changes must pass the signed build and emulator workflow before merge.
5. Open a PR into `main`. Merge only after required checks pass and review findings are addressed. The existing deployment workflow then updates production.

Do not replace the owner's scene, edit setup or service configuration incidentally, or grant one assistant access to another's credentials. Use one shared server identity and task state across communication channels.

## Commit attribution

Credit only assistants that actually contributed. For Antigravity / Gemini-authored work, include `Co-authored-by: Gemini <noreply@google.com>` (or `Antigravity <noreply@google.com>`). For Codex-authored work, use `Codex <codex@openai.com>` as the author of a substantive code commit, retaining the human maintainer as a co-author. Do not change the maintainer's global Git identity or rewrite published history to add credits. Contributors appear after their code reaches the default branch; a credits file or branch name alone does not update GitHub's Contributors box.

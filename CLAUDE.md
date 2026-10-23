# ssot-redact: instructions for developers

Python package `ssot-redact` (import `ssot_redact`, command `ssot-redact`): redacts a folder of real files
before it goes to an LLM or into an ssot-curator instance. It depends on `ssot-curator` for the readers of
the files (PDF, Word, Excel, mail, chats, OCR) and never changes it: what the curator needs stays there.

All hard-coded text (code, comments, messages, docs) is in **English**.

## Rules
- **This repository is public.** No real data, no real names, no customer or company tied to a real case,
  in code, tests, docs, commits or file names. Tests use only synthetic data (`curator.demo_files`,
  generated images and mail, `tests/msgfile.py`).
- The configurations, candidates, fake-value tables and reports the tool writes contain real data: they are
  git-ignored (`*.yaml`, `*-report.md`) and must stay outside the repository anyway.
- No secrets in the code.
- A change of behaviour comes with a test and with `docs/guide.md` and the skill
  (`.claude/skills/ssot-redact/SKILL.md`) updated; `CHANGELOG.md` for every release.

## Commands
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ../ssot-curator   # local clone of the curator (Windows paths)
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest -q
```

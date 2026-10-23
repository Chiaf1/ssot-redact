# ssot-redact

Redacts a folder of real files — names, companies, emails, phone numbers — **before** it goes to an LLM:
into the `raw/` of an [ssot-curator](https://github.com/Chiaf1/ssot-curator) instance, or to any analysis you
want to run on data you are not allowed to send as they are.

It works on whole folders, in the original formats (txt, csv, Word, Excel, PDF, mail, WhatsApp exports,
images), and it **verifies** what it wrote: a report tells you what was replaced, what was skipped and
whether any forbidden term is still readable.

Status: 0.1.0. Tested on synthetic data and on one real folder (about 90 files: manuals, reports, notes,
spreadsheets, screenshots). Automatic redaction is never perfect: read the report and look at some files
yourself before sending anything.

## How it works

```bash
ssot-redact init redact.yaml --sample ../data --destination my-instance/raw   # a starter configuration
ssot-redact discover redact.yaml   # read everything, list the names to redact: nothing is copied
#   → review redact-candidates.yaml, copy the names into `substitutions:` of redact.yaml
ssot-redact run redact.yaml        # copy + redact + verify → redact-report.md
ssot-redact add redact.yaml        # later: only the new files, with the same fake values
ssot-redact verify redact.yaml     # verification only
```

- **Names** you list (`substitutions`) are replaced everywhere, file and folder names included.
  `discover` finds the candidates for you: mail senders and recipients, chat authors, names in mail
  addresses, capitalized words that are (almost) never written in lowercase, mail domains.
- **Emails** become `person-N@example.test` and **phone numbers** `phone-N`, always the same fake value for
  the same real one, so who wrote to whom stays readable. A number counts as a phone only after `tel`,
  `cell`, `fax`, `phone`… or with a `+` prefix: codes and hexadecimal values are left alone.
- **PDFs** are rebuilt as text only, one page per original page (citations by page stay valid). **Mail**
  is rebuilt with sender, recipients, date, subject, body, thread and redacted attachments. **Images and
  scans** get black boxes over the words to hide (OCR with Tesseract) and lose their metadata.
- **Formats it cannot redact** (old `.doc`/`.xls`, archives, executables…) are **not copied**: they are
  listed in the report. A damaged file is reported and skipped; the others go on.

The full workflow, the configuration and how to read the report: **[docs/guide.md](docs/guide.md)**.
With Claude Code, open this repository and ask: the `ssot-redact` skill guides you step by step.

## Install

Requirements: Python ≥ 3.12, git, and [uv](https://docs.astral.sh/uv/) (or pipx). For images and scanned
PDFs, also [Tesseract](https://github.com/tesseract-ocr/tesseract) with the languages of your documents.

```bash
uv tool install git+https://github.com/Chiaf1/ssot-redact.git            # latest
uv tool install git+https://github.com/Chiaf1/ssot-redact.git@v0.1.0     # a chosen release (CHANGELOG.md)
ssot-redact --version
```

It installs [ssot-curator](https://github.com/Chiaf1/ssot-curator) too: the readers of the files are the
curator's, so what is verified here is exactly what the curator will read.

## Keep the real data out

The configuration, `*-candidates.yaml`, `*-pseudonyms.yaml` (real value → fake value) and `*-report.md`
contain the real names. Keep them, the sample and the destination **outside any git repository**. You are
responsible for what you send to an LLM service: redaction lowers the risk, it does not remove it, and data
of other people may need the owner's consent even when redacted.

## License

Code: [MIT](LICENSE). Documentation: [CC BY 4.0](LICENSE-docs). Dependencies: ssot-curator (MIT),
pypdfium2 (Apache-2.0/BSD), click (BSD), PyYAML (MIT); Tesseract (Apache-2.0) as a system program.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ../ssot-curator      # a local clone of the curator (or let pip fetch it from git)
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q                # Windows: .venv\Scripts\python
```

Tests use synthetic data only. See [CLAUDE.md](CLAUDE.md).

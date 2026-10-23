# Changelog

All notable changes to `ssot-redact`. Versions follow [semantic versioning](https://semver.org/).

## 0.1.0

First release, from the redaction tool of ssot-curator (`tools/prepare_raw.py`, removed there in 0.4.2):

- the `ssot-redact` command: `init`, `discover`, `run`, `add`, `verify`;
- whole folders (`include`, `exclude`, `map`) or a list of files;
- `discover` lists the names to redact from the whole sample: mail senders and recipients, names in mail
  addresses, chat authors, capitalized words (almost) never written in lowercase, mail domains;
- emails and phone numbers replaced by fake values, always the same, also with `add`; a number counts as a
  phone only after a cue word (tel, cell, fax, phone…) or with a `+` prefix;
- txt/csv/md, Word, Excel, PDF (rebuilt as text), mail (`.eml`, `.mbox`, `.msg`, rebuilt), images and
  scanned PDFs (OCR and black boxes); folder and file names redacted;
- files it cannot redact, and images or scans without `ocr:`, are skipped and listed, never copied as they
  are by default; a damaged file is reported and skipped;
- verification of the whole destination (text, names, metadata, mail, images with OCR) and a report.

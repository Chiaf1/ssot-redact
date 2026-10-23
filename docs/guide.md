# ssot-redact: guide

1. [What it is for](#1-what-it-is-for)
2. [Before you start](#2-before-you-start)
3. [The workflow](#3-the-workflow)
4. [The configuration](#4-the-configuration)
5. [Reviewing the candidates](#5-reviewing-the-candidates)
6. [What happens to each format](#6-what-happens-to-each-format)
7. [Reading the report](#7-reading-the-report)
8. [Checking by hand](#8-checking-by-hand)
9. [Large volumes](#9-large-volumes)
10. [With ssot-curator](#10-with-ssot-curator)
11. [Limits](#11-limits)
12. [Troubleshooting](#12-troubleshooting)

## 1. What it is for

You have a folder of real files (mail, reports, notes, spreadsheets, manuals, chats, screenshots) and you
want an LLM to work on them, but you cannot send them as they are: they name people, customers, suppliers,
phone numbers. `ssot-redact` makes a **redacted copy** of the folder, in the same formats, and checks it.

The originals are never modified. The copy goes to a destination folder of your choice: the `raw/` of an
[ssot-curator](https://github.com/Chiaf1/ssot-curator) instance, or any folder you will hand to an LLM.

It does not decide for you what is sensitive. It finds the candidates, replaces what you approve, replaces
emails and phone numbers by itself, and tells you what is still there.

## 2. Before you start

- **Install** it (README, "Install"); for images and scanned PDFs also Tesseract with the languages of
  your documents (e.g. `ita+eng`).
- **Choose a working folder outside any git repository**, e.g. `~/redaction/customer-x/`. The
  configuration and every file the tool writes next to it contain the real names.
- **Have the right to do it.** Redacting lowers the risk of sending data to an LLM service; it does not
  remove it. If the data are not yours, get the owner's consent to the processing, also after redaction.

## 3. The workflow

```bash
cd ~/redaction/customer-x
ssot-redact init redact.yaml --sample /path/to/originals --destination out/raw
ssot-redact discover redact.yaml
```

1. **`init`** writes a commented starter `redact.yaml` with the paths relative to it.
2. **`discover`** reads every file of the sample and writes `redact-candidates.yaml`: the names that look
   like people, companies and places, the most widespread first. Nothing is copied. On a first pass you can
   exclude the images (`exclude: ["**/*.png", "**/*.jpg"]`): OCR is slow.
3. **Review the candidates** ([section 5](#5-reviewing-the-candidates)): copy the ones to hide into
   `substitutions:`, the harmless words into `allowed:`.
4. **`run`** copies and redacts the sample into the destination (which must be empty), then verifies it and
   writes `redact-report.md`. Exit code 0: nothing forbidden found; 2: forbidden terms still readable or
   replacements lost; 1: refused (e.g. destination not empty).
5. **Read the report** ([section 7](#7-reading-the-report)). If a forbidden term is still there, or the
   words to review show a name you missed, add it to `substitutions:`, **empty the destination** and `run`
   again.
6. **Look at some files yourself** ([section 8](#8-checking-by-hand)).
7. Only then give the destination to the LLM.

Later, for new files in the sample: `ssot-redact add redact.yaml` redacts only the files not yet in the
destination, with the same fake emails and phone numbers. `ssot-redact verify redact.yaml` re-checks the
destination at any time (for instance after adding a name to `forbidden_extra`).

## 4. The configuration

```yaml
sample: ../originals            # the originals, relative to this file: never modified
destination: out/raw            # the redacted copy: must be empty for `run`

include: ["**/*"]               # which files (default: all); globs relative to the sample
exclude: ["Old/**", "**/*.bak"] # files to leave out
map:                            # sample folder → destination folder (first match); default: the same path
  - {from: "Mail", to: "conversations"}

substitutions:                  # in order: longest forms first; case-insensitive, whole words
  - ["ACME Industrial S.p.A.", "CUSTOMER"]
  - ["ACME", "CUSTOMER"]
  - ["Mario Rossi", "Technician 1"]
  - ["Rossi", "Technician 1"]
forbidden_extra: ["acme"]       # more terms that must not remain anywhere (verification only)
allowed: ["Ethernet", "Siemens"]  # capitalized words that are fine: not proposed again

auto: {emails: true, phones: true}   # default
unknown_formats: skip           # default; `copy` copies files it cannot redact AS THEY ARE
ocr: {command: tesseract, languages: ita+eng}   # images and scanned PDFs; without it they are skipped
```

Notes:
- **`substitutions`** are applied in order, so put `"Mario Rossi"` before `"Rossi"`, or the full name
  becomes `"Mario Technician 1"`. A term matches whole words, ignoring case; spaces in a term match any
  spacing. Choose replacements that keep the meaning: `Technician 1`, `CUSTOMER`, `Supplier A`.
- Every term of `substitutions` and `forbidden_extra`, and every real email replaced, is searched in the
  whole destination during the verification.
- `files: [{from: "a/b.pdf", to: "docs/b.pdf"}]` instead of `include`/`exclude`/`map` takes only the listed
  files (useful for a small test).
- **Files written next to the configuration** (all with real data): `<name>-candidates.yaml`,
  `<name>-pseudonyms.yaml` (real email/phone → fake one; keep it for `add`), `<name>-report.md`.

## 5. Reviewing the candidates

`redact-candidates.yaml` has four sections, each sorted by the number of files a name appears in:

| Section | What it holds | How reliable |
|---|---|---|
| `people` | mail senders and recipients, names in mail addresses (`mario.rossi@…`), chat authors | high: almost all are to hide; a replacement is proposed (`Person N`) |
| `names` | two or three capitalized words in a row, none a common lowercase word | medium: people, companies, but also titles ("Quick Start") |
| `words` | single capitalized words (almost) never written in lowercase | low: surnames, places and companies among many technical terms |
| `domains` | mail domains | each is an organization: its name is usually among the words |

How to go through it:
1. **`people`** first: keep the lines (they are valid YAML) in `substitutions:`; rename `Person N` to
   something meaningful (`Technician 1`, `Customer contact`). Add the surname alone after the full name if
   the documents use it alone.
2. **`names`**: keep the real names; ignore titles and product names.
3. **`words`** and **`domains`**: the lines are commented (`# - [...]`). Uncomment the names of people,
   customers, suppliers, plants, towns that identify the customer; put the harmless words in `allowed:` so
   they stop coming back. You do not have to go to the bottom: the words that appear in one file only are
   cheap to catch later in the report.
4. Run `discover` again after editing: the names already in `substitutions` or `allowed` disappear from the
   list.

What `discover` cannot find: a name written only in lowercase, a nickname, a name only inside images
(without `ocr:`), a customer identified by a code or an address. Think about those yourself and add them.

## 6. What happens to each format

| Format | What the tool does |
|---|---|
| `.txt`, `.csv`, `.md` | replaced in the text; the encoding is kept |
| `.docx` | replaced in paragraphs, tables, headers and footers; author and other metadata emptied |
| `.xlsx` | replaced in every text cell and in sheet names; author emptied; numbers and formulas untouched |
| `.pdf` with text | **rebuilt as text only**, one page per original page; layout and images dropped; characters outside Windows-1252 become `?` |
| `.pdf` scanned | each page OCR'd, black boxes on the words to hide, rebuilt from the images (needs `ocr:`) |
| `.png`, `.jpg` | OCR, black boxes, saved without metadata (EXIF, GPS) (needs `ocr:`) |
| `.eml`, `.mbox`, `.msg` | **rebuilt** with sender, recipients, date, subject, text body, thread (fake message ids) and attachments redacted by their format; attachments it cannot redact are dropped; other headers (servers, IPs) dropped; `.msg` becomes `.eml` |
| anything else | not copied, listed in the report (`unknown_formats: copy` copies it as it is) |

For every file:
- emails and phone numbers are replaced first (`auto`), then the `substitutions`;
- folder and file names are redacted too;
- the modification date of the original is kept (an SSOT uses it to date a document);
- identical files stay identical, so a duplicate stays recognizable.

**Phone numbers**: a number is replaced only when `tel`, `tel.`, `telefono`, `phone`, `cell`, `cellulare`,
`mobile`, `fax` or `whatsapp` comes right before it, or when it starts with `+`. Numbers without a cue are
left alone (they are listed for review): codes, serial numbers and hexadecimal values look like phone
numbers too.

## 7. Reading the report

`redact-report.md`, in order:

- **Unreadable replacement text**: a replacement made but not readable in the result (the text was lost
  while rebuilding the file). Must be empty.
- **Failed (not copied)**: files that could not be read (damaged, password-protected…).
- **Not copied**: by extension, the files it cannot redact, and images or scans without `ocr:`. Decide for
  each group: convert them (e.g. `.doc` to `.docx`) and redo, or leave them out.
- **Emails and phone numbers replaced automatically**: how many different ones. Check
  `redact-pseudonyms.yaml`: if a "phone" is in fact a code, set `auto: {phones: false}` and redo.
- **Replacements made**: per file, what was replaced and how many times; notes (PDF rebuilt, mail rebuilt,
  attachments dropped, identical copy).
- **Images: words read with low OCR confidence**: check these images yourself.
- **Verification: forbidden terms still present**: must say `None.` If not, the file and the term: add a
  form of the name to `substitutions` (e.g. without accents, all capitals, with a typo) and redo.
- **To review by hand**: emails and phone-like numbers still present, and every capitalized word with its
  count. Read the list from the top: a name you missed usually shows up here.

The verification ignores case, accents and spacing (`M A R I O` is found for terms of 6 letters or more),
and reads everything a reader could see: text, file names, document metadata, mail headers and attachments,
and the images again with OCR.

## 8. Checking by hand

Before sending anything, open a few files of the destination of each kind, chosen where names are likely:
the mail with the most recipients, a report with a signature, a spreadsheet of contacts, a screenshot.
Look for what no list contains: a signature as an image, a name in a table header, a plate number, an
address, an order number that identifies the customer.

## 9. Large volumes

- **Split the work by folders** (`include:`), starting from the most sensitive ones (mail, reports).
- **First pass without images** (`exclude: ["**/*.png", "**/*.jpg", "**/*.jpeg"]`): OCR takes seconds per
  image, and scans are the riskiest part. Add them later with `ssot-redact add`.
- `discover` on a large sample gives thousands of words: go through `people` and `names` fully, `words`
  from the top. The report after the first `run` is the second net.
- Progress is printed every 50 files (200 for `discover` and the verification); a damaged file does not stop
  the run.
- `run` refuses a destination that is not empty: to redo after changing the configuration, empty it by hand
  (it holds only redacted copies). `add` never rewrites the files already there.

## 10. With ssot-curator

Point `destination` at the `raw/` of an instance (or at a folder of it), and use `map:` to put each sample
folder in the `raw/` folder whose reading hint fits it (`curator.yaml` → `sources`). Then in the instance:
`curator run --dry-run`, then `curator run`. With `add`, the new redacted files are read at the next run.

The readers of the files are the curator's: what the verification reads is exactly what the curator will
send to the LLM.

## 11. Limits

- **A name that is not in any list is not replaced.** `discover` helps; it does not guarantee.
- **OCR misreads**: a name read wrong is not covered. Check the images listed with low confidence, or leave
  images out.
- **PDFs lose their layout**: tables become lines of text. The originals keep it.
- **Mail lose formatting and most headers**: the content the curator uses is kept.
- **Context can identify**: a unique machine, a town, an event. Redaction removes names, not knowledge.
- Phone numbers without a cue word and in non-Italian formats without `+` are not replaced: check the
  "possible phone numbers" in the report.

## 12. Troubleshooting

| Message | What to do |
|---|---|
| `already contains files` | `run` needs an empty destination: empty it, or use `add` for the new files only |
| `file not found in the sample` | a path in `files:` is wrong |
| report: `image without ocr:` | add `ocr:` (and install Tesseract) or exclude the images |
| report: forbidden term in a file | add the form found to `substitutions`, empty the destination, `run` again |
| a "phone" that is a code | it had a cue word before it: `auto: {phones: false}`, empty the destination and redo |
| `UnicodeEncodeError` on a text file | the file mixes encodings: convert it to UTF-8 and redo |

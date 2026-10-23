"""The `ssot-redact` command: init, discover, run, add, verify (docs/guide.md)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from ssot_redact import __version__
from ssot_redact.redact import run

STARTER = """\
# ssot-redact configuration. It contains real names: keep it OUTSIDE any repository and outside the
# destination. Workflow: `ssot-redact discover` -> review the candidates -> `ssot-redact run` -> read the
# report -> look at some files yourself. Guide: https://github.com/Chiaf1/ssot-redact/blob/main/docs/guide.md
sample: {sample}             # the originals, relative to this file: never modified
destination: {destination}   # the redacted copy (e.g. the raw/ of an SSOT instance): must be empty

# include: ["**/*"]          # which files of the sample (default: all)
exclude: []                  # e.g. ["Old/**", "**/*.bak"]
# map:                       # sample folder -> destination folder (first match); default: the same path
#   - {{from: "Mail", to: "conversations"}}

substitutions: []            # ["Real Name", "Replacement"], longest forms first (full name before surname)
forbidden_extra: []          # more terms that must not remain anywhere
allowed: []                  # capitalized words that are fine: not proposed again

# auto: {{emails: true, phones: true}}   # fake emails and phone numbers, always the same per real value
# unknown_formats: skip      # files of a format not handled: skip (default) or copy WITHOUT redaction
# ocr: {{command: tesseract, languages: eng}}   # images and scanned PDFs; without it they are skipped
"""


@click.group(help="Redact a folder of real files (names, emails, phone numbers) before it goes to an LLM "
                  "or into an SSOT instance. Start with `ssot-redact init`.")
@click.version_option(__version__, prog_name="ssot-redact")
def cli():
    pass


@cli.command()
@click.argument("config", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--sample", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Folder of the original files.")
@click.option("--destination", required=True, type=click.Path(path_type=Path),
              help="Folder of the redacted copy (created; must be empty).")
def init(config: Path, sample: Path, destination: Path):
    """Write a starter configuration."""
    if config.exists():
        raise click.ClickException(f"{config} already exists")
    base = config.resolve().parent

    def rel(p: Path) -> str:
        return Path(os.path.relpath(p.resolve(), base)).as_posix()

    config.write_text(STARTER.format(sample=rel(sample), destination=rel(destination)), encoding="utf-8")
    click.echo(f"Written {config}. Next: ssot-redact discover {config}")


def _mode(mode: str, doc: str):
    @click.argument("config", type=click.Path(exists=True, dir_okay=False))
    def command(config: str):
        sys.exit(run(config, mode))
    command.__doc__ = doc
    cli.command(name=mode)(command)


_mode("discover", "Read the whole sample and list the names to redact in <config>-candidates.yaml; "
                  "nothing is copied.")
_mode("run", "Copy and redact the sample into the (empty) destination, then verify: <config>-report.md.")
_mode("add", "Like run, only for the files not yet in the destination (same fake values as before).")
_mode("verify", "Verify the destination only: forbidden terms, emails, phone numbers, words to review.")


def main():
    cli()

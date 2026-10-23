"""ssot-redact on SYNTHETIC data only: the names disappear from text, metadata, mail and file names; identical
copies stay identical; whole folders, fake emails and phones, formats not handled, discovery, the command."""
import re

import pytest
import yaml
from click.testing import CliRunner

from curator import demo_files as make_examples
from ssot_redact import redact
from ssot_redact.cli import cli

pytest.importorskip("pypdfium2")


def test_redaction_end_to_end(tmp_path):
    sample = tmp_path / "sample"
    (sample / "Ditta ROSSI").mkdir(parents=True)
    (sample / "nota.txt").write_bytes("Chiamato Mario Rossi (mario.rossi@example.com), poi Rossi ha richiamato.\n"
                                      .encode("cp1252"))
    pdf = make_examples.make_pdf([["Cliente ROSSI SRL", "Tecnico: Bianchi Luca", "Ore 6,5"]])
    (sample / "prot.pdf").write_bytes(pdf)
    (sample / "Ditta ROSSI" / "prot.pdf").write_bytes(pdf)
    make_examples.make_docx(sample / "rep.docx", [("h", "Intervento di Luca Bianchi"), ("p", "Presente Mario Rossi.")])
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active["A1"] = "Referente: Mario Rossi"
    wb.properties.creator = "Mario Rossi"
    wb.save(sample / "tab.xlsx")

    cfg = {
        "sample": "sample", "destination": "inst/raw",
        "files": [{"from": "nota.txt", "to": "note/nota.txt"},
                  {"from": "prot.pdf", "to": "docs/prot.pdf"},
                  {"from": "Ditta ROSSI/prot.pdf", "to": "docs/Ditta CLIENTE/prot.pdf"},
                  {"from": "rep.docx", "to": "docs/rep.docx"},
                  {"from": "tab.xlsx", "to": "docs/tab.xlsx"}],
        "substitutions": [["mario.rossi@example.com", "[OMITTED]"], ["ROSSI SRL", "CLIENTE"],
                          ["Mario Rossi", "Persona 1"], ["Rossi", "Persona 1"],
                          ["Bianchi Luca", "Tecnico 1"], ["Luca Bianchi", "Tecnico 1"]],
        "forbidden_extra": ["Bianchi", "Mario"],
    }
    cfg_path = tmp_path / "redaction.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    before = {p: p.read_bytes() for p in sample.rglob("*") if p.is_file()}

    assert redact.run(cfg_path) == 0
    raw = tmp_path / "inst" / "raw"
    assert {p: p.read_bytes() for p in sample.rglob("*") if p.is_file()} == before   # sample untouched
    a, b = (raw / "docs/prot.pdf").read_bytes(), (raw / "docs/Ditta CLIENTE/prot.pdf").read_bytes()
    assert a == b                                                                      # identical copies
    for p in raw.rglob("*"):
        if p.is_file():
            t = redact.all_text(p).lower()
            assert "rossi" not in t and "bianchi" not in t and "mario" not in t, p
    assert "Persona 1" in (raw / "note/nota.txt").read_bytes().decode("cp1252")
    pdf_text = redact.all_text(raw / "docs/prot.pdf")
    assert "Cliente CLIENTE" in pdf_text and "Tecnico: Tecnico 1" in pdf_text and "6,5" in pdf_text  # in order
    assert (raw / "docs/prot.pdf").stat().st_mtime == pytest.approx((sample / "prot.pdf").stat().st_mtime)
    report = (tmp_path / "redaction-report.md").read_text(encoding="utf-8")
    assert "## Verification: forbidden terms still present\n\nNone." in report

    # a second run on the same destination refuses
    assert redact.run(cfg_path) == 1


def test_images_and_scans_get_black_boxes_and_add_mode(tmp_path):
    from helpers import scanned_pdf, tesseract, text_image
    from PIL import Image
    exe = tesseract()
    sample = tmp_path / "sample"
    sample.mkdir()
    img = text_image(sample / "screen.png", ["Intervento di Mario Rossi su AX4", "Scrivere a mario@example.com"])
    im = Image.open(img)
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"                 # camera maker: metadata must not survive
    im.save(sample / "photo.jpg", "JPEG", exif=exif)
    scanned_pdf(sample / "scan.pdf", ["Foglio di Mario Rossi", "Sostituito il connettore ID8"], tmp_path)
    (sample / "nota.txt").write_text("Nota senza nomi.\n", encoding="utf-8")
    cfg = {"sample": "sample", "destination": "inst/raw", "ocr": {"command": exe, "languages": "eng"},
           "files": [{"from": "nota.txt", "to": "note/nota.txt"}],
           "substitutions": [["Mario Rossi", "Tecnico 1"], ["Rossi", "Tecnico 1"]]}
    cfg_path = tmp_path / "redact.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert redact.run(cfg_path) == 0
    # --add: the note is already there, only the images are processed
    cfg["files"] += [{"from": "screen.png", "to": "docs/screen.png"},
                     {"from": "photo.jpg", "to": "docs/photo.jpg"},
                     {"from": "scan.pdf", "to": "docs/scan.pdf"}]
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert redact.run(cfg_path) == 1                     # without --add: refused
    assert redact.run(cfg_path, "add") == 0
    raw = tmp_path / "inst" / "raw"
    from curator.ocr import TesseractOcr
    ocr = TesseractOcr(exe, "eng")
    for rel in ("docs/screen.png", "docs/photo.jpg"):
        text = ocr.read(raw / rel).text
        assert "Rossi" not in text and "example.com" not in text and "X4" in text
    assert not Image.open(raw / "docs/photo.jpg").getexif()
    from curator.config import SourceRule
    from curator.extractors import extract
    doc = extract(raw / "docs/scan.pdf", "docs/scan.pdf", SourceRule("docs/**/*", "pdf", [], True, {}),
                  reader=ocr, reader_mode="ocr")
    assert "Rossi" not in doc.text and "ID8" in doc.text
    report = (tmp_path / "redact-report.md").read_text(encoding="utf-8")
    assert "black boxes" in report and "Tecnico 1" in report


def _mbox(path, messages):
    """messages: (from, message id, in-reply-to, body, attachments [(name, bytes)])."""
    import mailbox
    from email.message import EmailMessage
    box = mailbox.mbox(str(path))
    for n, (sender, mid, reply, body, atts) in enumerate(messages):
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = sender, "Help <help@acme-srl.test>", "Axis 4"
        m["Date"], m["Message-ID"] = f"Mon, 0{n + 2} Mar 2026 09:10:00 +0100", mid
        if reply:
            m["In-Reply-To"] = m["References"] = reply
        m.set_content(body)
        for name, data in atts:
            m.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
        box.add(m)
    box.close()


def test_whole_folders_mail_pseudonyms_and_formats_not_handled(tmp_path):
    from datetime import datetime, timezone
    from msgfile import msg_bytes
    sample = tmp_path / "sample"
    for d in ("Customers/Ditta ROSSI", "Mail", "Old"):
        (sample / d).mkdir(parents=True)
    (sample / "Customers/Ditta ROSSI/call.txt").write_text(
        "Call Mario Rossi, tel. 333 123 4567, or mario.rossi@acme-srl.test.\n"
        "Default value: 00000181h, node 3000 0001. Swiss office +41 79 123 45 67.\n", encoding="utf-8")
    (sample / "Customers/Ditta ROSSI/again.txt").write_text(
        "Again mario.rossi@acme-srl.test, phone 3331234567.\n", encoding="utf-8")
    _mbox(sample / "Mail/thread.mbox", [
        ("Mario Rossi <mario.rossi@acme-srl.test>", "<m1@acme-srl.test>", None, "Axis 4 stops. Rossi", []),
        ("Luca Bianchi <luca.bianchi@acme-srl.test>", "<m2@acme-srl.test>", "<m1@acme-srl.test>", "Fixed.",
         [("report Rossi.pdf", make_examples.make_pdf([["Technician Rossi", "Fan replaced"]])),
          ("tool.exe", b"MZ binary")])])
    (sample / "Mail/single.msg").write_bytes(msg_bytes(
        "Visit of Luca Bianchi", "Mario Rossi asked for the visit.", "Luca Bianchi", "luca.bianchi@acme-srl.test",
        "help@acme-srl.test", "<m3@acme-srl.test>", datetime(2026, 3, 5, 9, 0, tzinfo=timezone.utc),
        attachments=[("note.txt", b"Rossi was here")]))
    (sample / "Old/old.txt").write_text("Rossi, old.\n", encoding="utf-8")
    (sample / "legacy.doc").write_bytes(b"\xd0\xcf\x11\xe0 Rossi")
    (sample / "~$lock.docx").write_bytes(b"lock")
    (sample / "broken.docx").write_bytes(b"not a zip")
    cfg = {"sample": "sample", "destination": "inst/raw", "exclude": ["Old/**"],
           "map": [{"from": "Mail", "to": "conversations"}],
           "substitutions": [["Mario Rossi", "Person 1"], ["Rossi", "Person 1"],
                             ["Luca Bianchi", "[Technician 1]"], ["Bianchi", "[Technician 1]"]],
           "forbidden_extra": ["acme"]}
    cfg_path = tmp_path / "redact.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    assert redact.run(cfg_path) == 0
    raw = tmp_path / "inst" / "raw"
    files = sorted(p.relative_to(raw).as_posix() for p in raw.rglob("*") if p.is_file())
    assert files == ["Customers/Ditta Person 1/again.txt", "Customers/Ditta Person 1/call.txt",
                     "conversations/single.eml", "conversations/thread.mbox"]
    for f in files:
        t = redact.all_text(raw / f).lower()
        assert "rossi" not in t and "bianchi" not in t and "acme" not in t, f
    call, again = ((raw / "Customers/Ditta Person 1" / n).read_text(encoding="utf-8") for n in ("call.txt", "again.txt"))
    assert "person-1@example.test" in call and "person-1@example.test" in again      # the same fake everywhere
    assert "phone-1" in call and "phone-1" in again
    assert "00000181h" in call and "3000 0001" in call and "+41" not in call    # codes stay; +prefix replaced
    from curator.extractors.email import read_messages
    m1, m2 = read_messages(raw / "conversations/thread.mbox")
    assert m2.in_reply_to == m1.message_id and m1.message_id.endswith("@example.test>")   # thread kept
    assert [a.name for a in m2.attachments] == ["report Person 1.pdf"]                    # .exe dropped
    (m3,) = read_messages(raw / "conversations/single.eml")
    assert re.fullmatch(r"\[Technician 1\] <person-\d+@example\.test>", m3.sender)
    assert m3.subject == "Visit of [Technician 1]" and m3.date.day == 5
    assert m3.attachments[0].data == b"Person 1 was here"
    report = (tmp_path / "redact-report.md").read_text(encoding="utf-8")
    assert "**.doc** ×1: legacy.doc" in report and "broken.docx: " in report and "tool.exe" in report
    assert "lock" not in report and "old.txt" not in report
    assert "mario.rossi@acme-srl.test" in (tmp_path / "redact-pseudonyms.yaml").read_text(encoding="utf-8")

    # --add: a new file gets the same fake values as before
    (sample / "Customers/new.txt").write_text("Write to mario.rossi@acme-srl.test\n", encoding="utf-8")
    assert redact.run(cfg_path, "add") == 0
    assert "person-1@example.test" in (raw / "Customers/new.txt").read_text(encoding="utf-8")


def test_discover_lists_the_names_without_writing_raw(tmp_path):
    sample = tmp_path / "sample"
    sample.mkdir()
    _mbox(sample / "box.mbox", [("Giulia Verdi <giulia.verdi@beta.test>", "<a@beta.test>", None, "Hello", [])])
    (sample / "chat.txt").write_text("04/03/26, 08:15 - Marco Neri: hello\n"
                                     "04/03/26, 08:16 - Marco Neri: Alberto Gialli called\n", encoding="utf-8")
    (sample / "note.txt").write_text("Report of Alberto Gialli. Thanks, thanks and thanks again. Gialli, gialli. Copy to "
                                     "alberto.gialli@beta.test\n", encoding="utf-8")
    cfg_path = tmp_path / "redact.yaml"
    cfg_path.write_text(yaml.safe_dump({"sample": "sample", "destination": "inst/raw",
                                        "substitutions": [["Neri", "Person 9"]]}), encoding="utf-8")
    assert redact.run(cfg_path, "discover") == 0
    assert not (tmp_path / "inst").exists()
    text = (tmp_path / "redact-candidates.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    people = {name: line for name, line in zip([p[0] for p in data["people"]], data["people"])}
    assert {"Giulia Verdi", "Marco Neri"} <= set(people)
    assert "mail header" in text and "chat author" in text
    assert "Alberto Gialli" in people and not data["names"]      # found by its address: among the people
    assert '"Gialli"' in text and '"Thanks"' not in text          # also written in lowercase: an ordinary word
    assert '"beta.test"' in text


def test_images_and_scans_without_ocr_are_skipped_not_stopped(tmp_path):
    from helpers import scanned_pdf, text_image
    sample = tmp_path / "sample"
    sample.mkdir()
    text_image(sample / "screen.png", ["Mario Rossi"])
    scanned_pdf(sample / "scan.pdf", ["Mario Rossi"], tmp_path)
    (sample / "note.txt").write_text("Mario Rossi called.\n", encoding="utf-8")
    cfg_path = tmp_path / "redact.yaml"
    cfg_path.write_text(yaml.safe_dump({"sample": "sample", "destination": "out",
                                        "substitutions": [["Mario Rossi", "Person 1"]]}), encoding="utf-8")
    assert redact.run(cfg_path) == 0
    assert sorted(p.name for p in (tmp_path / "out").rglob("*") if p.is_file()) == ["note.txt"]
    report = (tmp_path / "redact-report.md").read_text(encoding="utf-8")
    assert "image without `ocr:`** ×1: screen.png" in report and "scanned PDF without `ocr:`** ×1: scan.pdf" in report


def test_command_init_discover_run_verify(tmp_path):
    run = CliRunner().invoke
    sample = tmp_path / "data"
    sample.mkdir()
    (sample / "note.txt").write_text("Visit of Mario Rossi.\n", encoding="utf-8")
    cfg_path = tmp_path / "work" / "redact.yaml"
    cfg_path.parent.mkdir()
    r = run(cli, ["init", str(cfg_path), "--sample", str(sample), "--destination", str(tmp_path / "out")])
    assert r.exit_code == 0 and "ssot-redact discover" in r.output
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert cfg["sample"] == "../data" and cfg["destination"] == "../out" and cfg["substitutions"] == []
    assert run(cli, ["init", str(cfg_path), "--sample", str(sample), "--destination", "x"]).exit_code == 1
    assert run(cli, ["discover", str(cfg_path)]).exit_code == 0
    assert '"Mario Rossi"' in (tmp_path / "work" / "redact-candidates.yaml").read_text(encoding="utf-8")
    cfg["substitutions"] = [["Mario Rossi", "Person 1"]]
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert run(cli, ["run", str(cfg_path)]).exit_code == 0
    assert (tmp_path / "out" / "note.txt").read_text(encoding="utf-8") == "Visit of Person 1.\n"
    assert run(cli, ["run", str(cfg_path)]).exit_code == 1                  # destination not empty
    (tmp_path / "out" / "leak.txt").write_text("Mario Rossi\n", encoding="utf-8")
    r = run(cli, ["verify", str(cfg_path)])
    assert r.exit_code == 2 and "forbidden terms found: 1" in r.output

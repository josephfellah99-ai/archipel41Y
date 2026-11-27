"""Extraction de texte et de tableaux depuis les formats bureautiques courants.

Formats : PDF natif, PDF scanné (OCR), JPG/PNG/TIFF (OCR), XLSX, XLS, CSV, DOCX,
DOC (via LibreOffice si installé), TXT. Les archives ZIP sont dépliées par
`expand_zip`. Chaque résultat indique la méthode employée et les avertissements :
rien n'est masqué à l'utilisateur.
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_EXT = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp",
    ".xlsx", ".xlsm", ".xls", ".csv", ".docx", ".doc", ".txt", ".md", ".zip",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
# Formats stockés et prévisualisés mais sans extraction de texte (CAO / BIM)
BINARY_ONLY_EXT = {".dwg", ".dxf", ".ifc", ".pln", ".pla", ".rvt", ".skp", ".3dm"}


@dataclass
class Page:
    number: int
    text: str = ""
    tables: list[list[list[str]]] = field(default_factory=list)
    ocr: bool = False


@dataclass
class ExtractResult:
    filename: str
    pages: list[Page] = field(default_factory=list)
    method: str = ""
    ocr_used: bool = False
    warnings: list[str] = field(default_factory=list)
    status: str = "ok"  # ok|ocr|vide|non_supporte|erreur

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)

    @property
    def tables(self) -> list[tuple[int, list[list[str]]]]:
        return [(p.number, t) for p in self.pages for t in p.tables]

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "method": self.method,
            "ocr_used": self.ocr_used,
            "warnings": self.warnings,
            "status": self.status,
            "page_count": len(self.pages),
            "table_count": sum(len(p.tables) for p in self.pages),
        }


# --------------------------------------------------------------------------- OCR
def find_tesseract(explicit: str | None = None) -> str | None:
    candidates = [explicit, os.environ.get("TESSERACT_CMD"), shutil.which("tesseract")]
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                candidates.append(os.path.join(base, "Tesseract-OCR", "tesseract.exe"))
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def ocr_available(tesseract_cmd: str | None = None) -> bool:
    return find_tesseract(tesseract_cmd) is not None


def _ocr_image(img, tesseract_cmd: str | None) -> str:
    import pytesseract

    cmd = find_tesseract(tesseract_cmd)
    if not cmd:
        raise RuntimeError("OCR indisponible : Tesseract n'est pas installé sur ce poste.")
    pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        langs = pytesseract.get_languages(config="")
    except Exception:
        langs = []
    lang = "fra" if "fra" in langs else "eng"
    # psm 6 : bloc de texte uniforme — conserve mieux les lignes de tableaux de devis
    return pytesseract.image_to_string(img.convert("L"), lang=lang, config="--psm 6")


# --------------------------------------------------------------------------- formats
def _clean_cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).replace("\n", " ").strip()


def _extract_pdf(path: Path, res: ExtractResult, tesseract_cmd: str | None) -> None:
    import pdfplumber

    res.method = "pdf-natif"
    ocr_pages = 0
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=False) or ""
            tables = []
            try:
                for t in page.extract_tables():
                    rows = [[_clean_cell(c) for c in row] for row in t if row and any(c for c in row)]
                    if len(rows) >= 2:
                        tables.append(rows)
            except Exception as exc:  # tableaux mal formés
                res.warnings.append(f"Page {i} : détection de tableau impossible ({exc}).")
            pg = Page(number=i, text=text, tables=tables)
            if len(text.strip()) < 25:
                # Page probablement scannée → OCR
                try:
                    from .pdfium_safe import PDFIUM_LOCK

                    with PDFIUM_LOCK:  # pdfplumber.to_image utilise pdfium : jamais en parallèle
                        img = page.to_image(resolution=300).original
                    pg.text = _ocr_image(img, tesseract_cmd)
                    pg.ocr = True
                    ocr_pages += 1
                except Exception as exc:
                    res.warnings.append(f"Page {i} : aucun texte natif et OCR impossible — {exc}")
            res.pages.append(pg)
    if ocr_pages:
        res.ocr_used = True
        res.method = "pdf-ocr" if ocr_pages == len(res.pages) else "pdf-mixte"
        res.warnings.append(
            f"{ocr_pages} page(s) traitée(s) par OCR : vérifiez attentivement les montants extraits."
        )


def _extract_image(path: Path, res: ExtractResult, tesseract_cmd: str | None) -> None:
    from PIL import Image, ImageOps

    res.method = "image-ocr"
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.width < 1800:  # agrandir les petites images améliore nettement l'OCR
        ratio = 1800 / img.width
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))
    text = _ocr_image(img, tesseract_cmd)
    res.pages.append(Page(number=1, text=text, ocr=True))
    res.ocr_used = True
    res.warnings.append("Document image traité par OCR : vérifiez attentivement les montants extraits.")


def _extract_xlsx(path: Path, res: ExtractResult) -> None:
    import openpyxl

    res.method = "tableur-xlsx"
    # lecture en mémoire : le stockage par empreinte n'a pas d'extension de fichier
    wb = openpyxl.load_workbook(io.BytesIO(path.read_bytes()), data_only=True, read_only=True)
    for i, ws in enumerate(wb.worksheets, start=1):
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [_clean_cell(c) for c in row]
            if any(cells):
                rows.append(cells)
        text = f"[Feuille : {ws.title}]\n" + "\n".join(" | ".join(c for c in r if c) for r in rows)
        res.pages.append(Page(number=i, text=text, tables=[rows] if rows else []))
    wb.close()


def _extract_xls(path: Path, res: ExtractResult) -> None:
    import xlrd

    res.method = "tableur-xls"
    book = xlrd.open_workbook(file_contents=path.read_bytes())
    for i, sh in enumerate(book.sheets(), start=1):
        rows = []
        for r in range(sh.nrows):
            cells = [_clean_cell(c) for c in sh.row_values(r)]
            if any(cells):
                rows.append(cells)
        text = f"[Feuille : {sh.name}]\n" + "\n".join(" | ".join(c for c in r if c) for r in rows)
        res.pages.append(Page(number=i, text=text, tables=[rows] if rows else []))


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _extract_csv(path: Path, res: ExtractResult) -> None:
    res.method = "csv"
    content = _decode(path.read_bytes())
    sample = content[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";" if sample.count(";") >= sample.count(",") else ","
    rows = [[_clean_cell(c) for c in r] for r in csv.reader(io.StringIO(content), delimiter=delim)]
    rows = [r for r in rows if any(r)]
    res.pages.append(Page(number=1, text="\n".join(" | ".join(r) for r in rows), tables=[rows] if rows else []))


def _extract_docx(path: Path, res: ExtractResult) -> None:
    import docx

    res.method = "docx"
    d = docx.Document(str(path))
    paras = [p.text for p in d.paragraphs if p.text.strip()]
    tables = []
    for t in d.tables:
        rows = []
        for row in t.rows:
            cells = []
            prev = None
            for c in row.cells:  # les cellules fusionnées sont répétées par python-docx
                if c._tc is prev:
                    continue
                prev = c._tc
                cells.append(_clean_cell(c.text))
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    table_text = "\n".join(" | ".join(r) for t in tables for r in t)
    res.pages.append(Page(number=1, text="\n".join(paras) + ("\n" + table_text if table_text else ""), tables=tables))


def find_libreoffice(explicit: str | None = None) -> str | None:
    candidates = [explicit, shutil.which("soffice"), shutil.which("libreoffice")]
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            candidates.append(os.path.join(base, "LibreOffice", "program", "soffice.exe"))
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def _extract_doc(path: Path, res: ExtractResult, libreoffice_cmd: str | None) -> None:
    soffice = find_libreoffice(libreoffice_cmd)
    if not soffice:
        res.status = "non_supporte"
        res.method = "doc"
        res.warnings.append(
            "Format Word 97-2003 (.doc) : installez LibreOffice sur ce poste ou enregistrez le fichier "
            "au format .docx pour permettre l'extraction."
        )
        return
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "docx", "--outdir", tmp, str(path)],
            check=True, capture_output=True, timeout=180,
        )
        out = Path(tmp) / (path.stem + ".docx")
        _extract_docx(out, res)
    res.method = "doc-libreoffice"


def extract_document(path: str | Path, filename: str | None = None, *,
                     tesseract_cmd: str | None = None, libreoffice_cmd: str | None = None) -> ExtractResult:
    path = Path(path)
    filename = filename or path.name
    ext = Path(filename).suffix.lower()
    res = ExtractResult(filename=filename)
    try:
        if ext == ".pdf":
            _extract_pdf(path, res, tesseract_cmd)
        elif ext in IMAGE_EXT:
            _extract_image(path, res, tesseract_cmd)
        elif ext in (".xlsx", ".xlsm"):
            _extract_xlsx(path, res)
        elif ext == ".xls":
            _extract_xls(path, res)
        elif ext == ".csv":
            _extract_csv(path, res)
        elif ext == ".docx":
            _extract_docx(path, res)
        elif ext == ".doc":
            _extract_doc(path, res, libreoffice_cmd)
        elif ext in (".txt", ".md"):
            res.method = "texte"
            res.pages.append(Page(number=1, text=_decode(path.read_bytes())))
        elif ext in BINARY_ONLY_EXT:
            res.method = "binaire"
            res.status = "non_supporte"
            res.warnings.append("Fichier CAO/BIM conservé et versionné ; pas d'extraction de texte pour ce format.")
            return res
        else:
            res.status = "non_supporte"
            res.warnings.append(f"Format {ext or 'inconnu'} non pris en charge pour l'extraction.")
            return res
    except RuntimeError as exc:
        res.status = "erreur"
        res.warnings.append(str(exc))
        return res
    except Exception as exc:
        res.status = "erreur"
        res.warnings.append(f"Erreur de lecture du fichier : {type(exc).__name__}: {exc}")
        return res
    if res.status == "ok":
        if not res.text.strip():
            res.status = "vide"
            res.warnings.append("Aucun texte exploitable n'a été trouvé dans ce document.")
        elif res.ocr_used:
            res.status = "ocr"
    return res


def _zip_name(info: zipfile.ZipInfo) -> str:
    """Nom d'une entrée ZIP : UTF-8 si l'archive le déclare, sinon encodage OEM de Windows (CP850 en France, puis CP437)."""
    if info.flag_bits & 0x800:
        return info.filename
    raw = info.filename.encode("cp437", "replace")
    for enc in ("utf-8", "cp850"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return info.filename


def expand_zip(path: str | Path, max_files: int = 200, max_total_mb: int = 500) -> list[tuple[str, bytes]]:
    """Déplie une archive ZIP (récursivement) en protégeant contre les « zip bombs »
    et les chemins malveillants. Retourne [(nom, contenu)]."""
    out: list[tuple[str, bytes]] = []
    total = 0

    def walk(zf: zipfile.ZipFile, prefix: str, depth: int):
        nonlocal total
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _zip_name(info).replace("\\", "/")
            if name.startswith("__MACOSX/") or Path(name).name.startswith("."):
                continue
            base = Path(name).name  # on ignore toute arborescence (pas de « ../ »)
            if info.file_size > max_total_mb * 1024 * 1024:
                continue
            total += info.file_size
            if total > max_total_mb * 1024 * 1024 or len(out) >= max_files:
                raise ValueError("Archive trop volumineuse ou contenant trop de fichiers.")
            data = zf.read(info)
            ext = Path(base).suffix.lower()
            if ext == ".zip" and depth < 2:
                walk(zipfile.ZipFile(io.BytesIO(data)), prefix + Path(base).stem + "/", depth + 1)
            elif ext in SUPPORTED_EXT | BINARY_ONLY_EXT:
                out.append((prefix + base, data))

    with zipfile.ZipFile(str(path)) as zf:
        walk(zf, "", 0)
    return out

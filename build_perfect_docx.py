#!/usr/bin/env python3
"""
build_perfect_docx.py - Professional LaTeX to Word (.docx) converter for RKA P3.
Uses Pandoc 3.14 to convert LaTeX (with native OMML equations, zero raw LaTeX remnants)
and python-docx to style tables, headings, cover page, and headers/footers.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

BASE_DIR = Path(__file__).resolve().parent
KAP_DIR = BASE_DIR / "kapituluak"
IRUDIAK_DIR = BASE_DIR / "irudiak"
PANDOC_EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc" / "pandoc.exe"

DRIVE_DIR = Path(
    r"G:\Mi unidad\Borrar - Dualismo filosófico - Eneko\Espiritualismo\Estudios\Euskal Herriko Unibertsitatea\Compartido Eneko\4. Kurtsoa\4. Kurtsoa 1. Lauhilekoa\RKA\rka_6\3. Proiektua"
)

LOCAL_DOCX = BASE_DIR / "Praktika_Txostena_RKA_P3.docx"
DRIVE_DOCX1 = DRIVE_DIR / "Praktika_Txostena_RKA_P3.docx"
DRIVE_DOCX2 = DRIVE_DIR / "Praktika Txostena.docx"

REF_MAP = {
    # Figures
    "fig:diag-kp2": "3.1",
    "fig:kp-grafikoak": "3.2",
    "fig:kp-ibilbideak": "3.2a",
    "fig:kp-angeluak": "3.2b",
    "fig:v-ibilbideak": "3.3",
    "fig:pid-grafikoak": "3.4",
    "fig:pid-ibilbideak": "3.4a",
    "fig:pid-angeluak": "3.4b",
    "fig:enun-ibilbideak": "3.5",
    # Tables
    "tab:kp-sweep": "3.1",
    "tab:abiadura-sweep": "3.2",
    "tab:pid-sweep": "3.3",
    "tab:enuntziatua-sweep": "3.4",
    "tab:aldaerak": "4.1",
    # Sections
    "sec:estrategia": "1.1",
    "sec:prozesua": "1.2",
    "sec:geometria": "2.1",
    "sec:erregresioa": "2.2",
    "sec:kontrol-legeak": "2.3",
    "sec:pid-inplementazioa": "2.4",
    "sec:angelu-egiaztapena": "3.1",
    "sec:emaitzak-p": "3.2",
    "sec:emaitzak-abiadura": "3.3",
    "sec:emaitzak-pid": "3.4",
    "sec:emaitzak-enuntziatua": "3.5",
    "sec:aldaerak": "4.1",
    "sec:ondorio-nagusiak": "4.2",
    "sec:exekuzioa": "A.1",
    "sec:fitxategiak": "A.2",
}

TABLE_CAPTIONS = {
    "tab:kp-sweep": "3.1. taula: $K_p$ parametroaren eragina Gazebon. Tarte egokia: $1{,}5 \\le K_p \\le 2{,}0$.",
    "tab:abiadura-sweep": "3.2. taula: Abiadura-legeen konparaketa: konstantea ($K_V = 0$) vs moldatua ($K_V = 2$).",
    "tab:pid-sweep": "3.3. taula: $K_i$ eta $K_d$ osagaien eta PID konbinazioaren eragina ($K_p = 2{,}0$). Tarte egokiak: $0 \\le K_i \\le 0{,}2$ eta $0 \\le K_d \\le 0{,}3$.",
    "tab:enuntziatua-sweep": "3.4. taula: Enuntziatuko adibideen ebaluazioa Gazebon: hiruretan seinaleak jotzen ditu.",
    "tab:aldaerak": "4.1. taula: Hiru aldaera nagusien konparaketa Gazeboko \\texttt{yahboom\\_track} zirkuituan.",
}

FIG_CAPTIONS = {
    "fig:diag-kp2": "3.1. irudia: Laserrak atzemandako puntuak eta doitutako zuzena seinale baten ondoan ($K_p = 2{,}0$). Erregresioak zutoina naturaltasunez iragazten du.",
    "fig:v-ibilbideak": "3.3. irudia: Abiadura konstantearen ($K_V = 0$) eta moldatuaren ($K_V = 2$) arteko ibilbideak.",
    "fig:enun-ibilbideak": "3.5. irudia: Enuntziatuko hiru adibideen ibilbideak: hiruretan robotak kanpoko seinaleak jotzen ditu $K_p = 0{,}6$ txikiegia delako izkinak garbi hartzeko.",
}

def extract_braced(text: str, start_pos: int) -> tuple[str, int]:
    depth = 0
    for idx in range(start_pos, len(text)):
        if text[idx] == '{':
            depth += 1
        elif text[idx] == '}':
            depth -= 1
            if depth == 0:
                return text[start_pos + 1:idx], idx + 1
    return text[start_pos + 1:], len(text)

def clean_chapter_latex(text: str) -> str:
    t = text

    # Pre-replace table captions with explicit numbers before stripping labels
    for label, cap_text in TABLE_CAPTIONS.items():
        t = re.sub(
            r'\\caption\{[^}]*\}\s*\\label\{' + re.escape(label) + r'\}',
            lambda m, ct=cap_text: f'\\caption{{{ct}}}',
            t
        )

    # Pre-replace standalone figure captions with explicit numbers
    for label, cap_text in FIG_CAPTIONS.items():
        t = re.sub(
            r'\\caption\{[^}]*\}\s*\\label\{' + re.escape(label) + r'\}',
            lambda m, ct=cap_text: f'\\caption{{{ct}}}',
            t
        )

    # Remove remaining labels
    t = re.sub(r'\\label\{[^}]+\}', '', t)

    # Replace \ref{...}
    for k, v in REF_MAP.items():
        t = t.replace(f'\\ref{{{k}}}', v)
    
    # In case any \ref is left
    t = re.sub(r'\\ref\{[^}]+\}', '1', t)

    # Remove layout-specific memoir commands
    t = re.sub(r'\\(?:clearpage|newpage|noindent)', '', t)
    t = re.sub(r'\\(?:Needspace|needspace)\{[^}]+\}', '', t)
    t = re.sub(r'\\addlinespace(?:\[[^\]]*\])?', '', t)

    # Convert tabularx to standard 6-column tabular
    while r'\begin{tabularx}' in t:
        pos = t.find(r'\begin{tabularx}')
        end0 = pos + len(r'\begin{tabularx}')
        b1 = t.find('{', end0)
        _, end1 = extract_braced(t, b1)
        b2 = t.find('{', end1)
        _, end2 = extract_braced(t, b2)
        t = t[:pos] + r'\begin{tabular}{llllll}' + t[end2:]

    t = t.replace(r'\end{tabularx}', r'\end{tabular}')

    # Unpack subfigures into sequential full-width figures
    kp_subfigs_replacement = (
        r"\begin{figure}[h]\centering\includegraphics[width=0.85\textwidth]{irudiak/kp_ibilbideak.png}"
        r"\caption{3.2a irudia: Ibilbideak zirkuituan (\texttt{/gz\_pose}) $K_p$ parametroaren arabera.}\end{figure}"
        "\n\n"
        r"\begin{figure}[h]\centering\includegraphics[width=0.85\textwidth]{irudiak/kp_angeluak.png}"
        r"\caption{3.2b irudia: $\theta$ orientazio-angelua denboran zehar $K_p$ desberdinekin.}\end{figure}"
    )
    t = re.sub(
        r'\\begin\{figure\}\[H\]\s*\\centering\s*\\begin\{subfigure\}.*?kp_grafikoak.*?\\end\{figure\}',
        lambda m: kp_subfigs_replacement,
        t,
        flags=re.DOTALL
    )

    pid_subfigs_replacement = (
        r"\begin{figure}[h]\centering\includegraphics[width=0.85\textwidth]{irudiak/pid_ibilbideak.png}"
        r"\caption{3.4a irudia: Ibilbideak PID konbinazioetarako ($K_p = 2{,}0$).}\end{figure}"
        "\n\n"
        r"\begin{figure}[h]\centering\includegraphics[width=0.85\textwidth]{irudiak/pid_angeluak.png}"
        r"\caption{3.4b irudia: $\theta$ orientazio-angelua denboran zehar PID osagaiekin.}\end{figure}"
    )
    t = re.sub(
        r'\\begin\{figure\}\[H\]\s*\\centering\s*\\begin\{subfigure\}.*?pid_grafikoak.*?\\end\{figure\}',
        lambda m: pid_subfigs_replacement,
        t,
        flags=re.DOTALL
    )

    # For standalone figures: ensure irudiak/ prefix
    def fix_img_path(m):
        opts = m.group(1) or ""
        p = m.group(2)
        if not p.startswith("irudiak/") and not p.startswith("irudiak\\"):
            p = f"irudiak/{p}"
        return f"\\includegraphics[{opts}]{{{p}}}" if opts else f"\\includegraphics{{{p}}}"

    t = re.sub(r'\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}', fix_img_path, t)

    return t

def assemble_pandoc_latex() -> str:
    chaps = [
        ("1. Sarrera", KAP_DIR / "01_sarrera.tex"),
        ("2. Metodologia eta Garapena", KAP_DIR / "02_garapena.tex"),
        ("3. Emaitzak eta Ebaluazioa", KAP_DIR / "03_emaitzak.tex"),
        ("4. Ondorioak", KAP_DIR / "04_ondorioak.tex"),
        ("A. Eranskina: Kodea eta Exekuzioa", KAP_DIR / "05_eranskina.tex"),
    ]

    parts = [
        r"\documentclass{report}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{amsmath}",
        r"\usepackage{booktabs}",
        r"\usepackage{graphicx}",
        r"\begin{document}",
    ]

    for title, path in chaps:
        raw = path.read_text(encoding="utf-8")
        clean = clean_chapter_latex(raw)
        parts.append(f"\\chapter*{{{title}}}")
        parts.append(clean)
        parts.append(r"\newpage")

    parts.append(r"\end{document}")
    return "\n\n".join(parts)

def style_table(table):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    num_rows = len(table.rows)
    for r_idx, row in enumerate(table.rows):
        trPr = row._tr.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
        
        # Header row
        if r_idx == 0:
            trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
            for cell in row.cells:
                tcPr = cell._tc.get_or_add_tcPr()
                tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="F1F5F9"/>'))
                tcBorders = parse_xml(
                    f'<w:tcBorders {nsdecls("w")}>'
                    f'  <w:top w:val="single" w:sz="12" w:space="0" w:color="0F172A"/>'
                    f'  <w:bottom w:val="single" w:sz="12" w:space="0" w:color="0F172A"/>'
                    f'  <w:left w:val="none"/>'
                    f'  <w:right w:val="none"/>'
                    f'</w:tcBorders>'
                )
                tcPr.append(tcBorders)
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = Pt(4)
                    p.paragraph_format.space_after = Pt(4)
                    for run in p.runs:
                        run.font.bold = True
                        run.font.size = Pt(9.5)
                        run.font.name = "Calibri"
                        run.font.color.rgb = RGBColor(15, 23, 42)
        elif r_idx == num_rows - 1:
            for cell in row.cells:
                tcPr = cell._tc.get_or_add_tcPr()
                tcBorders = parse_xml(
                    f'<w:tcBorders {nsdecls("w")}>'
                    f'  <w:bottom w:val="single" w:sz="12" w:space="0" w:color="0F172A"/>'
                    f'  <w:left w:val="none"/>'
                    f'  <w:right w:val="none"/>'
                    f'</w:tcBorders>'
                )
                tcPr.append(tcBorders)
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = Pt(2.5)
                    p.paragraph_format.space_after = Pt(2.5)
                    for run in p.runs:
                        run.font.size = Pt(9)
                        run.font.name = "Calibri"
        else:
            for cell in row.cells:
                tcPr = cell._tc.get_or_add_tcPr()
                tcBorders = parse_xml(
                    f'<w:tcBorders {nsdecls("w")}>'
                    f'  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                    f'  <w:left w:val="none"/>'
                    f'  <w:right w:val="none"/>'
                    f'</w:tcBorders>'
                )
                tcPr.append(tcBorders)
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = Pt(2.5)
                    p.paragraph_format.space_after = Pt(2.5)
                    for run in p.runs:
                        run.font.size = Pt(9)
                        run.font.name = "Calibri"

def add_cover_page(doc):
    cover_p = doc.paragraphs[0]
    
    def insert_p_before(text="", space_before=0, space_after=6, align=WD_ALIGN_PARAGRAPH.CENTER, bold=False, size=11, color=(15, 23, 42)):
        new_p = doc.add_paragraph()
        new_p.alignment = align
        new_p.paragraph_format.space_before = Pt(space_before)
        new_p.paragraph_format.space_after = Pt(space_after)
        if text:
            r = new_p.add_run(text)
            r.font.name = "Calibri"
            r.font.bold = bold
            r.font.size = Pt(size)
            r.font.color.rgb = RGBColor(*color)
        cover_p._p.addprevious(new_p._p)
        return new_p

    insert_p_before("EUSKAL HERRIKO UNIBERTSITATEA (UPV/EHU)", space_before=24, space_after=2, size=11, bold=True, color=(71, 85, 105))
    insert_p_before("INFORMATIKA FAKULTATEA", space_before=0, space_after=2, size=11, bold=True, color=(71, 85, 105))
    insert_p_before("Informatika Ingeniaritzako Gradua  ·  Robotika eta Kontrol Adimendunak", space_before=0, space_after=40, size=10, color=(100, 116, 139))

    insert_p_before("Paretari jarraitzen atzeraelikadurazko kontrolaren bidez (PID)", space_before=40, space_after=12, size=22, bold=True, color=(15, 23, 42))
    insert_p_before("Laser bidezko erregresio lineala eta PID kontrolagailua Gazeboko ingurune simulatuan", space_before=0, space_after=60, size=13, color=(51, 65, 85))

    insert_p_before("Egileak:", space_before=30, space_after=4, size=10, bold=True, color=(100, 116, 139))
    insert_p_before("Eneko Ruiz  ·  Eneko Pardavila  ·  Omar Ouinas", space_before=0, space_after=20, size=12, bold=True, color=(15, 23, 42))

    insert_p_before("Irakaslea: Elena Lazkano", space_before=10, space_after=4, size=11, color=(51, 65, 85))
    insert_p_before("2026ko azaroa", space_before=0, space_after=40, size=11, color=(100, 116, 139))

    p_break = doc.add_paragraph()
    p_break.paragraph_format.page_break_before = True
    cover_p._p.addprevious(p_break._p)

def post_process_docx(docx_path: Path):
    doc = Document(docx_path)

    for sec in doc.sections:
        sec.top_margin = Inches(0.98)
        sec.bottom_margin = Inches(0.98)
        sec.left_margin = Inches(0.98)
        sec.right_margin = Inches(0.98)
        sec.header_distance = Inches(0.5)
        sec.footer_distance = Inches(0.5)

        hdr = sec.header
        hp = hdr.paragraphs[0]
        hp.text = "Robotika eta Kontrol Adimendunak  ·  PID Kontrolagailua (Gazebo)"
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if hp.runs:
            hp.runs[0].font.size = Pt(8.5)
            hp.runs[0].font.name = "Calibri"
            hp.runs[0].font.color.rgb = RGBColor(100, 116, 139)

        ftr = sec.footer
        fp = ftr.paragraphs[0]
        fp.text = "Informatika Fakultatea (UPV/EHU)                        Orria "
        fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for r in fp.runs:
            r.font.size = Pt(8.5)
            r.font.name = "Calibri"
            r.font.color.rgb = RGBColor(100, 116, 139)

        fldSimple_page = parse_xml(r'<w:fldSimple %s w:instr="PAGE"/>' % nsdecls('w'))
        fp._p.append(fldSimple_page)

        r_mid = fp.add_run(" / ")
        r_mid.font.size = Pt(8.5)
        r_mid.font.name = "Calibri"
        r_mid.font.color.rgb = RGBColor(100, 116, 139)

        fldSimple_numpages = parse_xml(r'<w:fldSimple %s w:instr="NUMPAGES"/>' % nsdecls('w'))
        fp._p.append(fldSimple_numpages)

    add_cover_page(doc)

    for tbl in doc.tables:
        if len(tbl.rows) > 1 and len(tbl.columns) >= 3:
            style_table(tbl)

    for p in doc.paragraphs:
        if p.style.name == "Source Code" or "Consolas" in [r.font.name for r in p.runs if r.font.name]:
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.05
            p.paragraph_format.left_indent = Inches(0.2)
            p.paragraph_format.right_indent = Inches(0.2)
            for r in p.runs:
                r.font.name = "Consolas"
                r.font.size = Pt(8.5)
                r.font.color.rgb = RGBColor(30, 41, 59)
        elif p.style.name.startswith("Heading 1"):
            p.paragraph_format.space_before = Pt(20)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.keep_with_next = True
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.size = Pt(16)
                r.font.bold = True
                r.font.color.rgb = RGBColor(15, 23, 42)
        elif p.style.name.startswith("Heading 2"):
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.size = Pt(13)
                r.font.bold = True
                r.font.color.rgb = RGBColor(30, 41, 59)
        elif p.style.name == "Caption":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(10)
            for r in p.runs:
                r.font.name = "Calibri"
                r.font.size = Pt(9.5)
                r.font.italic = True
                r.font.color.rgb = RGBColor(71, 85, 105)
        else:
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.15
            for r in p.runs:
                if not r.font.name:
                    r.font.name = "Calibri"
                if not r.font.size:
                    r.font.size = Pt(10.5)

    doc.save(docx_path)
    print(f"[OK] Post-processed {docx_path}")

def main():
    print("[*] Assembling unified LaTeX for Pandoc...")
    full_latex = assemble_pandoc_latex()
    combined_tex = BASE_DIR / "pandoc_combined.tex"
    combined_tex.write_text(full_latex, encoding="utf-8")
    print(f"[OK] Wrote {len(full_latex)} chars to {combined_tex}")

    raw_docx = BASE_DIR / "raw_pandoc.docx"
    print("[*] Running Pandoc conversion to DOCX with native OMML...")
    cmd = [
        str(PANDOC_EXE),
        "-f", "latex",
        "-t", "docx",
        str(combined_tex),
        "-o", str(raw_docx),
        "--resource-path", f"{IRUDIAK_DIR};{BASE_DIR}"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("[ERROR] Pandoc failed:", res.stderr)
        return
    print(f"[OK] Pandoc converted successfully to {raw_docx}")

    print("[*] Post-processing DOCX layout, tables, and headers/footers...")
    post_process_docx(raw_docx)

    shutil.copy2(raw_docx, LOCAL_DOCX)
    print(f"[OK] Saved local DOCX: {LOCAL_DOCX} ({LOCAL_DOCX.stat().st_size} bytes)")

    if DRIVE_DIR.exists():
        shutil.copy2(raw_docx, DRIVE_DOCX1)
        shutil.copy2(raw_docx, DRIVE_DOCX2)
        print(f"[OK] Copied to Google Drive: {DRIVE_DOCX1}")
        print(f"[OK] Copied to Google Drive: {DRIVE_DOCX2}")
    else:
        print(f"[WARN] Drive directory not found: {DRIVE_DIR}")

if __name__ == "__main__":
    main()

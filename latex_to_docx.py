import re
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

DRIVE_DIR = Path(r"G:\Mi unidad\Borrar - Dualismo filosófico - Eneko\Espiritualismo\Estudios\Euskal Herriko Unibertsitatea\Compartido Eneko\4. Kurtsoa\4. Kurtsoa 1. Lauhilekoa\RKA\rka_6\3. Proiektua")
BASE_DIR = Path(__file__).resolve().parent

OUTPUT_DOCX_MAIN = DRIVE_DIR / "Praktika_Txostena_RKA_P3.docx"
LOCAL_DOCX_MAIN = BASE_DIR / "Praktika_Txostena_RKA_P3.docx"

REFS = {
    "fig:ibilbideak": "1",
    "fig:traj-p1": "1a",
    "fig:traj-p2": "1b",
    "fig:traj-p3": "1c",
    "fig:kamera-segmentazioa": "2",
    "fig:sim-zirkuitua": "3",
    "fig:abiadurak-telemetria": "4",
    "tab:rwander-10min": "1",
    "tab:rwander-5min": "1",
    "tab:sim-emaitzak": "2",
    "tab:road-5saiakera": "2",
    "tab:rwander-extra": "4",
    "lst:rwander": "1",
    "lst:road": "2",
    "sec:oz-sektoreak": "2.1",
    "sec:oz-mugimendua": "2.2",
    "sec:oz-esplorazioa": "2.3",
    "sec:oz-emaitzak": "2.4",
    "sec:oz-arriskuak": "2.5",
    "sec:er-eremuak": "3.1",
    "sec:er-abiadurak": "3.2",
    "sec:er-simulazioa": "3.3",
    "sec:er-doikuntzak": "3.4",
    "sec:er-emaitzak": "3.5",
    "sec:eranskina-probak": "5.1",
    "sec:eranskina-materialak": "5.2",
}

CITES = {
    "ros2": "[1]",
    "lazkano2026": "[2]",
    "gazebo": "[3]",
}

table_counter = 0
fig_counter = 0


def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>'))


def extract_braced(text: str, start_pos: int) -> tuple[str, int]:
    """Finds the contents of { ... } starting at start_pos (where text[start_pos] == '{').
    Returns (inside_text, end_pos_including_closing_brace)."""
    assert text[start_pos] == '{'
    depth = 0
    for idx in range(start_pos, len(text)):
        if text[idx] == '{':
            depth += 1
        elif text[idx] == '}':
            depth -= 1
            if depth == 0:
                return text[start_pos + 1:idx], idx + 1
    return text[start_pos + 1:], len(text)


def clean_latex(text: str) -> str:
    t = text

    # 1. Strip \label{...} and \setlength{...}{...}
    while r'\label{' in t:
        pos = t.find(r'\label{')
        _, end = extract_braced(t, pos + len(r'\label{') - 1)
        t = t[:pos] + t[end:]

    while r'\setlength{' in t:
        pos = t.find(r'\setlength{')
        _, end1 = extract_braced(t, pos + len(r'\setlength{') - 1)
        rest = t[end1:].lstrip()
        if rest.startswith('{'):
            start2 = t.find('{', end1)
            _, end2 = extract_braced(t, start2)
            t = t[:pos] + t[end2:]
        else:
            t = t[:pos] + t[end1:]

    # 2. Replace \ref{...}
    while r'\ref{' in t:
        pos = t.find(r'\ref{')
        key, end = extract_braced(t, pos + len(r'\ref{') - 1)
        clean_key = key.strip()
        val = REFS.get(clean_key, "1")
        t = t[:pos] + val + t[end:]

    # 3. Replace \cite{...}
    while r'\cite{' in t:
        pos = t.find(r'\cite{')
        key, end = extract_braced(t, pos + len(r'\cite{') - 1)
        clean_key = key.strip()
        val = CITES.get(clean_key, "")
        t = t[:pos] + val + t[end:]

    # 4. Replace fractions: \frac{num}{den}
    while r'\frac{' in t:
        pos = t.find(r'\frac{')
        num, end1 = extract_braced(t, pos + len(r'\frac{') - 1)
        rest = t[end1:].lstrip()
        if rest.startswith('{'):
            start2 = t.find('{', end1)
            den, end2 = extract_braced(t, start2)
            clean_num = clean_latex(num)
            clean_den = clean_latex(den)
            if '+' in clean_num or '-' in clean_num:
                frac_str = f"({clean_num}) / {clean_den}"
            else:
                frac_str = f"{clean_num} / {clean_den}"
            t = t[:pos] + frac_str + t[end2:]
        else:
            t = t[:pos] + clean_latex(num) + t[end1:]

    # 5. Unwrap formatting macros: \textbf{...}, \texttt{...}, etc.
    for macro in [r'\textbf{', r'\texttt{', r'\emph{', r'\mathbf{', r'\text{']:
        while macro in t:
            pos = t.find(macro)
            inner, end = extract_braced(t, pos + len(macro) - 1)
            clean_inner = clean_latex(inner)
            t = t[:pos] + clean_inner + t[end:]

    # 6. Specific math/symbols
    t = t.replace(r'\mathcal{U}', 'U')
    t = t.replace(r'\bar{t}', 't̄')
    t = t.replace(r'\max', 'max')
    t = t.replace(r'\min', 'min')
    t = t.replace(r'V_{\max}', 'V_max')
    t = t.replace(r'V_{\min}', 'V_min')
    t = re.sub(r'([A-Za-z]+)_\{([^}]+)\}', r'\1_\2', t)

    t = t.replace('{,}', ',')
    t = t.replace('~', ' ')
    t = t.replace(r'\,', ' ')
    t = t.replace(r'\_', '_')
    t = t.replace(r'\%', '%')
    t = t.replace(r'\dots', '...')
    t = t.replace(r'\pm', '±')
    t = t.replace(r'\le', '≤')
    t = t.replace(r'\ge', '≥')
    t = t.replace(r'\approx', '≈')
    t = t.replace(r'\pi', 'π')
    t = t.replace(r'\theta', 'θ')
    t = t.replace(r'\omega', 'ω')
    t = t.replace(r'\cdot', '·')
    t = t.replace(r'\times', '×')
    t = t.replace(r'^\circ', '°')
    t = t.replace(r'\circ', '°')
    t = t.replace(r'\tabcolsep', '')
    t = t.replace('--', '–')

    # Strip inline $ math delimiters
    t = t.replace('$', '')

    # Trailing backslashes before spaces or end of string
    t = re.sub(r'\\(?=\s|$|[.,:;])', '', t)

    # Clean double spaces
    t = re.sub(r' +', ' ', t)
    return t.strip()


def add_code_block(doc, code_text):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "F4F5F7")
    cell.width = Inches(6.5)

    # Prevent row split across pages
    trPr = tbl.rows[0]._tr.get_or_add_trPr()
    trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.keep_together = True

    clean_code = code_text.strip()
    run = p.add_run(clean_code)
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(30, 41, 59)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(4)


def parse_latex_table(doc, table_text: str):
    global table_counter
    caption = ""
    m_cap = re.search(r'\\caption(?:\[[^\]]*\])?\{', table_text)
    if m_cap:
        start_brace = m_cap.end() - 1
        raw_cap, _ = extract_braced(table_text, start_brace)
        caption = clean_latex(raw_cap)

    # Extract table rows
    rows = []
    for line in table_text.splitlines():
        line = line.strip()
        if not line or any(cmd in line for cmd in ("\\begin", "\\end", "\\toprule", "\\midrule", "\\bottomrule", "\\caption", "\\centering", "\\label", "\\setlength")):
            continue
        if "\\multicolumn" in line:
            m_txt = re.search(r'\{@\{\}l\}\{', line)
            if m_txt:
                start_brace = m_txt.end() - 1
                inner, _ = extract_braced(line, start_brace)
                rows.append([clean_latex(inner)])
            continue
        if "\\\\" in line:
            line = line.replace("\\\\", "")
        parts = [clean_latex(c) for c in line.split("&")]
        if any(p.strip() for p in parts):
            rows.append(parts)

    if not rows:
        return

    num_cols = max(len(r) for r in rows)
    tbl = doc.add_table(rows=len(rows), cols=num_cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    table_counter += 1

    for r_idx, r_data in enumerate(rows):
        row_obj = tbl.rows[r_idx]
        trPr = row_obj._tr.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
        if r_idx == 0:
            trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))

        is_header = (r_idx == 0)
        is_colspan = (len(r_data) == 1 and num_cols > 1)

        if is_colspan:
            cell = tbl.cell(r_idx, 0)
            cell.text = r_data[0]
            for c_idx in range(1, num_cols):
                cell.merge(tbl.cell(r_idx, c_idx))
            if cell.paragraphs[0].runs:
                cell.paragraphs[0].runs[0].bold = True
            set_cell_background(cell, "F8FAFC")
            continue

        for c_idx, val in enumerate(r_data):
            cell = tbl.cell(r_idx, c_idx)
            cell.text = val
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            if is_header:
                set_cell_background(cell, "E2E8F0")
                if p.runs:
                    p.runs[0].bold = True
            else:
                set_cell_background(cell, "FFFFFF" if r_idx % 2 == 1 else "F8FAFC")

    if caption:
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(3)
        p_cap.paragraph_format.space_after = Pt(6)
        r = p_cap.add_run(f"{table_counter}. taula: {caption}")
        r.font.size = Pt(9.5)
        r.italic = True
        r.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def parse_figure_block(doc, fig_text: str):
    global fig_counter
    fig_counter += 1

    # Extract subfigures if any
    subfig_matches = list(re.finditer(r'\\begin\{subfigure\}(?:\[[^\]]*\])?\{[^}]*\}', fig_text))
    subfigs = []
    for sf in subfig_matches:
        start_sf = sf.start()
        end_sf = fig_text.find(r'\end{subfigure}', start_sf)
        sf_content = fig_text[start_sf:end_sf]
        m_img = re.search(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', sf_content)
        m_cap = re.search(r'\\caption(?:\[[^\]]*\])?\{', sf_content)
        subcap = ""
        if m_cap:
            raw_c, _ = extract_braced(sf_content, m_cap.end() - 1)
            subcap = clean_latex(raw_c)
        if m_img:
            subfigs.append((m_img.group(1).strip(), subcap))

    # Main outer caption
    no_subfigs = re.sub(r'\\begin\{subfigure\}.*?\\end\{subfigure\}', '', fig_text, flags=re.DOTALL)
    m_main_cap = re.search(r'\\caption(?:\[[^\]]*\])?\{', no_subfigs)
    cap_text = ""
    if m_main_cap:
        raw_mc, _ = extract_braced(no_subfigs, m_main_cap.end() - 1)
        cap_text = clean_latex(raw_mc)

    if len(subfigs) == 3:
        # 3 trajectories: 2 on top (Row 1), 1 centered below (Row 2)
        # Width: 3.05 inches each for clear axis readability
        tbl = doc.add_table(rows=2, cols=2)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Row 1: Pose 1 & Pose 2
        for c_idx in range(2):
            cell = tbl.cell(0, c_idx)
            img_name, subcap = subfigs[c_idx]
            img_path = BASE_DIR / "irudiak" / img_name
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            if img_path.exists():
                p.add_run().add_picture(str(img_path), width=Inches(3.05))
            p_cap = cell.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_after = Pt(4)
            r_c = p_cap.add_run(f"({chr(97 + c_idx)}) {subcap}")
            r_c.font.size = Pt(8.5)
            r_c.italic = True
            r_c.font.color.rgb = RGBColor(71, 85, 105)

        # Row 2: Pose 3 centered across 2 merged cells
        cell_bottom = tbl.cell(1, 0)
        cell_bottom.merge(tbl.cell(1, 1))
        img_name, subcap = subfigs[2]
        img_path = BASE_DIR / "irudiak" / img_name
        p_b = cell_bottom.paragraphs[0]
        p_b.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_b.paragraph_format.space_before = Pt(2)
        p_b.paragraph_format.space_after = Pt(2)
        if img_path.exists():
            p_b.add_run().add_picture(str(img_path), width=Inches(3.05))
        p_b_cap = cell_bottom.add_paragraph()
        p_b_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_b_cap.paragraph_format.space_after = Pt(4)
        r_b_c = p_b_cap.add_run(f"(c) {subcap}")
        r_b_c.font.size = Pt(8.5)
        r_b_c.italic = True
        r_b_c.font.color.rgb = RGBColor(71, 85, 105)

        for row in tbl.rows:
            trPr = row._tr.get_or_add_trPr()
            trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

        tblPr = tbl._tbl.tblPr
        tblBorders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'<w:top w:val="none"/><w:left w:val="none"/><w:bottom w:val="none"/><w:right w:val="none"/>'
            f'<w:insideH w:val="none"/><w:insideV w:val="none"/>'
            f'</w:tblBorders>'
        )
        tblPr.append(tblBorders)

    elif subfigs:
        tbl = doc.add_table(rows=1, cols=len(subfigs))
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        for col_idx, (img_name, subcap) in enumerate(subfigs):
            cell = tbl.cell(0, col_idx)
            img_path = BASE_DIR / "irudiak" / img_name
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            if img_path.exists():
                p.add_run().add_picture(str(img_path), width=Inches(3.1))
            p_cap = cell.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_after = Pt(4)
            r_c = p_cap.add_run(subcap)
            r_c.font.size = Pt(8.5)
            r_c.italic = True
        for row in tbl.rows:
            row._tr.get_or_add_trPr().append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
        tblPr = tbl._tbl.tblPr
        tblBorders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'<w:top w:val="none"/><w:left w:val="none"/><w:bottom w:val="none"/><w:right w:val="none"/>'
            f'<w:insideH w:val="none"/><w:insideV w:val="none"/>'
            f'</w:tblBorders>'
        )
        tblPr.append(tblBorders)
    else:
        m_img = re.search(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', fig_text)
        if m_img:
            img_name = m_img.group(1).strip()
            img_path = BASE_DIR / "irudiak" / img_name
            if img_path.exists():
                p_img = doc.add_paragraph()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(6)
                p_img.paragraph_format.space_after = Pt(4)
                p_img.paragraph_format.keep_with_next = True
                width = Inches(5.2) if ("kamera" in img_name or "abiadurak" in img_name) else Inches(4.5)
                p_img.add_run().add_picture(str(img_path), width=width)

    if cap_text:
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(8)
        p_cap.paragraph_format.keep_with_next = True
        r = p_cap.add_run(f"{fig_counter}. irudia: {cap_text}")
        r.font.size = Pt(9.5)
        r.italic = True
        r.font.color.rgb = RGBColor(71, 85, 105)


def parse_chapter_content(doc, content: str):
    lines = content.splitlines()
    in_code = False
    code_lines = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Comments
        if line.startswith("%"):
            i += 1
            continue

        # Code block
        if "\\begin{lstlisting}" in line:
            in_code = True
            code_lines = []
            i += 1
            continue
        elif "\\end{lstlisting}" in line:
            in_code = False
            add_code_block(doc, "\n".join(code_lines))
            i += 1
            continue
        elif in_code:
            code_lines.append(lines[i])
            i += 1
            continue

        # Table block
        if "\\begin{table}" in line:
            table_lines = [line]
            i += 1
            while i < len(lines) and "\\end{table}" not in lines[i]:
                table_lines.append(lines[i])
                i += 1
            if i < len(lines):
                table_lines.append(lines[i])
                i += 1
            parse_latex_table(doc, "\n".join(table_lines))
            continue
        elif "\\begin{tabular" in line:
            table_lines = [line]
            i += 1
            while i < len(lines) and "\\end{tabular" not in lines[i]:
                table_lines.append(lines[i])
                i += 1
            if i < len(lines):
                table_lines.append(lines[i])
                i += 1
            parse_latex_table(doc, "\n".join(table_lines))
            continue

        # Figure block
        if "\\begin{figure}" in line:
            figure_lines = [line]
            i += 1
            while i < len(lines) and "\\end{figure}" not in lines[i]:
                figure_lines.append(lines[i])
                i += 1
            if i < len(lines):
                figure_lines.append(lines[i])
                i += 1
            parse_figure_block(doc, "\n".join(figure_lines))
            continue

        # Headings
        if line.startswith(r'\section{') or line.startswith(r'\section['):
            pos = len(r'\section')
            while pos < len(line) and line[pos] == '[':
                cb = line.find(']', pos)
                if cb != -1:
                    pos = cb + 1
                else:
                    break
            if pos < len(line) and line[pos] == '{':
                inner, _ = extract_braced(line, pos)
                doc.add_heading(clean_latex(inner), level=2)
            else:
                doc.add_heading(clean_latex(line), level=2)
            i += 1
            continue

        if line.startswith(r'\subsection{') or line.startswith(r'\subsection['):
            pos = len(r'\subsection')
            while pos < len(line) and line[pos] == '[':
                cb = line.find(']', pos)
                if cb != -1:
                    pos = cb + 1
                else:
                    break
            if pos < len(line) and line[pos] == '{':
                inner, _ = extract_braced(line, pos)
                doc.add_heading(clean_latex(inner), level=3)
            else:
                doc.add_heading(clean_latex(line), level=3)
            i += 1
            continue

        if line.startswith(r'\paragraph{'):
            inner, end_pos = extract_braced(line, len(r'\paragraph'))
            p = doc.add_paragraph()
            r = p.add_run(clean_latex(inner) + " ")
            r.bold = True
            rest = line[end_pos:].strip()
            if rest:
                p.add_run(clean_latex(rest))
            i += 1
            continue

        # Enumerate / Itemize
        if line.startswith("\\item"):
            item_text = line[len("\\item"):].strip()
            if item_text.startswith(r'\textbf{'):
                start_brace = len(r'\textbf')
                inner, end_pos = extract_braced(item_text, start_brace)
                prefix = clean_latex(inner)
                body = clean_latex(item_text[end_pos:])
                p = doc.add_paragraph(style='List Bullet')
                r = p.add_run(prefix + " ")
                r.bold = True
                if body:
                    p.add_run(body)
            else:
                p = doc.add_paragraph(clean_latex(item_text), style='List Bullet')
            i += 1
            continue

        # Equations
        if line.startswith(r"\begin{equation}") or line == r"\[":
            end_tag = r"\end{equation}" if "equation" in line else r"\]"
            eq_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(end_tag):
                eq_lines.append(lines[i].strip())
                i += 1
            i += 1
            raw_eq = " ".join(eq_lines)
            eq_text = clean_latex(raw_eq)
            p_eq = doc.add_paragraph()
            p_eq.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_eq.paragraph_format.space_before = Pt(6)
            p_eq.paragraph_format.space_after = Pt(6)
            p_eq.paragraph_format.keep_with_next = True
            r_eq = p_eq.add_run(eq_text)
            r_eq.italic = True
            r_eq.font.size = Pt(11)
            continue

        # Bold question prompts (from peer review / guide)
        if line.startswith(r'\textbf{') and line.endswith("}"):
            inner, _ = extract_braced(line, len(r'\textbf'))
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True
            r = p.add_run(clean_latex(inner))
            r.bold = True
            r.font.color.rgb = RGBColor(15, 23, 42)
            i += 1
            continue

        # Skip formatting and layout directives
        if (
            line.startswith(r"\needspace")
            or line.startswith(r"\clearpage")
            or line.startswith(r"\vspace")
            or line.startswith(r"\begin{itemize}")
            or line.startswith(r"\end{itemize}")
            or line.startswith(r"\begin{enumerate}")
            or line.startswith(r"\end{enumerate}")
            or line.startswith(r"\begin{description}")
            or line.startswith(r"\end{description}")
            or line.startswith(r"\begin{figure}")
            or line.startswith(r"\end{figure}")
            or line in (r"\centering", r"\hfill", r"\begingroup", r"\endgroup", r"\]")
        ):
            i += 1
            continue

        # Regular paragraph
        if line:
            p_lines = [line]
            i += 1
            while i < len(lines):
                next_l = lines[i].strip()
                if not next_l or next_l.startswith("\\"):
                    break
                p_lines.append(next_l)
                i += 1
            doc.add_paragraph(clean_latex(" ".join(p_lines)))
        else:
            i += 1


def add_xml_field(para, field_name):
    run = para.add_run()
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(100, 116, 139)
    fld = parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr="{field_name}"/>')
    run._r.append(fld)


def build_document():
    global table_counter, fig_counter
    table_counter = 0
    fig_counter = 0

    doc = Document()

    # Configure margins and page numbering footer
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

        footer = section.footer
        p_ftr = footer.paragraphs[0]
        p_ftr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_txt = p_ftr.add_run("Orria ")
        r_txt.font.size = Pt(9)
        r_txt.font.color.rgb = RGBColor(100, 116, 139)
        add_xml_field(p_ftr, "PAGE")
        r_sep = p_ftr.add_run(" / ")
        r_sep.font.size = Pt(9)
        r_sep.font.color.rgb = RGBColor(100, 116, 139)
        add_xml_field(p_ftr, "NUMPAGES")

    # Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(12)
    p_title.paragraph_format.space_after = Pt(4)
    r_title = p_title.add_run("3. Proiektua")
    r_title.bold = True
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(22)
    r_title.font.color.rgb = RGBColor(15, 23, 42)

    # Subtitle
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(14)
    r_sub = p_sub.add_run("Praktikaren txostena")
    r_sub.italic = True
    r_sub.font.size = Pt(12)
    r_sub.font.color.rgb = RGBColor(71, 85, 105)

    # Authors & Info box
    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_meta.paragraph_format.space_after = Pt(24)
    r_meta = p_meta.add_run(
        "Egileak: Eneko Ruiz, Eneko Pardavila, Omar Ouinas\n"
        "Informatika Ingeniaritzako Gradua · Robotika eta Kontrol Adimendunak (Irakaslea: Elena Lazkano)\n"
        "Euskal Herriko Unibertsitatea (UPV/EHU)"
    )
    r_meta.font.size = Pt(10)
    r_meta.font.color.rgb = RGBColor(100, 116, 139)

    chapters = [
        ("1. Sarrera", "01_sarrera.tex"),
        ("2. Metodologia eta Garapena", "02_garapena.tex"),
        ("3. Emaitzak eta Ebaluazioa", "03_emaitzak.tex"),
        ("4. Ondorioak", "04_ondorioak.tex"),
        ("5. Eranskina", "05_eranskina.tex"),
    ]

    for ch_title, filename in chapters:
        f_path = BASE_DIR / "kapituluak" / filename
        if not f_path.exists():
            continue

        doc.add_heading(ch_title, level=1)
        content = f_path.read_text(encoding="utf-8")
        parse_chapter_content(doc, content)

    # Save to local destination
    if LOCAL_DOCX_MAIN.exists():
        try:
            LOCAL_DOCX_MAIN.unlink()
        except Exception:
            pass
    doc.save(str(LOCAL_DOCX_MAIN))
    print(f"[OK] Guardado localmente: {LOCAL_DOCX_MAIN.name}")

    # Save to Google Drive
    if DRIVE_DIR.exists():
        try:
            if OUTPUT_DOCX_MAIN.exists():
                OUTPUT_DOCX_MAIN.unlink()
        except Exception:
            pass
        doc.save(str(OUTPUT_DOCX_MAIN))
        print(f"[OK] Guardado en Google Drive: {OUTPUT_DOCX_MAIN.name}")
    else:
        print(f"[ALERTA] No se encontro la carpeta de Drive: {DRIVE_DIR}")


if __name__ == "__main__":
    build_document()

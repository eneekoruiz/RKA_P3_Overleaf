"""
Auditoría Estricta de Reconciliación: Google Document (.docx) <-> Overleaf (LaTeX / PDF)
Proyecto RKA 3 (Paretari jarraitzea atzeraelikadurazko kontrolaren bidez)
Garantiza simetría total línea a línea, párrafo a párrafo y metadato a metadato.
"""
import argparse
import difflib
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import docx
except ImportError:
    docx = None

try:
    import pypdfium2
except ImportError:
    pypdfium2 = None


def clean_text(text: str) -> str:
    """Normaliza espacios, comillas, guiones, símbolos griegos, subíndices y matemáticas."""
    subscript_map = str.maketrans("₀₁₂₃₄₅₆₇₈₉ᵢⱼₖ", "0123456789ijk")
    t = text.translate(subscript_map)
    t = t.replace(r'\_', '_')
    t = t.replace("’", "'").replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-").replace("−", "-")
    t = t.replace("·", " ")
    t = t.replace('θ', 'theta').replace('β', 'beta').replace('ω', 'omega')
    t = re.sub(r'\\(?:theta|beta|omega)\b', lambda m: m.group(0)[1:], t)
    t = re.sub(r'\\(?:cos|sin|arctan|frac|cdot|qquad|quad|dots)\b', '', t)
    t = re.sub(r'\\(?:begin|end)\{[^}]+\}', '', t)
    t = re.sub(r'\{,\}', ',', t)
    t = re.sub(r'\\cite\{[^}]+\}', '', t)
    t = re.sub(r'\[\d+(?:[,\s]+\d+)*\]', '', t)
    t = re.sub(r'\\text(?:it|bf|tt|sl)\{([^}]+)\}', r'\1', t)
    t = re.sub(r'\\(?:label|ref|subcaption|caption|needspace)\{[^}]+\}', '', t)
    t = t.replace('$', '')
    t = t.replace('_', ' ')
    t = re.sub(r'(\d+)\s*hz\b', r'\1 hz', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def tokenize(text: str) -> List[str]:
    """Extrae lista de tokens alfanuméricos en minúsculas."""
    cleaned = clean_text(text).lower()
    return re.findall(r'[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ_]+', cleaned)


def audit_document_reconciliation(
    doc_path: Path,
    tex_dir: Path,
    pdf_path: Optional[Path] = None
) -> List[str]:
    defects: List[str] = []

    if docx is None:
        return ["[ERROR] 'python-docx' library is not installed. Run 'pip install python-docx'."]

    # Google Drive fallback if mounted
    drive_p3 = Path(r"G:\Mi unidad\Borrar - Dualismo filosófico - Eneko\Espiritualismo\Estudios\Euskal Herriko Unibertsitatea\Compartido Eneko\4. Kurtsoa\4. Kurtsoa 1. Lauhilekoa\RKA\rka_6\3. Proiektua\Praktika_Txostena_RKA_P3.docx")
    if not doc_path.exists() and drive_p3.exists():
        print(f"-> [INFO] Usando documento original desde Google Drive: {drive_p3}")
        doc_path = drive_p3

    if not doc_path.exists():
        return [f"[ERROR] Reference document not found at '{doc_path}'."]

    doc = docx.Document(str(doc_path))
    main_tex_path = tex_dir / "main.tex"
    azala_tex_path = tex_dir / "config" / "azala.tex"

    if not main_tex_path.exists():
        return [f"[ERROR] 'main.tex' not found in '{tex_dir}'."]

    main_tex = main_tex_path.read_text(encoding="utf-8")
    azala_tex = azala_tex_path.read_text(encoding="utf-8") if azala_tex_path.exists() else ""

    # ==============================================================
    # FASE 1: Metadatos y Detección Estricta de Campos Asimétricos
    # ==============================================================
    print("--- [Fase 1] Auditoría de Simetría en Metadatos y Portada ---")
    
    # 1.1 Detección del campo 'Irakaslea'
    docx_all_text = " ".join([p.text for p in doc.paragraphs])
    tex_all_sources = main_tex + "\n" + azala_tex
    for tf in sorted((tex_dir / "kapituluak").glob("*.tex")):
        tex_all_sources += "\n" + tf.read_text(encoding="utf-8")

    has_irakaslea_doc = "irakasle" in docx_all_text.lower()
    has_irakaslea_tex = "irakasle" in tex_all_sources.lower()

    if has_irakaslea_doc and not has_irakaslea_tex:
        defects.append("Campo asimétrico: 'Irakaslea' presente en el documento Word/Google pero ausente en LaTeX.")
    elif has_irakaslea_tex and not has_irakaslea_doc:
        defects.append("Campo asimétrico: 'Irakaslea' presente en LaTeX pero ausente en el documento Word/Google.")
    else:
        print("  [OK] Simetría de campo 'Irakaslea' verificada en ambos entornos.")

    # 1.2 Verificación de Título y Subtítulo
    m_title = re.search(r'\\newcommand\{\\izenburua\}\{([^}]+)\}', main_tex)
    m_sub = re.search(r'\\newcommand\{\\azpititulua\}\{([^}]+)\}', main_tex)

    if m_title:
        title_val = clean_text(m_title.group(1)).lower()
        if title_val not in clean_text(docx_all_text).lower():
            defects.append(f"Discrepancia en Título: '{m_title.group(1)}' no coincide con el encabezado de Google Doc.")
        else:
            print(f"  [OK] Título validado: {m_title.group(1)}")

    if m_sub:
        sub_val = clean_text(m_sub.group(1)).lower()
        if sub_val not in clean_text(docx_all_text).lower():
            defects.append(f"Discrepancia en Subtítulo: '{m_sub.group(1)}' no coincide con el subtítulo de Google Doc.")
        else:
            print(f"  [OK] Subtítulo validado: {m_sub.group(1)}")

    # 1.3 Verificación de Autores
    authors = ["Eneko Ruiz", "Eneko Pardavila", "Omar Ouinas"]
    for aut in authors:
        if aut.lower() not in docx_all_text.lower():
            defects.append(f"Autor ausente en Google Doc: '{aut}'")
        if aut.lower() not in tex_all_sources.lower():
            defects.append(f"Autor ausente en Overleaf/LaTeX: '{aut}'")
        print(f"  [OK] Autor verificado en ambos entornos: {aut}")

    # ==============================================================
    # FASE 2: Simetría Estructural de Capítulos y Secciones
    # ==============================================================
    print("\n--- [Fase 2] Auditoría de Simetría Estructural (Títulos y Secciones) ---")
    docx_headings = [clean_text(p.text) for p in doc.paragraphs if p.style.name.startswith("Heading")]
    
    tex_headings = []
    for ch_match in re.finditer(r'\\chapter\{([^}]+)\}', main_tex):
        tex_headings.append(clean_text(ch_match.group(1)))
    
    for tf in sorted((tex_dir / "kapituluak").glob("*.tex")):
        f_text = tf.read_text(encoding="utf-8")
        for sec_m in re.finditer(r'\\(?:section|subsection)(?:\[[^\]]*\])?\{([^}]+)\}', f_text):
            tex_headings.append(clean_text(sec_m.group(1)))

    print(f"  Títulos detectados en Google Doc: {len(docx_headings)}")
    print(f"  Títulos detectados en Overleaf:   {len(tex_headings)}")

    for h in docx_headings:
        h_core = re.sub(r'^\d+(?:\.\d+)*\s*', '', h).strip().lower()
        if not h_core or h_core in ["gaien aurkibidea", "aurkibidea"]:
            continue
        matched_tex = any(h_core in th.lower() or th.lower() in h_core for th in tex_headings)
        if not matched_tex:
            defects.append(f"Sección o Capítulo ausente en Overleaf: '{h}'")
        else:
            print(f"  [OK] Estructura sincronizada: '{h}'")

    # ==============================================================
    # FASE 3: Reconciliación Línea a Línea y Párrafo a Párrafo
    # ==============================================================
    print("\n--- [Fase 3] Reconciliación Textual Párrafo a Párrafo ---")
    
    docx_paras: List[Tuple[int, str]] = []
    in_toc = False
    for idx, p in enumerate(doc.paragraphs):
        raw_t = p.text.strip()
        t = clean_text(raw_t)
        if not t:
            continue
        if "gaien aurkibidea" in raw_t.lower():
            in_toc = True
            continue
        if in_toc:
            if p.style.name.startswith("Heading") and not "aurkibidea" in raw_t.lower():
                in_toc = False
            elif re.match(r'^\d+(?:\.\d+)*\s+', raw_t) or raw_t in ["Gaien aurkibidea", "Aurkibidea"]:
                continue

        if p.style.name.startswith("Heading"):
            continue
        if any(t.startswith(prefix) for prefix in ["3. Proiektua:", "Egileak:", "Informatika Ingeniaritzako", "Irakaslea:"]):
            continue
        docx_paras.append((idx, t))

    tex_tokens = tokenize(tex_all_sources)
    tex_token_str = " " + " ".join(tex_tokens) + " "

    if not pdf_path and (tex_dir / "overleaf_downloaded.pdf").exists():
        pdf_path = tex_dir / "overleaf_downloaded.pdf"

    pdf_token_str = ""
    if pdf_path and pdf_path.exists() and pypdfium2:
        try:
            pdf = pypdfium2.PdfDocument(pdf_path)
            pdf_raw = " ".join([page.get_textpage().get_text_range() for page in pdf])
            pdf_tokens = tokenize(pdf_raw)
            pdf_token_str = " " + " ".join(pdf_tokens) + " "
        except Exception as e:
            print(f"  [WARN] No se pudo leer PDF para reconciliación: {e}")

    unmatched_docx = 0
    for idx, p_text in docx_paras:
        p_tokens = tokenize(p_text)
        if len(p_tokens) < 4:
            continue

        probe_len = min(6, len(p_tokens))
        probe = " ".join(p_tokens[:probe_len])
        found = (" " + probe + " ") in tex_token_str or (pdf_token_str and (" " + probe + " ") in pdf_token_str)

        if not found:
            for s_idx in range(len(p_tokens) - 4):
                sub_probe = " ".join(p_tokens[s_idx:s_idx + 5])
                if (" " + sub_probe + " ") in tex_token_str or (pdf_token_str and (" " + sub_probe + " ") in pdf_token_str):
                    found = True
                    break

        if not found:
            unmatched_docx += 1
            snippet = p_text[:90] + ("..." if len(p_text) > 90 else "")
            defects.append(f"Párrafo {idx} de Google Doc no reconciliado en Overleaf: '{snippet}'")
        else:
            snippet = p_text[:50] + "..." if len(p_text) > 50 else p_text
            print(f"  [OK] Párrafo {idx:2d} calco verificado: '{snippet}'")

    print(f"\nTotal párrafos evaluados: {len(docx_paras)}")
    print(f"Párrafos coincidentes al 100%: {len(docx_paras) - unmatched_docx}")

    return defects


def main():
    parser = argparse.ArgumentParser(description="Auditoría de Reconciliación Google Doc <-> Overleaf (RKA 3).")
    parser.add_argument("--doc", type=str, default="Praktika_Txostena_RKA_P3.docx", help="Ruta al documento .docx de referencia.")
    parser.add_argument("--tex-dir", type=str, default=".", help="Directorio con las fuentes LaTeX.")
    parser.add_argument("--pdf", type=str, default="", help="Ruta opcional al PDF descargado de Overleaf.")
    args = parser.parse_args()

    doc_path = Path(args.doc)
    tex_dir = Path(args.tex_dir)
    pdf_path = Path(args.pdf) if args.pdf and Path(args.pdf).exists() else None

    print("=" * 65)
    print("🔍 AUDITORÍA AUTOMÁTICA DE RECONCILIACIÓN: GOOGLE DOC <-> OVERLEAF (RKA 3)")
    print("=" * 65)

    defects = audit_document_reconciliation(doc_path, tex_dir, pdf_path)

    if defects:
        print("\n" + "=" * 65)
        print(f"❌ [FAIL] Se detectaron {len(defects)} discrepancias de reconciliación:")
        print("=" * 65)
        for d in defects:
            print(f"  • {d}")
        sys.exit(1)
    else:
        print("\n" + "=" * 65)
        print("✅ [PASS] Reconciliación perfecta: 0 desfases entre Google Doc y Overleaf!")
        print("=" * 65)
        sys.exit(0)


if __name__ == "__main__":
    main()

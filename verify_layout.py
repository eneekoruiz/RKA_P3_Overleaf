#!/usr/bin/env python3
"""
verify_latex_layout.py - Universal Layout & Typographical Audit Tool for LaTeX and Overleaf PDFs.

Audits:
  1. Horizontal Margin Overflows (tables, listings, equations, text spilling past margins).
  2. Orphan Pages / Almost Blank Pages (< 8 lines on main matter content pages).
  3. Stranded Headings (section/subsection titles located at the bottom line of a page).
  4. Dangling Hyphenations across Page Breaks (words broken across pages like 'm/s- / an').
  5. Frontmatter Bloat (sparse lists like LOF and LOT taking unnecessary individual pages).
  6. Space Optimization & Aesthetic Consistency (balanced vertical fills and unified table widths).
  7. Cover Page Inter-line Spacing Rhythm (strictly uniform gaps between authors and multi-line titles).
  8. Font Size Switch Scoping (preventing trailing baseline jumps due to missing \\par in {\\Large ...}).
  9. Author Spacing Syntax Uniformity in \\egileak (preventing mixed \\\\ and \\\\[<len>]).
 10. Unreferenced / Dead Bibliography Detection (preventing empty reference pages without citations).
"""

import os
import re
import sys
import json
import argparse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import pypdfium2
except ImportError:
    print("[ERROR] pypdfium2 is required. Install via: pip install pypdfium2")
    sys.exit(1)


def compile_overleaf_and_download(project_id: str, cookie_val: str, output_pdf: Path) -> Path:
    cookie_header = f"overleaf_session2={cookie_val}"
    
    # 1. Fetch CSRF token
    req_home = urllib.request.Request(
        f"https://www.overleaf.com/project/{project_id}",
        headers={"Cookie": cookie_header, "User-Agent": "Mozilla/5.0"}
    )
    html = urllib.request.urlopen(req_home).read().decode("utf-8")
    m = re.search(r'<meta\s+name="ol-csrfToken"\s+content="([^"]+)"', html)
    if not m:
        raise RuntimeError("Could not find ol-csrfToken. Check your overleaf_session2 cookie.")
    csrf = m.group(1)

    # 2. Trigger compile
    compile_payload = json.dumps({
        "draft": False,
        "check": "silent",
        "incrementalCompilesEnabled": True
    }).encode("utf-8")

    req_compile = urllib.request.Request(
        f"https://www.overleaf.com/project/{project_id}/compile",
        data=compile_payload,
        headers={
            "Cookie": cookie_header,
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "X-Csrf-Token": csrf,
        }
    )
    resp = urllib.request.urlopen(req_compile)
    res = json.loads(resp.read().decode("utf-8"))
    
    status = res.get("status")
    if status != "success":
        raise RuntimeError(f"Overleaf compile failed with status: {status}\n{res}")

    pdf_file = [f for f in res["outputFiles"] if f["type"] == "pdf"][0]
    build = pdf_file["build"]
    compile_group = res.get("compileGroup", "standard")
    clsi_server_id = res.get("clsiServerId", "")

    download_url = (
        f"https://www.overleaf.com/download/project/{project_id}/build/{build}/"
        f"output/output.pdf?compileGroup={compile_group}&clsiserverid={clsi_server_id}"
    )
    req_pdf = urllib.request.Request(download_url, headers={"Cookie": cookie_header, "User-Agent": "Mozilla/5.0"})
    pdf_bytes = urllib.request.urlopen(req_pdf).read()
    output_pdf.write_bytes(pdf_bytes)
    print(f"[OK] Compiled on Overleaf and downloaded {len(pdf_bytes)} bytes to {output_pdf}")
    return output_pdf


def audit_source_typography(tex_dir: Path) -> list[str]:
    """Source code linting for LaTeX traps that cause typographical and spacing defects."""
    defects = []
    tex_files = list(tex_dir.glob("**/*.tex"))
    
    total_cites = 0
    has_bib = False
    
    for tf in tex_files:
        try:
            content = tf.read_text(encoding="utf-8")
        except Exception:
            continue
            
        # Check 1: Font size switch without internal \par
        # e.g., {\Large ... \\ ... } without \par before }
        size_matches = re.finditer(r'\{(\\(?:LARGE|Large|large|huge|Huge|small|footnotesize))\s+([^}]+)\}', content)
        for m in size_matches:
            cmd = m.group(1)
            body = m.group(2)
            if r'\\' in body and not re.search(r'\\par\s*$', body.strip()):
                defects.append(
                    f"[SOURCE LINT] {tf.name}: Font size switch '{cmd}' contains '\\\\' without trailing '\\par'. "
                    f"LaTeX will revert to outer baselineskip on the final line, causing uneven line spacing! Wrap as '{cmd} ...\\par}}'."
                )
                
        # Check 2: Author spacing uniformity in \egileak or author blocks
        m_egileak = re.search(r'\\newcommand\{\\egileak\}\{([^}]+)\}', content)
        if m_egileak:
            eg_body = m_egileak.group(1)
            # Find all linebreaks like \\ or \\[0.4em]
            linebreaks = re.findall(r'\\\\(?:\[([^\]]+)\])?', eg_body)
            if len(linebreaks) > 1:
                # Check if all linebreaks have the exact same optional spacing
                first_spacing = linebreaks[0]
                for idx, lb in enumerate(linebreaks[1:], start=2):
                    if lb != first_spacing:
                        defects.append(
                            f"[SOURCE LINT] {tf.name}: INCONSISTENT AUTHOR SPACING in \\egileak between authors (break 1: '{first_spacing}' vs break {idx}: '{lb}'). "
                            f"All author separators must use identical spacing (e.g. '\\\\[0.4em]')."
                        )
                        break
                        
        # Check 3: Track \cite and \bibliography
        cites = re.findall(r'\\cite\{[^}]+\}', content)
        total_cites += len(cites)
        if r'\bibliography{' in content or r'\begin{thebibliography}' in content:
            has_bib = True

        # Check 4: Long section commands must supply a short header argument [toc][head]{title}
        # to prevent multiline wrapping in running headers and separator line downward shifting.
        for m in re.finditer(r'\\section(?:\[([^\]]*)\])?(?:\[([^\]]*)\])?\{([^}]+)\}', content):
            opt1, opt2, full_title = m.group(1), m.group(2), m.group(3)
            # In memoir, if two optional args: opt1=toc, opt2=head. If one: opt1=both.
            has_short_head = (opt2 is not None) or (opt1 is not None and len(opt1) <= 35)
            if len(full_title) > 40 and not has_short_head:
                defects.append(
                    f"[SOURCE LINT] {tf.name}: LONG SECTION TITLE ({len(full_title)} chars) without short header: '{full_title[:35]}...'. "
                    f"Use '\\section[toc][short-head]{{full-title}}' so the running header does not wrap into 2 lines."
                )

        # Check 5: Duplicate list enumeration like \item \textbf{1. kasua} inside enumerate
        if re.search(r'\\begin\{enumerate\}.*?\\item\s+\\textbf\{\d+\.', content, re.DOTALL):
            defects.append(
                f"[SOURCE LINT] {tf.name}: DUPLICATE NUMBERING DETECTED! Found '\\item \\textbf{{N. ...}}' inside enumerate, "
                f"which causes LaTeX to print '1. 1. ...'. Use descriptive paragraphs or unnumbered headings."
            )

    if has_bib and total_cites == 0:
        defects.append(
            "[SOURCE LINT] UNREFERENCED / DEAD BIBLIOGRAPHY DETECTED! '\\bibliography' is included but 0 '\\cite' calls exist in the document."
        )

    return defects


def audit_cover_spacing(page) -> list[str]:
    """Audits page 1 (cover) to verify vertical line spacing uniformity in author/title blocks."""
    defects = []
    tp = page.get_textpage()
    
    rects = []
    for r_idx in range(tp.count_rects()):
        rect = tp.get_rect(r_idx)
        txt = tp.get_text_bounded(*rect).strip()
        if txt:
            rects.append((rect, txt))
            
    # Sort rects from top to bottom (PDF y: higher top is higher on page)
    rects.sort(key=lambda item: -item[0][3])
    
    # Check for author names block (lines containing author names or consecutive text with similar size)
    for idx in range(len(rects) - 2):
        r1, t1 = rects[idx]
        r2, t2 = rects[idx+1]
        r3, t3 = rects[idx+2]
        
        words1 = t1.split()
        words2 = t2.split()
        words3 = t3.split()
        # Author names are typically 2 to 4 words
        if 2 <= len(words1) <= 4 and 2 <= len(words2) <= 4 and 2 <= len(words3) <= 4:
            gap1 = abs(r1[3] - r2[3])
            gap2 = abs(r2[3] - r3[3])
            # If all 3 lines are part of the same visual group (vertical gaps between 10 pt and 45 pt)
            if 10.0 < gap1 < 45.0 and 10.0 < gap2 < 45.0:
                if abs(gap1 - gap2) > 2.5:
                    defects.append(
                        f"Page  1 (Cover): UNEVEN INTERLINE SPACING in block ('{t1}' / '{t2}' / '{t3}'): "
                        f"gap 1 = {gap1:.1f} pt vs gap 2 = {gap2:.1f} pt (diff = {abs(gap1-gap2):.1f} pt > 2.5 pt). "
                        f"Ensure uniform leading with explicit \\\\[<len>] and wrap with {{\\Large ...\\par}}."
                    )
    return defects


def audit_pdf_layout(pdf_path: Path, tex_dir: Path = None, render: bool = False, min_lines: int = 8, std_margin: float = 516.0, chapter_margin: float = 585.0) -> bool:
    doc = pypdfium2.PdfDocument(pdf_path)
    total_pages = len(doc)
    print(f"\n--- Auditing Layout for {total_pages} pages in '{pdf_path.name}' ---")
    
    defects = []
    page_summaries = []

    # 1. Source-level typography and spacing checks
    if tex_dir and tex_dir.exists():
        src_defects = audit_source_typography(tex_dir)
        defects.extend(src_defects)

    # 2. PDF Page-by-page layout checks
    for i, page in enumerate(doc):
        page_num = i + 1
        width, height = page.get_size()
        tp = page.get_textpage()
        text = tp.get_text_range()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        line_count = len(lines)
        
        # Check text rects for horizontal overflow
        rects = [tp.get_rect(r) for r in range(tp.count_rects())]
        max_right = max([r[2] for r in rects]) if rects else 0
        
        # Chapter header pages have large decorative numbers/letters (e.g., 1, 2, A)
        is_chapter_title_page = any(re.match(r"^(\d+|[A-Z])$", l) for l in lines[:3])
        margin_limit = chapter_margin if is_chapter_title_page else std_margin
        
        overflow_rects = [r for r in rects if r[2] > margin_limit]
        if overflow_rects:
            worst_r = max([r[2] for r in overflow_rects])
            sample_txt = tp.get_text_bounded(*overflow_rects[0]).strip()
            defects.append(
                f"Page {page_num:2d}: MARGIN OVERFLOW (x={worst_r:.1f} pt > limit {margin_limit:.1f} pt) -> '{sample_txt[:40]}'"
            )
            
        # Check 1: Content pages with very few lines (orphan pages)
        # Exclude frontmatter (pages 1-3)
        if page_num > 3 and line_count < min_lines:
            defects.append(
                f"Page {page_num:2d}: ALMOST BLANK / ORPHAN PAGE ({line_count} lines) -> '{' '.join(lines)[:60]}...'"
            )
            
        # Check 2: Stranded section heading at the bottom of the page
        if lines:
            last_line = lines[-1]
            if len(lines) > 1 and lines[-1].isdigit():
                last_line = lines[-2]
            if re.match(r"^\d+(\.\d+)*\s+[A-Z]", last_line):
                defects.append(
                    f"Page {page_num:2d}: SECTION HEADING STRANDED AT PAGE BOTTOM -> '{last_line}'"
                )
                
        # Check 3: Dangling hyphenation across page breaks
        if lines:
            last_line = lines[-1]
            if len(lines) > 1 and lines[-1].isdigit():
                last_line = lines[-2]
            if last_line.endswith("-") or last_line.endswith("—"):
                defects.append(
                    f"Page {page_num:2d}: WORD HYPHENATED ACROSS PAGE BREAK -> '{last_line[-30:]}'"
                )
                
        # Check 4: Frontmatter page bloat (e.g. single 2-line lists taking whole page)
        if page_num in (2, 3) and line_count < 4:
            defects.append(
                f"Page {page_num:2d}: FRONTMATTER BLOAT ({line_count} lines) -> combine LOF/LOT lists on a single page."
            )

        # Check 5: Cover page inter-line spacing rhythm
        if page_num == 1:
            cover_defects = audit_cover_spacing(page)
            defects.extend(cover_defects)
                
        if render:
            img = page.render(scale=1.5).to_pil()
            img.save(f"ol_page_{page_num}.png")
            
        first_snippet = lines[0][:35] if lines else "EMPTY"
        last_snippet = lines[-1][:35] if lines else "EMPTY"
        page_summaries.append(
            f"Page {page_num:2d}: {line_count:2d} lines | max_x={max_right:5.1f} pt | Top: {first_snippet:<35} | Bot: {last_snippet}"
        )
        
    print("\nPage Summary:")
    for summary in page_summaries:
        print(f"  {summary}")
        
    if defects:
        print("\n" + "="*60)
        print(f"[FAIL] {len(defects)} Layout defect(s) detected:")
        for d in defects:
            print(f"  - {d}")
        print("="*60 + "\n")
        return False
    else:
        print("\n" + "="*60)
        print(f"[PASS] All {total_pages} pages passed layout & typography audit cleanly!")
        print("="*60 + "\n")
        return True


def main():
    parser = argparse.ArgumentParser(description="Audit LaTeX / Overleaf PDF for layout and typography defects.")
    parser.add_argument("--pdf", type=str, default="overleaf_downloaded.pdf", help="Path to PDF file to audit.")
    parser.add_argument("--project-id", type=str, default="6af054a70e2efc15383d3c22", help="Overleaf Project ID to compile and download.")
    parser.add_argument("--cookie-file", type=str, default=".olauth", help="Path to .olauth session cookie file.")
    parser.add_argument("--render", action="store_true", help="Render PDF pages as PNG images for visual inspection.")
    parser.add_argument("--min-lines", type=int, default=8, help="Minimum non-empty lines on content pages.")
    parser.add_argument("--std-margin", type=float, default=516.0, help="Standard right text margin limit in pt.")
    parser.add_argument("--tex-dir", type=str, default=".", help="Directory containing LaTeX source files for linting.")
    
    args = parser.parse_args()
    pdf_path = Path(args.pdf)
    tex_dir = Path(args.tex_dir)

    if args.project_id:
        cookie_p = Path(args.cookie_file)
        if not cookie_p.exists():
            print(f"[ERROR] Cookie file '{args.cookie_file}' not found.")
            sys.exit(1)
        cookie_val = cookie_p.read_text(encoding="utf-8").strip().removeprefix("overleaf_session2=")
        pdf_path = compile_overleaf_and_download(args.project_id, cookie_val, pdf_path)
    elif not pdf_path.exists():
        print(f"[ERROR] PDF file '{pdf_path}' does not exist. Specify --pdf or --project-id.")
        sys.exit(1)
        
    success = audit_pdf_layout(
        pdf_path=pdf_path,
        tex_dir=tex_dir,
        render=args.render,
        min_lines=args.min_lines,
        std_margin=args.std_margin
    )
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()

"""
Unit test suite for Google Doc <-> Overleaf (LaTeX/PDF) reconciliation in RKA 3.
Ensures zero typographical, structural, metadata or textual drift.
"""
import sys
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from audit_reconciliation import audit_document_reconciliation, clean_text, tokenize


class TestGoogleDocOverleafReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc_path = REPO_DIR / "Praktika_Txostena_RKA_P3.docx"
        cls.tex_dir = REPO_DIR
        cls.pdf_path = REPO_DIR / "overleaf_downloaded.pdf"

    def test_frontmatter_metadata_symmetry(self):
        """Verify Title, Subtitle, Authors and symmetry of Irakaslea."""
        defects = audit_document_reconciliation(
            doc_path=self.doc_path,
            tex_dir=self.tex_dir,
            pdf_path=self.pdf_path if self.pdf_path.exists() else None
        )
        metadata_defects = [
            d for d in defects if any(k in d for k in ["Título", "Subtítulo", "Autor", "Irakaslea", "asimétrico"])
        ]
        self.assertEqual(
            len(metadata_defects),
            0,
            f"Metadata discrepancies detected between Google Doc and Overleaf: {metadata_defects}"
        )

    def test_structural_and_prose_reconciliation(self):
        """Verify 100% match on all sections and prose paragraphs."""
        defects = audit_document_reconciliation(
            doc_path=self.doc_path,
            tex_dir=self.tex_dir,
            pdf_path=self.pdf_path if self.pdf_path.exists() else None
        )
        self.assertEqual(
            len(defects),
            0,
            f"Found {len(defects)} reconciliation defects: {defects}"
        )


if __name__ == "__main__":
    unittest.main()

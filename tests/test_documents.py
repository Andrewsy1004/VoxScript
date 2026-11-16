import tempfile
import unittest
from pathlib import Path

from app.core.errors import DocumentError
from app.documents import to_markdown


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_docx_to_markdown(self):
        import docx

        d = docx.Document()
        d.add_heading("Fotosíntesis", level=1)
        d.add_heading("Fases", level=2)
        p = d.add_paragraph("La clorofila ")
        p.add_run("absorbe luz").bold = True
        p.add_run(".")
        d.add_paragraph("Fase luminosa", style="List Bullet")
        d.add_paragraph("Primer paso", style="List Number")
        table = d.add_table(rows=2, cols=2)
        table.cell(0, 0).text, table.cell(0, 1).text = "Fase", "Lugar"
        table.cell(1, 0).text, table.cell(1, 1).text = "Calvin", "Estroma"
        path = self.tmp / "apuntes.docx"
        d.save(path)

        src = to_markdown(path)
        self.assertEqual(src.name, "apuntes.docx")
        md = src.markdown
        self.assertIn("# Fotosíntesis", md)
        self.assertIn("## Fases", md)
        self.assertIn("La clorofila **absorbe luz**.", md)
        self.assertIn("- Fase luminosa", md)
        self.assertIn("1. Primer paso", md)
        self.assertIn("| Fase | Lugar |", md)
        self.assertIn("| Calvin | Estroma |", md)

    def test_pdf_to_markdown(self):
        import pymupdf

        path = self.tmp / "libro.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "La mitocondria produce energia.", fontsize=12)
        doc.save(path)
        doc.close()
        self.assertIn("mitocondria produce energia", to_markdown(path).markdown)

    def test_scanned_pdf_raises(self):
        import pymupdf

        path = self.tmp / "escaneado.pdf"
        doc = pymupdf.open()
        doc.new_page()
        doc.save(path)
        doc.close()
        with self.assertRaises(DocumentError) as ctx:
            to_markdown(path)
        self.assertIn("escaneado", str(ctx.exception))

    def test_text_and_markdown(self):
        path = self.tmp / "notas.md"
        path.write_text("# Título\n\n\n\n\nTexto.", encoding="utf-8")
        self.assertEqual(to_markdown(path).markdown, "# Título\n\nTexto.")

    def test_unsupported_formats(self):
        for name in ("viejo.doc", "hoja.xlsx"):
            path = self.tmp / name
            path.write_bytes(b"x")
            with self.assertRaises(DocumentError):
                to_markdown(path)

    def test_empty_and_corrupt(self):
        empty = self.tmp / "vacio.txt"
        empty.write_text("  \n", encoding="utf-8")
        with self.assertRaises(DocumentError):
            to_markdown(empty)
        corrupt = self.tmp / "roto.docx"
        corrupt.write_bytes(b"no es un zip")
        with self.assertRaises(DocumentError):
            to_markdown(corrupt)


if __name__ == "__main__":
    unittest.main()

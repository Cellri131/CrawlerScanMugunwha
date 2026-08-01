from docx import Document
from docx.shared import Pt

def export_docx(tree, filename="export.docx"):
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(12)

    for item in tree.get_children():
        val = tree.item(item, "values")
        text = val[0] if val else ""
        doc.add_paragraph(text)

    doc.save(filename)

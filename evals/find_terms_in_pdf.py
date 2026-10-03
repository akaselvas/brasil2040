"""Procura 74% / 99% nos PDFs de Energia (texto + tabelas). Uso: python evals/find_terms_in_pdf.py <pasta_dos_pdfs>"""
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

PAT = re.compile(r"\b99\s*%|\b74\s*%")
CTX = re.compile(r"SE/CO|Sudeste|d[eé]ficit", re.I)

for pdf in sorted(Path(sys.argv[1]).glob("Energia*.pdf")):
    doc = fitz.open(pdf)
    for n, page in enumerate(doc, 1):
        text = page.get_text("text")
        try:
            tabs = "\n".join(
                " | ".join(str(c) for c in row)
                for t in page.find_tables().tables
                for row in t.extract()
            )
        except Exception:
            tabs = ""
        for src, body in (("texto", text), ("tabela", tabs)):
            for m in PAT.finditer(body):
                if CTX.search(body):
                    a = max(m.start() - 120, 0)
                    print(f"{pdf.name} pág.{n} [{src}] imgs={len(page.get_images())}: ...{body[a:m.end()+80]!r}\n")
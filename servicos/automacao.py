"""Automações de tarefas repetitivas.
Adaptado de dois projetos: cortar-pdf (pypdf) e Create-Files (criar pastas)."""
import io
import re
import zipfile

from pypdf import PdfReader, PdfWriter
from werkzeug.utils import secure_filename

# linha isolada com número romano (início de capítulo), como no projeto original
PADRAO_ROMANO = re.compile(r"^\s*[IVXLCDM]{1,5}\s*$", re.MULTILINE)


def _pdf_bytes(paginas):
    w = PdfWriter()
    for p in paginas:
        w.add_page(p)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def extrair_paginas(arquivo, primeira, ultima):
    """Devolve (bytes do PDF, total de páginas). Páginas contadas a partir de 1."""
    leitura = PdfReader(arquivo)
    total = len(leitura.pages)
    if not (1 <= primeira <= ultima <= total):
        raise ValueError(f"Intervalo inválido. O PDF tem {total} páginas.")
    return _pdf_bytes(leitura.pages[primeira - 1:ultima]), total


def inicio_dos_capitulos(leitura):
    inicios = []
    for i, pagina in enumerate(leitura.pages):
        texto = pagina.extract_text() or ""
        if any(PADRAO_ROMANO.match(linha.strip()) for linha in texto.split("\n")):
            inicios.append(i)
    return inicios


def dividir_por_capitulos(arquivo, capitulos_por_arquivo=5):
    """Detecta capítulos (números romanos isolados) e agrupa N por PDF.
    Devolve (zip em bytes, nº de capítulos, nº de PDFs)."""
    leitura = PdfReader(arquivo)
    inicios = inicio_dos_capitulos(leitura)
    if not inicios:
        raise ValueError("Não encontrei capítulos (números romanos em linha isolada) neste PDF.")

    fins = [i - 1 for i in inicios[1:]] + [len(leitura.pages) - 1]
    capitulos = list(zip(inicios, fins))
    n = max(1, capitulos_por_arquivo)
    grupos = [capitulos[i:i + n] for i in range(0, len(capitulos), n)]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for num, grupo in enumerate(grupos, 1):
            paginas = [leitura.pages[p] for ini, fim in grupo for p in range(ini, fim + 1)]
            z.writestr(f"parte_{num:02d}.pdf", _pdf_bytes(paginas))
    return buf.getvalue(), len(capitulos), len(grupos)


def pastas_em_zip(nomes_texto):
    """Cria um ZIP com pastas vazias, uma por nome (separados por vírgula ou linha)."""
    nomes = [secure_filename(n.strip()) for n in re.split(r"[,\n]", nomes_texto)]
    nomes = [n for n in nomes if n]
    if not nomes:
        raise ValueError("Informe ao menos um nome de pasta.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in dict.fromkeys(nomes):  # tira repetidos mantendo a ordem
            z.writestr(zipfile.ZipInfo(n + "/"), "")
    return buf.getvalue(), len(nomes)

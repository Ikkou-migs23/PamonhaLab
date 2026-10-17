"""Pamonha Lab - MVP simples em Flask."""
import io
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from functools import wraps

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, send_file, send_from_directory, url_for)
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

from servicos import automacao, vetor, video

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
JOBS_DIR = os.path.join(BASE_DIR, "jobs")
DB_PATH = os.path.join(BASE_DIR, "pamonha.db")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # teto geral: 2 GB (só o vídeo usa tudo isso)
LIMITE_PADRAO = 200 * 1024 * 1024               # demais rotas: 200 MB
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "pamonha")
Image.MAX_IMAGE_PIXELS = 50_000_000

# Catálogo de serviços (fica aqui mesmo, é só uma lista)
SERVICOS = [
    {"slug": "imagem", "icone": "🖼️", "nome": "Tratamento de imagens",
     "desc": "Converta formato, redimensione, comprima e passe para preto e branco.",
     "ferramenta": "ferramenta_imagem"},
    {"slug": "video", "icone": "🎬", "nome": "Vídeos curtos",
     "desc": "Divida um vídeo longo em cortes de duração fixa, prontos para postar.",
     "ferramenta": "ferramenta_video"},
    {"slug": "vetor", "icone": "✏️", "nome": "Vetorização de imagens",
     "desc": "Transforme logos e desenhos em SVG colorido, pronto para ampliar.",
     "ferramenta": "ferramenta_vetor"},
    {"slug": "design", "icone": "🎨", "nome": "Pequenos trabalhos de design",
     "desc": "Logos, posts, cartões e peças simples."},
    {"slug": "arquivos", "icone": "📐", "nome": "Conversão e preparação de arquivos",
     "desc": "Deixamos seu arquivo no formato e tamanho que você precisa."},
    {"slug": "automacao", "icone": "🧩", "nome": "Automação de tarefas",
     "desc": "Divida PDFs por capítulos, extraia páginas e crie várias pastas de uma vez.",
     "ferramenta": "ferramenta_automacao"},
    {"slug": "outro", "icone": "🔧", "nome": "Outra demanda",
     "desc": "Não achou o que procura? Conte o que você precisa."},
]
STATUS = ["novo", "em andamento", "concluído"]


# ---------- banco ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            criado_em TEXT DEFAULT (datetime('now','localtime')),
            nome TEXT NOT NULL,
            contato TEXT NOT NULL,
            servico TEXT NOT NULL,
            descricao TEXT NOT NULL,
            arquivo TEXT,
            status TEXT NOT NULL DEFAULT 'novo')""")


init_db()


# ---------- admin ----------
def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        auth = request.authorization
        if not auth or auth.password != ADMIN_PASSWORD:
            return Response("Acesso restrito.", 401,
                            {"WWW-Authenticate": 'Basic realm="Pamonha Lab"'})
        return f(*a, **kw)
    return wrapper


# ---------- páginas ----------
@app.route("/")
def index():
    return render_template("index.html", servicos=SERVICOS)


@app.route("/pedido", methods=["GET", "POST"])
def pedido():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        contato = request.form.get("contato", "").strip()
        servico = request.form.get("servico", "outro")
        descricao = request.form.get("descricao", "").strip()
        if not (nome and contato and descricao):
            flash("Preencha nome, contato e a descrição da demanda.", "erro")
            return render_template("pedido.html", servicos=SERVICOS,
                                   form=request.form), 400

        arquivo_salvo = None
        arq = request.files.get("arquivo")
        if arq and arq.filename:
            arquivo_salvo = f"{uuid.uuid4().hex[:8]}_{secure_filename(arq.filename)}"
            arq.save(os.path.join(UPLOAD_DIR, arquivo_salvo))

        db = get_db()
        db.execute("INSERT INTO pedidos (nome, contato, servico, descricao, arquivo)"
                   " VALUES (?,?,?,?,?)",
                   (nome, contato, servico, descricao, arquivo_salvo))
        db.commit()
        return redirect(url_for("pedido_ok"))

    pre = request.args.get("servico", "")
    return render_template("pedido.html", servicos=SERVICOS, form={"servico": pre})


@app.route("/pedido/enviado")
def pedido_ok():
    return render_template("pedido_ok.html")


# ---------- ferramenta de imagem ----------
FORMATOS = {"png": ("PNG", "image/png"), "jpg": ("JPEG", "image/jpeg"),
            "webp": ("WEBP", "image/webp")}


@app.route("/ferramentas/imagem", methods=["GET", "POST"])
def ferramenta_imagem():
    if request.method == "GET":
        return render_template("imagem.html")

    arq = request.files.get("imagem")
    if not arq or not arq.filename:
        flash("Escolha uma imagem para começar.", "erro")
        return render_template("imagem.html"), 400

    try:
        img = Image.open(arq.stream)
        img = ImageOps.exif_transpose(img)
    except Exception:
        flash("Não consegui abrir esse arquivo. Envie um PNG, JPG, WEBP, GIF ou BMP.", "erro")
        return render_template("imagem.html"), 400

    # largura máxima (opcional)
    largura = request.form.get("largura", type=int)
    if largura and 0 < largura < img.width:
        altura = round(img.height * largura / img.width)
        img = img.resize((largura, altura), Image.LANCZOS)

    # preto e branco (opcional)
    if request.form.get("pb"):
        img = ImageOps.grayscale(img)

    fmt_key = request.form.get("formato", "png")
    fmt, mime = FORMATOS.get(fmt_key, FORMATOS["png"])
    qualidade = min(max(request.form.get("qualidade", 85, type=int), 10), 100)

    if fmt == "JPEG":  # JPEG não tem transparência
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            fundo = Image.new("RGB", img.size, "white")
            fundo.paste(img, mask=img.split()[-1])
            img = fundo
        else:
            img = img.convert("RGB")

    buf = io.BytesIO()
    opcoes = {"optimize": True}
    if fmt in ("JPEG", "WEBP"):
        opcoes["quality"] = qualidade
    img.save(buf, fmt, **opcoes)
    buf.seek(0)

    base = os.path.splitext(secure_filename(arq.filename))[0] or "imagem"
    return send_file(buf, mimetype=mime, as_attachment=True,
                     download_name=f"{base}-pamonha.{fmt_key}")


# ---------- vetorização ----------
@app.route("/ferramentas/vetor", methods=["GET", "POST"])
def ferramenta_vetor():
    if request.method == "GET":
        return render_template("vetor.html")

    arq = request.files.get("imagem")
    if not arq or not arq.filename:
        flash("Escolha uma imagem para vetorizar.", "erro")
        return render_template("vetor.html"), 400

    fundo = (0, 0, 0) if request.form.get("fundo") == "preto" else (255, 255, 255)
    n_cores = request.form.get("cores", 24, type=int)
    try:
        rgb = vetor.carregar_rgb(arq.stream, fundo)
    except Exception:
        flash("Não consegui abrir esse arquivo. Envie um PNG, JPG, WEBP ou BMP.", "erro")
        return render_template("vetor.html"), 400

    svg = vetor.vetorizar(rgb, n_cores)
    base = os.path.splitext(secure_filename(arq.filename))[0] or "imagem"
    return send_file(io.BytesIO(svg.encode("utf-8")), mimetype="image/svg+xml",
                     as_attachment=True, download_name=f"{base}-vetor.svg")


# ---------- vídeos curtos (processa em segundo plano) ----------
# O andamento fica em jobs/<id>/status.json, então sobrevive a recarregamentos da página.
def _status_path(jid):
    return os.path.join(JOBS_DIR, jid, "status.json")


def salvar_job(jid, job):
    tmp = _status_path(jid) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(job, f)
    os.replace(tmp, _status_path(jid))


def ler_job(jid):
    if not re.fullmatch(r"[0-9a-f]{10}", jid):
        return None
    try:
        with open(_status_path(jid), encoding="utf-8") as f:
            job = json.load(f)
    except (OSError, ValueError):
        return None
    # se o servidor foi reiniciado no meio do corte, a thread morreu junto
    if job["status"] == "processando" and job.get("pid") != os.getpid():
        job["status"] = "erro"
        job["erro"] = "O servidor reiniciou durante o corte. Envie o vídeo novamente."
    return job


def limpar_jobs_antigos(horas=2):
    limite = time.time() - horas * 3600
    for nome in os.listdir(JOBS_DIR):
        pasta = os.path.join(JOBS_DIR, nome)
        if os.path.isdir(pasta) and os.path.getmtime(pasta) < limite:
            shutil.rmtree(pasta, ignore_errors=True)


def rodar_corte(jid, entrada, nome, duracao):
    pasta = os.path.join(JOBS_DIR, jid)
    job = {"status": "processando", "feitos": 0, "total": 0, "pid": os.getpid()}
    try:
        def progresso(feitos, total):
            job["feitos"], job["total"] = feitos, total
            salvar_job(jid, job)

        saida = os.path.join(pasta, "cortes")
        arquivos = video.cortar_video(entrada, saida, nome, duracao, progresso)
        zip_path = os.path.join(pasta, f"{nome}-cortes.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as z:
            for a in arquivos:
                z.write(a, os.path.basename(a))
        job["zip"], job["status"] = zip_path, "pronto"
    except Exception as e:
        job["status"], job["erro"] = "erro", str(e)
    finally:
        if os.path.exists(entrada):
            os.remove(entrada)
        shutil.rmtree(os.path.join(pasta, "cortes"), ignore_errors=True)
        salvar_job(jid, job)


@app.route("/ferramentas/video", methods=["GET", "POST"])
def ferramenta_video():
    if request.method == "GET":
        return render_template("video.html")

    arq = request.files.get("video")
    duracao = request.form.get("duracao", 60, type=int)
    if not arq or not arq.filename:
        flash("Escolha um vídeo para cortar.", "erro")
        return render_template("video.html"), 400
    if not 3 <= duracao <= 600:
        flash("A duração de cada corte deve ficar entre 3 e 600 segundos.", "erro")
        return render_template("video.html"), 400

    limpar_jobs_antigos()
    jid = uuid.uuid4().hex[:10]
    os.makedirs(os.path.join(JOBS_DIR, jid))
    entrada = os.path.join(JOBS_DIR, jid, secure_filename(arq.filename) or "video.mp4")
    arq.save(entrada)

    nome = os.path.splitext(secure_filename(arq.filename))[0] or "corte"
    salvar_job(jid, {"status": "processando", "feitos": 0, "total": 0, "pid": os.getpid()})
    threading.Thread(target=rodar_corte, args=(jid, entrada, nome, duracao), daemon=True).start()
    return redirect(url_for("video_status", jid=jid))


@app.route("/ferramentas/video/<jid>")
def video_status(jid):
    job = ler_job(jid)
    if not job:
        flash("Esse trabalho não existe mais. Envie o vídeo novamente.", "erro")
        return redirect(url_for("ferramenta_video"))
    return render_template("video_status.html", job=job, jid=jid)


@app.route("/ferramentas/video/<jid>/baixar")
def video_baixar(jid):
    job = ler_job(jid)
    if not job or job["status"] != "pronto" or not os.path.isfile(job["zip"]):
        abort(404)
    return send_file(job["zip"], as_attachment=True)


# ---------- automação de tarefas ----------
@app.route("/ferramentas/automacao", methods=["GET", "POST"])
def ferramenta_automacao():
    if request.method == "GET":
        return render_template("automacao.html")

    acao = request.form.get("acao")
    try:
        if acao == "pastas":
            dados, n = automacao.pastas_em_zip(request.form.get("nomes", ""))
            return send_file(io.BytesIO(dados), mimetype="application/zip",
                             as_attachment=True, download_name=f"{n}-pastas.zip")

        arq = request.files.get("pdf")
        if not arq or not arq.filename:
            raise ValueError("Escolha um arquivo PDF.")
        base = os.path.splitext(secure_filename(arq.filename))[0] or "documento"

        if acao == "paginas":
            ini = request.form.get("inicio", type=int)
            fim = request.form.get("fim", type=int)
            if not ini or not fim:
                raise ValueError("Informe a primeira e a última página.")
            dados, _ = automacao.extrair_paginas(arq.stream, ini, fim)
            return send_file(io.BytesIO(dados), mimetype="application/pdf",
                             as_attachment=True, download_name=f"{base}-p{ini}-{fim}.pdf")

        if acao == "capitulos":
            por = request.form.get("por_arquivo", 5, type=int)
            dados, _, _ = automacao.dividir_por_capitulos(arq.stream, por)
            return send_file(io.BytesIO(dados), mimetype="application/zip",
                             as_attachment=True, download_name=f"{base}-capitulos.zip")

        raise ValueError("Ação desconhecida.")
    except Exception as e:
        flash(str(e) if isinstance(e, ValueError) else
              "Não consegui processar esse arquivo. Confira se é um PDF válido.", "erro")
        return render_template("automacao.html"), 400


# ---------- admin ----------
@app.route("/admin")
@admin_required
def admin():
    pedidos = get_db().execute("SELECT * FROM pedidos ORDER BY id DESC").fetchall()
    nomes = {s["slug"]: s["nome"] for s in SERVICOS}
    return render_template("admin.html", pedidos=pedidos, status_opcoes=STATUS, nomes=nomes)


@app.route("/admin/<int:pid>/status", methods=["POST"])
@admin_required
def admin_status(pid):
    novo = request.form.get("status")
    if novo in STATUS:
        db = get_db()
        db.execute("UPDATE pedidos SET status=? WHERE id=?", (novo, pid))
        db.commit()
    return redirect(url_for("admin"))


@app.route("/admin/arquivo/<path:nome>")
@admin_required
def admin_arquivo(nome):
    if not os.path.isfile(os.path.join(UPLOAD_DIR, nome)):
        abort(404)
    return send_from_directory(UPLOAD_DIR, nome, as_attachment=True)


@app.before_request
def limitar_tamanho():
    """Só a ferramenta de vídeo aceita arquivos grandes."""
    if request.method == "POST" and request.endpoint != "ferramenta_video":
        if (request.content_length or 0) > LIMITE_PADRAO:
            abort(413)


@app.errorhandler(413)
def muito_grande(_e):
    limite = "2 GB" if request.endpoint == "ferramenta_video" else "200 MB"
    flash(f"Arquivo grande demais. O limite aqui é {limite}.", "erro")
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    # use_reloader=False: o recarregador automático reiniciava o servidor no meio dos cortes
    app.run(debug=True, use_reloader=False)

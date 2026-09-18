import os
import re
import json
import shutil
import secrets
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
BACKUP_DIR = BASE_DIR / "backups"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "encantar-dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'encantar.db'}"
).replace("postgres://", "postgresql://")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, default="Administrador")
    email = db.Column(db.String(180), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    ultimo_login = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, default="")

class Evento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(180), nullable=False)
    tipo = db.Column(db.String(100), default="")
    data_evento = db.Column(db.String(30), default="")
    local = db.Column(db.String(180), default="")
    descricao = db.Column(db.Text, default="")
    imagem = db.Column(db.String(255), default="")
    album_url = db.Column(db.String(500), default="")
    destaque = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    descricao = db.Column(db.Text, default="")
    icone = db.Column(db.String(80), default="sparkles")
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)

class Equipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    cargo = db.Column(db.String(160), default="")
    bio = db.Column(db.Text, default="")
    foto = db.Column(db.String(255), default="")
    instagram = db.Column(db.String(300), default="")
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    evento = db.Column(db.String(180), default="")
    mensagem = db.Column(db.Text, nullable=False)
    nota = db.Column(db.Integer, default=5)
    aprovado = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Imagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(180), default="")
    arquivo = db.Column(db.String(255), nullable=False)
    categoria = db.Column(db.String(100), default="Galeria")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Visita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pagina = db.Column(db.String(180), default="/")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

def cfg(key, default=""):
    item = Configuracao.query.filter_by(chave=key).first()
    return item.valor if item else default

@app.context_processor
def inject_globals():
    return {
        "site": {
            "nome": cfg("nome_empresa", "Encantar Cerimonial"),
            "slogan": cfg("slogan", "Momentos inesquecíveis começam com cuidado."),
            "descricao": cfg("descricao", "Cerimonial, organização e cuidado em cada detalhe."),
            "whatsapp": cfg("whatsapp", ""),
            "instagram": cfg("instagram", ""),
            "facebook": cfg("facebook", ""),
            "email": cfg("email", ""),
            "maps": cfg("maps", ""),
            "endereco": cfg("endereco", ""),
            "telefone": cfg("telefone", ""),
            "logo": cfg("logo", ""),
        },
        "ano": datetime.now().year
    }

@app.before_request
def csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)

@app.context_processor
def csrf_processor():
    return {"csrf_token": session.get("csrf_token", "")}

def check_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or sent != session.get("csrf_token"):
            abort(400, description="Token de segurança inválido.")

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file, prefix="imagem"):
    if not file or not file.filename or not allowed_file(file.filename):
        return ""
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"{prefix}_{secrets.token_hex(8)}.{ext}")
    file.save(UPLOAD_DIR / filename)
    return filename

def whatsapp_link():
    number = re.sub(r"\D", "", cfg("whatsapp", ""))
    if not number:
        return ""
    return f"https://wa.me/{number}"

def register_visit(page):
    try:
        db.session.add(Visita(pagina=page))
        db.session.commit()
    except Exception:
        db.session.rollback()

@app.route("/")
def home():
    register_visit("/")
    eventos = Evento.query.order_by(Evento.destaque.desc(), Evento.criado_em.desc()).limit(6).all()
    servicos = Servico.query.filter_by(ativo=True).order_by(Servico.ordem, Servico.id).all()
    equipe = Equipe.query.filter_by(ativo=True).order_by(Equipe.ordem, Equipe.id).limit(4).all()
    feedbacks = Feedback.query.filter_by(aprovado=True).order_by(Feedback.criado_em.desc()).limit(6).all()
    imagens = Imagem.query.order_by(Imagem.criado_em.desc()).limit(12).all()
    return render_template("home.html", eventos=eventos, servicos=servicos, equipe=equipe, feedbacks=feedbacks, imagens=imagens, whatsapp=whatsapp_link())

@app.route("/sobre")
def sobre():
    register_visit("/sobre")
    return render_template("sobre.html")

@app.route("/equipe")
def equipe_publica():
    register_visit("/equipe")
    equipe = Equipe.query.filter_by(ativo=True).order_by(Equipe.ordem, Equipe.id).all()
    return render_template("equipe.html", equipe=equipe)

@app.route("/servicos")
def servicos_publicos():
    register_visit("/servicos")
    servicos = Servico.query.filter_by(ativo=True).order_by(Servico.ordem, Servico.id).all()
    return render_template("servicos.html", servicos=servicos)

@app.route("/eventos")
def eventos_publicos():
    register_visit("/eventos")
    eventos = Evento.query.order_by(Evento.destaque.desc(), Evento.data_evento.desc(), Evento.id.desc()).all()
    return render_template("eventos.html", eventos=eventos)

@app.route("/galeria")
def galeria_publica():
    register_visit("/galeria")
    imagens = Imagem.query.order_by(Imagem.criado_em.desc()).all()
    return render_template("galeria.html", imagens=imagens)

@app.route("/depoimentos", methods=["GET", "POST"])
def depoimentos():
    if request.method == "POST":
        check_csrf()
        nome = request.form.get("nome", "").strip()
        evento = request.form.get("evento", "").strip()
        mensagem = request.form.get("mensagem", "").strip()
        try:
            nota = max(1, min(5, int(request.form.get("nota", 5))))
        except ValueError:
            nota = 5
        if not nome or not mensagem:
            flash("Preencha seu nome e depoimento.", "error")
        else:
            db.session.add(Feedback(nome=nome, evento=evento, mensagem=mensagem, nota=nota, aprovado=False))
            db.session.commit()
            flash("Obrigado! Seu depoimento foi enviado para análise.", "success")
            return redirect(url_for("depoimentos"))
    feedbacks = Feedback.query.filter_by(aprovado=True).order_by(Feedback.criado_em.desc()).all()
    return render_template("depoimentos.html", feedbacks=feedbacks)

@app.route("/faq")
def faq():
    register_visit("/faq")
    return render_template("faq.html")

@app.route("/contato")
def contato():
    register_visit("/contato")
    return render_template("contato.html", whatsapp=whatsapp_link())

@app.route("/orcamento", methods=["GET", "POST"])
def orcamento():
    if request.method == "POST":
        check_csrf()
        nome = request.form.get("nome", "").strip()
        tipo = request.form.get("tipo", "").strip()
        data = request.form.get("data", "").strip()
        convidados = request.form.get("convidados", "").strip()
        telefone = request.form.get("telefone", "").strip()
        mensagem = request.form.get("mensagem", "").strip()
        text = f"Olá, Encantar Cerimonial! Gostaria de solicitar um orçamento.%0A%0ANome: {nome}%0ATipo de evento: {tipo}%0AData: {data}%0AConvidados: {convidados}%0ATelefone: {telefone}%0AObservações: {mensagem}"
        link = whatsapp_link()
        if link:
            return redirect(link + "?text=" + text)
        flash("O WhatsApp da empresa ainda não foi configurado no painel administrativo.", "error")
    return render_template("orcamento.html")

# ---------------- ADMIN ----------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        check_csrf()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        user = Usuario.query.filter_by(email=email).first()
        if user and check_password_hash(user.senha_hash, senha):
            session["admin_id"] = user.id
            user.ultimo_login = datetime.utcnow()
            db.session.commit()
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("E-mail ou senha inválidos.", "error")
    return render_template("admin/login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html",
        eventos=Evento.query.count(),
        servicos=Servico.query.count(),
        equipe=Equipe.query.count(),
        imagens=Imagem.query.count(),
        feedbacks=Feedback.query.filter_by(aprovado=False).count(),
        visitas=Visita.query.count(),
        ultimo_evento=Evento.query.order_by(Evento.id.desc()).first()
    )

@app.route("/admin/eventos", methods=["GET", "POST"])
@admin_required
def admin_eventos():
    if request.method == "POST":
        check_csrf()
        action = request.form.get("action")
        if action == "delete":
            item = Evento.query.get_or_404(int(request.form["id"]))
            db.session.delete(item)
        else:
            item = Evento.query.get(int(request.form.get("id", 0))) if request.form.get("id") else Evento()
            item.titulo = request.form.get("titulo", "").strip()
            item.tipo = request.form.get("tipo", "").strip()
            item.data_evento = request.form.get("data_evento", "").strip()
            item.local = request.form.get("local", "").strip()
            item.descricao = request.form.get("descricao", "").strip()
            item.album_url = request.form.get("album_url", "").strip()
            item.destaque = bool(request.form.get("destaque"))
            upload = save_upload(request.files.get("imagem"), "evento")
            if upload:
                item.imagem = upload
            if not item.id:
                db.session.add(item)
        db.session.commit()
        return redirect(url_for("admin_eventos"))
    edit = Evento.query.get(request.args.get("edit", type=int)) if request.args.get("edit") else None
    return render_template("admin/eventos.html", eventos=Evento.query.order_by(Evento.id.desc()).all(), edit=edit)

@app.route("/admin/servicos", methods=["GET", "POST"])
@admin_required
def admin_servicos():
    if request.method == "POST":
        check_csrf()
        action = request.form.get("action")
        if action == "delete":
            db.session.delete(Servico.query.get_or_404(int(request.form["id"])))
        else:
            item = Servico.query.get(int(request.form.get("id", 0))) if request.form.get("id") else Servico()
            item.nome = request.form.get("nome", "").strip()
            item.descricao = request.form.get("descricao", "").strip()
            item.icone = request.form.get("icone", "sparkles").strip()
            item.ordem = request.form.get("ordem", 0, type=int)
            item.ativo = bool(request.form.get("ativo"))
            if not item.id: db.session.add(item)
        db.session.commit()
        return redirect(url_for("admin_servicos"))
    edit = Servico.query.get(request.args.get("edit", type=int)) if request.args.get("edit") else None
    return render_template("admin/servicos.html", servicos=Servico.query.order_by(Servico.ordem, Servico.id).all(), edit=edit)

@app.route("/admin/equipe", methods=["GET", "POST"])
@admin_required
def admin_equipe():
    if request.method == "POST":
        check_csrf()
        action = request.form.get("action")
        if action == "delete":
            db.session.delete(Equipe.query.get_or_404(int(request.form["id"])))
        else:
            item = Equipe.query.get(int(request.form.get("id", 0))) if request.form.get("id") else Equipe()
            item.nome = request.form.get("nome", "").strip()
            item.cargo = request.form.get("cargo", "").strip()
            item.bio = request.form.get("bio", "").strip()
            item.instagram = request.form.get("instagram", "").strip()
            item.ordem = request.form.get("ordem", 0, type=int)
            item.ativo = bool(request.form.get("ativo"))
            upload = save_upload(request.files.get("foto"), "equipe")
            if upload: item.foto = upload
            if not item.id: db.session.add(item)
        db.session.commit()
        return redirect(url_for("admin_equipe"))
    edit = Equipe.query.get(request.args.get("edit", type=int)) if request.args.get("edit") else None
    return render_template("admin/equipe.html", equipe=Equipe.query.order_by(Equipe.ordem, Equipe.id).all(), edit=edit)

@app.route("/admin/imagens", methods=["GET", "POST"])
@admin_required
def admin_imagens():
    if request.method == "POST":
        check_csrf()
        action = request.form.get("action")
        if action == "delete":
            item = Imagem.query.get_or_404(int(request.form["id"]))
            if item.arquivo:
                try: (UPLOAD_DIR / item.arquivo).unlink()
                except FileNotFoundError: pass
            db.session.delete(item)
        else:
            files = request.files.getlist("arquivos")
            for file in files:
                filename = save_upload(file, "galeria")
                if filename:
                    db.session.add(Imagem(
                        titulo=request.form.get("titulo", "").strip(),
                        categoria=request.form.get("categoria", "Galeria").strip(),
                        arquivo=filename
                    ))
        db.session.commit()
        return redirect(url_for("admin_imagens"))
    return render_template("admin/imagens.html", imagens=Imagem.query.order_by(Imagem.id.desc()).all())

@app.route("/admin/feedbacks", methods=["POST"])
@admin_required
def admin_feedbacks():
    check_csrf()
    item = Feedback.query.get_or_404(int(request.form["id"]))
    action = request.form.get("action")
    if action == "approve": item.aprovado = True
    elif action == "unapprove": item.aprovado = False
    elif action == "delete": db.session.delete(item)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/configuracoes", methods=["GET", "POST"])
@admin_required
def admin_configuracoes():
    keys = ["nome_empresa","slogan","descricao","whatsapp","instagram","facebook","email","maps","endereco","telefone","logo"]
    if request.method == "POST":
        check_csrf()
        for key in keys:
            value = request.form.get(key, "").strip()
            item = Configuracao.query.filter_by(chave=key).first()
            if not item:
                item = Configuracao(chave=key)
                db.session.add(item)
            item.valor = value
        db.session.commit()
        flash("Configurações salvas.", "success")
        return redirect(url_for("admin_configuracoes"))
    values = {key: cfg(key, "") for key in keys}
    return render_template("admin/configuracoes.html", values=values)

@app.route("/admin/feedbacks", methods=["GET", "POST"])
@admin_required
def admin_feedbacks_page():
    if request.method == "POST":
        check_csrf()
        item = Feedback.query.get_or_404(int(request.form["id"]))
        action = request.form.get("action")
        if action == "approve": item.aprovado = True
        elif action == "unapprove": item.aprovado = False
        elif action == "delete": db.session.delete(item)
        db.session.commit()
        return redirect(url_for("admin_feedbacks_page"))
    return render_template("admin/feedbacks.html", feedbacks=Feedback.query.order_by(Feedback.criado_em.desc()).all())

@app.route("/admin/backup")
@admin_required
def admin_backup():
    import sqlite3
    db_url = app.config["SQLALCHEMY_DATABASE_URI"]
    if not db_url.startswith("sqlite:///"):
        flash("Backup local automático está disponível nesta versão para SQLite. Em produção com PostgreSQL, use o backup do provedor.", "error")
        return redirect(url_for("admin_dashboard"))
    db_path = db_url.replace("sqlite:///", "", 1)
    if not os.path.isabs(db_path):
        db_path = str(BASE_DIR / db_path)
    if not os.path.exists(db_path):
        flash("Banco ainda não encontrado.", "error")
        return redirect(url_for("admin_dashboard"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"encantar_backup_{stamp}.db"
    shutil.copy2(db_path, target)
    return send_from_directory(BACKUP_DIR, target.name, as_attachment=True)

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="A página que você procurou não existe."), 404

@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, message=getattr(e, "description", "Requisição inválida.")), 400

@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template("error.html", code=500, message="Ocorreu um erro interno. Tente novamente."), 500

def init_db():
    with app.app_context():
        db.create_all()
        if not Usuario.query.first():
            email = os.environ.get("ADMIN_EMAIL", "admin@encantarcerimonial.com")
            password = os.environ.get("ADMIN_PASSWORD", "Encantar@123")
            db.session.add(Usuario(
                nome="Administrador",
                email=email,
                senha_hash=generate_password_hash(password)
            ))
        defaults = {
            "nome_empresa": "Encantar Cerimonial",
            "slogan": "Momentos inesquecíveis começam com cuidado.",
            "descricao": "Planejamento, organização e cerimonial para transformar celebrações em memórias especiais.",
            "whatsapp": "",
            "instagram": "",
            "facebook": "",
            "email": "",
            "maps": "",
            "endereco": "",
            "telefone": "",
            "logo": ""
        }
        for key, value in defaults.items():
            if not Configuracao.query.filter_by(chave=key).first():
                db.session.add(Configuracao(chave=key, valor=value))
        db.session.commit()

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
else:
    init_db()

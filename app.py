import os
import re
import secrets
import shutil
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
    send_from_directory,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# =========================================================
# CAMINHOS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
BACKUP_DIR = BASE_DIR / "backups"

INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "encantar-dev-secret-change-me"
)

database_url = os.environ.get("DATABASE_URL", "").strip()

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql://", 1
        )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    sqlite_path = INSTANCE_DIR / "encantar.db"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(sqlite_path)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


# =========================================================
# MODELOS
# =========================================================

class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, default="Administrador")
    email = db.Column(db.String(180), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    ultimo_login = db.Column(db.DateTime, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Configuracao(db.Model):
    __tablename__ = "configuracoes"

    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, default="")


class Evento(db.Model):
    __tablename__ = "eventos"

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
    __tablename__ = "servicos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    descricao = db.Column(db.Text, default="")
    icone = db.Column(db.String(80), default="sparkles")
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)


class Equipe(db.Model):
    __tablename__ = "equipe"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    cargo = db.Column(db.String(160), default="")
    bio = db.Column(db.Text, default="")
    foto = db.Column(db.String(255), default="")
    instagram = db.Column(db.String(300), default="")
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)


class Feedback(db.Model):
    __tablename__ = "feedbacks"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    evento = db.Column(db.String(180), default="")
    mensagem = db.Column(db.Text, nullable=False)
    nota = db.Column(db.Integer, default=5)
    aprovado = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Imagem(db.Model):
    __tablename__ = "imagens"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(180), default="")
    arquivo = db.Column(db.String(255), nullable=False)
    categoria = db.Column(db.String(100), default="Galeria")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Visita(db.Model):
    __tablename__ = "visitas"

    id = db.Column(db.Integer, primary_key=True)
    pagina = db.Column(db.String(180), default="/")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


# =========================================================
# AUXILIARES
# =========================================================

def cfg(key, default=""):
    item = Configuracao.query.filter_by(chave=key).first()
    return item.valor if item else default


@app.context_processor
def inject_globals():
    return {
        "site": {
            "nome": cfg("nome_empresa", "Encantar Cerimonial"),
            "slogan": cfg(
                "slogan",
                "Momentos inesquecíveis começam com cuidado."
            ),
            "descricao": cfg(
                "descricao",
                "Cerimonial, organização e cuidado em cada detalhe."
            ),
            "whatsapp": cfg("whatsapp", ""),
            "instagram": cfg("instagram", ""),
            "facebook": cfg("facebook", ""),
            "email": cfg("email", ""),
            "maps": cfg("maps", ""),
            "endereco": cfg("endereco", ""),
            "telefone": cfg("telefone", ""),
            "logo": cfg("logo", ""),
            "banner": cfg("banner", ""),
        },
        "ano": datetime.now().year,
    }


@app.before_request
def criar_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)


@app.context_processor
def csrf_processor():
    return {"csrf_token": session.get("csrf_token", "")}


def check_csrf():
    if request.method != "POST":
        return

    enviado = request.form.get("_csrf", "")
    armazenado = session.get("csrf_token")

    if not enviado or enviado != armazenado:
        abort(400, description="Token de segurança inválido.")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(
                url_for("admin_login", next=request.path)
            )
        return view(*args, **kwargs)

    return wrapped


def allowed_file(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def save_upload(file, prefix="imagem"):
    if not file or not file.filename:
        return ""

    if not allowed_file(file.filename):
        return ""

    extension = file.filename.rsplit(".", 1)[1].lower()

    filename = secure_filename(
        f"{prefix}_{secrets.token_hex(8)}.{extension}"
    )

    destination = UPLOAD_DIR / filename
    file.save(destination)

    return filename


def delete_upload(filename):
    if not filename:
        return

    try:
        file_path = UPLOAD_DIR / filename
        if file_path.exists():
            file_path.unlink()
    except Exception:
        pass


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


# =========================================================
# SITE PÚBLICO
# =========================================================

@app.route("/")
def home():
    register_visit("/")

    eventos = (
        Evento.query
        .order_by(Evento.destaque.desc(), Evento.criado_em.desc())
        .limit(6)
        .all()
    )

    servicos = (
        Servico.query
        .filter_by(ativo=True)
        .order_by(Servico.ordem, Servico.id)
        .all()
    )

    equipe = (
        Equipe.query
        .filter_by(ativo=True)
        .order_by(Equipe.ordem, Equipe.id)
        .limit(4)
        .all()
    )

    feedbacks = (
        Feedback.query
        .filter_by(aprovado=True)
        .order_by(Feedback.criado_em.desc())
        .limit(6)
        .all()
    )

    imagens = (
        Imagem.query
        .order_by(Imagem.criado_em.desc())
        .limit(12)
        .all()
    )

    return render_template(
        "home.html",
        eventos=eventos,
        servicos=servicos,
        equipe=equipe,
        feedbacks=feedbacks,
        imagens=imagens,
        whatsapp=whatsapp_link(),
    )


@app.route("/sobre")
def sobre():
    register_visit("/sobre")
    return render_template("sobre.html")


@app.route("/equipe")
def equipe_publica():
    register_visit("/equipe")

    equipe = (
        Equipe.query
        .filter_by(ativo=True)
        .order_by(Equipe.ordem, Equipe.id)
        .all()
    )

    return render_template("equipe.html", equipe=equipe)


@app.route("/servicos")
def servicos_publicos():
    register_visit("/servicos")

    servicos = (
        Servico.query
        .filter_by(ativo=True)
        .order_by(Servico.ordem, Servico.id)
        .all()
    )

    return render_template("servicos.html", servicos=servicos)


@app.route("/eventos")
def eventos_publicos():
    register_visit("/eventos")

    eventos = (
        Evento.query
        .order_by(
            Evento.destaque.desc(),
            Evento.data_evento.desc(),
            Evento.id.desc()
        )
        .all()
    )

    return render_template("eventos.html", eventos=eventos)


@app.route("/galeria")
def galeria_publica():
    register_visit("/galeria")

    imagens = (
        Imagem.query
        .order_by(Imagem.criado_em.desc())
        .all()
    )

    return render_template("galeria.html", imagens=imagens)


@app.route("/depoimentos", methods=["GET", "POST"])
def depoimentos():
    if request.method == "POST":
        check_csrf()

        nome = request.form.get("nome", "").strip()
        evento = request.form.get("evento", "").strip()
        mensagem = request.form.get("mensagem", "").strip()

        try:
            nota = int(request.form.get("nota", 5))
            nota = max(1, min(5, nota))
        except (ValueError, TypeError):
            nota = 5

        if not nome or not mensagem:
            flash("Preencha seu nome e depoimento.", "error")
        else:
            db.session.add(
                Feedback(
                    nome=nome,
                    evento=evento,
                    mensagem=mensagem,
                    nota=nota,
                    aprovado=False,
                )
            )
            db.session.commit()

            flash(
                "Obrigado! Seu depoimento foi enviado para análise.",
                "success"
            )

            return redirect(url_for("depoimentos"))

    feedbacks = (
        Feedback.query
        .filter_by(aprovado=True)
        .order_by(Feedback.criado_em.desc())
        .all()
    )

    return render_template(
        "depoimentos.html",
        feedbacks=feedbacks
    )


@app.route("/faq")
def faq():
    register_visit("/faq")
    return render_template("faq.html")


@app.route("/contato")
def contato():
    register_visit("/contato")
    return render_template(
        "contato.html",
        whatsapp=whatsapp_link()
    )


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

        texto = (
            "Olá, Encantar Cerimonial! "
            "Gostaria de solicitar um orçamento."
            "%0A%0A"
            f"Nome: {nome}"
            f"%0ATipo de evento: {tipo}"
            f"%0AData: {data}"
            f"%0AConvidados: {convidados}"
            f"%0ATelefone: {telefone}"
            f"%0AObservações: {mensagem}"
        )

        link = whatsapp_link()

        if link:
            return redirect(link + "?text=" + texto)

        flash(
            "O WhatsApp da empresa ainda não foi configurado no painel administrativo.",
            "error"
        )

    return render_template("orcamento.html")


# =========================================================
# ADMIN - LOGIN
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        check_csrf()

        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.senha_hash, senha):
            session["admin_id"] = usuario.id
            usuario.ultimo_login = datetime.utcnow()
            db.session.commit()

            destino = request.args.get("next")

            if not destino or not destino.startswith("/"):
                destino = url_for("admin_dashboard")

            return redirect(destino)

        flash("E-mail ou senha inválidos.", "error")

    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect(url_for("admin_login"))


# =========================================================
# ADMIN - DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template(
        "admin/dashboard.html",
        eventos=Evento.query.count(),
        servicos=Servico.query.count(),
        equipe=Equipe.query.count(),
        imagens=Imagem.query.count(),
        feedbacks=Feedback.query.filter_by(aprovado=False).count(),
        visitas=Visita.query.count(),
        ultimo_evento=(
            Evento.query.order_by(Evento.id.desc()).first()
        ),
    )


# =========================================================
# ADMIN - EVENTOS
# =========================================================

@app.route("/admin/eventos", methods=["GET", "POST"])
@admin_required
def admin_eventos():
    if request.method == "POST":
        check_csrf()

        action = request.form.get("action", "")

        if action == "delete":
            try:
                item_id = int(request.form.get("id", 0))
            except ValueError:
                abort(400)

            item = Evento.query.get_or_404(item_id)
            old_image = item.imagem

            db.session.delete(item)
            db.session.commit()

            delete_upload(old_image)

            flash("Evento excluído com sucesso.", "success")

        else:
            item_id = request.form.get("id")

            if item_id:
                try:
                    item = Evento.query.get_or_404(int(item_id))
                except ValueError:
                    abort(400)
            else:
                item = Evento()

            item.titulo = request.form.get("titulo", "").strip()
            item.tipo = request.form.get("tipo", "").strip()
            item.data_evento = request.form.get("data_evento", "").strip()
            item.local = request.form.get("local", "").strip()
            item.descricao = request.form.get("descricao", "").strip()
            item.album_url = request.form.get("album_url", "").strip()
            item.destaque = bool(request.form.get("destaque"))

            upload = save_upload(
                request.files.get("imagem"),
                "evento"
            )

            if upload:
                old_image = item.imagem
                item.imagem = upload

                if old_image:
                    delete_upload(old_image)

            if not item.id:
                db.session.add(item)

            db.session.commit()

            flash("Evento salvo com sucesso.", "success")

        return redirect(url_for("admin_eventos"))

    edit_id = request.args.get("edit", type=int)
    edit = Evento.query.get_or_404(edit_id) if edit_id else None

    eventos = Evento.query.order_by(Evento.id.desc()).all()

    return render_template(
        "admin/eventos.html",
        eventos=eventos,
        edit=edit
    )


# =========================================================
# ADMIN - SERVIÇOS
# =========================================================

@app.route("/admin/servicos", methods=["GET", "POST"])
@admin_required
def admin_servicos():
    if request.method == "POST":
        check_csrf()

        action = request.form.get("action", "")

        if action == "delete":
            try:
                item_id = int(request.form.get("id", 0))
            except ValueError:
                abort(400)

            item = Servico.query.get_or_404(item_id)
            db.session.delete(item)
            db.session.commit()

            flash("Serviço excluído com sucesso.", "success")

        else:
            item_id = request.form.get("id")

            if item_id:
                try:
                    item = Servico.query.get_or_404(int(item_id))
                except ValueError:
                    abort(400)
            else:
                item = Servico()

            item.nome = request.form.get("nome", "").strip()
            item.descricao = request.form.get("descricao", "").strip()
            item.icone = request.form.get("icone", "sparkles").strip()
            item.ordem = request.form.get("ordem", 0, type=int)
            item.ativo = bool(request.form.get("ativo"))

            if not item.id:
                db.session.add(item)

            db.session.commit()

            flash("Serviço salvo com sucesso.", "success")

        return redirect(url_for("admin_servicos"))

    edit_id = request.args.get("edit", type=int)
    edit = Servico.query.get_or_404(edit_id) if edit_id else None

    servicos = (
        Servico.query
        .order_by(Servico.ordem, Servico.id)
        .all()
    )

    return render_template(
        "admin/servicos.html",
        servicos=servicos,
        edit=edit
    )


# =========================================================
# ADMIN - EQUIPE
# =========================================================

@app.route("/admin/equipe", methods=["GET", "POST"])
@admin_required
def admin_equipe():
    if request.method == "POST":
        check_csrf()

        action = request.form.get("action", "")

        if action == "delete":
            try:
                item_id = int(request.form.get("id", 0))
            except ValueError:
                abort(400)

            item = Equipe.query.get_or_404(item_id)
            old_photo = item.foto

            db.session.delete(item)
            db.session.commit()

            delete_upload(old_photo)

            flash("Membro removido com sucesso.", "success")

        else:
            item_id = request.form.get("id")

            if item_id:
                try:
                    item = Equipe.query.get_or_404(int(item_id))
                except ValueError:
                    abort(400)
            else:
                item = Equipe()

            item.nome = request.form.get("nome", "").strip()
            item.cargo = request.form.get("cargo", "").strip()
            item.bio = request.form.get("bio", "").strip()
            item.instagram = request.form.get("instagram", "").strip()
            item.ordem = request.form.get("ordem", 0, type=int)
            item.ativo = bool(request.form.get("ativo"))

            upload = save_upload(
                request.files.get("foto"),
                "equipe"
            )

            if upload:
                old_photo = item.foto
                item.foto = upload

                if old_photo:
                    delete_upload(old_photo)

            if not item.id:
                db.session.add(item)

            db.session.commit()

            flash(
                "Membro da equipe salvo com sucesso.",
                "success"
            )

        return redirect(url_for("admin_equipe"))

    edit_id = request.args.get("edit", type=int)
    edit = Equipe.query.get_or_404(edit_id) if edit_id else None

    equipe = (
        Equipe.query
        .order_by(Equipe.ordem, Equipe.id)
        .all()
    )

    return render_template(
        "admin/equipe.html",
        equipe=equipe,
        edit=edit
    )


# =========================================================
# ADMIN - IMAGENS
# =========================================================

@app.route("/admin/imagens", methods=["GET", "POST"])
@admin_required
def admin_imagens():
    if request.method == "POST":
        check_csrf()

        action = request.form.get("action", "")

        if action == "delete":
            try:
                item_id = int(request.form.get("id", 0))
            except ValueError:
                abort(400)

            item = Imagem.query.get_or_404(item_id)
            arquivo = item.arquivo

            db.session.delete(item)
            db.session.commit()

            delete_upload(arquivo)

            flash("Imagem excluída com sucesso.", "success")

        else:
            arquivos = request.files.getlist("arquivos")

            titulo = request.form.get("titulo", "").strip()
            categoria = request.form.get(
                "categoria",
                "Galeria"
            ).strip()

            adicionadas = 0

            for arquivo in arquivos:
                filename = save_upload(
                    arquivo,
                    "galeria"
                )

                if filename:
                    db.session.add(
                        Imagem(
                            titulo=titulo,
                            categoria=categoria,
                            arquivo=filename
                        )
                    )
                    adicionadas += 1

            db.session.commit()

            if adicionadas:
                flash(
                    f"{adicionadas} imagem(ns) adicionada(s) com sucesso.",
                    "success"
                )
            else:
                flash(
                    "Nenhuma imagem válida foi enviada.",
                    "error"
                )

        return redirect(url_for("admin_imagens"))

    imagens = (
        Imagem.query
        .order_by(Imagem.id.desc())
        .all()
    )

    return render_template(
        "admin/imagens.html",
        imagens=imagens
    )


# =========================================================
# ADMIN - FEEDBACKS
# =========================================================

@app.route("/admin/feedbacks", methods=["GET", "POST"])
@admin_required
def admin_feedbacks_page():
    if request.method == "POST":
        check_csrf()

        try:
            item_id = int(request.form.get("id", 0))
        except ValueError:
            abort(400)

        item = Feedback.query.get_or_404(item_id)
        action = request.form.get("action", "")

        if action == "approve":
            item.aprovado = True
            flash("Depoimento aprovado.", "success")

        elif action == "unapprove":
            item.aprovado = False
            flash(
                "Depoimento retirado da publicação.",
                "success"
            )

        elif action == "delete":
            db.session.delete(item)
            flash("Depoimento excluído.", "success")

        db.session.commit()

        return redirect(url_for("admin_feedbacks_page"))

    feedbacks = (
        Feedback.query
        .order_by(Feedback.criado_em.desc())
        .all()
    )

    return render_template(
        "admin/feedbacks.html",
        feedbacks=feedbacks
    )


# =========================================================
# ADMIN - CONFIGURAÇÕES
# =========================================================

@app.route("/admin/configuracoes", methods=["GET", "POST"])
@admin_required
def admin_configuracoes():
    keys = [
        "nome_empresa",
        "slogan",
        "descricao",
        "whatsapp",
        "instagram",
        "facebook",
        "email",
        "maps",
        "endereco",
        "telefone",
        "logo"
    ]

    if request.method == "POST":
        check_csrf()

        # Salva as configurações de texto
        for key in keys:
            # A logo será tratada separadamente abaixo
            if key == "logo":
                continue

            value = request.form.get(key, "").strip()

            item = Configuracao.query.filter_by(chave=key).first()

            if not item:
                item = Configuracao(chave=key)
                db.session.add(item)

            item.valor = value

        # ==========================================
        # UPLOAD DA LOGO
        # ==========================================

        logo_file = request.files.get("logo_file")

        if logo_file and logo_file.filename:

            if not allowed_file(logo_file.filename):
                flash(
                    "Formato de logo inválido. Use PNG, JPG, JPEG, WEBP ou GIF.",
                    "error"
                )
                return redirect(url_for("admin_configuracoes"))

            # Salva a nova logo
            novo_arquivo = save_upload(
                logo_file,
                prefix="logo"
            )

            if novo_arquivo:
                item_logo = Configuracao.query.filter_by(
                    chave="logo"
                ).first()

                if not item_logo:
                    item_logo = Configuracao(chave="logo")
                    db.session.add(item_logo)

                item_logo.valor = novo_arquivo

        db.session.commit()

        flash("Configurações salvas com sucesso.", "success")

        return redirect(url_for("admin_configuracoes"))

    values = {
        key: cfg(key, "")
        for key in keys
    }

    return render_template(
        "admin/configuracoes.html",
        values=values
    )
        # -------------------------------------------------
        # NOVO: upload do banner da página inicial
        # -------------------------------------------------

        banner_file = request.files.get("banner")

        if banner_file and banner_file.filename:

            novo_banner = save_upload(
                banner_file,
                "banner"
            )

            if not novo_banner:
                flash(
                    "O banner não foi enviado. Use PNG, JPG, JPEG, WEBP ou GIF.",
                    "error"
                )
                db.session.rollback()
                return redirect(
                    url_for("admin_configuracoes")
                )

            banner_item = (
                Configuracao.query
                .filter_by(chave="banner")
                .first()
            )

            if not banner_item:
                banner_item = Configuracao(
                    chave="banner"
                )
                db.session.add(banner_item)

            antigo_banner = banner_item.valor
            banner_item.valor = novo_banner

            if antigo_banner:
                delete_upload(antigo_banner)

        db.session.commit()

        flash(
            "Configurações salvas com sucesso.",
            "success"
        )

        return redirect(
            url_for("admin_configuracoes")
        )

    values = {
        key: cfg(key, "")
        for key in keys
    }

    return render_template(
        "admin/configuracoes.html",
        values=values
    )


# =========================================================
# ADMIN - BACKUP
# =========================================================

@app.route("/admin/backup")
@admin_required
def admin_backup():

    database_uri = app.config["SQLALCHEMY_DATABASE_URI"]

    if database_uri.startswith("postgresql://"):
        flash(
            "O banco do site está usando PostgreSQL. "
            "O backup do banco deve ser feito pelo próprio "
            "provedor do PostgreSQL/Render.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if not database_uri.startswith("sqlite:///"):
        flash(
            "Tipo de banco não suportado para backup local.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    db_path = database_uri.replace(
        "sqlite:///",
        "",
        1
    )

    if not os.path.isabs(db_path):
        db_path = str(BASE_DIR / db_path)

    if not os.path.exists(db_path):
        flash(
            "Banco ainda não encontrado.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    target = BACKUP_DIR / f"encantar_backup_{stamp}.db"

    shutil.copy2(db_path, target)

    return send_from_directory(
        BACKUP_DIR,
        target.name,
        as_attachment=True
    )


# =========================================================
# ERROS
# =========================================================

@app.errorhandler(400)
def bad_request(error):
    db.session.rollback()

    return render_template(
        "error.html",
        code=400,
        message=getattr(
            error,
            "description",
            "Requisição inválida."
        )
    ), 400


@app.errorhandler(404)
def not_found(error):
    return render_template(
        "error.html",
        code=404,
        message="A página que você procurou não existe."
    ), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()

    return render_template(
        "error.html",
        code=500,
        message="Ocorreu um erro interno. Tente novamente."
    ), 500


# =========================================================
# INICIALIZAÇÃO DO BANCO
# =========================================================

def init_db():

    with app.app_context():

        db.create_all()

        # -----------------------------------------
        # ADMINISTRADOR
        # -----------------------------------------

        if not Usuario.query.first():

            admin_email = os.environ.get(
                "ADMIN_EMAIL",
                "admin@encantarcerimonial.com"
            ).strip().lower()

            admin_password = os.environ.get(
                "ADMIN_PASSWORD",
                "Encantar@123"
            )

            admin = Usuario(
                nome="Administrador",
                email=admin_email,
                senha_hash=generate_password_hash(
                    admin_password
                )
            )

            db.session.add(admin)

        # -----------------------------------------
        # CONFIGURAÇÕES PADRÃO
        # -----------------------------------------

        defaults = {
            "nome_empresa":
                "Encantar Cerimonial",

            "slogan":
                "Momentos inesquecíveis começam com cuidado.",

            "descricao":
                "Planejamento, organização e cerimonial para transformar celebrações em memórias especiais.",

            "whatsapp":
                "",

            "instagram":
                "",

            "facebook":
                "",

            "email":
                "",

            "maps":
                "",

            "endereco":
                "",

            "telefone":
                "",

            "logo":
                "",

            # NOVO
            "banner":
                "",
        }

        for key, value in defaults.items():

            exists = (
                Configuracao.query
                .filter_by(chave=key)
                .first()
            )

            if not exists:
                db.session.add(
                    Configuracao(
                        chave=key,
                        valor=value
                    )
                )

        db.session.commit()


# =========================================================
# INICIALIZAÇÃO
# =========================================================

try:
    init_db()

except Exception as error:

    print(
        "ERRO AO INICIALIZAR O BANCO DE DADOS:"
    )

    print(repr(error))

    raise


# =========================================================
# EXECUÇÃO LOCAL
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )

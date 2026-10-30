"""
login.py

Blueprint responsável pela autenticação da aplicação.

Correção aplicada neste review (ver relatório de code review):
- Sanitização do `username` antes de logar, para evitar log injection
  (um username contendo '\\r'/'\\n' podia forjar linhas de log falsas,
  já que o valor não passa por validação de formato antes deste ponto
  no fluxo de login).
"""

import logging
from functools import wraps

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from extensions import limiter
from .login_database import (
    criar_usuario,
    init_db,
    segundos_restantes_bloqueio,
    validar_login,
)

logger = logging.getLogger(__name__)

login_bp = Blueprint(
    "login_bp",
    __name__,
    template_folder="templates",
)

# Cria a tabela de usuários caso ainda não exista
init_db()

# Limite defensivo para evitar payloads muito grandes vindos do form
MAX_INPUT_LEN = 256

# Chave de sessão que lembra QUAL usuário acabou de ser bloqueado neste
# navegador. É apenas uma dica de interface: permite que um F5 (GET, sem
# username) continue exibindo o contador. O tempo restante NUNCA vem daqui,
# é sempre recalculado a partir de `bloqueado_ate` no banco.
_SESSION_BLOQUEIO_KEY = "login_bloqueio_usuario"


def _sanitizar_para_log(valor: str) -> str:
    """Remove caracteres de quebra de linha antes de gravar em log.

    Evita log injection (CRLF injection): sem isso, um usuário poderia
    enviar um "username" contendo '\\r'/'\\n' para forjar linhas de log
    falsas e dificultar auditoria/forense.
    """
    if not valor:
        return valor
    return valor.replace("\r", "").replace("\n", "")


@login_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    """Tela de login."""

    if request.method == "POST":
        username = request.form.get("username", "").strip()[:MAX_INPUT_LEN]
        senha = request.form.get("senha", "")[:MAX_INPUT_LEN]

        sucesso, mensagem = validar_login(username, senha)

        # Nunca logar a senha, mesmo truncada ou com erro.
        # Username sanitizado para evitar log injection (ver docstring
        # de _sanitizar_para_log).
        logger.info(
            "Tentativa de login | usuario=%s | sucesso=%s",
            _sanitizar_para_log(username),
            sucesso,
        )

        if sucesso:
            # Regenera a sessão no login para mitigar session fixation
            session.clear()
            session["usuario"] = username
            return redirect(url_for("pedidos.index"))

        # Se a falha deixou (ou já encontrou) a conta bloqueada, a tela mostra
        # o aviso de bloqueio com contador no lugar da mensagem de erro.
        # A decisão de bloquear continua em validar_login(); aqui só lemos.
        restante = segundos_restantes_bloqueio(username)
        if restante > 0:
            session[_SESSION_BLOQUEIO_KEY] = username
            return render_template(
                "login.html",
                username=username,
                bloqueio_segundos=restante,
            )

        session.pop(_SESSION_BLOQUEIO_KEY, None)
        flash(mensagem, "error")

        return render_template(
            "login.html",
            username=username,
        )

    # GET (ex.: F5 durante o bloqueio): retoma o contador com o tempo REAL
    # restante, calculado pelo banco, em vez de reiniciar os 15 minutos.
    username_bloqueado = session.get(_SESSION_BLOQUEIO_KEY)
    if username_bloqueado:
        restante = segundos_restantes_bloqueio(username_bloqueado)
        if restante > 0:
            return render_template(
                "login.html",
                username=username_bloqueado,
                bloqueio_segundos=restante,
            )
        session.pop(_SESSION_BLOQUEIO_KEY, None)

    return render_template("login.html")


@login_bp.route("/logout")
def logout():
    """Encerra a sessão do usuário."""

    session.clear()
    flash("Você saiu da sua conta.", "success")

    return redirect(url_for("login_bp.login"))


@login_bp.route("/cadastro", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def cadastro():
    """Cadastro de novos usuários."""

    if request.method == "POST":

        username = request.form.get("username", "").strip()[:MAX_INPUT_LEN]
        email = request.form.get("email", "").strip()[:MAX_INPUT_LEN] or None
        senha = request.form.get("senha", "")[:MAX_INPUT_LEN]
        confirmar_senha = request.form.get("confirmar_senha", "")[:MAX_INPUT_LEN]

        if senha != confirmar_senha:
            flash("As senhas não coincidem.", "error")

            return render_template(
                "cadastro.html",
                username=username,
                email=email,
            )

        sucesso, mensagem = criar_usuario(
            username=username,
            senha=senha,
            email=email,
        )

        logger.info(
            "Tentativa de cadastro | usuario=%s | sucesso=%s",
            _sanitizar_para_log(username),
            sucesso,
        )

        if sucesso:
            flash("Cadastro realizado com sucesso. Faça seu login.", "success")
            return redirect(url_for("login_bp.login"))

        flash(mensagem, "error")

        return render_template(
            "cadastro.html",
            username=username,
            email=email,
        )

    return render_template("cadastro.html")


def login_required(view_func):
    """
    Decorator para proteger rotas que exigem autenticação.

    Exemplo:

        @pedidos_bp.route("/")
        @login_required
        def index():
            ...
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):

        if "usuario" not in session:
            flash(
                "Você precisa fazer login para acessar esta página.",
                "error",
            )
            return redirect(url_for("login_bp.login"))

        return view_func(*args, **kwargs)

    return wrapper
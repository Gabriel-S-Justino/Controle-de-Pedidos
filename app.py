import os
import logging
import ipaddress
from datetime import timedelta
from datetime import datetime

from flask import Flask, abort, request
from werkzeug.middleware.proxy_fix import ProxyFix

from config import MAX_CONTENT_LENGTH, SECRET_KEY
from extensions import csrf, limiter
from login.login import login_bp
from routes.pedidos import pedidos_bp

# =========================================================
# APP
# =========================================================
app = Flask(__name__)
logger = logging.getLogger(__name__)

# =========================================================
# CONFIGURAÇÕES
# =========================================================
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# =========================================================
# VERSÃO
# =========================================================
APP_VERSION = "8.0.2"


@app.context_processor
def inject_app_version():
    return {
        "app_version": APP_VERSION
    }
    
@app.context_processor
def inject_app_info():
    return {
        "app_version": APP_VERSION,
        "current_year": datetime.now().year,
    }
# =========================================================
# PROXY / SESSÃO
# =========================================================
# Defina ATRAS_DE_PROXY=true apenas quando a aplicação estiver
# atrás de um reverse proxy (Nginx, Apache, Cloudflare, etc.)
ATRAS_DE_PROXY = (
    os.getenv("ATRAS_DE_PROXY", "false")
    .strip()
    .lower()
    == "true"
)

if ATRAS_DE_PROXY:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
    )

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = ATRAS_DE_PROXY
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

# =========================================================
# EXTENSÕES DE SEGURANÇA (CSRF + rate limiting)
# =========================================================
csrf.init_app(app)
limiter.init_app(app)

# =========================================================
# SEGURANÇA
# =========================================================
@app.before_request
def bloquear_acessos_externos():
    try:
        ip_remoto = request.remote_addr
        if not ip_remoto:
            logger.warning("Requisição sem IP de origem.")
            abort(403)
        ip = ipaddress.ip_address(ip_remoto)
        if not (ip.is_private or ip.is_loopback):
            logger.warning(
                "Tentativa de acesso externo bloqueada | "
                "IP=%s | Método=%s | URL=%s",
                ip_remoto,
                request.method,
                request.url,
            )
            abort(403)
    except (ValueError, TypeError):
        logger.warning(
            "IP inválido recebido | IP=%s",
            request.remote_addr,
        )
        abort(403)


# =========================================================
# BLUEPRINTS
# =========================================================
app.register_blueprint(login_bp)
app.register_blueprint(pedidos_bp)

# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    # ATENÇÃO: debug=True nunca deve ir para produção — habilita o
    # debugger interativo do Werkzeug, que permite execução remota de
    # código caso a porta fique acessível. Controle isso por variável
    # de ambiente e mantenha False fora do desenvolvimento local.
    debug_mode = os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=debug_mode,
    )
 
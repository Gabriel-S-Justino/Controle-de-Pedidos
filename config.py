import os
from pathlib import Path

from dotenv import load_dotenv

# =========================================================
# PATHS BASE
# =========================================================
BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _obrigatoria(nome: str) -> str:
    valor = os.environ.get(nome)
    if not valor:
        raise RuntimeError(
            f"Variável de ambiente obrigatória ausente: {nome}. "
            f"Defina em {BASE_DIR / '.env'} (fora do controle de versão) "
            f"ou no ambiente do processo."
        )
    return valor


# =========================================================
# DATABASE
# =========================================================
DATABASE = str(BASE_DIR / os.environ.get("DATABASE", "databases/pedidos.db"))

# =========================================================
# SECRET
# =========================================================
SECRET_KEY = _obrigatoria("SECRET_KEY")

# =========================================================
# UPLOADS
# =========================================================
UPLOAD_FOLDER = str(BASE_DIR / os.environ.get("UPLOAD_FOLDER", "uploads"))
MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =========================================================
# LOGS
# =========================================================
LOG_FOLDER = str(BASE_DIR / os.environ.get("LOG_FOLDER", "logs"))
os.makedirs(LOG_FOLDER, exist_ok=True)

# =========================================================
# SMTP / EMAIL
# =========================================================
# Exemplo de .env (nunca commitar este arquivo — ver .env.example):
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=seuemail@gmail.com
# SMTP_PASSWORD=senha-de-app-google  (senha de app, não a senha da conta)
# SMTP_USE_TLS=true
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = _obrigatoria("SMTP_USER")
SMTP_PASSWORD = _obrigatoria("SMTP_PASSWORD")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").strip().lower() == "true"
EMAIL_REMETENTE = SMTP_USER

# =========================================================
# NOTIFICAÇÕES
# =========================================================
# Tempo em segundos: 1800 = 30min, 300 = 5min, 3600 = 1h
NOTIFICATION_INTERVAL = int(os.environ.get("NOTIFICATION_INTERVAL", 1800))

# =========================================================
# FRETES
# =========================================================
# Lista, não set: ordem é relevante para eventual uso em <select>.
# Atualmente não consumido em nenhum lugar do projeto (dead code —
# templates/index.html tem as opções fixas em HTML).
TIPOS_FRETE = [
    "Aéreo",
    "Rodoviário",
    "Retirada",
]

# =========================================================
# FILE VALIDATION
# =========================================================
ALLOWED_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "xlsx",
}
ALLOWED_MIMES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
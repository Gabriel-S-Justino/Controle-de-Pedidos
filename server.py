import logging
import os
import socket
from datetime import datetime

from waitress import serve

from config import LOG_FOLDER
from database import criar_banco
from services.notification_service import iniciar_scheduler
from app import app



# =========================================================
# LOGGING — handler com rotação diária real de pasta
# =========================================================

class DailyFolderFileHandler(logging.Handler):

    def __init__(self, base_folder: str, filename: str = "server.log", encoding: str = "utf-8"):
        super().__init__()
        self._base_folder = base_folder
        self._filename = filename
        self._encoding = encoding
        self._dia_atual = None
        self._file_handler = None
        self._abrir_handler_do_dia()

    def _abrir_handler_do_dia(self):
        agora = datetime.now()
        dia = agora.strftime("%Y-%m-%d")

        if dia == self._dia_atual:
            return

        pasta = os.path.join(
            self._base_folder,
            agora.strftime("%Y"),
            agora.strftime("%m"),
            agora.strftime("%d"),
        )
        os.makedirs(pasta, exist_ok=True)

        caminho = os.path.join(pasta, self._filename)
        novo_handler = logging.FileHandler(caminho, encoding=self._encoding)
        if self.formatter:
            novo_handler.setFormatter(self.formatter)

        antigo = self._file_handler
        self._file_handler = novo_handler
        self._dia_atual = dia

        if antigo:
            antigo.close()

    def setFormatter(self, fmt):
        super().setFormatter(fmt)
        if self._file_handler:
            self._file_handler.setFormatter(fmt)

    def emit(self, record):
        self._abrir_handler_do_dia()
        self._file_handler.emit(record)

    def close(self):
        if self._file_handler:
            self._file_handler.close()
        super().close()


logging.basicConfig(
    level=logging.INFO,
    format=(
        "[%(asctime)s] "
        "[%(levelname)s] "
        "[%(filename)s:%(lineno)d] "
        "%(message)s"
    ),
    handlers=[
        DailyFolderFileHandler(LOG_FOLDER),
        logging.StreamHandler(),
    ],
    force=True,
)

logger = logging.getLogger(__name__)


# =========================================================
# SERVER CONFIG
# =========================================================

def obter_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            # Não estabelece conexão de fato, apenas descobre
            # qual interface seria usada para sair da máquina.
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


HOST = os.environ.get("SERVER_HOST") or obter_ip()

try:
    PORT = int(os.environ.get("SERVER_PORT", "8080"))
except ValueError:
    logger.warning("SERVER_PORT inválido (%s), usando padrão 8080", os.environ.get("SERVER_PORT"))
    PORT = 8080


# =========================================================
# STARTUP
# =========================================================

logger.info("=========================================================")
logger.info("Controle de pedidos - CNP")
logger.info("Created by - Gabriel S. Justino")
logger.info("=========================================================")

try:
    logger.info("Inicializando banco...")
    criar_banco()
    logger.info("Banco inicializado")

    logger.info("Inicializando scheduler...")
    iniciar_scheduler()
    logger.info("Scheduler iniciado")

    logger.info(f"Servidor disponível em http://{HOST}:{PORT}")
    serve(
        app,
        host=HOST,
        port=PORT,
        threads=8,
    )
except Exception:
    logger.exception("Falha fatal na inicialização do servidor")
    raise
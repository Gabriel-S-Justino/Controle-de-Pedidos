
# services/notification_service.py
"""Regras de disparo das notificações automáticas dos pedidos."""

import logging
import os
import threading
import time
from datetime import datetime
from urllib.parse import quote

import config
from config import NOTIFICATION_INTERVAL
from database import conectar
from helpers import converter_data
from services.email_service import email_alerta, email_atrasado, email_entregue

logger = logging.getLogger(__name__)

DIAS_ALERTA = 3


def _link_pedido(pedido_id) -> str | None:
    base_url = getattr(config, "APP_BASE_URL", None)
    if not base_url or pedido_id is None:
        return None
    return f"{base_url.rstrip('/')}/pedidos/{quote(str(pedido_id), safe='')}"


def _preparar_pedido(pedido: dict) -> dict:
    """
    Mantém os dados originais do banco e acrescenta apenas metadados
    necessários à infraestrutura de notificação.
    """
    pedido["_link_sistema"] = _link_pedido(pedido.get("id"))

    arquivo = pedido.get("arquivo")
    pedido["_anexo_nome"] = os.path.basename(arquivo) if arquivo else None

    return pedido


def _processar_pedido(conn, pedido: dict, hoje) -> None:
    email = pedido.get("email")
    if not email:
        return

    pedido = _preparar_pedido(pedido)

    entregue = int(pedido.get("entregue") or 0)

    if entregue == 1:
        if pedido.get("email_entregue_enviado"):
            return

        # data_entrega ainda não existe no schema atual; quando existir,
        # será usada. Até lá, "hoje" representa a detecção pelo scheduler.
        data_entrega = converter_data(pedido.get("data_entrega")) or hoje

        if email_entregue(email, pedido, data_entrega):
            conn.execute(
                "UPDATE pedidos SET email_entregue_enviado = 1 WHERE id = ?",
                (pedido["id"],),
            )
        return

    previsao = converter_data(pedido.get("previsao_chegada"))
    if not previsao:
        return

    dias = (previsao - hoje).days

    if dias < 0:
        if pedido.get("email_atraso_enviado"):
            return

        if email_atrasado(email, pedido, abs(dias)):
            conn.execute(
                "UPDATE pedidos SET email_atraso_enviado = 1 WHERE id = ?",
                (pedido["id"],),
            )
        return

    if 0 <= dias <= DIAS_ALERTA:
        if pedido.get("email_alerta_enviado"):
            return

        if email_alerta(email, pedido, dias):
            conn.execute(
                "UPDATE pedidos SET email_alerta_enviado = 1 WHERE id = ?",
                (pedido["id"],),
            )


def verificar_pedidos() -> None:
    hoje = datetime.now().date()

    with conectar() as conn:
        pedidos = conn.execute(
            "SELECT * FROM pedidos WHERE deletado = 0"
        ).fetchall()

        for linha in pedidos:
            pedido = dict(linha)
            try:
                _processar_pedido(conn, pedido, hoje)
            except Exception:
                logger.exception(
                    "Erro ao processar pedido id=%s",
                    pedido.get("id"),
                )

        conn.commit()


def scheduler() -> None:
    logger.info("Scheduler de notificações iniciado.")

    while True:
        try:
            verificar_pedidos()
        except Exception:
            logger.exception("Erro no ciclo do scheduler.")

        time.sleep(NOTIFICATION_INTERVAL)


def iniciar_scheduler() -> None:
    thread = threading.Thread(
        target=scheduler,
        daemon=True,
        name="notification-scheduler",
    )
    thread.start()
    logger.info("Thread do scheduler iniciada.")
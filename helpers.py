import os
import re
from datetime import datetime

from config import ALLOWED_EXTENSIONS, ALLOWED_MIMES

# =========================================================
# FRETES
# =========================================================

# NOTA: config.TIPOS_FRETE existe e também não é usado em nenhum
# lugar do projeto (dead code duplicado). Mantido aqui como lista
# (ordem importa para eventual uso em <select>), enquanto
# config.TIPOS_FRETE é um set (sem ordem garantida) — os dois não
# podem ser unificados sem antes corrigir o tipo em config.py.
TIPOS_FRETE = [
    "Aéreo",
    "Rodoviário",
    "Retirada",
]


# =========================================================
# FORMATAR MOEDA
# =========================================================

def formatar_moeda(valor) -> str:
    try:
        valor = float(valor or 0)

        return (
            f"R$ {valor:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    except (TypeError, ValueError):
        return "R$ 0,00"


# =========================================================
# NORMALIZAR VALOR
# =========================================================

_PADRAO_APENAS_MILHAR = re.compile(r"^\d{1,3}(\.\d{3})+$")


def normalizar_valor(valor) -> float:
    """
    Converte string de valor monetário para float.

    Assunção de formato (heurística, não garantia):
    - "1.234,56" -> 1234.56  (padrão BR completo: milhar + decimal)
    - "1.234"    -> 1234.0   (apenas quando casa com grupos de 3 dígitos
                              após o ponto — tratado como milhar sem decimais)
    - "1234.56"  -> 1234.56  (ponto como decimal, sem grupos de milhar)

    Casos genuinamente ambíguos (ex.: um valor "1.234" vindo de fonte que
    usa "." como decimal americano e quer dizer 1,234) são resolvidos
    incorretamente por esta heurística. A correção definitiva é garantir
    um contrato de formato explícito na origem do dado (ver documentação
    de alternativas).
    """
    if valor is None:
        return 0.0

    valor = str(valor).strip()

    if not valor:
        return 0.0

    valor = valor.replace("R$", "").replace(" ", "")

    if not valor:
        return 0.0

    negativo = valor.startswith("-")
    if negativo:
        valor = valor[1:]

    if "," in valor:
        # Formato BR completo: "." é milhar, "," é decimal.
        valor = valor.replace(".", "").replace(",", ".")
    elif _PADRAO_APENAS_MILHAR.match(valor):
        # Só milhar, sem parte decimal: "1.234" -> "1234"
        valor = valor.replace(".", "")
    # Caso contrário, "." já é separador decimal — mantém como está.

    try:
        resultado = float(valor)
    except (TypeError, ValueError):
        return 0.0

    return -resultado if negativo else resultado


# =========================================================
# CONVERTER DATA
# =========================================================

def converter_data(data_str):
    if not data_str:
        return None

    formatos = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(str(data_str).strip(), formato).date()
        except ValueError:
            pass

    return None


# =========================================================
# STATUS OPERACIONAL
# =========================================================

def obter_status_operacional(previsao_chegada, entregue, data_embarque, data_pedido):
    """Deriva o status operacional usando somente campos já existentes."""
    try:
        if int(entregue or 0) == 1:
            return {"key": "entregue", "label": "Entregue", "priority": 5}
    except (TypeError, ValueError):
        pass
    previsao = converter_data(previsao_chegada)
    hoje = datetime.now().date()
    dias = (previsao - hoje).days if previsao else None
    if dias is not None and dias < 0:
        return {"key": "atrasado", "label": "Atrasado", "priority": 1, "dias": dias}
    if dias is not None and dias <= 3:
        return {"key": "proximo", "label": "Próximo do prazo", "priority": 3, "dias": dias}
    if data_embarque:
        return {"key": "transito", "label": "Em trânsito", "priority": 2, "dias": dias}
    if converter_data(data_pedido) == hoje:
        return {"key": "novo", "label": "Novo", "priority": 4, "dias": dias}
    return {"key": "aguardando", "label": "Aguardando envio", "priority": 4, "dias": dias}

def gerar_status_linha(previsao_chegada, entregue) -> str:
    status = obter_status_operacional(previsao_chegada, entregue, None, None)
    return {"entregue": "linha-entregue", "atrasado": "linha-atrasada", "proximo": "linha-alerta"}.get(status["key"], "")


# =========================================================
# VALIDAR EMAIL
# =========================================================

# \Z em vez de $: $ casa também antes de um '\n' final, permitindo
# que "user@dominio.com\n" passe na validação. Como este valor é
# usado depois como cabeçalho MIME "To" (email_service.py), uma
# quebra de linha não bloqueada aqui é vetor de injeção de cabeçalho.
_REGEX_EMAIL = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\Z')


def email_valido(email) -> bool:
    if not email:
        return False

    return bool(_REGEX_EMAIL.match(str(email).strip()))


# =========================================================
# ARQUIVOS
# =========================================================

def arquivo_permitido(filename: str) -> bool:
    if "." not in filename:
        return False

    extensao = filename.rsplit(".", 1)[1].lower()

    return extensao in ALLOWED_EXTENSIONS


# =========================================================
# MIME TYPES
# =========================================================

def mime_permitido(mimetype: str) -> bool:
    return mimetype in ALLOWED_MIMES


# =========================================================
# GERAR PASTA DE UPLOAD
# =========================================================

def gerar_pasta_upload(base_folder: str) -> str:
    agora = datetime.now()

    pasta_mes = os.path.join(
        base_folder,
        agora.strftime("%Y"),
        agora.strftime("%m"),
    )

    os.makedirs(pasta_mes, exist_ok=True)

    return pasta_mes
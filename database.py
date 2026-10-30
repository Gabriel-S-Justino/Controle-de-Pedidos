# database.py

import sqlite3
from contextlib import contextmanager

from config import DATABASE

# =========================================================
# CONNECTION
# =========================================================

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    # WAL: permite leituras concorrentes durante escrita.
    # busy_timeout: em vez de falhar imediatamente com "database is
    # locked" quando outra thread segura o lock de escrita, espera
    # até 5s antes de levantar erro. Necessário porque Waitress roda
    # com threads=8 e o scheduler de notification_service.py também
    # abre conexões próprias, gerando escrita concorrente real.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    return conn


@contextmanager
def conectar():
    """
    Context manager para uso opcional nos call sites (routes/pedidos.py,
    services/notification_service.py), garantindo fechamento da conexão
    mesmo em caso de exceção. get_connection() é mantida como está para
    não quebrar compatibilidade com o código existente.

    Uso:
        with conectar() as conn:
            conn.execute(...)
            conn.commit()
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# =========================================================
# HELPERS
# =========================================================

# PRAGMA table_info não aceita bind parameter (?) para nome de tabela.
# Allowlist explícita evita que esta função vire vetor de SQL injection
# caso seja reutilizada no futuro com `tabela` vindo de entrada externa.
_TABELAS_VALIDAS = {"pedidos"}


def coluna_existe(conn: sqlite3.Connection, tabela: str, coluna: str) -> bool:
    if tabela not in _TABELAS_VALIDAS:
        raise ValueError(f"Tabela não permitida: {tabela!r}")

    resultado = conn.execute(f"PRAGMA table_info({tabela})").fetchall()
    colunas = [item["name"] for item in resultado]

    return coluna in colunas


# =========================================================
# DATABASE
# =========================================================

def criar_banco() -> None:
    conn = get_connection()

    try:
        # =================================================
        # TABELA BASE
        # =================================================
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fornecedor TEXT,
                transportadora TEXT,
                tipo_frete TEXT,
                data_pedido TEXT,
                previsao_chegada TEXT,
                valor REAL,
                responsavel TEXT,
                email TEXT,
                arquivo TEXT,
                entregue INTEGER DEFAULT 0,
                deletado INTEGER DEFAULT 0,
                email_atraso_enviado INTEGER DEFAULT 0,
                email_alerta_enviado INTEGER DEFAULT 0,
                email_entregue_enviado INTEGER DEFAULT 0,
                vendedor TEXT,
                nota_fiscal TEXT,
                cte TEXT,
                data_embarque TEXT,
                observacao TEXT,
                valor_nota REAL,
                valor_frete REAL,
                numero_pedido TEXT
            )
            """
        )

        # =================================================
        # MIGRAÇÕES AUTOMÁTICAS
        # =================================================
        migracoes = {
            "email": "ALTER TABLE pedidos ADD COLUMN email TEXT",
            "email_atraso_enviado": (
                "ALTER TABLE pedidos ADD COLUMN email_atraso_enviado "
                "INTEGER DEFAULT 0"
            ),
            "email_alerta_enviado": (
                "ALTER TABLE pedidos ADD COLUMN email_alerta_enviado "
                "INTEGER DEFAULT 0"
            ),
            "email_entregue_enviado": (
                "ALTER TABLE pedidos ADD COLUMN email_entregue_enviado "
                "INTEGER DEFAULT 0"
            ),
            # Novos campos opcionais (cadastro/edição de pedido). Todos
            # aceitam NULL, então pedidos já existentes continuam
            # funcionando normalmente sem precisar de dado retroativo.
            "vendedor": "ALTER TABLE pedidos ADD COLUMN vendedor TEXT",
            "nota_fiscal": "ALTER TABLE pedidos ADD COLUMN nota_fiscal TEXT",
            "cte": "ALTER TABLE pedidos ADD COLUMN cte TEXT",
            "data_embarque": "ALTER TABLE pedidos ADD COLUMN data_embarque TEXT",
            "observacao": "ALTER TABLE pedidos ADD COLUMN observacao TEXT",
            "valor_nota": "ALTER TABLE pedidos ADD COLUMN valor_nota REAL",
            "valor_frete": "ALTER TABLE pedidos ADD COLUMN valor_frete REAL",
            "numero_pedido": "ALTER TABLE pedidos ADD COLUMN numero_pedido TEXT",
        }

        for coluna, sql in migracoes.items():
            if not coluna_existe(conn, "pedidos", coluna):
                conn.execute(sql)

        conn.commit()
    finally:
        conn.close()
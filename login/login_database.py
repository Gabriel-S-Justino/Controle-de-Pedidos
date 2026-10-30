"""
login_database.py

Camada de acesso ao banco de dados para o sistema de login.
Usa SQLite (arquivo local) e armazena senhas com hash seguro
(werkzeug.security), nunca em texto puro.

Correções aplicadas neste review (ver relatório de code review):
1. Reset de `tentativas_falhas` quando o bloqueio expira (bug crítico
   que permitia manter uma conta bloqueada indefinidamente com 1
   tentativa falha a cada janela de bloqueio).
2. Incremento de `tentativas_falhas` feito de forma atômica no SQL
   (evita race condition de leitura+escrita em Python).
3. Normalização de e-mail (lowercase/strip) antes de validar/persistir.
4. Checagem mínima de complexidade de senha (letra + dígito), além do
   tamanho.
5. Migrações automáticas de schema (padrão importado de database.py):
   `coluna_existe()` com allowlist de tabela + dict `migracoes`,
   permitindo adicionar colunas novas em `usuarios` sem quebrar bancos
   já existentes em produção (evita "no such column" após deploy).
"""

import math
import re
import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from config import BASE_DIR

# Caminho do arquivo do banco de dados (fica dentro da pasta login/)
DB_PATH = os.path.join(BASE_DIR, "databases", "usuarios.db")

# Limites e regras de validação
USERNAME_MIN_LEN = 3
USERNAME_MAX_LEN = 30
SENHA_MIN_LEN = 8
SENHA_MAX_LEN = 128
EMAIL_MAX_LEN = 254
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_.-]+$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Exige ao menos uma letra e um dígito (checagem mínima de complexidade,
# recomendação NIST 800-63B: priorizar tamanho, mas evitar senhas triviais).
SENHA_TEM_LETRA_REGEX = re.compile(r"[A-Za-z]")
SENHA_TEM_DIGITO_REGEX = re.compile(r"\d")

# Bloqueio de conta após tentativas falhas consecutivas
MAX_TENTATIVAS_FALHAS = 5
TEMPO_BLOQUEIO_MINUTOS = 15

# Hash "isca" usado para equalizar o tempo de resposta quando o usuário
# não existe, evitando que um atacante descubra usuários válidos medindo
# o tempo de resposta do endpoint de login (timing attack).
_DUMMY_HASH = generate_password_hash("senha-isca-para-equalizar-tempo")


def get_connection():
    """Cria e retorna uma conexão com o banco SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # permite acessar colunas pelo nome
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================================================
# HELPERS DE MIGRAÇÃO
# =========================================================

# PRAGMA table_info não aceita bind parameter (?) para nome de tabela.
# Allowlist explícita evita que esta função vire vetor de SQL injection
# caso seja reutilizada no futuro com `tabela` vindo de entrada externa.
_TABELAS_VALIDAS = {"usuarios"}


def coluna_existe(conn: sqlite3.Connection, tabela: str, coluna: str) -> bool:
    if tabela not in _TABELAS_VALIDAS:
        raise ValueError(f"Tabela não permitida: {tabela!r}")

    resultado = conn.execute(f"PRAGMA table_info({tabela})").fetchall()
    colunas = [item["name"] for item in resultado]

    return coluna in colunas


def init_db():
    """Cria a tabela de usuários caso ela ainda não exista e aplica
    migrações automáticas de schema (colunas novas) em bancos já
    existentes."""
    conn = get_connection()
    try:
        # =================================================
        # TABELA BASE
        # =================================================
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                senha_hash TEXT NOT NULL,
                tentativas_falhas INTEGER NOT NULL DEFAULT 0,
                bloqueado_ate TIMESTAMP,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # =================================================
        # MIGRAÇÕES AUTOMÁTICAS
        # =================================================
        # Mesmo padrão de database.py: cada entrada é
        # "nome_da_coluna": "ALTER TABLE ... ADD COLUMN ...".
        # A migração só roda se a coluna ainda não existir, então é
        # seguro rodar `init_db()` toda vez que a aplicação sobe, mesmo
        # em bancos que já estão em produção com dados.
        #
        # Exemplo de uso futuro (deixe comentado até ser necessário):
        # migracoes = {
        #     "ultimo_login": "ALTER TABLE usuarios ADD COLUMN ultimo_login TIMESTAMP",
        # }
        migracoes: dict[str, str] = {}

        for coluna, sql in migracoes.items():
            if not coluna_existe(conn, "usuarios", coluna):
                conn.execute(sql)

        conn.commit()
    finally:
        conn.close()


def validar_username(username: str) -> tuple[bool, str]:
    """Valida formato e tamanho do nome de usuário."""
    if not username:
        return False, "Informe um usuário."
    if not (USERNAME_MIN_LEN <= len(username) <= USERNAME_MAX_LEN):
        return False, (
            f"Usuário deve ter entre {USERNAME_MIN_LEN} e "
            f"{USERNAME_MAX_LEN} caracteres."
        )
    if not USERNAME_REGEX.match(username):
        return False, "Usuário deve conter apenas letras, números, '.', '_' ou '-'."
    return True, ""


def validar_senha(senha: str) -> tuple[bool, str]:
    """Valida tamanho mínimo/máximo e complexidade mínima da senha."""
    if not senha:
        return False, "Informe uma senha."
    if len(senha) < SENHA_MIN_LEN:
        return False, f"A senha deve ter pelo menos {SENHA_MIN_LEN} caracteres."
    if len(senha) > SENHA_MAX_LEN:
        return False, f"A senha deve ter no máximo {SENHA_MAX_LEN} caracteres."
    if not SENHA_TEM_LETRA_REGEX.search(senha) or not SENHA_TEM_DIGITO_REGEX.search(senha):
        return False, "A senha deve conter ao menos uma letra e um número."
    return True, ""


def validar_email(email: str | None) -> tuple[bool, str]:
    """Valida formato e tamanho do e-mail (campo opcional)."""
    if email is None or email == "":
        return True, ""
    if len(email) > EMAIL_MAX_LEN:
        return False, "E-mail muito longo."
    if not EMAIL_REGEX.match(email):
        return False, "E-mail em formato inválido."
    return True, ""


def _normalizar_email(email: str | None) -> str | None:
    """Normaliza e-mail para minúsculas/sem espaços nas bordas.

    Evita que 'Usuario@Ex.com' e 'usuario@ex.com' sejam tratados como
    e-mails distintos pela constraint UNIQUE (comparação case-sensitive
    no SQLite por padrão).
    """
    if not email:
        return email
    return email.strip().lower()


def criar_usuario(username: str, senha: str, email: str = None) -> tuple[bool, str]:
    """
    Cria um novo usuário com senha em hash.
    Retorna (sucesso: bool, mensagem: str).
    """
    email = _normalizar_email(email)

    ok, msg = validar_username(username)
    if not ok:
        return False, msg

    ok, msg = validar_senha(senha)
    if not ok:
        return False, msg

    ok, msg = validar_email(email)
    if not ok:
        return False, msg

    senha_hash = generate_password_hash(senha)

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO usuarios (username, email, senha_hash) VALUES (?, ?, ?)",
            (username, email, senha_hash),
        )
        conn.commit()
        return True, "Usuário criado com sucesso."
    except sqlite3.IntegrityError:
        return False, "Usuário ou e-mail já cadastrado."
    finally:
        conn.close()


def validar_login(username: str, senha: str) -> tuple[bool, str]:
    """
    Verifica se as credenciais informadas são válidas.
    Retorna (sucesso: bool, mensagem: str).
    """
    # Limite defensivo de tamanho para evitar payloads gigantes antes de
    # tocar no banco de dados.
    if username and len(username) > USERNAME_MAX_LEN:
        username = username[:USERNAME_MAX_LEN]
    if senha and len(senha) > SENHA_MAX_LEN:
        return False, "Usuário ou senha inválidos."

    if not username or not senha:
        return False, "Preencha usuário e senha."

    conn = get_connection()
    try:
        usuario = conn.execute(
            "SELECT id, senha_hash, tentativas_falhas, bloqueado_ate "
            "FROM usuarios WHERE username = ?",
            (username,),
        ).fetchone()

        if usuario is None:
            # Executa um check_password_hash "isca" mesmo quando o usuário
            # não existe, para que o tempo de resposta seja parecido com o
            # caso de usuário existente + senha errada (mitiga timing attack).
            check_password_hash(_DUMMY_HASH, senha)
            return False, "Usuário ou senha inválidos."

        tentativas_atuais = usuario["tentativas_falhas"]

        # Verifica se a conta está temporariamente bloqueada.
        bloqueado_ate = usuario["bloqueado_ate"]
        if bloqueado_ate:
            bloqueado_ate_dt = datetime.fromisoformat(bloqueado_ate)
            if datetime.now() < bloqueado_ate_dt:
                return False, (
                    "Conta temporariamente bloqueada por excesso de "
                    "tentativas. Tente novamente mais tarde."
                )

            # CORREÇÃO (bug crítico): o bloqueio já expirou. Sem este reset,
            # o contador de tentativas continuava no valor antigo (ex.: 5) e
            # uma única falha subsequente já disparava um novo bloqueio de
            # 15 minutos — permitindo que um atacante mantivesse a conta
            # bloqueada indefinidamente com 1 tentativa a cada 15 minutos.
            # Ao expirar, o usuário deve ganhar MAX_TENTATIVAS_FALHAS
            # tentativas novas, não apenas 1.
            conn.execute(
                "UPDATE usuarios SET tentativas_falhas = 0, bloqueado_ate = NULL "
                "WHERE id = ?",
                (usuario["id"],),
            )
            conn.commit()
            tentativas_atuais = 0

        if check_password_hash(usuario["senha_hash"], senha):
            # Login OK: zera o contador de tentativas falhas (idempotente
            # mesmo se já foi zerado acima).
            conn.execute(
                "UPDATE usuarios SET tentativas_falhas = 0, bloqueado_ate = NULL "
                "WHERE id = ?",
                (usuario["id"],),
            )
            conn.commit()
            return True, "Login efetuado com sucesso."

        # Login falhou: incrementa contador de forma atômica no SQL
        # (evita race condition de ler o valor em Python e escrevê-lo de
        # volta, caso duas requisições concorrentes cheguem aqui juntas).
        tentativas = tentativas_atuais + 1

        if tentativas >= MAX_TENTATIVAS_FALHAS:
            bloqueio = datetime.now() + timedelta(minutes=TEMPO_BLOQUEIO_MINUTOS)
            conn.execute(
                "UPDATE usuarios SET tentativas_falhas = tentativas_falhas + 1, "
                "bloqueado_ate = ? WHERE id = ?",
                (bloqueio.isoformat(), usuario["id"]),
            )
            conn.commit()
            return False, (
                "Conta bloqueada por excesso de tentativas. "
                f"Tente novamente em {TEMPO_BLOQUEIO_MINUTOS} minutos."
            )

        conn.execute(
            "UPDATE usuarios SET tentativas_falhas = tentativas_falhas + 1 "
            "WHERE id = ?",
            (usuario["id"],),
        )
        conn.commit()
        return False, "Usuário ou senha inválidos."
    finally:
        conn.close()


def segundos_restantes_bloqueio(username: str) -> int:
    """Retorna quantos segundos faltam para o bloqueio do usuário terminar.

    Função somente-leitura: apenas consulta `bloqueado_ate`, sem alterar
    `tentativas_falhas` nem o próprio bloqueio. A regra de bloqueio
    continua inteiramente em `validar_login()`. Serve para a interface
    exibir o contador regressivo com base no instante REAL em que o
    bloqueio termina (fonte da verdade: banco de dados).

    Retorna 0 se o usuário não existe, não está bloqueado ou se o
    bloqueio já expirou. O valor é arredondado para cima, de modo que
    nunca é exibido "00:00" enquanto ainda há bloqueio ativo.
    """
    if not username:
        return 0
    username = username[:USERNAME_MAX_LEN]  # mesmo truncamento de validar_login

    conn = get_connection()
    try:
        linha = conn.execute(
            "SELECT bloqueado_ate FROM usuarios WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()

    if linha is None or not linha["bloqueado_ate"]:
        return 0

    try:
        restante = (
            datetime.fromisoformat(linha["bloqueado_ate"]) - datetime.now()
        ).total_seconds()
    except ValueError:
        return 0

    return max(0, math.ceil(restante))


def buscar_usuario_por_username(username: str):
    """Retorna os dados do usuário (sem a senha) ou None se não existir."""
    conn = get_connection()
    try:
        usuario = conn.execute(
            "SELECT id, username, email, criado_em FROM usuarios WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(usuario) if usuario else None
    finally:
        conn.close()
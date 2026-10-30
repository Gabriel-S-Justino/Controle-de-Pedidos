# pedidos.py

import logging
import os
import secrets
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from config import TIPOS_FRETE, UPLOAD_FOLDER
from database import conectar
from helpers import (
    arquivo_permitido,
    converter_data,
    email_valido,
    formatar_moeda,
    gerar_pasta_upload,
    gerar_status_linha,
    obter_status_operacional,
    mime_permitido,
    normalizar_valor,
)
from services.email_service import email_entregue
from login.login import login_required

logger = logging.getLogger(__name__)

pedidos_bp = Blueprint("pedidos", __name__)

# =========================================================
# FORMATAR PEDIDO
# =========================================================

def adicionar_observacao(observacao_atual, nova_observacao):
    """
    Mantém o histórico existente e adiciona uma nova observação
    identificada pela data atual, sem alterar as demais regras do pedido.
    """
    nova_observacao = (nova_observacao or "").strip()
    if not nova_observacao:
        return (observacao_atual or "").strip() or None

    linha = f"{datetime.now().strftime('%d/%m/%Y')} >> {nova_observacao}"
    historico = (observacao_atual or "").strip()

    if historico:
        return f"{historico}\n{linha}"

    return linha


def formatar_pedido(p) -> dict:
    p = dict(p)

    # "valor" já é float (coluna REAL do SQLite) — normalizar_valor()
    # é para strings de formulário, não para valores já numéricos.
    p["valor"] = float(p.get("valor") or 0)
    p["valor_formatado"] = formatar_moeda(p["valor"])

    # valor_nota/valor_frete são opcionais — None significa "não informado"
    # e é mantido como None (em vez de 0,00) para diferenciar dos casos em
    # que o usuário realmente preencheu zero.
    valor_nota = p.get("valor_nota")
    p["valor_nota"] = float(valor_nota) if valor_nota is not None else None
    p["valor_nota_formatado"] = (
        formatar_moeda(p["valor_nota"]) if p["valor_nota"] is not None else None
    )

    valor_frete = p.get("valor_frete")
    p["valor_frete"] = float(valor_frete) if valor_frete is not None else None
    p["valor_frete_formatado"] = (
        formatar_moeda(p["valor_frete"]) if p["valor_frete"] is not None else None
    )

    status = obter_status_operacional(p.get("previsao_chegada"), p.get("entregue"), p.get("data_embarque"), p.get("data_pedido"))
    p["status_key"] = status["key"]
    p["status_label"] = status["label"]
    p["status_priority"] = status["priority"]
    p["dias_para_entrega"] = status.get("dias")
    p["status_linha"] = gerar_status_linha(p.get("previsao_chegada"), p.get("entregue"))

    return p


# =========================================================
# OBTER PEDIDOS
# =========================================================

def obter_pedidos(deletado: int = 0, filtros: dict | None = None) -> list:
    """
    filtros aceita as chaves: fornecedor, pedido, vendedor, responsavel.
    Todas são opcionais e combináveis (AND). "pedido" filtra pelo campo
    numero_pedido (correspondência parcial, ex.: "PED-12" encontra
    pedidos cujo número contenha esse trecho). Campos de texto usam
    LIKE (case-insensitive por padrão no SQLite para ASCII) para
    permitir busca parcial.
    """
    condicoes = ["deletado=?"]
    parametros: list = [deletado]

    if filtros:
        fornecedor = (filtros.get("fornecedor") or "").strip()
        numero_pedido_filtro = (filtros.get("pedido") or "").strip()
        vendedor = (filtros.get("vendedor") or "").strip()
        transportadora = (filtros.get("transportadora") or "").strip()
        nota_fiscal = (filtros.get("nota_fiscal") or "").strip() 

        if fornecedor:
            condicoes.append("fornecedor LIKE ?")
            parametros.append(f"%{fornecedor}%")

        if numero_pedido_filtro:
            condicoes.append("numero_pedido LIKE ?")
            parametros.append(f"%{numero_pedido_filtro}%")
            
        if nota_fiscal:
            condicoes.append("nota_fiscal LIKE ?")
            parametros.append(f"%{nota_fiscal}%")

        if vendedor:
            condicoes.append("vendedor LIKE ?")
            parametros.append(f"%{vendedor}%")

        if transportadora:
            condicoes.append("transportadora LIKE ?")
            parametros.append(f"%{transportadora}%")

    query = (
        "SELECT * FROM pedidos WHERE "
        + " AND ".join(condicoes)
        + " ORDER BY id DESC"
    )

    with conectar() as conn:
        pedidos = conn.execute(query, parametros).fetchall()

    resultado = [formatar_pedido(p) for p in pedidos]
    status = ((filtros or {}).get("status") or "").strip()
    proximos = ((filtros or {}).get("proximos") or "").strip()
    if status:
        resultado = [p for p in resultado if p["status_label"] == status]
    if proximos == "1":
        resultado = [p for p in resultado if p["status_key"] == "proximo"]
    resultado.sort(key=lambda p: (p.get("status_priority", 99), -(p.get("id", 0) or 0)))
    return resultado


# =========================================================
# INDEX
# =========================================================

@pedidos_bp.route("/")
@login_required
def index():
    return redirect(url_for("pedidos.dashboard"))


# =========================================================
# DASHBOARD
# =========================================================

@pedidos_bp.route("/dashboard")
@login_required
def dashboard():
    pedidos_kpi = obter_pedidos()
    atrasados = sum(p["status_key"] == "atrasado" for p in pedidos_kpi)
    alertas = sum(p["status_key"] == "proximo" for p in pedidos_kpi)
    entregues = sum(p["status_key"] == "entregue" for p in pedidos_kpi)
    em_transito = sum(p["status_key"] == "transito" for p in pedidos_kpi)
    valor_total = sum(p["valor"] for p in pedidos_kpi)
    valor_transito = sum(p["valor"] for p in pedidos_kpi if p["status_key"] == "transito")
    valor_atrasado = sum(p["valor"] for p in pedidos_kpi if p["status_key"] == "atrasado")
    filtros = {
        "fornecedor": request.args.get("fornecedor", "").strip(),
        "pedido": request.args.get("pedido", "").strip(),
        "vendedor": request.args.get("vendedor", "").strip(),
        "transportadora": request.args.get("transportadora", "").strip(),
        "responsavel": request.args.get("responsavel", "").strip(),
        "status": request.args.get("status", "").strip(),
        "proximos": request.args.get("proximos", "").strip(),
        "nota_fiscal": request.args.get("nota_fiscal", "").strip(),
    }
    pedidos = obter_pedidos(filtros=filtros)
    return render_template("dashboard.html", pedidos=pedidos, total_pedidos=len(pedidos_kpi), atrasados=atrasados, alertas=alertas, entregues=entregues, em_transito=em_transito, valor_total=formatar_moeda(valor_total), valor_transito=formatar_moeda(valor_transito), valor_atrasado=formatar_moeda(valor_atrasado), filtros=filtros)

# =========================================================
# SALVAR
# =========================================================

@pedidos_bp.route("/salvar", methods=["POST"])
@login_required
def salvar():
    fornecedor = request.form.get("fornecedor", "").strip()
    transportadora = request.form.get("transportadora", "").strip()
    tipo_frete = request.form.get("tipo_frete", "").strip()
    data_pedido_raw = request.form.get("data_pedido", "").strip()
    previsao_raw = request.form.get("previsao_chegada", "").strip()
    previsao_chegada = converter_data(previsao_raw)
    responsavel = request.form.get("responsavel", "").strip()
    email = request.form.get("email", "").strip()

    # Novos campos — todos opcionais, não alteram nenhuma regra de
    # obrigatoriedade já existente.
    numero_pedido = request.form.get("numero_pedido", "").strip() or None
    vendedor = request.form.get("vendedor", "").strip() or None
    nota_fiscal = request.form.get("nota_fiscal", "").strip() or None
    cte = request.form.get("cte", "").strip() or None
    observacao = adicionar_observacao(None, request.form.get("observacao", ""))

    valor_nota_raw = request.form.get("valor_nota", "").strip()
    valor_nota = normalizar_valor(valor_nota_raw) if valor_nota_raw else None

    valor_frete_raw = request.form.get("valor_frete", "").strip()
    valor_frete = normalizar_valor(valor_frete_raw) if valor_frete_raw else None

    data_embarque_raw = request.form.get("data_embarque", "").strip()
    data_embarque = None
    if data_embarque_raw:
        data_embarque_convertida = converter_data(data_embarque_raw)
        if not data_embarque_convertida:
            flash("Data de embarque inválida")
            return redirect(url_for("pedidos.index"))
        data_embarque = data_embarque_raw

    if not fornecedor:
        flash("Fornecedor obrigatório")
        return redirect(url_for("pedidos.index"))

    if not transportadora:
        flash("Transportadora obrigatória")
        return redirect(url_for("pedidos.index"))

    if tipo_frete not in TIPOS_FRETE:
        flash("Tipo de frete inválido")
        return redirect(url_for("pedidos.index"))

    if not responsavel:
        flash("Responsável obrigatório")
        return redirect(url_for("pedidos.index"))

    if not email_valido(email):
        flash("Email inválido")
        return redirect(url_for("pedidos.index"))

    data_pedido = converter_data(data_pedido_raw)
    if not data_pedido:
        flash("Data do pedido inválida")
        return redirect(url_for("pedidos.index"))

    previsao_chegada = converter_data(previsao_raw)
    if not previsao_chegada:
        flash("Previsão de chegada inválida")
        return redirect(url_for("pedidos.index"))

    if previsao_chegada < data_pedido:
        flash("Previsão de chegada não pode ser anterior à data do pedido")
        return redirect(url_for("pedidos.index"))

    arquivo_nome = None
    arquivo = request.files.get("arquivo")

    if arquivo and arquivo.filename:
        if not arquivo_permitido(arquivo.filename):
            flash("Tipo de arquivo não permitido")
            return redirect(url_for("pedidos.index"))

        if not mime_permitido(arquivo.mimetype):
            flash("Tipo de arquivo não permitido")
            return redirect(url_for("pedidos.index"))

        nome_original = secure_filename(arquivo.filename)

        # Prefixo único evita sobrescrever arquivo de outro pedido com
        # o mesmo nome original no mesmo mês.
        nome = f"{uuid.uuid4().hex[:8]}_{nome_original}"

        pasta = gerar_pasta_upload(UPLOAD_FOLDER)
        caminho = os.path.join(pasta, nome)
        arquivo.save(caminho)

        agora = datetime.now()
        arquivo_nome = f"{agora.strftime('%Y')}/{agora.strftime('%m')}/{nome}"

    with conectar() as conn:
        cursor = conn.execute(
            """
            INSERT INTO pedidos(
                fornecedor, transportadora, tipo_frete,
                data_pedido, previsao_chegada,
                valor, responsavel, email, arquivo,
                entregue, deletado,
                vendedor, nota_fiscal, cte, data_embarque, observacao,
                valor_nota, valor_frete, numero_pedido
            )
            VALUES (?,?,?,?,?,?,?,?,?,0,0,?,?,?,?,?,?,?,?)
            """,
            (
                fornecedor,
                transportadora,
                tipo_frete,
                data_pedido_raw,
                previsao_raw,
                normalizar_valor(request.form.get("valor")),
                responsavel,
                email,
                arquivo_nome,
                vendedor,
                nota_fiscal,
                cte,
                data_embarque,
                observacao,
                valor_nota,
                valor_frete,
                numero_pedido,
            ),
        )
        
        pedido_id = cursor.lastrowid
        conn.commit()
        
        ip_usuario = request.headers.get(
            "X-Forwarded-For",
            request.remote_addr
        ).split(",")[0].strip()
        
        logger.info(
            "Novo pedido criado\nID=%s | Fornecedor=%s | Responsável=%s | Email=%s | Frete=%s | IP=%s",
            pedido_id,
            fornecedor,
            responsavel,
            email,
            tipo_frete,
            ip_usuario,
        )

    return redirect(url_for("pedidos.dashboard"))
    
# =========================================================
# EDITAR
# =========================================================

@pedidos_bp.route("/editar/<int:id>", methods=["POST"])
@login_required
def editar(id):

    fornecedor = request.form.get("fornecedor", "").strip()
    transportadora = request.form.get("transportadora", "").strip()
    tipo_frete = request.form.get("tipo_frete", "").strip()
    data_pedido = request.form.get("data_pedido", "").strip()
    previsao = request.form.get("previsao_chegada", "").strip()
    responsavel = request.form.get("responsavel", "").strip()
    email = request.form.get("email", "").strip()
    valor = normalizar_valor(request.form.get("valor"))

    # Novos campos — todos opcionais, não alteram nenhuma regra de
    # obrigatoriedade já existente.
    numero_pedido = request.form.get("numero_pedido", "").strip() or None
    vendedor = request.form.get("vendedor", "").strip() or None
    nota_fiscal = request.form.get("nota_fiscal", "").strip() or None
    cte = request.form.get("cte", "").strip() or None
    nova_observacao = request.form.get("nova_observacao", "").strip()

    valor_nota_raw = request.form.get("valor_nota", "").strip()
    valor_nota = normalizar_valor(valor_nota_raw) if valor_nota_raw else None

    valor_frete_raw = request.form.get("valor_frete", "").strip()
    valor_frete = normalizar_valor(valor_frete_raw) if valor_frete_raw else None

    data_embarque_raw = request.form.get("data_embarque", "").strip()
    data_embarque = None
    if data_embarque_raw:
        if not converter_data(data_embarque_raw):
            return jsonify(
                {"success": False, "error": "Data de embarque inválida"}
            )
        data_embarque = data_embarque_raw

    if not fornecedor:
        return jsonify({"success": False, "error": "Fornecedor obrigatório"})

    with conectar() as conn:

        pedido = conn.execute(
            "SELECT * FROM pedidos WHERE id=?",
            (id,),
        ).fetchone()

        if not pedido:
            return jsonify({"success": False})

        observacao = adicionar_observacao(
            pedido["observacao"],
            nova_observacao,
        )

        # Mantém o arquivo já salvo por padrão — só troca se um novo
        # arquivo foi de fato enviado neste request. Sem isso, o campo
        # "arquivo" do formulário de edição era ignorado e a coluna
        # nunca era atualizada, mesmo quando um novo arquivo era
        # selecionado no modal.
        arquivo_nome = pedido["arquivo"]
        arquivo_antigo = pedido["arquivo"]
        arquivo = request.files.get("arquivo")

        if arquivo and arquivo.filename:
            if not arquivo_permitido(arquivo.filename):
                return jsonify(
                    {"success": False, "error": "Tipo de arquivo não permitido"}
                )

            if not mime_permitido(arquivo.mimetype):
                return jsonify(
                    {"success": False, "error": "Tipo de arquivo não permitido"}
                )

            nome_original = secure_filename(arquivo.filename)
            nome = f"{uuid.uuid4().hex[:8]}_{nome_original}"

            pasta = gerar_pasta_upload(UPLOAD_FOLDER)
            caminho = os.path.join(pasta, nome)
            arquivo.save(caminho)

            agora = datetime.now()
            arquivo_nome = f"{agora.strftime('%Y')}/{agora.strftime('%m')}/{nome}"

        conn.execute(
            """
            UPDATE pedidos
            SET
                fornecedor=?,
                transportadora=?,
                tipo_frete=?,
                data_pedido=?,
                previsao_chegada=?,
                valor=?,
                responsavel=?,
                email=?,
                vendedor=?,
                nota_fiscal=?,
                cte=?,
                data_embarque=?,
                observacao=?,
                valor_nota=?,
                valor_frete=?,
                arquivo=?,
                numero_pedido=?
            WHERE id=?
            """,
            (
                fornecedor,
                transportadora,
                tipo_frete,
                data_pedido,
                previsao,
                valor,
                responsavel,
                email,
                vendedor,
                nota_fiscal,
                cte,
                data_embarque,
                observacao,
                valor_nota,
                valor_frete,
                arquivo_nome,
                numero_pedido,
                id,
            ),
        )

        conn.commit()

        # Só remove o arquivo antigo do disco depois do commit ter dado
        # certo, e só quando ele foi de fato substituído — nunca apaga
        # o arquivo atual se nada novo foi enviado.
        if arquivo_nome != arquivo_antigo and arquivo_antigo:
            try:
                os.remove(os.path.join(UPLOAD_FOLDER, arquivo_antigo))
            except OSError as e:
                logger.warning(
                    "Não foi possível remover arquivo antigo | ID=%s | Arquivo=%s | Erro=%s",
                    id, arquivo_antigo, e,
                )

        ip_usuario = request.headers.get(
            "X-Forwarded-For",
            request.remote_addr
        ).split(",")[0].strip()

        logger.info(
            "Pedido editado | ID=%s | Fornecedor=%s | Responsável=%s | IP=%s",
            id,
            fornecedor,
            responsavel,
            ip_usuario,
        )

    return jsonify({"success": True})
    
# =========================================================
# OBTER PEDIDO
# =========================================================

@pedidos_bp.route("/pedido/<int:id>")
@login_required
def obter_pedido(id):
    with conectar() as conn:
        pedido = conn.execute(
            "SELECT * FROM pedidos WHERE id=? AND deletado=0",
            (id,),
        ).fetchone()

    if not pedido:
        return jsonify({"success": False})

    return jsonify(
        {
            "success": True,
            "pedido": dict(pedido),
        }
    )


# =========================================================
# ENTREGAR
# =========================================================

@pedidos_bp.route("/entregar/<int:id>", methods=["POST"])
@login_required
def entregar(id):
    with conectar() as conn:
        pedido = conn.execute(
            "SELECT * FROM pedidos WHERE id=? AND deletado=0",
            (id,),
        ).fetchone()

        if not pedido:
            return jsonify({"success": False})

        pedido = dict(pedido)
        novo = 1 if int(pedido["entregue"] or 0) == 0 else 0

        conn.execute(
            "UPDATE pedidos SET entregue=? WHERE id=?",
            (novo, id),
        )
        conn.commit()

    # ---------------------------------------------------------
    # NOTIFICAÇÃO DE ENTREGA
    # ---------------------------------------------------------

    if novo == 1 and pedido.get("email"):
        try:
            data_entrega = datetime.now().date()

            enviado = email_entregue(
                pedido["email"],
                pedido,
                data_entrega,
            )

            if enviado:
                with conectar() as conn:
                    conn.execute(
                        """
                        UPDATE pedidos
                        SET email_entregue_enviado = 1
                        WHERE id = ?
                        """,
                        (id,),
                    )
                    conn.commit()

        except Exception:
            logger.exception(
                "Erro ao enviar email de entrega | pedido_id=%s",
                id,
            )

    elif novo == 0:
        with conectar() as conn:
            conn.execute(
                """
                UPDATE pedidos
                SET email_entregue_enviado = 0
                WHERE id = ?
                """,
                (id,),
            )
            conn.commit()

    return jsonify({
        "success": True,
        "entregue": bool(novo),
    })


# =========================================================
# APAGAR
# =========================================================

@pedidos_bp.route("/apagar/<int:id>", methods=["POST"])
@login_required
def apagar(id):
    with conectar() as conn:
        pedido = conn.execute(
            "SELECT fornecedor, responsavel FROM pedidos WHERE id=?",
            (id,),
        ).fetchone()

        cursor = conn.execute(
            "UPDATE pedidos SET deletado=1 WHERE id=? AND deletado=0",
            (id,),
        )

        conn.commit()
        sucesso = cursor.rowcount > 0

    if sucesso and pedido:
        logger.warning(
            "Pedido apagado | ID=%s | Fornecedor=%s | Responsável=%s | IP=%s",
            id,
            pedido["fornecedor"],
            pedido["responsavel"],
            request.remote_addr,
        )

    return jsonify({"success": sucesso})


# =========================================================
# LIXEIRA
# =========================================================

@pedidos_bp.route("/lixeira")
@login_required
def lixeira():
    return render_template("lixeira.html", pedidos=obter_pedidos(1))


# =========================================================
# RESTAURAR
# =========================================================

@pedidos_bp.route("/restaurar/<int:id>", methods=["POST"])
@login_required
def restaurar(id):
    with conectar() as conn:
        cursor = conn.execute(
            "UPDATE pedidos SET deletado=0 WHERE id=? AND deletado=1",
            (id,),
        )
        conn.commit()
        sucesso = cursor.rowcount > 0

    return jsonify({"success": sucesso})


# =========================================================
# DOWNLOAD
# =========================================================

@pedidos_bp.route("/uploads/<path:filename>")
@login_required
def uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)
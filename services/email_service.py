
# services/email_service.py
"""Montagem e envio das notificações de pedidos por e-mail."""

import html
import logging
import mimetypes
import os
import re
import smtplib
from datetime import date, datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    EMAIL_REMETENTE,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USER,
)

logger = logging.getLogger(__name__)

EMPRESA_NOME = "Central Nordeste"
EMPRESA_EMAIL = "compras@centralnordeste.com.br"

TEMAS = {
    "atrasado": {
        "principal": "#b91c1c",
        "fundo": "#fef2f2",
        "texto": "#991b1b",
        "subtexto": "#fecaca",
    },
    "alerta": {
        "principal": "#b45309",
        "fundo": "#fffbeb",
        "texto": "#92400e",
        "subtexto": "#fde68a",
    },
    "entregue": {
        "principal": "#15803d",
        "fundo": "#f0fdf4",
        "texto": "#166534",
        "subtexto": "#bbf7d0",
    },
}

COR_TEXTO = "#0f172a"
COR_SECUNDARIA = "#64748b"
COR_TERCIARIA = "#94a3b8"
COR_BORDA = "#e2e8f0"
COR_CARD = "#f8fafc"

_REGEX_EMAIL = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}\\Z"
)


def _esc(valor) -> str:
    return html.escape(str(valor), quote=True) if valor is not None else ""


def _destinatario_seguro(destinatario: str) -> bool:
    if not destinatario:
        return False

    destinatario = str(destinatario).strip()

    if "\r" in destinatario or "\n" in destinatario:
        return False

    return "@" in destinatario


def _sem_quebra_de_linha(valor) -> str:
    return str(valor).replace("\\r", " ").replace("\\n", " ")


def _formatar_valor(valor) -> str:
    if valor is None:
        return ""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        logger.warning("Valor inválido para moeda: %r", valor)
        return ""
    bruto = f"{numero:,.2f}"
    bruto = bruto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {bruto}"


def _formatar_data(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")

    texto = str(valor).strip()
    for formato in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return texto


def _preheader(pedido: dict, situacao: str) -> str:
    partes = ["Pedido"]
    if pedido.get("numero_pedido"):
        partes.append(f"#{pedido['numero_pedido']}")
    if pedido.get("fornecedor"):
        partes.append(f"de {pedido['fornecedor']}")
    partes.append(situacao)
    return " ".join(partes) + "."


def _campo(titulo: str, valor, largura: str = "48%") -> str:
    if valor in (None, ""):
        return ""
    return f"""
    <td width="{largura}" style="padding:0 0 18px;vertical-align:top;">
        <div style="font-size:10px;line-height:14px;color:{COR_TERCIARIA};
                    font-weight:800;letter-spacing:.6px;text-transform:uppercase;
                    margin-bottom:5px;">{_esc(titulo)}</div>
        <div style="font-size:14px;line-height:20px;color:{COR_TEXTO};
                    font-weight:600;word-break:break-word;">{_esc(valor)}</div>
    </td>
    """


def _grid_campos(campos: list[tuple[str, object]]) -> str:
    validos = [(t, v) for t, v in campos if v not in (None, "")]
    if not validos:
        return ""

    linhas = []
    for i in range(0, len(validos), 2):
        esquerda = _campo(*validos[i])
        direita = _campo(*validos[i + 1]) if i + 1 < len(validos) else ""
        linhas.append(
            f"""
            <tr>
                {esquerda}
                <td width="4%" style="font-size:1px;line-height:1px;">&nbsp;</td>
                {direita}
            </tr>
            """
        )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(linhas)}</table>'


def _secao(titulo: str, descricao: str = "") -> str:
    descricao_html = (
        f'<div style="margin-top:3px;color:{COR_SECUNDARIA};font-size:12px;'
        f'line-height:18px;">{_esc(descricao)}</div>'
        if descricao
        else ""
    )
    return f"""
    <tr>
        <td style="padding:8px 0 16px;">
            <div style="color:{COR_TEXTO};font-size:13px;line-height:18px;
                        font-weight:800;letter-spacing:.2px;">{_esc(titulo)}</div>
            {descricao_html}
        </td>
    </tr>
    """


def _card_destaque(titulo: str, valor: str, descricao: str, tema: dict) -> str:
    valor_html = (
        f'<div style="color:{COR_TEXTO};font-size:24px;line-height:30px;'
        f'font-weight:800;margin-top:3px;">{_esc(valor)}</div>'
        if valor else ""
    )
    descricao_html = (
        f'<div style="color:{COR_SECUNDARIA};font-size:12px;line-height:18px;'
        f'margin-top:4px;">{_esc(descricao)}</div>'
        if descricao else ""
    )
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="margin:0 0 24px;">
        <tr>
            <td style="background:{tema['fundo']};
                       border:1px solid {tema['principal']}22;
                       border-left:4px solid {tema['principal']};
                       border-radius:8px;padding:16px 18px;">
                <div style="color:{tema['texto']};font-size:10px;line-height:14px;
                            font-weight:800;letter-spacing:.7px;
                            text-transform:uppercase;">{_esc(titulo)}</div>
                {valor_html}
                {descricao_html}
            </td>
        </tr>
    </table>
    """


def _timeline(etapas: list[tuple[str, str, str]]) -> str:
    validas = [etapa for etapa in etapas if etapa[1]]
    if len(validas) < 2:
        return ""

    largura = f"{100 // len(validas)}%"
    celulas = []
    for rotulo, data, cor in validas:
        celulas.append(
            f"""
            <td width="{largura}" align="center" style="padding:0 3px;vertical-align:top;">
                <div style="height:3px;background:{cor};margin-bottom:9px;"></div>
                <div style="color:{cor};font-size:16px;line-height:16px;font-weight:700;">&#9679;</div>
                <div style="color:{COR_SECUNDARIA};font-size:10px;line-height:15px;margin-top:4px;">
                    {_esc(rotulo)}
                </div>
                <div style="color:{COR_TEXTO};font-size:12px;line-height:17px;font-weight:700;">
                    {_esc(data)}
                </div>
            </td>
            """
        )
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="margin:0 0 26px;">
        <tr>{"".join(celulas)}</tr>
    </table>
    """


def _bloco_valores(pedido: dict) -> str:
    valores = [
        ("Valor do pedido", _formatar_valor(pedido.get("valor"))),
        ("Valor da NF", _formatar_valor(pedido.get("valor_nota"))),
        ("Valor do frete", _formatar_valor(pedido.get("valor_frete"))),
    ]
    valores = [(t, v) for t, v in valores if v]
    if not valores:
        return ""

    celulas = []
    for i, (titulo, valor) in enumerate(valores):
        borda = f"border-right:1px solid {COR_BORDA};" if i < len(valores) - 1 else ""
        celulas.append(
            f"""
            <td width="{100 // len(valores)}%" style="padding:14px 12px;vertical-align:top;{borda}">
                <div style="color:{COR_TERCIARIA};font-size:10px;line-height:14px;
                            font-weight:800;letter-spacing:.5px;text-transform:uppercase;
                            margin-bottom:5px;">{_esc(titulo)}</div>
                <div style="color:{COR_TEXTO};font-size:15px;line-height:20px;font-weight:800;">
                    {_esc(valor)}
                </div>
            </td>
            """
        )
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="margin:0 0 24px;border:1px solid {COR_BORDA};border-radius:8px;background:#ffffff;">
        <tr>{"".join(celulas)}</tr>
    </table>
    """


def _observacao(valor) -> str:
    if valor in (None, ""):
        return ""

    observacoes = [
        linha.strip()
        for linha in str(valor).splitlines()
        if linha.strip()
    ]

    if not observacoes:
        return ""

    conteudo = "<br>".join(_esc(linha) for linha in observacoes)

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="margin:0 0 24px;">
        <tr>
            <td style="background:{COR_CARD};border:1px solid {COR_BORDA};
                       border-radius:8px;padding:14px 16px;">
                <div style="color:{COR_TERCIARIA};font-size:10px;line-height:14px;
                            font-weight:800;letter-spacing:.6px;text-transform:uppercase;
                            margin-bottom:5px;">Observações</div>
                <div style="color:{COR_SECUNDARIA};font-size:13px;line-height:20px;">
                    {conteudo}
                </div>
            </td>
        </tr>
    </table>
    """


def _anexo_nome(pedido: dict) -> str | None:
    return pedido.get("_anexo_nome") or (
        os.path.basename(pedido["arquivo"])
        if pedido.get("arquivo")
        else None
    )


def _bloco_anexo(pedido: dict) -> str:
    nome = _anexo_nome(pedido)
    if not nome:
        return ""
    return (
        f'<div style="color:{COR_SECUNDARIA};font-size:11px;line-height:17px;'
        f'margin:0 0 20px;">Documento anexado: <strong>{_esc(nome)}</strong></div>'
    )


def _template_html(
    *,
    titulo: str,
    subtitulo: str,
    tema: dict,
    corpo: str,
    badge: str,
    link: str | None,
    texto_botao: str,
    preheader: str,
) -> str:
    botao = ""
    if link:
        botao = f"""
        <tr>
            <td style="padding:4px 32px 28px;">
                <a href="{_esc(link)}"
                   style="display:inline-block;background:{tema['principal']};
                          color:#ffffff;text-decoration:none;padding:13px 24px;
                          border-radius:7px;font-size:13px;line-height:18px;font-weight:800;">
                    {_esc(texto_botao)}
                </a>
            </td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<style>
body {{ margin:0!important; padding:0!important; width:100%!important; background:#f1f5f9;
       -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
table {{ border-spacing:0; }}
@media screen and (max-width:640px) {{
    .email-container {{ width:100%!important; border-radius:0!important; }}
    .email-padding {{ padding-left:20px!important; padding-right:20px!important; }}
}}
</style>
</head>
<body>
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;">
    {_esc(preheader)}
</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#f1f5f9;padding:28px 0;">
<tr><td align="center">
<table role="presentation" class="email-container" width="620" cellpadding="0" cellspacing="0"
       style="width:100%;max-width:620px;background:#ffffff;border:1px solid {COR_BORDA};
              border-radius:12px;overflow:hidden;">
    <tr>
        <td class="email-padding" style="padding:20px 32px;background:#ffffff;border-bottom:1px solid {COR_BORDA};">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                <td><div style="color:{COR_TEXTO};font-size:15px;line-height:20px;font-weight:800;
                                letter-spacing:.4px;">{_esc(EMPRESA_NOME.upper())}</div></td>
                <td align="right"><div style="color:{COR_SECUNDARIA};font-size:11px;line-height:16px;font-weight:600;">
                    Sistema de Pedidos
                </div></td>
            </tr></table>
        </td>
    </tr>
    <tr>
        <td class="email-padding" style="padding:24px 32px;background:{tema['principal']};">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                <td valign="middle">
                    <div style="color:#ffffff;font-size:21px;line-height:27px;font-weight:800;">{_esc(titulo)}</div>
                    <div style="color:{tema['subtexto']};font-size:13px;line-height:19px;margin-top:3px;">
                        {_esc(subtitulo)}
                    </div>
                </td>
                <td width="1" align="right" valign="middle">
                    <div style="display:inline-block;background:#ffffff;color:{tema['principal']};
                                border-radius:20px;padding:6px 12px;white-space:nowrap;
                                font-size:10px;line-height:14px;font-weight:800;letter-spacing:.4px;">
                        {_esc(badge)}
                    </div>
                </td>
            </tr></table>
        </td>
    </tr>
    <tr>
        <td class="email-padding" style="padding:28px 32px 4px;color:{COR_TEXTO};
                                         font-family:Arial,Helvetica,sans-serif;">
            {corpo}
        </td>
    </tr>
    {botao}
    <tr>
        <td class="email-padding" style="padding:18px 32px;background:{COR_CARD};border-top:1px solid {COR_BORDA};">
            <div style="color:{COR_TERCIARIA};font-size:10px;line-height:16px;">
                {_esc(EMPRESA_NOME)} &middot; {_esc(EMPRESA_EMAIL)} &middot; E-mail automático, não responda.
            </div>
            <div style="color:{COR_TERCIARIA};font-size:10px;line-height:16px;margin-top:2px;">
                Enviado em {_esc(datetime.now().strftime("%d/%m/%Y %H:%M"))}.
            </div>
        </td>
    </tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def criar_conexao() -> smtplib.SMTP:
    smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
    smtp.ehlo()
    if SMTP_USE_TLS:
        smtp.starttls()
        smtp.ehlo()
    smtp.login(SMTP_USER, SMTP_PASSWORD)
    return smtp


def _anexar_arquivo(
    mensagem: MIMEMultipart,
    anexo_path: str,
    anexo_nome: str | None = None,
) -> bool:
    nome = anexo_nome or os.path.basename(anexo_path)
    try:
        with open(anexo_path, "rb") as arquivo:
            conteudo = arquivo.read()
    except OSError as exc:
        logger.error("Não foi possível ler anexo '%s': %s", anexo_path, exc)
        return False

    mime, _ = mimetypes.guess_type(nome)
    subtype = mime.split("/", 1)[1] if mime else "octet-stream"
    parte = MIMEApplication(conteudo, _subtype=subtype)
    parte.add_header("Content-Disposition", "attachment", filename=nome)
    mensagem.attach(parte)
    return True


def enviar_email(
    destinatario: str,
    assunto: str,
    html_corpo: str,
    *,
    texto_corpo: str | None = None,
    anexo_path: str | None = None,
    anexo_nome: str | None = None,
) -> bool:
    if not _destinatario_seguro(destinatario):
        logger.error("Destinatário inválido: %r", destinatario)
        return False

    smtp = None
    destinatario = destinatario.strip()

    try:
        mensagem = MIMEMultipart("mixed")
        mensagem["From"] = EMAIL_REMETENTE
        mensagem["To"] = destinatario
        mensagem["Subject"] = _sem_quebra_de_linha(assunto)

        alternativa = MIMEMultipart("alternative")
        if texto_corpo:
            alternativa.attach(MIMEText(texto_corpo, "plain", "utf-8"))
        alternativa.attach(MIMEText(html_corpo, "html", "utf-8"))
        mensagem.attach(alternativa)

        if anexo_path:
            _anexar_arquivo(mensagem, anexo_path, anexo_nome)

        smtp = criar_conexao()
        smtp.sendmail(EMAIL_REMETENTE, destinatario, mensagem.as_string())
        logger.info("E-mail enviado para %s: %s", destinatario, assunto)
        return True
    except Exception:
        logger.exception("Erro ao enviar e-mail para %s", destinatario)
        return False
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                logger.debug("Falha ao encerrar SMTP.", exc_info=True)


def _texto_alternativo(assunto: str, pedido: dict, extras: list[str]) -> str:
    linhas = [
        assunto,
        "",
        f"Pedido: #{pedido['numero_pedido']}" if pedido.get("numero_pedido") else "Pedido: não informado",
        f"Fornecedor: {pedido['fornecedor']}" if pedido.get("fornecedor") else "Fornecedor: não informado",
        f"Responsável: {pedido['responsavel']}" if pedido.get("responsavel") else "Responsável: não informado",
        f"Data do pedido: {_formatar_data(pedido['data_pedido'])}" if pedido.get("data_pedido") else None,
        f"Previsão de entrega: {_formatar_data(pedido['previsao_chegada'])}" if pedido.get("previsao_chegada") else None,
        f"Valor: {_formatar_valor(pedido['valor'])}" if pedido.get("valor") is not None else None,
    ]
    if pedido.get("observacao"):
        linhas.extend(["", "Observações:"])
        linhas.extend(
            linha.strip()
            for linha in str(pedido["observacao"]).splitlines()
            if linha.strip()
        )

    linhas.extend([""] + extras)
    return "\\n".join(linha for linha in linhas if linha is not None)


def _identificacao(pedido: dict) -> str:
    partes = []
    if pedido.get("numero_pedido"):
        partes.append(f"Pedido #{pedido['numero_pedido']}")
    if pedido.get("fornecedor"):
        partes.append(f"Fornecedor: {pedido['fornecedor']}")
    return " · ".join(partes) or "Atualização de pedido"


def _resumo(pedido: dict, incluir_vendedor: bool) -> str:
    campos = [
        ("Nº do pedido", f"#{pedido['numero_pedido']}" if pedido.get("numero_pedido") else None),
        ("Fornecedor", pedido.get("fornecedor")),
        ("Responsável", pedido.get("responsavel")),
        ("Data do pedido", _formatar_data(pedido.get("data_pedido"))),
        ("Previsão de entrega", _formatar_data(pedido.get("previsao_chegada"))),
        ("Valor do pedido", _formatar_valor(pedido.get("valor"))),
    ]
    if incluir_vendedor:
        campos.append(("Vendedor", pedido.get("vendedor")))
    return _grid_campos(campos)


def _logistica(pedido: dict) -> str:
    return _grid_campos([
        ("Transportadora", pedido.get("transportadora")),
        ("Tipo de frete", pedido.get("tipo_frete")),
        ("Data de embarque", _formatar_data(pedido.get("data_embarque"))),
    ])


def _documentos(pedido: dict) -> str:
    return _grid_campos([
        ("Nota fiscal", pedido.get("nota_fiscal")),
        ("CTe", pedido.get("cte")),
    ])


def email_atrasado(
    destinatario: str,
    pedido: dict,
    dias_atraso: int,
) -> bool:
    tema = TEMAS["atrasado"]
    numero = pedido.get("numero_pedido")
    previsao = _formatar_data(pedido.get("previsao_chegada"))
    assunto = f"Pedido #{numero} em atraso" if numero else "Pedido em atraso"

    if previsao:
        descricao = f"A previsão original de entrega era {previsao}."
    else:
        descricao = "A previsão original de entrega foi ultrapassada."

    corpo = f"""
    <p style="margin:0 0 22px;color:{COR_SECUNDARIA};font-size:14px;line-height:21px;">
        O pedido abaixo ultrapassou a data prevista de entrega e precisa de acompanhamento.
    </p>
    {_card_destaque("Atenção necessária", f"{dias_atraso} dias de atraso", descricao, tema)}
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        {_secao("Resumo do pedido")}
        <tr><td>{_resumo(pedido, True)}</td></tr>
        {_secao("Linha do tempo", "Principais datas registradas para o pedido.")}
        <tr><td>{_timeline([
            ("Pedido criado", _formatar_data(pedido.get("data_pedido")), "#16a34a"),
            ("Embarque", _formatar_data(pedido.get("data_embarque")), "#16a34a"),
            ("Previsão", previsao, "#cbd5e1"),
            ("Hoje", _formatar_data(datetime.now().date()), tema["principal"]),
        ])}</td></tr>
        {_secao("Logística")}
        <tr><td>{_logistica(pedido)}</td></tr>
        {_secao("Documentação")}
        <tr><td>{_documentos(pedido)}</td></tr>
    </table>
    {_bloco_valores(pedido)}
    {_observacao(pedido.get("observacao"))}
    {_bloco_anexo(pedido)}
    """

    html_corpo = _template_html(
        titulo="Pedido em atraso",
        subtitulo=_identificacao(pedido),
        tema=tema,
        corpo=corpo,
        badge=f"{dias_atraso} DIAS DE ATRASO",
        link=pedido.get("_link_sistema"),
        texto_botao="Abrir pedido no sistema",
        preheader=_preheader(pedido, f"está {dias_atraso} dias atrasado"),
    )

    texto = _texto_alternativo(
        assunto,
        pedido,
        [f"Situação: {dias_atraso} dias de atraso.", f"Previsão: {previsao}" if previsao else ""],
    )

    return enviar_email(
        destinatario,
        assunto,
        html_corpo,
        texto_corpo=texto,
        anexo_path=pedido.get("arquivo"),
        anexo_nome=_anexo_nome(pedido),
    )


def email_alerta(
    destinatario: str,
    pedido: dict,
    dias_restantes: int,
) -> bool:
    tema = TEMAS["alerta"]
    numero = pedido.get("numero_pedido")
    previsao = _formatar_data(pedido.get("previsao_chegada"))
    assunto = (
        f"Pedido #{numero} próximo do vencimento"
        if numero
        else "Pedido próximo do vencimento"
    )

    if dias_restantes == 0:
        descricao = "A entrega está prevista para hoje."
        valor = "Hoje"
        badge = "ENTREGA HOJE"
        situacao = "vence hoje"
    elif dias_restantes == 1:
        descricao = "A entrega está prevista para amanhã."
        valor = "1 dia restante"
        badge = "1 DIA RESTANTE"
        situacao = "vence amanhã"
    else:
        descricao = f"A entrega está prevista para daqui a {dias_restantes} dias."
        valor = f"{dias_restantes} dias restantes"
        badge = f"{dias_restantes} DIAS RESTANTES"
        situacao = f"vence em {dias_restantes} dias"

    corpo = f"""
    <p style="margin:0 0 22px;color:{COR_SECUNDARIA};font-size:14px;line-height:21px;">
        Este pedido está próximo da data prevista de entrega. Confira abaixo as principais informações.
    </p>
    {_card_destaque("Prazo de entrega", valor, f"{descricao} " + (f"Previsão: {previsao}." if previsao else ""), tema)}
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        {_secao("Resumo do pedido")}
        <tr><td>{_resumo(pedido, False)}</td></tr>
        {_secao("Linha do tempo", "Acompanhe o prazo e o andamento logístico.")}
        <tr><td>{_timeline([
            ("Pedido criado", _formatar_data(pedido.get("data_pedido")), "#16a34a"),
            ("Embarque", _formatar_data(pedido.get("data_embarque")), "#16a34a"),
            ("Hoje", _formatar_data(datetime.now().date()), tema["principal"]),
            ("Previsão", previsao, "#cbd5e1"),
        ])}</td></tr>
        {_secao("Logística")}
        <tr><td>{_logistica(pedido)}</td></tr>
    </table>
    {_observacao(pedido.get("observacao"))}
    """

    html_corpo = _template_html(
        titulo="Alerta de pedido",
        subtitulo=_identificacao(pedido),
        tema=tema,
        corpo=corpo,
        badge=badge,
        link=pedido.get("_link_sistema"),
        texto_botao="Abrir pedido no sistema",
        preheader=_preheader(pedido, situacao),
    )

    texto = _texto_alternativo(
        assunto,
        pedido,
        [f"Situação: {descricao}", f"Previsão: {previsao}" if previsao else ""],
    )

    return enviar_email(destinatario, assunto, html_corpo, texto_corpo=texto)


def email_entregue(
    destinatario: str,
    pedido: dict,
    data_entrega,
) -> bool:
    tema = TEMAS["entregue"]
    numero = pedido.get("numero_pedido")
    assunto = f"Pedido #{numero} entregue" if numero else "Pedido entregue"

    corpo = f"""
    <p style="margin:0 0 22px;color:{COR_SECUNDARIA};font-size:14px;line-height:21px;">
        O pedido foi marcado como entregue. Abaixo está o resumo completo para registro e acompanhamento.
    </p>
    {_card_destaque(
        "Entrega concluída",
        _formatar_data(data_entrega),
        "Pedido finalizado no sistema.",
        tema,
    )}
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        {_secao("Resumo do pedido")}
        <tr><td>{_resumo(pedido, True)}</td></tr>
        {_secao("Linha do tempo", "Histórico das principais etapas do pedido.")}
        <tr><td>{_timeline([
            ("Pedido criado", _formatar_data(pedido.get("data_pedido")), "#16a34a"),
            ("Embarque", _formatar_data(pedido.get("data_embarque")), "#16a34a"),
            ("Entregue", _formatar_data(data_entrega), tema["principal"]),
        ])}</td></tr>
        {_secao("Logística")}
        <tr><td>{_logistica(pedido)}</td></tr>
        {_secao("Documentação")}
        <tr><td>{_documentos(pedido)}</td></tr>
    </table>
    {_bloco_valores(pedido)}
    {_observacao(pedido.get("observacao"))}
    {_bloco_anexo(pedido)}
    """

    html_corpo = _template_html(
        titulo="Pedido entregue",
        subtitulo=_identificacao(pedido),
        tema=tema,
        corpo=corpo,
        badge="ENTREGUE",
        link=pedido.get("_link_sistema"),
        texto_botao="Abrir pedido no sistema",
        preheader=_preheader(pedido, "foi entregue"),
    )

    texto = _texto_alternativo(
        assunto,
        pedido,
        [
            f"Situação: entregue em {_formatar_data(data_entrega)}.",
            f"Nota fiscal: {pedido['nota_fiscal']}" if pedido.get("nota_fiscal") else "",
            f"CTe: {pedido['cte']}" if pedido.get("cte") else "",
        ],
    )

    return enviar_email(
        destinatario,
        assunto,
        html_corpo,
        texto_corpo=texto,
        anexo_path=pedido.get("arquivo"),
        anexo_nome=_anexo_nome(pedido),
    )
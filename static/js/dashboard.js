const csrfMeta = document.querySelector('meta[name="csrf-token"]');
if (!csrfMeta) throw new Error("Meta tag do CSRF não encontrada.");
const csrfToken = csrfMeta.content;

function abrirModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.style.display = "flex";
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
}

function fecharModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.style.display = "none";
    modal.setAttribute("aria-hidden", "true");
    if (!document.querySelector('.modal[aria-hidden="false"]')) document.body.classList.remove("modal-open");
}

function abrirModalNovo() {
    const form = document.getElementById("formNovo");
    if (form) form.reset();
    calcularPercentualFrete("valor_nota_novo", "valor_frete_novo", "percentual_frete_novo");
    abrirModal("modalPedidoNovo");
    document.getElementById("numero_pedido_novo")?.focus();
}

function esc(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function formatMoney(value) {
    const n = Number(value || 0);
    return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function statusLabel(pedido) {
    if (Number(pedido.entregue) === 1) return ["Entregue", "entregue"];
    const previsao = parseDate(pedido.previsao_chegada);
    if (previsao) {
        const diff = Math.ceil((previsao - new Date()) / 86400000);
        if (diff < 0) return ["Atrasado", "atrasado"];
        if (diff <= 3) return ["Próximo do prazo", "proximo"];
    }
    if (pedido.data_embarque) return ["Em trânsito", "transito"];
    const dataPedido = parseDate(pedido.data_pedido);
    const hoje = new Date();
    if (dataPedido && dataPedido.toDateString() === hoje.toDateString()) return ["Novo", "novo"];
    return ["Aguardando envio", "aguardando"];
}

function parseDate(value) {
    if (!value) return null;
    const parts = String(value).split("-");
    if (parts.length !== 3) return null;
    const date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return Number.isNaN(date.getTime()) ? null : date;
}

async function visualizarPedido(id) {
    const modal = document.getElementById("modalVisualizar");
    const content = document.getElementById("visualizarConteudo");
    const anexoBtnReset = document.getElementById("btnVisualizarAnexo");
    if (anexoBtnReset) {
        anexoBtnReset.style.display = "none";
        anexoBtnReset.onclick = null;
    }
    abrirModal("modalVisualizar");
    content.innerHTML = '<div class="loading-state">Carregando informações...</div>';
    try {
        const response = await fetch(`/pedido/${id}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!data.success) throw new Error("Pedido não encontrado");
        const p = data.pedido;
        const [status, statusKey] = statusLabel(p);
        document.getElementById("visualizarTitulo").textContent = `#${p.numero_pedido || p.id}`;
        const arquivoUrl = p.arquivo ? `/uploads/${encodeURI(p.arquivo)}` : null;
        const arquivo = arquivoUrl
            ? `<a class="detail-file" target="_blank" rel="noopener noreferrer" href="${arquivoUrl}">Abrir arquivo</a>`
            : '<span class="muted">Nenhum arquivo anexado</span>';
        const anexoBtn = document.getElementById("btnVisualizarAnexo");
        if (anexoBtn) {
            if (arquivoUrl) {
                anexoBtn.style.display = "";
                anexoBtn.onclick = () => window.open(arquivoUrl, "_blank", "noopener,noreferrer");
            } else {
                anexoBtn.style.display = "none";
                anexoBtn.onclick = null;
            }
        }
        content.innerHTML = `
            <div class="detail-hero">
                <div><span class="detail-caption">Situação atual</span><span class="status-badge status-${statusKey}">${esc(status)}</span></div>
                <div class="detail-hero-value"><span class="detail-caption">Valor do pedido</span><strong>${formatMoney(p.valor)}</strong></div>
            </div>
            <div class="detail-grid">
                <section class="detail-section"><h3>Identificação</h3><dl>
                    <div><dt>Fornecedor</dt><dd>${esc(p.fornecedor || "-")}</dd></div>
                    <div><dt>Vendedor</dt><dd>${esc(p.vendedor || "-")}</dd></div>
                    <div><dt>Responsável</dt><dd>${esc(p.responsavel || "-")}</dd></div>
                    <div><dt>E-mail</dt><dd>${esc(p.email || "-")}</dd></div>
                </dl></section>
                <section class="detail-section"><h3>Logística e prazo</h3><dl>
                    <div><dt>Transportadora</dt><dd>${esc(p.transportadora || "-")}</dd></div>
                    <div><dt>Tipo de frete</dt><dd>${esc(p.tipo_frete || "-")}</dd></div>
                    <div><dt>Data do pedido</dt><dd>${esc(p.data_pedido || "-")}</dd></div>
                    <div><dt>Previsão</dt><dd>${esc(p.previsao_chegada || "-")}</dd></div>
                    <div><dt>Embarque</dt><dd>${esc(p.data_embarque || "Ainda não embarcado")}</dd></div>
                </dl></section>
                <section class="detail-section"><h3>Financeiro</h3><dl>
                    <div><dt>Valor total</dt><dd>${formatMoney(p.valor)}</dd></div>
                    <div><dt>Valor da nota</dt><dd>${p.valor_nota == null ? "-" : formatMoney(p.valor_nota)}</dd></div>
                    <div><dt>Valor do frete</dt><dd>${p.valor_frete == null ? "-" : formatMoney(p.valor_frete)}</dd></div>
                    <div><dt>% do frete</dt><dd>${p.valor_nota > 0 && p.valor_frete != null ? ((p.valor_frete / p.valor_nota) * 100).toFixed(2).replace('.', ',') + '%' : '-'}</dd></div>
                </dl></section>
                <section class="detail-section"><h3>Documentação</h3><dl>
                    <div><dt>Nota fiscal</dt><dd>${esc(p.nota_fiscal || "-")}</dd></div>
                    <div><dt>CTE</dt><dd>${esc(p.cte || "-")}</dd></div>
                    <div><dt>Arquivo</dt><dd>${arquivo}</dd></div>
                </dl></section>
                <section class="detail-section detail-wide"><h3>Observações</h3><p class="detail-note">${esc(p.observacao || "Nenhuma observação registrada.")}</p></section>
            </div>`;
    } catch (error) {
        console.error(error);
        content.innerHTML = '<div class="empty-state compact"><strong>Não foi possível carregar o pedido.</strong><span>Tente novamente.</span></div>';
    }
}

async function editarPedido(id) {
    try {
        const response = await fetch(`/pedido/${id}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!data.success) throw new Error("Pedido não encontrado");
        const p = data.pedido;
        const fields = ["numero_pedido", "fornecedor", "transportadora", "tipo_frete", "data_pedido", "previsao_chegada", "valor", "responsavel", "email", "vendedor", "nota_fiscal", "cte", "data_embarque", "observacao", "valor_nota", "valor_frete"];
        fields.forEach(name => {
            const field = document.getElementById(name);
            if (field) field.value = p[name] ?? "";
        });
        calcularPercentualFrete("valor_nota", "valor_frete", "percentual_frete");
        document.getElementById("formEditar").action = `/editar/${id}`;
        abrirModal("modalEditar");
        document.getElementById("fornecedor")?.focus();
    } catch (error) {
        console.error(error);
        alert("Erro ao carregar os dados do pedido.");
    }
}

async function toggleEntrega(id, checkbox) {
    const anterior = !checkbox.checked;
    checkbox.disabled = true;
    try {
        const response = await fetch(`/entregar/${id}`, { method: "POST", headers: { "X-CSRF-Token": csrfToken } });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!data.success) { checkbox.checked = anterior; alert("Não foi possível atualizar o status de entrega."); return; }
        location.reload();
    } catch (error) {
        console.error(error);
        checkbox.checked = anterior;
        alert("Erro de comunicação com o servidor. Tente novamente.");
    } finally { checkbox.disabled = false; }
}

async function apagarPedido(id, botao) {
    if (!confirm("Deseja mover este pedido para a lixeira?")) return;
    if (botao.disabled) return;
    botao.disabled = true;
    try {
        const response = await fetch(`/apagar/${id}`, { method: "POST", headers: { "X-CSRF-Token": csrfToken } });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!data.success) { alert("Não foi possível excluir o pedido."); botao.disabled = false; return; }
        location.reload();
    } catch (error) {
        console.error(error);
        botao.disabled = false;
        alert("Erro de comunicação com o servidor. Tente novamente.");
    }
}

function converterParaNumero(valor) {
    if (!valor) return 0;
    valor = String(valor).trim();
    if (valor.includes(",") && valor.includes(".")) valor = valor.replace(/\./g, "").replace(",", ".");
    else if (valor.includes(",")) valor = valor.replace(",", ".");
    const numero = parseFloat(valor);
    return Number.isNaN(numero) ? 0 : numero;
}

function calcularPercentualFrete(valorNotaId, freteId, percentualId) {
    const nota = document.getElementById(valorNotaId);
    const frete = document.getElementById(freteId);
    const percentual = document.getElementById(percentualId);
    if (!nota || !frete || !percentual) return;
    const valorNota = converterParaNumero(nota.value);
    const valorFrete = converterParaNumero(frete.value);
    const resultado = valorNota > 0 ? (valorFrete / valorNota) * 100 : 0;
    percentual.value = `${resultado.toFixed(2).replace('.', ',')}%`;
}

document.getElementById("formEditar")?.addEventListener("submit", async function (e) {
    e.preventDefault();
    const form = this;
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Salvando...";
    try {
        const response = await fetch(form.action, { method: "POST", headers: { "X-CSRF-Token": csrfToken }, body: new FormData(form) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!data.success) { alert(data.error || "Não foi possível atualizar o pedido."); return; }
        fecharModal("modalEditar");
        location.reload();
    } catch (error) {
        console.error(error);
        alert("Erro ao salvar as alterações.");
    } finally {
        submit.disabled = false;
        submit.textContent = "Salvar alterações";
    }
});

document.addEventListener("click", event => {
    const target = event.target;
    if (target.classList.contains("modal")) fecharModal(target.id);
});

document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        document.querySelectorAll('.modal[aria-hidden="false"]').forEach(modal => fecharModal(modal.id));
    }
});
const csrfMeta = document.querySelector('meta[name="csrf-token"]');

if (!csrfMeta) {
    throw new Error("Meta tag do CSRF não encontrada.");
}

const csrfToken = csrfMeta.content;

async function restaurarPedido(id, botao) {

    if (!confirm("Deseja restaurar este pedido?")) {
        return;
    }

    if (botao.disabled) {
        return;
    }
    botao.disabled = true;

    try {

        const response = await fetch(`/restaurar/${id}`, {
			method: "POST",
			headers: {
				"X-CSRF-Token": csrfToken
				}
		});

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            // Referência direta ao elemento que disparou o evento —
            // elimina a ambiguidade de buscar por substring no onclick.
            botao.closest("tr").remove();
            return;
        }

        alert("Erro ao restaurar pedido");
        botao.disabled = false;

    } catch (e) {
        alert("Erro ao restaurar pedido");
        botao.disabled = false;
    }

}
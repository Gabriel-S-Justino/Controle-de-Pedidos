document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("cadastro-form");
    const btnSubmit = document.getElementById("cadastro-submit");

    form.addEventListener("submit", function () {
        if (form.checkValidity()) {
            btnSubmit.disabled = true;
            btnSubmit.textContent = "Criando conta...";
        }
    });

    window.addEventListener("pageshow", function (evento) {
        if (evento.persisted) {
            btnSubmit.disabled = false;
            btnSubmit.textContent = "Criar Conta";
        }
    });
});
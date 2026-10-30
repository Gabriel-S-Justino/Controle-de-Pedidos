document.addEventListener("DOMContentLoaded", function () {
            const form = document.getElementById("login-form");
            const btnSubmit = document.getElementById("login-submit");
            const senhaInput = document.getElementById("senha");
            const btnToggle = document.getElementById("toggle-password");
            const iconClosed = document.getElementById("icon-eye-closed");
            const iconOpen = document.getElementById("icon-eye-open");

            // Lógica de visualização de senha
            btnToggle.addEventListener("click", function () {
                const type = senhaInput.getAttribute("type") === "password" ? "text" : "password";
                senhaInput.setAttribute("type", type);
                
                if (type === "text") {
                    iconClosed.style.display = "none";
                    iconOpen.style.display = "block";
                    btnToggle.setAttribute("aria-label", "Ocultar senha");
                } else {
                    iconClosed.style.display = "block";
                    iconOpen.style.display = "none";
                    btnToggle.setAttribute("aria-label", "Mostrar senha");
                }
            });

            // =====================================================
            // Bloqueio temporário: contador regressivo
            // =====================================================
            // O backend é a fonte da verdade: o template entrega quantos
            // segundos FALTAM (calculado a partir de `bloqueado_ate`). Aqui
            // só convertemos isso em um instante-limite local e exibimos.
            // Como o valor vem recalculado a cada carregamento, um F5 nunca
            // reinicia os 15 minutos. Se o relógio do navegador divergir,
            // o pior caso é liberar o formulário um pouco antes/depois — o
            // servidor continua recusando qualquer tentativa durante o
            // bloqueio real e devolve o tempo restante atualizado.
            const lockoutMsg = document.getElementById("lockout-msg");
            const lockoutCountdown = document.getElementById("lockout-countdown");
            let lockoutDeadline = null; // epoch (ms) em que o bloqueio termina
            let lockoutTimer = null;

            function formatarTempo(totalSegundos) {
                const min = Math.floor(totalSegundos / 60);
                const seg = totalSegundos % 60;
                return String(min).padStart(2, "0") + ":" + String(seg).padStart(2, "0");
            }

            function bloqueioAtivo() {
                return lockoutDeadline !== null && Date.now() < lockoutDeadline;
            }

            function encerrarBloqueio() {
                clearTimeout(lockoutTimer);
                lockoutTimer = null;
                lockoutDeadline = null;

                const caixa = lockoutMsg ? lockoutMsg.closest(".messages") : null;
                if (caixa) caixa.remove();

                btnSubmit.disabled = false;
                btnSubmit.textContent = "Entrar";
                senhaInput.focus();
            }

            function atualizarContador() {
                const restanteMs = lockoutDeadline - Date.now();
                if (restanteMs <= 0) {
                    encerrarBloqueio();
                    return;
                }

                lockoutCountdown.textContent = formatarTempo(Math.ceil(restanteMs / 1000));

                // Reagenda alinhado à virada do próximo segundo, sem acumular
                // deriva (setInterval simples atrasa em abas em segundo plano).
                lockoutTimer = setTimeout(atualizarContador, restanteMs % 1000 || 1000);
            }

            if (lockoutMsg && lockoutCountdown) {
                const restante = parseInt(lockoutMsg.dataset.remainingSeconds, 10);
                if (Number.isFinite(restante) && restante > 0) {
                    lockoutDeadline = Date.now() + restante * 1000;
                    btnSubmit.disabled = true;
                    atualizarContador();
                }
            }

            // Evita duplo submit (e impede envio enquanto bloqueado)
            form.addEventListener("submit", function (evento) {
                if (bloqueioAtivo()) {
                    evento.preventDefault();
                    return;
                }
                if (form.checkValidity()) {
                    btnSubmit.disabled = true;
                    btnSubmit.textContent = "Entrando...";
                }
            });

            // Restaura o botão se o usuário voltar pelo cache do navegador
            window.addEventListener("pageshow", function (evento) {
                if (!evento.persisted) return;

                if (lockoutDeadline !== null) {
                    // Página restaurada do bfcache no meio do bloqueio:
                    // recalcula pelo relógio (encerra se já passou).
                    clearTimeout(lockoutTimer);
                    atualizarContador();
                    return;
                }

                btnSubmit.disabled = false;
                btnSubmit.textContent = "Entrar";
            });
        });
 // Auto-dismiss: sem isso, .flash (position:fixed) fica na tela
 // indefinidamente, já que não há nenhum outro mecanismo de remoção.
 document.querySelectorAll(".flash").forEach((elemento) => {
     setTimeout(() => elemento.remove(), 6000)
 })
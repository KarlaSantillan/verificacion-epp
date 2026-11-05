// Mostrar u ocultar la contraseña
document.querySelectorAll("[data-toggle-password]").forEach((boton) => {
  boton.addEventListener("click", () => {
    const campo = document.getElementById(boton.dataset.togglePassword);
    const visible = campo.type === "text";
    campo.type = visible ? "password" : "text";
    boton.setAttribute("aria-label", visible ? "Mostrar contraseña" : "Ocultar contraseña");
    boton.querySelector("i").className = visible ? "bi bi-eye" : "bi bi-eye-slash";
  });
});

// Evita envíos dobles y muestra el estado "Verificando…"
document.querySelectorAll("form[data-loading]").forEach((formulario) => {
  formulario.addEventListener("submit", () => {
    const boton = formulario.querySelector("button[type=submit]");
    if (!boton) return;
    boton.disabled = true;
    boton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>' + formulario.dataset.loading;
  });
});

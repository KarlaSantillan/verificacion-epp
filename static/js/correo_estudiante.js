// Correo institucional del estudiante (HU16: notificación del llamado de atención).
// El SGA no entrega el correo: si el estudiante identificado no lo tiene, el docente puede escribirlo
// una sola vez. Es opcional y no bloquea la verificación.
(function () {
  function texto(valor) {
    const span = document.createElement("span");
    span.textContent = valor ?? "";
    return span.innerHTML;
  }

  function lineaCorreo(correo, nuevo) {
    return `<div class="small"><i class="bi bi-envelope me-1"></i>Correo: <strong>${texto(correo)}</strong>${
      nuevo ? ' <span class="text-success">· guardado</span>' : ""
    }</div>`;
  }

  document.addEventListener("epp:identificacion", (evento) => {
    const datos = evento.detail;
    const resultado = document.getElementById("resultado");
    const anterior = document.getElementById("bloqueCorreo");
    if (anterior) anterior.remove();
    if (!datos.ok || !datos.estudiante || !datos.estudiante.id) return;

    const bloque = document.createElement("div");
    bloque.id = "bloqueCorreo";
    bloque.className = "mt-3";

    if (datos.estudiante.correo) {
      bloque.innerHTML = lineaCorreo(datos.estudiante.correo, false);
      resultado.append(bloque);
      return;
    }

    bloque.innerHTML = `
      <form class="border rounded-3 p-2" novalidate>
        <label for="correoEstudiante" class="form-label small fw-semibold mb-1">
          Correo institucional <span class="fw-normal text-muted-epp">(opcional, para notificaciones)</span>
        </label>
        <div class="d-flex gap-2">
          <input id="correoEstudiante" type="email" class="form-control form-control-sm" maxlength="120"
                 placeholder="usuario@unemi.edu.ec" autocomplete="off">
          <button type="submit" class="btn btn-epp-outline btn-sm px-3">Guardar</button>
        </div>
        <div class="small mt-1" aria-live="polite"></div>
      </form>`;
    resultado.append(bloque);

    const formulario = bloque.querySelector("form");
    const campo = bloque.querySelector("input");
    const estado = bloque.querySelector("[aria-live]");
    formulario.addEventListener("submit", async (e) => {
      e.preventDefault();
      estado.className = "small mt-1 text-muted-epp";
      estado.textContent = "Guardando…";
      try {
        const respuesta = await fetch(window.EPP.urlCorreo, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": window.EPP.csrf },
          body: JSON.stringify({ estudiante: datos.estudiante.id, correo: campo.value }),
        });
        const r = await respuesta.json();
        if (!r.ok) throw new Error(r.mensaje);
        bloque.innerHTML = lineaCorreo(r.correo, true);
      } catch (error) {
        estado.className = "small mt-1 text-danger";
        estado.textContent = error.message || "No se pudo guardar el correo.";
      }
    });
  });
})();

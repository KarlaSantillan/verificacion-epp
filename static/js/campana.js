// Campana de notificaciones que se actualiza sola (HU15 / RF12-CA01).
// - Al instante: cuando esta pantalla registra una validación (evento "epp:validacion-registrada").
// - Cada 5 segundos, mientras la pestaña está visible (incidencias registradas en otro equipo).
// - Al volver a la pestaña.
// Si aparece un estudiante nuevo que requiere llamado, la campana se mueve (sin avisos en pantalla).
(function () {
  const campana = document.getElementById("campana");
  if (!campana) return;
  const boton = document.getElementById("campanaBoton");
  const menu = document.getElementById("campanaMenu");
  const INTERVALO_MS = 5000;
  let conocidos = new Set((campana.dataset.ids || "").split(",").filter(Boolean).map(Number));
  let consultando = false;

  function texto(valor) {
    const span = document.createElement("span");
    span.textContent = valor ?? "";
    return span.innerHTML;
  }

  function pintarContador(total) {
    let contador = boton.querySelector(".contador");
    if (total > 0) {
      if (!contador) {
        contador = document.createElement("span");
        contador.className = "contador";
        boton.append(contador);
      }
      contador.textContent = total;
    } else if (contador) {
      contador.remove();
    }
    boton.setAttribute("aria-label", `Notificaciones, ${total} pendientes`);
  }

  // Aviso discreto: solo se mueve la campana (sin mensajes en pantalla).
  function avisar() {
    boton.classList.remove("sacudir");
    void boton.offsetWidth; // reinicia la animación
    boton.classList.add("sacudir");
  }

  async function actualizar() {
    if (consultando) return;
    consultando = true;
    try {
      const respuesta = await fetch(campana.dataset.url, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!respuesta.ok) return;
      const datos = await respuesta.json();
      pintarContador(datos.total);
      menu.innerHTML = datos.html;
      const nuevos = datos.estudiantes.filter((e) => !conocidos.has(e.id));
      conocidos = new Set(datos.estudiantes.map((e) => e.id));
      if (nuevos.length) avisar();
    } catch (e) {
      // Sin conexión con el servidor: se intenta de nuevo en la próxima vuelta.
    } finally {
      consultando = false;
    }
  }

  document.addEventListener("epp:validacion-registrada", actualizar);
  setInterval(() => {
    if (document.visibilityState === "visible") actualizar();
  }, INTERVALO_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") actualizar();
  });
})();

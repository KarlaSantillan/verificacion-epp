// Materia y práctica de la sesión (asesoría del 12/11/2026).
// El docente las escribe una vez; se guardan en la sesión y acompañan a cada validación registrada.
(function () {
  const caja = document.getElementById("datosSesion");
  if (!caja) return;
  const url = caja.dataset.url;
  const campos = { materia: document.getElementById("materia"), practica: document.getElementById("practica") };
  const estado = document.getElementById("estadoSesion");
  const CLAVE_RECIENTES = "epp_practicas_recientes";
  let espera = null;
  let ultimo = JSON.stringify(valores());

  function valores() {
    return { materia: campos.materia.value.trim(), practica: campos.practica.value.trim() };
  }

  // Sugerencias: lo último que escribió este docente en este navegador.
  function leerRecientes() {
    try { return JSON.parse(localStorage.getItem(CLAVE_RECIENTES)) || { materia: [], practica: [] }; }
    catch (e) { return { materia: [], practica: [] }; }
  }
  function pintarSugerencias() {
    const recientes = leerRecientes();
    for (const nombre of ["materia", "practica"]) {
      const lista = document.getElementById(nombre === "materia" ? "sugerenciasMateria" : "sugerenciasPractica");
      if (!lista) continue;
      lista.innerHTML = "";
      for (const texto of recientes[nombre] || []) {
        const opcion = document.createElement("option");
        opcion.value = texto;
        lista.appendChild(opcion);
      }
    }
  }
  function recordar(datos) {
    const recientes = leerRecientes();
    for (const nombre of ["materia", "practica"]) {
      if (!datos[nombre]) continue;
      recientes[nombre] = [datos[nombre], ...(recientes[nombre] || []).filter((t) => t !== datos[nombre])].slice(0, 10);
    }
    try { localStorage.setItem(CLAVE_RECIENTES, JSON.stringify(recientes)); } catch (e) { /* sin almacenamiento: no pasa nada */ }
    pintarSugerencias();
  }

  async function guardar() {
    clearTimeout(espera);
    const datos = valores();
    const texto = JSON.stringify(datos);
    if (texto === ultimo) return;
    estado.textContent = "Guardando…";
    try {
      const respuesta = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.EPP.csrf },
        body: texto,
      });
      const resultado = await respuesta.json();
      if (!resultado.ok) throw new Error(resultado.mensaje);
      ultimo = texto;
      recordar(datos);
      estado.innerHTML = '<i class="bi bi-check2"></i> Guardado';
      setTimeout(() => { if (estado.textContent.includes("Guardado")) estado.textContent = ""; }, 2500);
    } catch (e) {
      estado.textContent = "No se pudo guardar";
    }
  }

  // Vacía los dos campos para escribir los de la nueva clase y reinicia la hora de inicio de la práctica.
  async function empezarNueva() {
    campos.materia.value = "";
    campos.practica.value = "";
    const datos = { ...valores(), nueva: true };
    try {
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.EPP.csrf },
        body: JSON.stringify(datos),
      });
      ultimo = JSON.stringify(valores());
    } catch (e) {
      estado.textContent = "No se pudo guardar";
    }
    campos.materia.focus();
  }

  // Botón "Nueva práctica": primero muestra el resumen de la clase que termina (si hubo verificaciones).
  const btnNueva = document.getElementById("btnNuevaPractica");
  const modal = document.getElementById("modalResumen");
  const cuerpo = document.getElementById("cuerpoResumen");
  const estadoResumen = document.getElementById("estadoResumen");
  const ventana = modal && window.bootstrap ? new bootstrap.Modal(modal) : null;

  if (btnNueva) {
    btnNueva.addEventListener("click", async () => {
      await guardar(); // por si la materia o la práctica se acaban de escribir
      if (!ventana) return empezarNueva();
      btnNueva.disabled = true;
      try {
        const respuesta = await fetch(caja.dataset.urlResumen, { headers: { Accept: "application/json" }, cache: "no-store" });
        const datos = await respuesta.json();
        // Siempre se pide confirmación: así un clic por error no borra la materia y la práctica.
        cuerpo.innerHTML = datos.total
          ? `<p class="small mb-3">Este es el resumen de la práctica actual. Al confirmar se vacían la materia y la práctica para empezar otra clase.</p>${datos.html}`
          : '<p class="mb-0">Todavía no hay verificaciones en esta práctica. ¿Desea vaciar la materia y la práctica para empezar otra clase?</p>';
        document.getElementById("btnImprimirResumen").classList.toggle("d-none", !datos.total);
        document.getElementById("btnCorreoResumen").classList.toggle("d-none", !datos.total);
        estadoResumen.textContent = "";
        ventana.show();
      } catch (e) {
        cuerpo.innerHTML = '<p class="mb-0">No se pudo cargar el resumen. ¿Desea empezar una nueva práctica de todas formas?</p>';
        document.getElementById("btnImprimirResumen").classList.add("d-none");
        document.getElementById("btnCorreoResumen").classList.add("d-none");
        ventana.show();
      } finally {
        btnNueva.disabled = false;
      }
    });
  }

  if (modal) {
    document.getElementById("btnEmpezarPractica").addEventListener("click", () => {
      ventana.hide();
      empezarNueva();
    });

    // Imprimir: abre el documento con formato de guía de práctica y lanza la impresión (o "Guardar como PDF").
    document.getElementById("btnImprimirResumen").addEventListener("click", () => {
      window.open(`${caja.dataset.urlImprimir}?imprimir=1`, "_blank");
    });

    const btnCorreo = document.getElementById("btnCorreoResumen");
    btnCorreo.addEventListener("click", async () => {
      btnCorreo.disabled = true;
      estadoResumen.className = "small me-auto text-muted-epp";
      estadoResumen.textContent = "Enviando…";
      try {
        const respuesta = await fetch(caja.dataset.urlEnviar, { method: "POST", headers: { "X-CSRFToken": window.EPP.csrf } });
        const datos = await respuesta.json();
        estadoResumen.className = `small me-auto ${datos.ok ? "text-success" : "text-danger"}`;
        estadoResumen.textContent = datos.mensaje;
      } catch (e) {
        estadoResumen.className = "small me-auto text-danger";
        estadoResumen.textContent = "No se pudo enviar el correo.";
      } finally {
        btnCorreo.disabled = false;
      }
    });
  }

  for (const campo of Object.values(campos)) {
    campo.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(guardar, 700); });
    campo.addEventListener("change", guardar);
  }
  pintarSugerencias();
})();

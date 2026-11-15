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

  // Botón "Nueva práctica": vacía los dos campos para escribir los de la nueva clase.
  const btnNueva = document.getElementById("btnNuevaPractica");
  if (btnNueva) {
    btnNueva.addEventListener("click", () => {
      campos.materia.value = "";
      campos.practica.value = "";
      guardar();
      campos.materia.focus();
    });
  }

  for (const campo of Object.values(campos)) {
    campo.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(guardar, 700); });
    campo.addEventListener("change", guardar);
  }
  pintarSugerencias();
})();

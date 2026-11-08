// Aviso de estudiante reincidente al identificarlo (HU15 / RF12-CA04). No bloquea la verificación.
(function () {
  document.addEventListener("epp:identificacion", (evento) => {
    const datos = evento.detail;
    const resultado = document.getElementById("resultado");
    const anterior = document.getElementById("avisoReincidente");
    if (anterior) anterior.remove();
    if (!datos.ok || !datos.reincidencia) return;
    const r = datos.reincidencia;
    const requiere = r.estado === "Requiere llamado de atención";
    const aviso = document.createElement("div");
    aviso.id = "avisoReincidente";
    aviso.className = `aviso ${requiere ? "aviso-error" : "aviso-warn"} mt-3`;
    aviso.setAttribute("role", "status");
    aviso.innerHTML = `<i class="bi ${requiere ? "bi-exclamation-octagon" : "bi-eye"} me-1"></i>`;
    aviso.append(`${r.estado}: ${r.incidencias} incidencia${r.incidencias === 1 ? "" : "s"} en el periodo. Puede continuar con la verificación.`);
    resultado.append(aviso);
  });
})();

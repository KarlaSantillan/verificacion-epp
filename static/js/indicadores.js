// Dashboard de indicadores (HU14 / RF11).
(function () {
  // CA02: al cambiar el periodo o el laboratorio, se recalculan los indicadores.
  const filtros = document.getElementById("filtrosIndicadores");
  if (filtros) {
    filtros.querySelectorAll("[data-autoenviar]").forEach((campo) => {
      campo.addEventListener("change", () => filtros.submit());
    });
  }

  const nodoDatos = document.getElementById("datosSerie");
  const lienzo = document.getElementById("graficoCumplimiento");
  if (!nodoDatos || !lienzo) return;
  const serie = JSON.parse(nodoDatos.textContent);

  // Si Chart.js no cargó (por ejemplo, sin internet), se muestra la tabla en su lugar.
  if (typeof Chart === "undefined") {
    document.getElementById("contenedorGrafico").classList.add("d-none");
    document.getElementById("tablaSerie").classList.add("show");
    return;
  }

  const estilo = getComputedStyle(document.documentElement);
  const color = (nombre, defecto) => (estilo.getPropertyValue(nombre) || defecto).trim();
  const VERDE = color("--epp-ok", "#15803d");
  const ROJO = color("--epp-bad", "#b91c1c");
  const AMBAR = color("--epp-warn", "#92400e");
  const TINTA = color("--epp-ink", "#14212d");

  const formato = (valor) => valor.toLocaleString("es-EC", { maximumFractionDigits: 1 });
  const colorPorcentaje = (valor) => (valor >= 90 ? VERDE : valor >= 70 ? AMBAR : ROJO);

  // Porcentaje de cumplimiento encima de cada barra.
  const etiquetasPorcentaje = {
    id: "etiquetasPorcentaje",
    afterDatasetsDraw(grafico) {
      const { ctx } = grafico;
      const superior = grafico.getDatasetMeta(grafico.data.datasets.length - 1);
      ctx.save();
      ctx.font = "600 11px Inter, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      superior.data.forEach((barra, i) => {
        const punto = serie[i];
        ctx.fillStyle = colorPorcentaje(punto.porcentaje);
        ctx.fillText(`${formato(punto.porcentaje)} %`, barra.x, barra.y - 4);
      });
      ctx.restore();
    },
  };

  const maximo = Math.max(...serie.map((p) => p.total));

  new Chart(lienzo, {
    type: "bar",
    data: {
      labels: serie.map((p) => p.etiqueta),
      datasets: [
        {
          label: "Cumple",
          data: serie.map((p) => p.conformes),
          backgroundColor: VERDE,
          borderColor: "#fff",
          borderWidth: { top: 1 },
          maxBarThickness: 36,
          stack: "validaciones",
        },
        {
          label: "No cumple",
          data: serie.map((p) => p.no_conformes),
          backgroundColor: ROJO,
          borderColor: "#fff",
          borderWidth: { bottom: 1 },
          borderRadius: { topLeft: 4, topRight: 4 },
          borderSkipped: false,
          maxBarThickness: 36,
          stack: "validaciones",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 22 } },
      plugins: {
        legend: { display: false }, // la leyenda va en texto debajo del gráfico
        tooltip: {
          mode: "index",
          intersect: false,
          displayColors: false,
          filter: (elemento) => elemento.datasetIndex === 0, // un solo bloque por barra
          callbacks: {
            title: (elementos) => {
              const p = serie[elementos[0].dataIndex];
              return p.fecha === p.hasta ? p.etiqueta : `${p.etiqueta} (lunes a domingo)`;
            },
            label: (elemento) => {
              const p = serie[elemento.dataIndex];
              return [
                `Validaciones: ${p.total}`,
                `Cumple: ${p.conformes}`,
                `No cumple: ${p.no_conformes}`,
                `Cumplimiento: ${formato(p.porcentaje)} %`,
              ];
            },
          },
        },
      },
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { color: TINTA } },
        y: {
          stacked: true,
          beginAtZero: true,
          suggestedMax: maximo + 1,
          title: { display: true, text: "Validaciones", color: TINTA },
          ticks: { precision: 0, color: TINTA },
          grid: { color: "#eef2f6" },
        },
      },
    },
    plugins: [etiquetasPorcentaje],
  });
})();

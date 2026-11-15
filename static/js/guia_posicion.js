// Guía de posición para la verificación de EPP (sugerencia de la tutora, asesoría del 12/11/2026).
// Muestra un personaje animado con la pose esperada y una silueta sobre el video.
// No modifica la detección: solo observa la lista de EPP y el resultado final.
(function () {
  const PIEL = "#f2c7a5", PELO = "#3b2a20", GUANTE = "#24364a", BATA = "#ffffff",
        BORDE = "#9fb0c0", MASCARILLA = "#bfe3f2", LENTE = "#d9f0ff", MARCO = "#1c3247";

  // Mano con guante, palma hacia la cámara (dibujada para el brazo izquierdo de la imagen).
  const mano = `
    <g class="mano">
      <rect x="27" y="62" width="5" height="16" rx="2.5" fill="${GUANTE}"/>
      <rect x="32.5" y="58" width="5" height="20" rx="2.5" fill="${GUANTE}"/>
      <rect x="38" y="59" width="5" height="19" rx="2.5" fill="${GUANTE}"/>
      <rect x="43.5" y="64" width="4.5" height="15" rx="2.25" fill="${GUANTE}"/>
      <rect x="45" y="78" width="5" height="12" rx="2.5" transform="rotate(-35 47 84)" fill="${GUANTE}"/>
      <rect x="27" y="74" width="21" height="17" rx="6" fill="${GUANTE}"/>
      <path d="M30 80 q8 4 15 0" stroke="#3d5570" stroke-width="1.4" fill="none" stroke-linecap="round"/>
    </g>`;

  // Brazo: el antebrazo gira en el codo y todo el brazo en el hombro.
  const brazo = `
    <g class="brazo-sup">
      <path d="M66 104 L38 138" stroke="${BORDE}" stroke-width="19" stroke-linecap="round"/>
      <path d="M66 104 L38 138" stroke="${BATA}" stroke-width="16" stroke-linecap="round"/>
      <g class="antebrazo">
        <path d="M38 138 L37 94" stroke="${BORDE}" stroke-width="17" stroke-linecap="round"/>
        <path d="M38 138 L37 94" stroke="${BATA}" stroke-width="14" stroke-linecap="round"/>
        ${mano}
      </g>
    </g>`;

  const personaje = `
  <svg class="personaje" viewBox="0 0 200 250" role="img" aria-label="Personaje con bata, mascarilla, gafas y guantes, de frente y con las manos levantadas a la altura de los hombros">
    <ellipse cx="100" cy="240" rx="52" ry="6" fill="#1c3247" opacity=".08"/>
    <g class="cuerpo">
      <!-- bata -->
      <path d="M64 102 Q100 92 136 102 L144 228 Q100 236 56 228 Z" fill="${BATA}" stroke="${BORDE}" stroke-width="2.5" stroke-linejoin="round"/>
      <path d="M88 97 L100 132 L112 97 Z" fill="#7fa3c4"/>
      <path d="M86 96 L100 134 L96 228 M114 96 L100 134" stroke="${BORDE}" stroke-width="2" fill="none" stroke-linejoin="round"/>
      <circle cx="104" cy="152" r="2.6" fill="${BORDE}"/><circle cx="104" cy="174" r="2.6" fill="${BORDE}"/><circle cx="104" cy="196" r="2.6" fill="${BORDE}"/>
      <path d="M118 176 h16 v14 h-16 z" fill="none" stroke="${BORDE}" stroke-width="2" stroke-linejoin="round"/>
      <rect x="121" y="171" width="3" height="10" rx="1.5" fill="#fb7e00"/>
      <g class="brazo izq">${brazo}</g>
      <g class="brazo der" transform="translate(200 0) scale(-1 1)">${brazo}</g>
      <!-- cuello y cabeza -->
      <rect x="93" y="82" width="14" height="14" rx="4" fill="${PIEL}"/>
      <circle cx="100" cy="60" r="26" fill="${PIEL}"/>
      <path d="M74 60 Q72 30 100 30 Q128 30 126 60 Q122 42 100 42 Q80 42 74 60 Z" fill="${PELO}"/>
      <!-- ojos (detrás de las gafas) -->
      <g class="ojos"><ellipse cx="90" cy="57" rx="2.6" ry="3.2" fill="#14212d"/><ellipse cx="110" cy="57" rx="2.6" ry="3.2" fill="#14212d"/></g>
      <!-- gafas de seguridad -->
      <path d="M74 54 L126 54" stroke="${MARCO}" stroke-width="3"/>
      <rect x="79" y="48" width="42" height="17" rx="7" fill="${LENTE}" fill-opacity=".55" stroke="${MARCO}" stroke-width="2.5"/>
      <path d="M84 52 l7 0" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
      <!-- mascarilla -->
      <path d="M77 66 Q100 62 123 66 Q122 84 100 88 Q78 84 77 66 Z" fill="${MASCARILLA}" stroke="#8cc6dc" stroke-width="1.5"/>
      <path d="M83 72 Q100 69 117 72 M84 78 Q100 75 116 78" stroke="#8cc6dc" stroke-width="1.3" fill="none"/>
      <path d="M77 67 Q72 66 74 60 M123 67 Q128 66 126 60" stroke="#8cc6dc" stroke-width="1.5" fill="none"/>
    </g>
    <g transform="translate(150 22)"><g class="visto">
      <circle r="13" fill="#15803d"/>
      <path d="M-6 0 l4 4.5 l8 -9" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    </g></g>
  </svg>`;

  // Silueta punteada que se dibuja sobre el video.
  const silueta = `
  <svg viewBox="0 0 200 250" preserveAspectRatio="xMidYMax meet" aria-hidden="true">
    <g class="trazo">
      <circle cx="100" cy="58" r="27"/>
      <path d="M62 104 Q100 92 138 104 L146 250 L54 250 Z"/>
      <circle cx="35" cy="62" r="11"/><circle cx="165" cy="62" r="11"/>
      <path class="brazos" d="M66 106 L36 140 L35 76 M134 106 L164 140 L165 76"/>
    </g>
  </svg>`;

  const pasos = [
    "Párese de frente, a 1–1,5 m de la cámara.",
    "Levante las manos a la altura de los hombros, con las palmas hacia la cámara.",
    "Quédese quieto hasta que se complete la barra.",
  ];

  const tarjeta = document.getElementById("guiaMascota");
  const capaSilueta = document.getElementById("guiaSilueta");
  const capaIntro = document.getElementById("guiaIntro");
  const lista = document.getElementById("listaEpp");
  const resultado = document.getElementById("resultadoFinal");
  const videoVacio = document.getElementById("videoVacio");
  if (!tarjeta || !capaSilueta || !lista) return;

  tarjeta.innerHTML = `
    <div class="guia-figura">${personaje}</div>
    <div>
      <div class="fw-semibold mb-1">Así debe ubicarse</div>
      <ol class="guia-pasos">${pasos.map((p, i) => `<li class="p${i + 1}">${p}</li>`).join("")}</ol>
    </div>`;
  capaSilueta.innerHTML = silueta;
  if (capaIntro) capaIntro.innerHTML = `<div class="guia-intro-caja">${personaje}<div class="fw-semibold">Así debe ubicarse</div><div class="small">Manos arriba, palmas hacia la cámara</div></div>`;

  // Estado de la silueta: visible mientras falten EPP obligatorios; verde y se desvanece cuando están todos.
  function actualizar() {
    const camaraLista = !videoVacio || videoVacio.classList.contains("d-none");
    const items = [...lista.querySelectorAll(".estado-epp")].filter((el) => !el.textContent.includes("(opcional)"));
    const completos = items.length > 0 && items.every((el) => el.classList.contains("detectado"));
    const hayResultado = resultado && !resultado.classList.contains("d-none");
    capaSilueta.classList.toggle("visible", camaraLista && !hayResultado);
    capaSilueta.classList.toggle("ok", completos);
  }

  // Al encenderse la cámara se muestra el personaje grande unos segundos.
  let introMostrada = false;
  function intro() {
    if (!capaIntro) return;
    const camaraLista = videoVacio && videoVacio.classList.contains("d-none");
    if (camaraLista && !introMostrada) {
      introMostrada = true;
      capaIntro.classList.remove("d-none", "salir");
      setTimeout(() => capaIntro.classList.add("salir"), 3200);
      setTimeout(() => capaIntro.classList.add("d-none"), 3800);
    }
    if (!camaraLista) introMostrada = false; // se vuelve a mostrar con el siguiente estudiante
  }

  const observar = (el, opciones) => el && new MutationObserver(() => { actualizar(); intro(); }).observe(el, opciones);
  observar(lista, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
  observar(resultado, { attributes: true, attributeFilter: ["class"] });
  observar(videoVacio, { attributes: true, attributeFilter: ["class"] });
  actualizar();
})();

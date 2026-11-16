(() => {
  const $ = id => document.getElementById(id);
  const storage = {
    get(key, fallback) {
      try { return sessionStorage.getItem(key) || fallback; } catch { return fallback; }
    },
  };
  const version = storage.get("bar-version", "stable") === "candidate" ? "candidate" : "stable";
  const allowedCases = ["complete", "missing", "food", "both"];
  const savedCase = storage.get("bar-case", "missing");
  const selectedCase = allowedCases.includes(savedCase) ? savedCase : "missing";
  const titles = {complete: "Todo disponible", missing: "Agua con gas agotada", food: "Tortilla agotada", both: "Bebida y comida agotadas"};
  const points = [[192, 272], [810, 105], [930, 255], [95, 180]];
  const map = document.querySelector(".planta");
  const waiter = map.querySelector(".camarero");
  const marker = document.createElementNS("http://www.w3.org/2000/svg", "g");
  marker.classList.add("event-marker");
  marker.setAttribute("visibility", "hidden");
  marker.innerHTML = '<circle r="33"></circle><text y="-42" text-anchor="middle"></text>';
  map.append(marker);
  const failureMarker = marker.cloneNode(true);
  failureMarker.classList.add("error");
  failureMarker.setAttribute("transform", "translate(810 105)");
  failureMarker.querySelector("text").textContent = "ERROR · BARRA";
  map.append(failureMarker);
  $("bar-version").textContent = version === "candidate" ? "Candidata · Barra ignora el stock" : "Estable · Barra comprueba el stock";
  $("bar-case").textContent = "Caso: " + titles[selectedCase];
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const wait = ms => new Promise(resolve => setTimeout(resolve, reduced ? 0 : ms));

  async function run() {
    const button = $("bar-run");
    button.disabled = true;
    for (let i = 0; i < 4; i++) $("bar-stage-" + i).className = "";
    $("bar-status").textContent = "Ejecutando el pedido en la API…";
    marker.setAttribute("visibility", "hidden");
    failureMarker.setAttribute("visibility", "hidden");
    try {
      const response = await fetch("/api/run", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({case: selectedCase, version}),
      });
      if (!response.ok) throw new Error("No se pudo ejecutar el pedido.");
      const result = await response.json();
      const messages = document.querySelector(".mensajes");
      for (const [index, event] of result.events.entries()) {
        const [x, y] = points[index];
        const stage = $("bar-stage-" + index);
        stage.className = event.state === "error" ? "error" : "active";
        marker.setAttribute("transform", `translate(${x} ${y})`);
        marker.setAttribute("visibility", "visible");
        marker.classList.toggle("error", event.state === "error");
        if (event.state === "error" && event.agent === "Barra") failureMarker.setAttribute("visibility", "visible");
        marker.querySelector("text").textContent = event.agent;
        waiter.style.transform = `translate(${x}px, ${y}px)`;
        $("bar-status").textContent = event.agent + ": " + event.detail;
        const row = document.createElement("div"), bubble = document.createElement("div");
        row.className = "msg agent-event" + (event.state === "error" ? " error" : "");
        bubble.className = "burbuja";
        bubble.textContent = event.agent + " · " + event.detail;
        row.append(bubble); messages.append(row); messages.scrollTop = messages.scrollHeight;
        await wait(1000);
        if (event.state !== "error") stage.className = "done";
      }
      $("bar-status").textContent = result.status === "ready"
        ? "Resultado: propuesto para servir. No se sirve ni se cobra realmente."
        : "Resultado: pedido retenido por falta de stock. No hay acción externa.";
    } catch (error) {
      $("bar-status").textContent = error.message;
    } finally { button.disabled = false; }
  }
  $("bar-run").addEventListener("click", run);
  if (new URLSearchParams(location.search).get("run") === "1") run();
})();

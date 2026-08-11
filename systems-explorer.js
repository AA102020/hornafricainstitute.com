const systemContent = {
  gulf: { label: "Gulf institutions", title: "Finance and organize cross-regional activity", copy: "Governments, development funds, investors, and firms direct capital, energy relationships, infrastructure projects, security cooperation, and diplomacy toward the Red Sea and Horn of Africa.", tags: ["Investment", "Energy", "Finance", "Diplomacy"], links: ["gulf-redsea"] },
  redsea: { label: "Red Sea maritime system", title: "Connect strategic routes, infrastructure, and security", copy: "Shipping lanes, choke points, ports, naval activity, and submarine cables connect Gulf and Horn institutions while concentrating commercial and security risks.", tags: ["Shipping", "Choke points", "Maritime security", "Cables"], links: ["gulf-redsea", "redsea-horn"] },
  horn: { label: "Horn of Africa ports and corridors", title: "Translate external flows into infrastructure and authority", copy: "Ports, roads, railways, logistics systems, customs institutions, and public authorities determine how maritime flows reach states, firms, and communities across the Horn of Africa.", tags: ["Ports", "Corridors", "Logistics", "Public authority"], links: ["redsea-horn", "horn-interior"] },
  interior: { label: "Interior markets and communities", title: "Generate economic, social, and political return flows", copy: "Markets and communities receive goods, investment, infrastructure, and security effects while producing trade, livestock, labor, migration, information, and political responses.", tags: ["Trade", "Food", "Mobility", "Livelihoods"], links: ["horn-interior"] }
};

document.querySelectorAll("[data-systems-explorer]").forEach((explorer) => {
  const nodes = [...explorer.querySelectorAll("[data-system]")];
  const controls = [...explorer.querySelectorAll("[data-flow]")];
  const links = [...explorer.querySelectorAll("[data-link]")];
  const selectSystem = (key) => {
    const content = systemContent[key];
    nodes.forEach((node) => { const active = node.dataset.system === key; node.classList.toggle("is-active", active); node.setAttribute("aria-pressed", String(active)); });
    links.forEach((link) => link.classList.toggle("is-related", content.links.includes(link.dataset.link)));
    explorer.querySelector("[data-detail-label]").textContent = content.label;
    explorer.querySelector("[data-detail-title]").textContent = content.title;
    explorer.querySelector("[data-detail-copy]").textContent = content.copy;
    explorer.querySelector("[data-detail-tags]").replaceChildren(...content.tags.map((tag) => { const item = document.createElement("span"); item.textContent = tag; return item; }));
  };
  nodes.forEach((node) => node.addEventListener("click", () => selectSystem(node.dataset.system)));
  controls.forEach((control) => control.addEventListener("click", () => {
    controls.forEach((item) => { const active = item === control; item.classList.toggle("is-active", active); item.setAttribute("aria-pressed", String(active)); });
    explorer.dataset.flowMode = control.dataset.flow === "all" ? "" : control.dataset.flow;
  }));
  selectSystem("gulf");
});

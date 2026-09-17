const $ = (selector) => document.querySelector(selector);
let currentState = null;

async function api(url, options = {}) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  const data = await response.json().catch(() => ({ ok: false, message: "Invalid server response" }));
  if (!response.ok || data.ok === false) throw new Error(data.message || "Request failed");
  return data;
}

function money(value) { return `$${Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }

function notify(message, error = false) {
  const toast = $("#toast");
  toast.textContent = message; toast.className = `toast show${error ? " error" : ""}`;
  window.clearTimeout(notify.timer); notify.timer = window.setTimeout(() => { toast.className = "toast"; }, 3600);
}

function showPlayerModal() {
  $("#player-modal").classList.remove("hidden");
  $("#player-name-input").focus();
}

function showLevelModal(level, flag) {
  $("#level-modal-title").textContent = "CONGRATULATIONS!";
  $("#level-modal-message").textContent = `LEVEL ${String(level).padStart(2, "0")} CLEARED - FLAG UNLOCKED.`;
  $("#unlocked-flag").textContent = flag;
  $("#level-modal").classList.remove("hidden");
}

function render(state) {
  currentState = state;
  $("#wallet").textContent = money(state.player.money);
  $("#player-wallet").textContent = money(state.player.money);
  $("#player-name").textContent = state.player.name.toUpperCase();
  $("#menu-player-name").textContent = state.player.name;
  $("#player-id").textContent = `ID: ${state.player.ID}`;
  $("#level-eyebrow").textContent = state.level_info.eyebrow;
  $("#level-name").textContent = state.level_info.name;
  $("#top-level-number").textContent = state.level;
  $("#top-level-name").textContent = state.level_info.eyebrow.split(" / ")[1] || state.level_info.name.toUpperCase();
  [1, 2, 3].forEach((level) => {
    const step = document.querySelector(`[data-level="${level}"]`);
    step.classList.toggle("active", level === state.level);
    step.classList.toggle("done", state.completed.includes(level));
    $(`#level-${level}-panel`).classList.toggle("hidden", level !== state.level || document.body.dataset.page === "save" && level === 3);
  });
  $("#save-disabled-panel").classList.toggle("hidden", document.body.dataset.page !== "save" || state.level !== 3);
  renderProducts(state);
  renderInventory(state);
  renderFlags(state);
  renderActivity(state);
}

function renderProducts(state) {
  const grid = $("#product-grid");
  const flagCard = `
    <article class="product flag-product">
      <img class="product-image" src="/icons/flag.png" alt="Flag">
      <div class="product-name">FLAG</div>
      <div class="product-price">BUY ${money(state.flag_price)} / UNLOCK LEVEL</div>
      <button type="button" data-buy="flag">BUY NOW -&gt;</button>
    </article>`;
  const productCards = Object.entries(state.products).map(([name, product]) => `
    <article class="product">
      <img class="product-image" src="/icons/${name}.png" alt="${name}">
      <div class="product-name">${name.toUpperCase()}</div>
      <div class="product-price">BUY ${money(product.price)} / SELL ${money(product.sell)}</div>
      <button type="button" data-buy="${name}">BUY NOW -&gt;</button>
    </article>`).join("");
  grid.innerHTML = flagCard + productCards;
  grid.querySelectorAll("[data-buy]").forEach((button) => button.addEventListener("click", () => buy(button.dataset.buy)));
}

function renderInventory(state) {
  const list = $("#inventory-list");
  const items = Object.entries(state.inventory).filter(([, quantity]) => quantity > 0);
  if (!items.length) {
    list.innerHTML = '<p class="empty-inventory">No Pokemon in inventory.</p>';
    return;
  }
  list.innerHTML = items.map(([name, quantity]) => `
    <div class="inventory-item">
      <img src="/icons/${name}.png" alt="${name}">
      <span>${name}</span>
      <strong>x${quantity}</strong>
      <div class="inventory-sale-controls">
        <label class="inventory-quantity"><span class="sr-only">Quantity</span><input type="number" min="1" max="100" step="1" value="1" data-quantity="${name}"></label>
        <button type="button" class="inventory-sell" data-sell="${name}">SELL</button>
      </div>
    </div>`).join("");
  list.querySelectorAll("[data-sell]").forEach((button) => button.addEventListener("click", () => {
    const quantity = Number(list.querySelector(`[data-quantity="${button.dataset.sell}"]`).value);
    sellInventory(button.dataset.sell, quantity);
  }));
}

function renderFlags(state) {
  const completed = new Set(state.completed);
  $("#flag-list").innerHTML = [1, 2, 3].map((level) => {
    const unlocked = completed.has(level);
    const value = unlocked ? (state.flags[String(level)] || `FLAG{level_${level}_cleared}`) : "LOCKED / COMPLETE PREVIOUS LEVEL";
    return `<div class="flag-item ${unlocked ? "unlocked" : "locked"}"><div class="flag-level">FLAG ${String(level).padStart(2, "0")}</div><div class="flag-value">${value}</div></div>`;
  }).join("");
}

function renderActivity(state) {
  $("#activity-log").innerHTML = state.activity.map((item) => `<div class="activity-entry ${item.kind}">${item.text}</div>`).join("");
}

async function buy(item) {
  try { const data = await api("/api/buy", { method: "POST", body: JSON.stringify({ item }) }); render(data.state); notify(data.message); if (item === "flag" && data.flag) showLevelModal(data.state.completed.at(-1) || data.state.level, data.flag); }
  catch (error) { notify(error.message, true); }
}

async function sellInventory(item, quantity) {
  try {
    const data = await api("/api/inventory/sell", { method: "POST", body: JSON.stringify({ item, quantity }) });
    render(data.state); notify(data.message);
  } catch (error) { notify(error.message, true); }
}

async function uploadSave(event) {
  const input = event.target;
  const file = input.files[0]; if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const data = await api("/api/upload-save", { method: "POST", body: JSON.stringify(payload) });
    render(data.state); notify(data.message);
  } catch (error) { notify(error.message, true); }
  input.value = "";
}

["#save-upload", "#save-upload-level2"].forEach((selector) => $(selector).addEventListener("change", uploadSave));

$("#buy-terminal-item").addEventListener("click", () => buy($("#sell-item").value));

$("#sell-item-button").addEventListener("click", async () => {
  const item = $("#sell-item").value;
  const quantity = $("#sell-quantity").value;
  const count = Math.min(50, Math.max(1, Number($("#repeat-count").value) || 1));
  try {
    let data;
    for (let i = 0; i < count; i += 1) data = await api("/api/sell", { method: "POST", body: JSON.stringify({ item, quantity }) });
    render(data.state); notify(`${count} sale request${count > 1 ? "s" : ""} completed.`);
  } catch (error) { notify(error.message, true); }
});

$("#reset-button").addEventListener("click", async () => { if (!window.confirm("Reset current sandbox session?")) return; await api("/api/reset", { method: "POST" }); window.location.reload(); });

$("#player-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try { const data = await api("/api/start", { method: "POST", body: JSON.stringify({ name: $("#player-name-input").value }) }); $("#player-modal").classList.add("hidden"); render(data.state); notify(data.message); }
  catch (error) { notify(error.message, true); }
});

$("#close-level-modal").addEventListener("click", () => $("#level-modal").classList.add("hidden"));

api("/api/state").then((state) => state.needs_name ? showPlayerModal() : render(state)).catch((error) => notify(error.message, true));

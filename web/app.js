const DATA_BASE = "./data";

const fmtNum = (n) => (n === null || n === undefined || isNaN(n))
  ? "—" : Number(n).toLocaleString("en-IN");

const fmtPct = (n) => (n === null || n === undefined || isNaN(n))
  ? "—" : `${Number(n).toFixed(2)}%`;

const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
};

async function loadJSON(name) {
  try {
    const res = await fetch(`${DATA_BASE}/${name}?t=${Date.now()}`);
    if (!res.ok) throw new Error(res.status);
    return await res.json();
  } catch (e) {
    console.error(`Failed to load ${name}`, e);
    return null;
  }
}

function priceLookup(prices) {
  const map = {};
  (prices?.stocks || []).forEach(s => { map[s.symbol] = s; });
  return map;
}

async function renderDeals() {
  const data = await loadJSON("bulk_deals.json");
  const wrap = document.getElementById("deals-body");
  const updated = document.getElementById("deals-updated");
  if (!data) { wrap.innerHTML = emptyRow("Deal data unavailable right now."); return; }
  updated.textContent = fmtDate(data.as_of);

  const rows = [
    ...(data.bulk_deals || []).map(r => ({ ...r, kind: "Bulk" })),
    ...(data.block_deals || []).map(r => ({ ...r, kind: "Block" })),
  ];

  if (!rows.length) { wrap.innerHTML = emptyRow("No bulk or block deals reported yet today."); return; }

  wrap.innerHTML = rows.map(r => {
    const side = (r.buySell || "").toUpperCase();
    const pillClass = side === "SELL" ? "sell" : "buy";
    return `<tr>
      <td>${r.symbol ?? "—"}</td>
      <td>${r.kind}</td>
      <td>${r.clientName ?? "—"}</td>
      <td><span class="pill ${pillClass}">${side || "—"}</span></td>
      <td class="num">${fmtNum(r.quantity)}</td>
      <td class="num">₹${fmtNum(r.tradePrice)}</td>
    </tr>`;
  }).join("");
}

async function renderDelivery() {
  const [data, prices] = await Promise.all([loadJSON("delivery.json"), loadJSON("prices.json")]);
  const wrap = document.getElementById("delivery-body");
  const updated = document.getElementById("delivery-updated");
  if (!data) { wrap.innerHTML = emptyRow("Delivery data unavailable right now."); return; }
  updated.textContent = fmtDate(data.as_of);

  const pMap = priceLookup(prices);
  const rows = (data.stocks || [])
    .filter(s => s.deliveryQtyPct !== undefined && s.deliveryQtyPct !== null)
    .sort((a, b) => (b.deliveryQtyPct ?? 0) - (a.deliveryQtyPct ?? 0));

  if (!rows.length) { wrap.innerHTML = emptyRow("No delivery data yet."); return; }

  wrap.innerHTML = rows.map(r => {
    const px = pMap[r.symbol];
    const chg = px?.changePct;
    const chgClass = chg > 0 ? "up" : chg < 0 ? "down" : "";
    return `<tr>
      <td>${r.symbol}</td>
      <td class="num">${fmtPct(r.deliveryQtyPct)}</td>
      <td class="num">${fmtNum(r.quantityTraded)}</td>
      <td class="num">${px ? `₹${fmtNum(px.close)}` : "—"}</td>
      <td class="num"><span class="pill ${chgClass}">${chg !== undefined ? fmtPct(chg) : "—"}</span></td>
    </tr>`;
  }).join("");
}

async function renderFiiDii() {
  const data = await loadJSON("fii_dii.json");
  const wrap = document.getElementById("fiidii-body");
  const updated = document.getElementById("fiidii-updated");
  if (!data) { wrap.innerHTML = emptyRow("FII/DII data unavailable right now."); return; }
  updated.textContent = fmtDate(data.as_of);

  const rows = data.rows || [];
  if (!rows.length) { wrap.innerHTML = emptyRow("No FII/DII figures published yet."); return; }

  wrap.innerHTML = rows.map(r => {
    const net = Number(r.netValue);
    const cls = net > 0 ? "up" : net < 0 ? "down" : "";
    return `<tr>
      <td>${r.category}</td>
      <td>${r.date}</td>
      <td class="num">₹${fmtNum(r.buyValue)} Cr</td>
      <td class="num">₹${fmtNum(r.sellValue)} Cr</td>
      <td class="num"><span class="pill ${cls}">₹${fmtNum(r.netValue)} Cr</span></td>
    </tr>`;
  }).join("");
}

function emptyRow(msg) {
  return `<tr><td colspan="6" class="empty-state">${msg}</td></tr>`;
}

function setupTabs() {
  const buttons = document.querySelectorAll("nav.tabs button");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("active"));
      document.querySelectorAll("section.panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.target).classList.add("active");
    });
  });
}

setupTabs();
renderDeals();
renderDelivery();
renderFiiDii();

const state = {
  config: null,
  defaults: null,
  availableGroups: [],
  statusChoices: [],
  statusBg: {},
  statusColors: {},
  minDays: 21,
  minDaysPreset: "10 dias",
  usdBrl: 5.2,
  linkTokens: 0, // tokens estimados do conteúdo do link do edital
  filterDate: null,   // yyyy-mm-dd (string) ou null
  valueMax: null,     // número em BRL ou null
  // Custo da sessão
  sessionCost: {
    inputTokens: 0,
    outputTokens: 0,
    costUsd: 0,
    costBrl: 0,
  },
};

// NOVO: Busca a cotação atual do dólar (USD-BRL)
async function fetchDollarRate() {
  try {
    // API pública e gratuita para cotação
    const resp = await fetch('https://economia.awesomeapi.com.br/last/USD-BRL');
    if (!resp.ok) return null;
    const data = await resp.json();
    // Usamos o 'bid' (preço de compra)
    const rate = data?.USDBRL?.bid;
    if (!rate) return null;

    const rateFloat = parseFloat(rate);
    return isNaN(rateFloat) ? null : rateFloat;
  } catch (e) {
    console.warn("Erro ao buscar cotação do dólar:", e);
    return null;
  }
}

// NOVO: Atualiza o state e o badge na tela com a nova cotação
function updateDollarUI(rate) {
  if (!rate || rate <= 0) return; // Não faz nada se a cotação falhar

  // 1. Atualiza o state global (usado nos cálculos de custo)
  state.usdBrl = rate;

  // 2. Atualiza o badge no HTML (na aba Perplexity)
  const badge = document.getElementById("dolar-value");
  if (badge) {
    // Formata para R$ 5.23 (exemplo)
    badge.textContent = rate.toFixed(2);
  }
}

// NOVO: Atualiza o contador de custo na UI
function updateCostTracker(costData) {
  if (!costData) return;

  // Acumula tokens e custos na sessão
  state.sessionCost.inputTokens += costData.input_tokens || 0;
  state.sessionCost.outputTokens += costData.output_tokens || 0;
  state.sessionCost.costUsd += costData.cost_usd || 0;
  state.sessionCost.costBrl += costData.cost_brl || 0;

  // Atualiza elementos da UI
  const tracker = document.getElementById("cost-tracker");
  const costBrl = document.getElementById("cost-brl");
  const costUsd = document.getElementById("cost-usd");
  const tokensCount = document.getElementById("cost-tokens-count");

  if (tracker) {
    tracker.classList.remove("hidden");
    tracker.classList.add("updating");
    setTimeout(() => tracker.classList.remove("updating"), 300);
  }

  if (costBrl) {
    costBrl.textContent = `R$ ${state.sessionCost.costBrl.toFixed(4).replace('.', ',')}`;
  }

  if (costUsd) {
    costUsd.textContent = `$${state.sessionCost.costUsd.toFixed(6)}`;
  }

  if (tokensCount) {
    const total = state.sessionCost.inputTokens + state.sessionCost.outputTokens;
    tokensCount.textContent = total.toLocaleString('pt-BR');
  }
}

// Mostra custo parcial (durante a coleta, antes de terminar)
function showPartialCost(inputTokens, outputTokens, modelId = "sonar") {
  const modelPrices = {
    "sonar": { input: 1.0, output: 1.0 },
    "sonar-pro": { input: 3.0, output: 15.0 },
    "sonar-reasoning": { input: 1.0, output: 5.0 },
  };

  const prices = modelPrices[modelId] || modelPrices["sonar"];
  const costUsd = (inputTokens * prices.input / 1_000_000) + (outputTokens * prices.output / 1_000_000);
  const costBrl = costUsd * state.usdBrl;

  updateCostTracker({
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    cost_usd: costUsd,
    cost_brl: costBrl,
  });
}

// ---------- Helpers One-Click (presets salvos em localStorage) ----------

// Utilitário global para parse de datas YYYY-MM-DD
function parseISO(d) {
  if (!d) return null;
  const [y, m, day] = d.split("-").map(Number);
  if (!y || !m || !day) return null;
  return new Date(y, m - 1, day);
}

// FILTRO GLOBAL (usa somente state.filterDate / state.valueMax)
// Regras:
// - Se não houver data/valor no item, NÃO exclui.
// - Só oculta quando houver dado E ele violar o limite.
function filterVisibleItems() {
  const allCards = document.querySelectorAll(".item-card");
  const limitDate = state.filterDate ? parseISO(state.filterDate) : null;
  const limitValue = Number.isFinite(state.valueMax) ? state.valueMax : null;
  allCards.forEach(card => {
    let ok = true;
    if (ok && limitDate) {
      const dl = card.dataset.deadline || "";
      if (dl) { // só filtra se o item tiver data
        const d = parseISO(dl.slice(0, 10));
        if (d && d < limitDate) ok = false;
      }
    }
    if (ok && limitValue !== null) {
      const amtStr = card.dataset.amount || "";
      if (amtStr !== "") {
        const amt = Number(amtStr);
        if (Number.isFinite(amt) && amt > limitValue) ok = false;
      }
    }
    card.style.display = ok ? "" : "none";
  });
}

const ONECLICK_KEY = "pplx_oneclick_presets_v1";

function loadOneClickPresets() {
  try {
    const raw = localStorage.getItem(ONECLICK_KEY);
    if (!raw) {
      // presets default
      const d = state.minDays || 21;
      const defaults = [
        {
          id: "amazonia",
          label: `Editais internacionais para aceleradoras na Amazônia (≥ ${d} dias)`,
          prompt: `Editais internacionais para aceleradoras na Amazônia com prazo mínimo de ${d} dias. Liste oportunidades relevantes, com links oficiais.`,
        },
        {
          id: "funda",
          label: `Fundações e Prêmios global para clima & biodiversidade (≥ ${d} dias)`,
          prompt: `Fundações e Prêmios para clima & biodiversidade com prazo mínimo de ${d} dias. Liste oportunidades relevantes, com links oficiais.`,
        },

        {
          id: "corp",
          label: `Corporativo/Aceleradoras global para clima & biodiversidade (≥ ${d} dias)`,
          prompt: `Corporativo/Aceleradoras global para clima & biodiversidade com prazo mínimo de ${d} dias. Liste oportunidades relevantes, com links oficiais.`,
        },


        {
          id: "gov",
          label: `Chamadas governamentais Brasil/LatAm focadas em inovação (≥ ${d} dias)`,
          prompt: `Chamadas governamentais Brasil/LatAm focadas em inovação com prazo mínimo de ${d} dias. Liste oportunidades relevantes, com links oficiais.`,
        },
      ];
      localStorage.setItem(ONECLICK_KEY, JSON.stringify(defaults));
      return defaults;
    }
    const arr = JSON.parse(raw);
    if (Array.isArray(arr)) return arr;
  } catch (e) {
    console.warn("erro ao carregar presets one-click", e);
  }
  return [];
}

function saveOneClickPresets(presets) {
  try {
    localStorage.setItem(ONECLICK_KEY, JSON.stringify(presets || []));
  } catch (e) {
    console.warn("erro ao salvar presets one-click", e);
  }
}

// flags de controle de long running tasks
let collectCancelRequested = false;
let diagAbortController = null;
let diagWindow = null;

// Helper simples para GET/POST no backend
async function apiGet(path, options = {}) {
  const resp = await fetch(path, {
    signal: options.signal,
  });
  if (!resp.ok) {
    throw new Error(`GET ${path} -> ${resp.status}`);
  }
  return await resp.json();
}

async function apiPost(path, body, options = {}) {
  const resp = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body || {}),
    signal: options.signal,
  });
  if (!resp.ok) {
    throw new Error(`POST ${path} -> ${resp.status}`);
  }
  return await resp.json();
}

// Desabilita/habilita interações na aba de gestão inteira
function setManageInteractivity(disabled) {
  const tab = document.getElementById("tab-manage");
  if (!tab) return;
  const els = tab.querySelectorAll("button, input, select, textarea");
  els.forEach((el) => {
    if (el.dataset.keepEnabled === "true") return;
    el.disabled = disabled;
  });
}

// Atualiza seção de erros genéricos
function renderErrors(errors, containerId = "errors-section") {
  const section = document.getElementById(containerId);
  const list = document.getElementById(
    containerId === "errors-section" ? "errors-list" : "pplx-errors-list"
  );
  if (!section || !list) return;
  list.innerHTML = "";
  if (!errors || errors.length === 0) {
    section.classList.add("hidden");
    return;
  }
  section.classList.remove("hidden");
  for (const [i, err] of errors.entries()) {
    const div = document.createElement("div");
    div.className = "error-item";
    div.innerHTML = `<strong>${i + 1}. [${err.ts}] ${err.where}</strong><br>${err.msg
      }<br><details><summary>Stacktrace</summary><pre>${err.stack}</pre></details>`;
    list.appendChild(div);
  }
}

// ---------- Inicialização de config ----------

async function loadConfig() {
  const data = await apiGet("/api/config");
  const cfg = data.config;
  state.config = cfg.config || {};
  state.defaults = cfg.defaults || {};
  state.availableGroups = cfg.available_groups || [];
  state.statusChoices = cfg.status_choices || [];
  state.statusBg = cfg.status_bg || {};
  state.statusColors = cfg.status_colors || {};

  // MIN_DAYS e PRESET
  const minDaysStr = state.config["MIN_DAYS"] || "21";
  state.minDays = parseInt(minDaysStr, 10) || 21;
  state.minDaysPreset = state.config["MIN_DAYS_PRESET"] || "10 dias";
  state.usdBrl = parseFloat(state.config["USD_BRL"] || "5.2");

  // Atualiza campo de dias na aba Perplexity, se existir
  const diasInput = document.getElementById("pplx-dias");
  if (diasInput) {
    diasInput.value = state.minDays.toString();
  }

  renderConfigUI();
  renderGroupsCheckboxes();
  renderGroups();
  renderErrors(data.errors);

  // Atualiza prompt/modelo Perplexity com o novo minDays/cotação
  try {
    recomputeTemplatePrompt();
  } catch (e) {
    // ignora se elementos ainda não estiverem no DOM
  }
}

// Renderiza campos de config (prazo mínimo e cotação)
function renderConfigUI() {
  const presetSelect = document.getElementById("preset-min-days");
  const customInput = document.getElementById("custom-min-days");

  // A cotação de USD foi removida da UI, então não tentamos mais achar o input
  // const usdInput = document.getElementById("usd-brl");
  // if (usdInput) usdInput.value = state.usdBrl.toString();

  if (!presetSelect || !customInput) return;

  // Descobre qual preset bate com o valor atual
  let presetLabel = state.minDaysPreset;
  const mapPreset = { 7: "7 dias", 10: "10 dias", 15: "15 dias" };
  const reverseMap = {
    "7 dias": "7",
    "10 dias": "10",
    "15 dias": "15",
    Personalizado: "custom",
  };

  if (!["7 dias", "10 dias", "15 dias"].includes(presetLabel)) {
    const candidate = parseInt(presetLabel, 10);
    if (mapPreset[candidate]) {
      presetLabel = mapPreset[candidate];
    } else {
      presetLabel = "10 dias";
    }
  }

  const presetValue = reverseMap[presetLabel] || "10";
  presetSelect.value = presetValue;
  if (presetValue === "custom") {
    customInput.classList.remove("hidden");
    customInput.value = state.minDays.toString();
  } else {
    customInput.classList.add("hidden");
    customInput.value = state.minDays.toString();
  }
}

// Renderiza lista de checkboxes de grupos
function renderGroupsCheckboxes() {
  const container = document.getElementById("groups-checkboxes");
  if (!container) return;
  container.innerHTML = "";

  // Grupos oficiais
  const OFFICIAL_GROUPS = [
    "Governo/Multilaterais",
    "Fundações e Prêmios",
    "América Latina/Brasil"
  ];

  for (const g of OFFICIAL_GROUPS) {
    const display = g.replace(/\s*\/\s*/g, '/');
    const id = `grp-${g.replace(/[^a-z0-9]/gi, "_")}`;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
      <label>
        <input type="checkbox" id="${id}" data-group="${g}" checked />
        ${display}
      </label>
    `;
    container.appendChild(wrapper);
  }
}

// ---------- Renderização de grupos / itens ----------

async function renderGroups() {
  const container = document.getElementById("groups-container");
  if (!container) return;
  container.innerHTML = "";

  for (const g of state.availableGroups) {
    // Evita criar o cartão do grupo 'Filantropia' também
    if (/filantrop/i.test(g)) continue;
    // Formata apenas para exibição: remove espaços antes/depois de '/'
    const display = g.replace(/\s*\/\s*/g, '/');

    const groupDiv = document.createElement("div");
    groupDiv.className = "group-card";
    const statusOptions = state.statusChoices || [];
    const statusSelectId = `status-filter-${g.replace(/[^a-z0-9]/gi, "_")}`;

    groupDiv.innerHTML = `
      <div class="group-header">
        <div class="group-header-main">
          <button class="group-toggle" data-group="${g}" aria-expanded="true">▾</button>
          <h3>${display}</h3>
        </div>
        <div class="group-toolbar">
          <button class="primary" data-action="save" data-group="${g}">💾 Salvar alterações</button>
          <button class="danger" data-action="delete" data-group="${g}">🗑️ Apagar selecionados</button>
          <label>Filtro
            <select id="${statusSelectId}" data-group="${g}">
              <option value="Todos">Todos</option>
              ${statusOptions
        .map((s) => `<option value="${s}">${s}</option>`)
        .join("")}
            </select>
          </label>
        </div>
      </div>
      <div class="group-body" data-group-body="${g}">
        <em>Carregando itens...</em>
      </div>
    `;
    container.appendChild(groupDiv);

    // Carrega itens para esse grupo
    const statusSelect = groupDiv.querySelector(`#${statusSelectId}`);
    await loadGroupItems(g, statusSelect.value);

    // Liga eventos dos botões / selects
    const saveBtn = groupDiv.querySelector('button[data-action="save"]');
    const delBtn = groupDiv.querySelector('button[data-action="delete"]');
    const toggleBtn = groupDiv.querySelector(".group-toggle");
    const groupBody = groupDiv.querySelector(".group-body");

    if (saveBtn) {
      saveBtn.addEventListener("click", () => saveGroupChanges(g));
    }
    if (delBtn) {
      delBtn.addEventListener("click", () => deleteSelectedInGroup(g));
    }
    if (statusSelect) {
      statusSelect.addEventListener("change", () =>
        loadGroupItems(g, statusSelect.value)
      );
    }
    if (toggleBtn && groupBody) {
      toggleBtn.addEventListener("click", () => {
        const isHidden = groupBody.classList.toggle("hidden");
        const expanded = !isHidden;
        toggleBtn.setAttribute("aria-expanded", expanded ? "true" : "false");
        toggleBtn.textContent = expanded ? "▾" : "▸";
      });
    }
  }
}

// Carrega itens de um grupo e desenha cards
async function loadGroupItems(group, statusFilter) {
  const bodyDiv = document.querySelector(
    `[data-group-body="${CSS.escape(group)}"]`
  );
  if (!bodyDiv) return;
  bodyDiv.innerHTML = "<em>Carregando itens...</em>";

  const params = new URLSearchParams({ group });
  if (statusFilter && statusFilter !== "Todos") {
    params.set("status", statusFilter);
  }

  try {
    const data = await apiGet(`/api/items?${params.toString()}`);
    const itemsData = data.items;
    renderErrors(data.errors);
    const sources = itemsData.sources || [];
    const total = itemsData.items_count || 0;

    if (total === 0) {
      bodyDiv.innerHTML = "<em>Sem itens para este grupo.</em>";
      return;
    }

    bodyDiv.innerHTML = "";
    // Helpers de filtro
    const parseBrl = (v) => {
      if (v == null) return NaN;
      if (typeof v === "number") return v;
      const s = String(v).replace(/\./g, "").replace(/,/g, ".").replace(/[^\d.]/g, "");
      const n = parseFloat(s);
      return isNaN(n) ? NaN : n;
    };
    const extractValue = (it) => {
      // tenta vários campos comuns
      const cand =
        it.value_brl ?? it.value ?? it.amount_brl ?? it.amount ?? null;
      const n = parseBrl(cand);
      return isNaN(n) ? null : n;
    };

    for (const src of sources) {
      const sDiv = document.createElement("div");
      sDiv.className = "source-card";
      const rawItems = src.items || [];
      const filtered = rawItems; // NÃO filtra aqui; só na UI
      const count = filtered.length;
      sDiv.innerHTML = `
        <div class="source-header">
          <strong>${src.source}</strong> — ${count} itens
        </div>
        <div class="source-body"></div>
      `;
      const sb = sDiv.querySelector(".source-body");
      for (const it of filtered) {
        const card = document.createElement("div");
        card.className = "item-card";
        card.dataset.uid = it.uid;
        // guarda dados para os filtros (se vierem do backend)
        if (it.deadline_iso) card.dataset.deadline = String(it.deadline_iso).slice(0, 10);
        // tenta mapear possíveis campos de valor (use o que você realmente tiver)
        const amt = it.value_brl ?? it.amount_brl ?? it.value ?? null;
        if (amt !== null && amt !== undefined) card.dataset.amount = String(amt);

        // Garantia: nunca deixar o card com fundo preto/escuro por causa do statusBg
        // (corrige o item 4.5 do seu pedido)
        const cand = (state.statusBg[it.status] || "").toLowerCase();
        const isDark =
          cand === "#000" || cand === "#000000" ||
          cand === "#111" || cand === "#111111" ||
          cand === "black" || cand === "rgb(0,0,0)";
        const bg = (!cand || isDark) ? "#f8f9ff" : cand;
        card.style.backgroundColor = bg;

        const seenChecked =
          String(it.seen || "").trim().toLowerCase() in {
            "1": 1,
            true: 1,
            sim: 1,
            yes: 1,
            "✅": 1,
          };

        const dnsChecked = !!it.do_not_show;

        card.innerHTML = `
          <div class="item-row">
            <div>
              <div class="item-title">
                ${it.title || "(sem título)"}
              </div>
              <div class="item-caption">
                <a href="${it.link}" target="_blank">${it.link}</a><br/>
                ${it.agency || ""} • ${it.region || ""}
              </div>
            </div>
            <div class="item-field">
              <label>Prazo</label>
              <div>${(it.deadline_iso || "").slice(0, 10) || "—"}</div>
            </div>
            <div class="item-field">
              <label>Status</label>
              <select class="field-status">
                ${state.statusChoices
            .map(
              (s) =>
                `<option value="${s}" ${s === it.status ? "selected" : ""
                }>${s}</option>`
            )
            .join("")}
              </select>
            </div>
            <div class="item-field">
              <label>Observações</label>
              <textarea class="field-notes">${it.notes || ""}</textarea>
            </div>
            <div class="item-field">
              <label>Flags</label>
              <div>
                <label>
                  <input type="checkbox" class="field-delete" />
                  Apagar
                </label><br/>
                <label>
                  <input type="checkbox" class="field-dns" ${dnsChecked ? "checked" : ""
          } />
                  Não mostrar novamente
                </label><br/>
                <label>
                  <input type="checkbox" class="field-seen" ${seenChecked ? "checked" : ""
          } />
                  Visto
                </label>
              </div>
            </div>
          </div>
        `;
        sb.appendChild(card);

        // Atualiza cor e salva na planilha ao mudar o status
        const statusSelect = card.querySelector(".field-status");
        if (statusSelect) {
          statusSelect.addEventListener("change", async () => {
            const newStatus = statusSelect.value;
            // Reaplica a mesma regra anti-preto quando o status muda
            const cand2 = (state.statusBg[newStatus] || "").toLowerCase();
            const isDark2 =
              cand2 === "#000" || cand2 === "#000000" ||
              cand2 === "#111" || cand2 === "#111111" ||
              cand2 === "black" || cand2 === "rgb(0,0,0)";
            const newBg = (!cand2 || isDark2) ? "#f8f9ff" : cand2;
            card.style.backgroundColor = newBg;

            const notesEl = card.querySelector(".field-notes");
            const dnsChk = card.querySelector(".field-dns");
            const seenChk = card.querySelector(".field-seen");

            try {
              const data = await apiPost("/api/items/update", {
                updates: [
                  {
                    uid: card.dataset.uid,
                    status: newStatus,
                    notes: notesEl ? notesEl.value : "",
                    do_not_show: dnsChk ? dnsChk.checked : false,
                    seen: seenChk ? seenChk.checked : false,
                  },
                ],
              });
              renderErrors(data.errors);
            } catch (err) {
              alert("Erro ao atualizar status: " + err);
            }
          });
        }
      }
      bodyDiv.appendChild(sDiv);
    }
    // aplica filtros atuais nos itens recém-renderizados
    filterVisibleItems();

  } catch (e) {
    bodyDiv.innerHTML = `<span style="color:#f88">Erro ao carregar itens: ${e}</span>`;
  }
}

// Salva alterações de todos os itens de um grupo
async function saveGroupChanges(group) {
  const bodyDiv = document.querySelector(
    `[data-group-body="${CSS.escape(group)}"]`
  );
  if (!bodyDiv) return;

  const cards = bodyDiv.querySelectorAll(".item-card");
  const updates = [];
  cards.forEach((card) => {
    const uid = card.dataset.uid;
    if (!uid) return;
    const statusSel = card.querySelector(".field-status");
    const notesEl = card.querySelector(".field-notes");
    const dnsChk = card.querySelector(".field-dns");
    const seenChk = card.querySelector(".field-seen");
    updates.push({
      uid,
      status: statusSel ? statusSel.value : "pendente",
      notes: notesEl ? notesEl.value : "",
      do_not_show: dnsChk ? dnsChk.checked : false,
      seen: seenChk ? seenChk.checked : false,
    });
  });

  if (updates.length === 0) return;

  const btns = document.querySelectorAll(
    `.group-card button[data-action="save"][data-group="${CSS.escape(group)}"]`
  );
  btns.forEach((b) => (b.disabled = true));
  try {
    const data = await apiPost("/api/items/update", { updates });
    renderErrors(data.errors);
    alert("Alterações salvas.");
    // Recarrega itens para refletir cores/status
    const statusSelect = document.querySelector(
      `#status-filter-${group.replace(/[^a-z0-9]/gi, "_")}`
    );
    const status = statusSelect ? statusSelect.value : "Todos";
    await loadGroupItems(group, status);
  } catch (e) {
    alert("Falha ao salvar: " + e);
  } finally {
    btns.forEach((b) => (b.disabled = false));
  }
}

// Apaga itens selecionados para um grupo
async function deleteSelectedInGroup(group) {
  const bodyDiv = document.querySelector(
    `[data-group-body="${CSS.escape(group)}"]`
  );
  if (!bodyDiv) return;

  const cards = bodyDiv.querySelectorAll(".item-card");
  const uids = [];
  cards.forEach((card) => {
    const uid = card.dataset.uid;
    const delChk = card.querySelector(".field-delete");
    if (uid && delChk && delChk.checked) {
      uids.push(uid);
    }
  });

  if (uids.length === 0) {
    alert("Nenhum item selecionado para apagar.");
    return;
  }

  if (!confirm(`Remover ${uids.length} item(ns)?`)) {
    return;
  }

  try {
    const data = await apiPost("/api/items/delete", { uids });
    renderErrors(data.errors);
    alert(`Removidos ${data.result.deleted} item(ns).`);
    const statusSelect = document.querySelector(
      `#status-filter-${group.replace(/[^a-z0-9]/gi, "_")}`
    );
    const status = statusSelect ? statusSelect.value : "Todos";
    await loadGroupItems(group, status);
  } catch (e) {
    alert("Erro ao apagar: " + e);
  }
}

// ---------- Botões principais de coleta / config ----------

async function handleSaveMinDays() {
  const presetSelect = document.getElementById("preset-min-days");
  const customInput = document.getElementById("custom-min-days");

  // Input de USD removido da UI, não precisamos mais lê-lo
  // const usdInput = document.getElementById("usd-brl");

  let minDays;
  let presetLabel;
  if (presetSelect.value === "custom") {
    minDays = parseInt(customInput.value || "21", 10);
    presetLabel = "Personalizado";
  } else {
    minDays = parseInt(presetSelect.value, 10);
    presetLabel = `${minDays} dias`;
  }

  const updates = [
    { key: "MIN_DAYS", value: String(minDays) },
    { key: "MIN_DAYS_PRESET", value: presetLabel },
  ];

  // A cotação USD ainda existe no state, mas não é mais atualizada por aqui
  // const usdVal = parseFloat(usdInput.value || "5.2");
  // if (!isNaN(usdVal)) {
  //   updates.push({ key: "USD_BRL", value: String(usdVal) });
  // }

  try {
    const data = await apiPost("/api/config", { updates });
    state.config = data.config.config;
    state.minDays = minDays;
    state.minDaysPreset = presetLabel;
    // state.usdBrl = usdVal; // Não atualizamos mais
    renderErrors(data.errors);
    alert("Configuração de prazo atualizada."); // Mensagem alterada
  } catch (e) {
    alert("Erro ao salvar configuração: " + e);
  }
}

// Coleta: botão principal (agora com progresso, cancelamento e execução por grupo)
// COLETA UNIVERSAL - Usa IA (Perplexity) para extrair editais
// Filtra pelos grupos selecionados nos checkboxes
async function handleRunCollect() {
  const btn = document.getElementById("btn-run-collect");
  const resultDiv = document.getElementById("collect-result");
  const progressOverlay = document.getElementById("collect-progress");
  const progressBar = document.getElementById("collect-progress-bar");
  const progressLabel = document.getElementById("collect-progress-label");
  if (!btn || !resultDiv) return;

  // Coleta grupos selecionados
  const selectedGroups = [];
  document
    .querySelectorAll("#groups-checkboxes input[type=checkbox]")
    .forEach((chk) => {
      if (chk.checked) {
        selectedGroups.push(chk.dataset.group);
      }
    });

  if (selectedGroups.length === 0) {
    resultDiv.innerHTML = `
      <div style="padding:20px;background:rgba(255,209,102,0.2);border-radius:8px;border:1px solid rgba(255,209,102,0.4);">
        <strong>⚠️ Nenhum grupo selecionado!</strong><br/><br/>
        Selecione ao menos um grupo para executar a coleta.
      </div>
    `;
    return;
  }

  // Verifica se há links cadastrados
  if (!linksState.links || linksState.links.length === 0) {
    resultDiv.innerHTML = `
      <div style="padding:20px;background:rgba(239,71,111,0.2);border-radius:8px;border:1px solid rgba(239,71,111,0.4);">
        <strong>⚠️ Nenhum link cadastrado!</strong><br/><br/>
        Clique em "CADASTRAR LINKS" para adicionar links.
      </div>
    `;
    return;
  }

  // Filtra links ativos E que pertencem aos grupos selecionados
  const activeLinks = linksState.links.filter(l => {
    if (l.ativo !== "true") return false;
    // Normaliza grupo do link para comparação
    const linkGroup = (l.grupo || "").replace(/\s*\/\s*/g, "/").trim();
    return selectedGroups.some(sg => {
      const selGroup = sg.replace(/\s*\/\s*/g, "/").trim();
      return linkGroup === selGroup;
    });
  });

  if (activeLinks.length === 0) {
    resultDiv.innerHTML = `
      <div style="padding:20px;background:rgba(255,209,102,0.2);border-radius:8px;border:1px solid rgba(255,209,102,0.4);">
        <strong>⚠️ Nenhum link ativo nos grupos selecionados!</strong><br/><br/>
        Grupos selecionados: ${selectedGroups.join(", ")}<br/>
        Clique em "CADASTRAR LINKS" para gerenciar seus links.
      </div>
    `;
    return;
  }

  // Economia de créditos: ignora links já executados (last_run preenchido)
  const eligibleLinks = activeLinks.filter((l) => !(l.last_run || "").trim());
  if (eligibleLinks.length === 0) {
    resultDiv.innerHTML = `
      <div style="padding:20px;background:rgba(255,209,102,0.2);border-radius:8px;border:1px solid rgba(255,209,102,0.4);">
        <strong>⚠️ Nenhum link disponível para nova execução.</strong><br/><br/>
        Todos os links ativos dos grupos selecionados já foram executados.<br/>
        Se precisar reprocessar algum, limpe o campo de última execução desse link.
      </div>
    `;
    return;
  }

  collectCancelRequested = false;
  resultDiv.innerHTML = "";
  btn.disabled = true;

  setManageInteractivity(true);
  // Lê o limite de links do seletor (0 = todos)
  const maxLinks = parseInt(document.getElementById("links-limit")?.value || "0", 10);
  const effectiveCount = (maxLinks > 0 && maxLinks < eligibleLinks.length) ? maxLinks : eligibleLinks.length;

  if (progressOverlay && progressBar && progressLabel) {
    progressOverlay.classList.remove("hidden");
    progressBar.max = 100;
    progressBar.value = 0;
    progressLabel.textContent = `Iniciando coleta de ${effectiveCount} link(s) em ${selectedGroups.length} grupo(s)…`;
  }

  let totalExtracted = 0;
  const summaryLines = [];

  try {
    if (progressLabel) {
      progressLabel.textContent = `🤖 Processando ${effectiveCount} link(s) via IA…`;
    }
    if (progressBar) {
      progressBar.value = 10;
    }

    // Obtém valor máximo do filtro, se configurado
    const maxValue = state.valueMax || null;

    const data = await apiPost("/api/collect/universal", {
      min_days: state.minDays,
      max_value: maxValue,
      model_id: "sonar", // Modelo mais barato e rápido
      groups: selectedGroups, // Filtra pelos grupos selecionados
      max_links: maxLinks,    // 0 = todos; >0 = limita a N links
      skip_already_run: true,
    });

    if (progressBar) {
      progressBar.value = 90;
    }

    const res = data.result || {};
    renderErrors(data.errors);

    // Atualiza contador de custo
    if (res.cost) {
      updateCostTracker(res.cost);
    }

    totalExtracted = res.items_saved || res.all_items?.length || 0;

    // Estatísticas por grupo
    const successLines = [];
    const errorLines = [];

    if (res.stats_by_group) {
      for (const [grupo, stats] of Object.entries(res.stats_by_group)) {
        successLines.push({
          type: 'success',
          text: `<strong>${grupo}</strong>: ${stats.total} editais de ${stats.links} link(s)`
        });
      }
    }

    // Erros específicos
    if (res.errors && res.errors.length > 0) {
      for (const err of res.errors) {
        const shortUrl = err.url.length > 50 ? err.url.substring(0, 50) + "…" : err.url;
        errorLines.push({
          type: 'error',
          text: `❌ ${shortUrl}: ${err.error}`
        });
      }
    }

    if (progressBar) {
      progressBar.value = 100;
    }

    // Recarrega links para atualizar status
    await loadLinks();

    // Monta resultado
    const cancelou = collectCancelRequested;
    const headerLine = cancelou
      ? "⚠️ Coleta cancelada."
      : "✅ Coleta concluída!";

    // Monta custo formatado
    const costInfo = res.cost ? `
      <div style="margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.1);">
        💰 <strong>Custo desta coleta:</strong> R$ ${res.cost.cost_brl.toFixed(4).replace('.', ',')} 
        <span style="color:#888;">(${res.cost.total_tokens.toLocaleString('pt-BR')} tokens)</span>
      </div>
    ` : '';

    const skippedAlreadyRun = res.skipped_already_run || 0;

    let resultHtml = `
      <div style="padding:20px;background:rgba(6,214,160,0.15);border-radius:8px;border:1px solid rgba(6,214,160,0.3);margin-bottom:16px;">
        <strong style="font-size:1.1rem;">${headerLine}</strong><br/><br/>
        📊 <strong>Editais extraídos:</strong> ${totalExtracted}<br/>
        🔗 <strong>Links processados:</strong> ${res.processed || effectiveCount} de ${res.total || effectiveCount}
        ${skippedAlreadyRun > 0 ? `<br/>⏭️ <strong>Links pulados (já executados):</strong> ${skippedAlreadyRun}` : ""}
        ${costInfo}
      </div>
    `;

    // Renderiza cards dismissíveis
    const allCards = [...successLines, ...errorLines];
    if (allCards.length > 0) {
      resultHtml += `
        <div id="collect-details-container" style="padding:16px;background:rgba(255,255,255,0.05);border-radius:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <strong>📋 Detalhes por grupo:</strong>
            <button onclick="clearAllCollectCards()" style="background:rgba(239,71,111,0.2);border:1px solid rgba(239,71,111,0.4);color:#EF476F;padding:4px 12px;border-radius:4px;cursor:pointer;font-size:0.85rem;">
              ✕ Limpar Todos
            </button>
          </div>
          <div id="collect-cards-list">
            ${allCards.map((card, idx) => `
              <div class="collect-card ${card.type}" id="collect-card-${idx}" style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;margin-bottom:6px;border-radius:4px;${card.type === 'error' ? 'background:rgba(239,71,111,0.1);border:1px solid rgba(239,71,111,0.3);' : 'background:rgba(6,214,160,0.1);border:1px solid rgba(6,214,160,0.3);'}">
                <span style="${card.type === 'error' ? 'color:#EF476F;' : ''}">${card.text}</span>
                <button onclick="dismissCollectCard(${idx})" style="background:transparent;border:none;color:${card.type === 'error' ? '#EF476F' : '#06D6A0'};cursor:pointer;font-size:1.2rem;padding:0 4px;opacity:0.7;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.7'">✕</button>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    resultDiv.innerHTML = resultHtml;

    await renderGroups();
  } catch (e) {
    resultDiv.innerHTML = `
      <div style="padding:20px;background:rgba(239,71,111,0.2);border-radius:8px;border:1px solid rgba(239,71,111,0.4);">
        <strong>❌ Erro na coleta:</strong><br/><br/>
        ${e.message || e}
      </div>
    `;
  } finally {
    btn.disabled = false;
    setManageInteractivity(false);
    if (progressOverlay) {
      progressOverlay.classList.add("hidden");
    }
  }
}

// Funções para dismiss dos cards de resultado
function dismissCollectCard(idx) {
  const card = document.getElementById(`collect-card-${idx}`);
  if (card) {
    card.style.transition = 'opacity 0.3s, transform 0.3s';
    card.style.opacity = '0';
    card.style.transform = 'translateX(20px)';
    setTimeout(() => {
      card.remove();
      // Se não há mais cards, esconde o container
      const list = document.getElementById('collect-cards-list');
      if (list && list.children.length === 0) {
        const container = document.getElementById('collect-details-container');
        if (container) container.remove();
      }
    }, 300);
  }
}

function clearAllCollectCards() {
  const container = document.getElementById('collect-details-container');
  if (container) {
    container.style.transition = 'opacity 0.3s';
    container.style.opacity = '0';
    setTimeout(() => container.remove(), 300);
  }
}

// Recarregar apenas da planilha
async function handleRefreshItems() {
  await renderGroups();
}

// Limpar todos os itens
async function handleClearAll() {
  if (!confirm("Tem certeza que deseja limpar TODOS os itens?")) {
    return;
  }
  try {
    const data = await apiPost("/api/items/clear", {});
    renderErrors(data.errors);
    await renderGroups();
    alert("Planilha 'items' limpa (somente cabeçalho mantido).");
  } catch (e) {
    alert("Erro ao limpar itens: " + e);
  }
}

// Diagnóstico: abre em nova janela, com barra de progresso e cancelamento
async function handleRunDiag() {
  const container = document.getElementById("diag-results");
  const progressOverlay = document.getElementById("diag-progress");
  const progressBar = document.getElementById("diag-progress-bar");
  const progressLabel = document.getElementById("diag-progress-label");
  if (!container) return;

  container.innerHTML = "";
  setManageInteractivity(true);
  if (progressOverlay && progressLabel) {
    progressOverlay.classList.remove("hidden");
    if (progressBar) {
      progressBar.removeAttribute("value"); // modo indeterminado
    }
    progressLabel.textContent = "Rodando diagnóstico dos providers…";
  }

  diagAbortController = new AbortController();

  try {
    const data = await apiPost(
      "/api/diag/providers",
      {},
      { signal: diagAbortController.signal }
    );
    const diag = data.diag;
    renderErrors(data.errors);

    container.innerHTML =
      "<em>Diagnóstico concluído. O resultado foi aberto em uma nova janela.</em>";

    // Abre (ou reaproveita) uma nova janela para exibir os resultados
    if (!diagWindow || diagWindow.closed) {
      diagWindow = window.open("", "_blank");
    }
    if (!diagWindow) {
      // popup bloqueado
      return;
    }

    diagWindow.document.open();
    diagWindow.document.write(`
      <!DOCTYPE html>
      <html lang="pt-BR">
        <head>
          <meta charset="UTF-8" />
          <title>Diagnóstico dos providers</title>
          <link rel="stylesheet" href="/static/styles.css" />
        </head>
        <body class="app-main">
          <h1>🔬 Diagnóstico dos providers</h1>
          <section id="diag-window-content"></section>
        </body>
      </html>
    `);
    diagWindow.document.close();

    const contentDiv =
      diagWindow.document.getElementById("diag-window-content");
    if (!contentDiv) {
      return;
    }

    const rows = diag.rows || [];
    const logs = diag.logs || [];

    let html = "<h3>Providers</h3>";
    if (!rows.length) {
      html += "<p><em>Nenhum provider retornado.</em></p>";
    } else {
      html += `<table class="diag-table">
        <thead>
          <tr>
            <th>Grupo</th><th>Fonte</th><th>Itens</th><th>Tempo (s)</th><th>Erro</th><th>Hint</th>
          </tr>
        </thead>
        <tbody>
          ${rows
          .map(
            (r) => `
            <tr>
              <td>${r.Grupo}</td>
              <td>${r.Fonte}</td>
              <td>${r.Itens}</td>
              <td>${r["Tempo (s)"]}</td>
              <td>${r.Erro || ""}</td>
              <td>${r.Hint || ""}</td>
            </tr>
          `
          )
          .join("")}
        </tbody>
      </table>`;
    }

    if (logs.length) {
      html += "<h3>Logs (últimas linhas)</h3><pre>";
      for (const row of logs.slice(1)) {
        html += row.join(" | ") + "\n";
      }
      html += "</pre>";
    }

    contentDiv.innerHTML = html;
  } catch (e) {
    if (e.name === "AbortError") {
      container.innerHTML =
        "<em>Diagnóstico cancelado pelo usuário.</em>";
    } else {
      container.innerHTML = `<span style="color:#f88">Erro no diagnóstico: ${e}</span>`;
    }
  } finally {
    setManageInteractivity(false);
    if (progressOverlay) {
      progressOverlay.classList.add("hidden");
    }
    diagAbortController = null;
  }
}

// ---------- Perplexity UI ----------

function approxTokens(text) {
  if (!text) return 0;
  return Math.max(1, Math.floor(text.length / 4));
}

function getPricingForModel(modelId) {
  const row = document.querySelector(
    `.pplx-cost-row[data-model="${CSS.escape(modelId)}"]`
  );
  if (!row) {
    return { pin: 1, pout: 1 };
  }
  const inInput = row.querySelector("input[id^='cost-in']");
  const outInput = row.querySelector("input[id^='cost-out']");
  const pin = parseFloat((inInput && inInput.value) || "1");
  const pout = parseFloat((outInput && outInput.value) || "1");
  return { pin, pout };
}

function updatePplxMetrics(promptText, extraTokensFromLink = 0) {
  const modelSelect = document.getElementById("pplx-model");
  const maxOutInput = document.getElementById("pplx-max");

  // Input de USD removido, usamos o valor do state
  // const usdInput = document.getElementById("usd-brl");
  const usdBrl = state.usdBrl; // Pega o valor default

  if (!modelSelect || !maxOutInput) return;

  const modelId = modelSelect.value;
  const { pin, pout } = getPricingForModel(modelId);

  const maxOut = parseInt(maxOutInput.value || "900", 10);
  // const usdBrl = parseFloat(usdInput.value || "5.2");

  const tinPrompt = approxTokens(promptText);
  const tin = tinPrompt + (extraTokensFromLink || 0);

  const custoUsd =
    (tin / 1_000_000.0) * pin + (maxOut / 1_000_000.0) * pout;
  const custoBrl = custoUsd * usdBrl;

  const elIn = document.getElementById("metric-tokens-in");
  const elUsd = document.getElementById("metric-cost-usd");
  const elBrl = document.getElementById("metric-cost-brl");
  if (elIn) elIn.innerText = tin.toString();
  if (elUsd) elUsd.innerText = custoUsd.toFixed(4);
  if (elBrl) elBrl.innerText = custoBrl.toFixed(4);
}

// Gera o prompt final com base na opção Modelo + tema + região + prazo + link
function recomputeTemplatePrompt() {
  const tpl = document.getElementById("pplx-tpl");
  const temaInput = document.getElementById("pplx-tema");
  const regInput = document.getElementById("pplx-reg");
  const diasInput = document.getElementById("pplx-dias");
  const linkInput = document.getElementById("pplx-edital-link");
  const outTa = document.getElementById("pplx-tpl-output");

  if (!outTa || !tpl) return;

  const tema = (temaInput && temaInput.value) || "";
  const reg = (regInput && regInput.value) || "";
  const dias = (diasInput && diasInput.value) || state.minDays;
  const link = (linkInput && linkInput.value) || "";

  let txt = "";
  if (tpl.value === "listar") {
    txt =
      `Liste oportunidades de financiamento (editais) relevantes para ${tema}, ` +
      `com foco em ${reg}, prazo mínimo de ${dias} dias. ` +
      `Considere também o contexto do edital (se aplicável) no seguinte link: ${link || "[nenhum link fornecido]"}. ` +
      `Traga links oficiais e resuma os requisitos principais.`;
  } else if (tpl.value === "resumo") {
    txt =
      `Resuma o edital disponível no seguinte link: ${link || "[cole aqui o link do edital]"}. ` +
      `Explique em português claro: elegibilidade, prazos, valores, critérios de seleção e documentos necessários. ` +
      `Organize a resposta em bullet points e inclua o link novamente no final.`;
  } else {
    txt =
      `Compare o edital do seguinte link principal: ${link || "[cole aqui o link do edital]"} ` +
      `com outras chamadas semelhantes que você encontrar para ${tema} em ${reg}. ` +
      `Destaque diferenças em foco, elegibilidade, prazos e montantes. ` +
      `Produza uma tabela comparativa e bullets com as principais conclusões.`;
  }

  outTa.value = txt;
  updatePplxMetrics(txt, state.linkTokens);
}

function getPplxPromptAndModeLabel() {
  const tpl = document.getElementById("pplx-tpl");
  const outTa = document.getElementById("pplx-tpl-output");
  const tplVal = tpl ? tpl.value : "listar";
  let label;
  if (tplVal === "listar") {
    label = "Modelos: listar oportunidades";
  } else if (tplVal === "resumo") {
    label = "Modelos: resumo de edital";
  } else {
    label = "Modelos: comparar chamadas";
  }
  return {
    prompt: outTa ? outTa.value : "",
    modeLabel: label,
  };
}

// Botão que conta tokens do conteúdo do link (PDF/HTML/etc) via backend
async function handleCountTokensFromLink() {
  const linkInput = document.getElementById("pplx-edital-link");
  const display = document.getElementById("pplx-link-tokens");
  if (!linkInput || !display) return;

  const url = (linkInput.value || "").trim();
  if (!url) {
    alert("Insira o link do edital primeiro.");
    return;
  }

  display.textContent = "Calculando…";

  try {
    const data = await apiPost("/api/perplexity/count_tokens", { url });
    renderErrors(data.errors, "pplx-errors");

    if (!data.ok) {
      display.textContent = "Não foi possível calcular";
      alert("Erro ao calcular tokens: " + (data.error || "desconhecido"));
      return;
    }

    const tokens = data.tokens || 0;
    state.linkTokens = tokens;
    display.textContent = `${tokens} tokens (aprox.)`;

    const { prompt } = getPplxPromptAndModeLabel();
    updatePplxMetrics(prompt, state.linkTokens);
  } catch (e) {
    display.textContent = "Erro";
    alert("Erro ao calcular tokens: " + e);
  }
}

async function handleRunPerplexity() {
  const btn = document.getElementById("btn-pplx-run");
  if (!btn) return;

  const { prompt, modeLabel } = getPplxPromptAndModeLabel();
  if (!prompt.trim()) {
    alert("Preencha o modelo de prompt / link antes de rodar a pesquisa.");
    return;
  }

  const modelSelect = document.getElementById("pplx-model");
  const tempInput = document.getElementById("pplx-temp");
  const maxOutInput = document.getElementById("pplx-max");
  const saveChk = document.getElementById("pplx-save");
  // Input de USD removido
  // const usdInput = document.getElementById("usd-brl");
  const editalLinkInput = document.getElementById("pplx-edital-link");

  const modeloApi = modelSelect.value;
  const { pin, pout } = getPricingForModel(modeloApi);

  const temp = parseFloat(tempInput.value || "0.2");
  const maxOut = parseInt(maxOutInput.value || "900", 10);
  const usdBrl = state.usdBrl; // Pega o valor default
  const save = !!saveChk.checked;
  const editalLink = editalLinkInput ? editalLinkInput.value || null : null;

  // Atualiza métricas antes de enviar (incluindo tokens do link, se já calculados)
  updatePplxMetrics(prompt, state.linkTokens);

  btn.disabled = true;
  const summaryDiv = document.getElementById("pplx-summary");
  const linksUl = document.getElementById("pplx-links");
  summaryDiv.innerHTML = "Consultando Perplexity…";
  linksUl.innerHTML = "";

  try {
    const data = await apiPost("/api/perplexity/search", {
      prompt,
      modelo_api: modeloApi,
      modo_label: modeLabel,
      temperature: temp,
      max_tokens: maxOut,
      pricing_in: pin,
      pricing_out: pout,
      usd_brl: usdBrl,
      save,
      link_tokens: state.linkTokens || 0,
      edital_link: editalLink,
    });
    const res = data.result;
    renderErrors(data.errors, "pplx-errors");

    if (res.error) {
      summaryDiv.innerHTML = `<span style="color:#f88">${res.error}</span>`;
      return;
    }

    summaryDiv.innerText = res.summary || "—";

    linksUl.innerHTML = "";
    (res.links || []).forEach((u) => {
      const li = document.createElement("li");
      li.innerHTML = `<a href="${u}" target="_blank">${u}</a>`;
      linksUl.appendChild(li);
    });

    // Se o backend retornar tokens/custos reais, sobrepõe as métricas
    if (typeof res.tokens_in === "number") {
      const elIn = document.getElementById("metric-tokens-in");
      if (elIn) elIn.innerText = res.tokens_in.toString();
    }
    if (typeof res.estimated_cost_usd === "number") {
      const elUsd = document.getElementById("metric-cost-usd");
      if (elUsd) elUsd.innerText = res.estimated_cost_usd.toFixed(4);
    }
    if (typeof res.estimated_cost_brl === "number") {
      const elBrl = document.getElementById("metric-cost-brl");
      if (elBrl) elBrl.innerText = res.estimated_cost_brl.toFixed(4);
    }
  } catch (e) {
    summaryDiv.innerHTML = `<span style="color:#f88">Erro: ${e}</span>`;
  } finally {
    btn.disabled = false;
  }
}

// ---------- Tabs ----------
function activateTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === `tab-${tabName}`);
  });
  // quando muda de aba, ajusta o botão da sidebar conforme a tela atual
  updateSidebarForTab(tabName);
}

// --- NOVO: quando estiver na aba Perplexity, o botão da esquerda vira "PÁGINA INICIAL"
function updateSidebarForTab(tabName) {
  // botões com data-perplexity-nav nas DUAS sidebars
  const btnManage = document.querySelector('#tab-manage .collect-sidebar [data-perplexity-nav]');
  const btnPplx = document.querySelector('#tab-perplexity .collect-sidebar [data-perplexity-nav]');

  // helper para limpar e aplicar handler
  const resetBtn = (el) => {
    if (!el) return el;
    const clone = el.cloneNode(true);

    // CORREÇÃO (aplicada da nossa conversa anterior):
    // Remove o atributo 'onclick' do HTML original.
    // Isso evita o conflito entre o 'onclick' (que definia o hash)
    // e o 'addEventListener' (que definia o href='/').
    clone.removeAttribute("onclick");

    el.parentNode.replaceChild(clone, el);
    return clone;
  };

  // estado: NA ABA PERPLEXITY -> botão vira "PÁGINA INICIAL" e leva para "/"
  if (tabName === 'perplexity' && btnPplx) {
    const b = resetBtn(btnPplx);
    b.textContent = 'PÁGINA INICIAL';
    b.addEventListener('click', () => { window.location.href = '/'; });
  }
  // fora da aba Perplexity -> ambos mostram "PESQUISA NO PERPLEXITY" e abrem a aba
  if (tabName !== 'perplexity') {
    if (btnManage) {
      const b1 = resetBtn(btnManage);
      b1.textContent = 'PESQUISA NO PERPLEXITY';
      b1.addEventListener('click', () => {
        activateTab('perplexity');
        history.replaceState(null, '', '#perplexity');
      });
    }
    if (btnPplx) {
      const b2 = resetBtn(btnPplx);
      b2.textContent = 'PESQUISA NO PERPLEXITY';
      b2.addEventListener('click', () => {
        activateTab('perplexity');
        history.replaceState(null, '', '#perplexity');
      });
    }
  }
}

function setupTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      activateTab(btn.dataset.tab);
      // atualiza o hash para permitir deep-link
      history.replaceState(null, "", `#${btn.dataset.tab}`);
    });
  });
  // Responde a alterações do hash vindas de botões externos/links
  window.addEventListener("hashchange", () => {
    const hash = (location.hash || "").replace("#", "");
    if (hash === "perplexity" || hash === "manage") activateTab(hash);
  });
}

// ---------- Eventos iniciais ----------

window.addEventListener("DOMContentLoaded", async () => {

  document.body.classList.add("collect-theme");
  setupTabs();

  // Abre a aba correta se vier via hash
  const hash = (window.location.hash || "").replace("#", "");
  if (hash === "perplexity" || hash === "manage") {
    activateTab(hash);
  }
  else {
    // Garante manage como default visual
    activateTab("manage");
  }

  // JAVASCRIPT REMOVIDO:
  // A função syncDolarTag foi removida pois o input 'usd-brl'
  // e o 'dolar-value' (badge) foram removidos do HTML.
  /*
  (function syncDolarTag(){
    const tag = document.getElementById("dolar-value");
    const usd = document.getElementById("usd-brl");
    if (!tag || !usd) return;
    const set = () => {
      const v = parseFloat(usd.value || "5.2");
      if (!isNaN(v)) tag.textContent = v.toFixed(2);
    };
    set();
    usd.addEventListener("input", set);
  })();
  */

  // ====== ELEMENTOS (existentes + novos) ======
  const presetSelect = document.getElementById("preset-min-days");
  const customInput = document.getElementById("custom-min-days");
  const btnSaveMinDays = document.getElementById("btn-save-min-days");

  const btnRunCollect = document.getElementById("btn-run-collect");
  const btnRefreshItems = document.getElementById("btn-refresh-items");
  const btnClearAll = document.getElementById("btn-clear-all");
  const btnDiag = document.getElementById("btn-diag");
  const btnRunDiag = document.getElementById("btn-run-diag");
  const btnCancelCollect = document.getElementById("btn-cancel-collect");
  const btnCancelDiag = document.getElementById("btn-cancel-diag");

  // NOVOS – chips de deadline + modal de valor
  const deadlineChips = document.querySelectorAll(".chip-deadline");
  const valueChip = document.getElementById("chip-valor");
  const valueModal = document.getElementById("value-modal");
  const valueMax = document.getElementById("value-max");
  const valueApply = document.getElementById("value-apply");
  const valueCancel = document.getElementById("value-cancel");

  // Perplexity
  const pplxTemp = document.getElementById("pplx-temp");
  const pplxTempValue = document.getElementById("pplx-temp-value");
  const pplxRunBtn = document.getElementById("btn-pplx-run");
  const pplxTpl = document.getElementById("pplx-tpl");
  const pplxTema = document.getElementById("pplx-tema");
  const pplxReg = document.getElementById("pplx-reg");
  const pplxDias = document.getElementById("pplx-dias");
  const pplxLink = document.getElementById("pplx-edital-link");
  const pplxCountTokensBtn = document.getElementById("pplx-count-tokens");
  const pplxModelSelect = document.getElementById("pplx-model");
  const pplxHtmlCheckbox = document.getElementById("pplx-html-checkbox");
  const pplxHtmlHelp = document.getElementById("pplx-html-help");
  const pplxPages = document.getElementById("pplx-edital-pages");
  const chipData = document.getElementById("chip-data");
  const nativeDate = document.getElementById("filter-date");

  // --- estado local de filtros ---
  let filterDateISO = null;   // yyyy-mm-dd ou null
  let valueMaxCache = 5000;   // já existia; mantemos aqui visível

  // Abre o seletor nativo ao clicar no chip
  if (chipData && nativeDate) {
    chipData.addEventListener("click", () => {
      // toggle: se já ativo, limpa; senão abre o datepicker
      if (chipData.classList.contains("active")) {
        chipData.classList.remove("active");
        chipData.innerHTML = `Data: dd/mm/aaaa <span class="caret">▾</span>`;
        state.filterDate = null;
        filterDateISO = null;
        filterVisibleItems();
        // também zera o input nativo para não ficar valor fantasma
        nativeDate.value = "";
        return;
      }
      if (nativeDate.showPicker) nativeDate.showPicker();
      else nativeDate.focus();
    });
    nativeDate.addEventListener("change", () => {
      const v = nativeDate.value; // yyyy-mm-dd
      if (v) {
        const [y, m, d] = v.split("-");
        chipData.innerHTML = `Data: ${d}/${m}/${y} <span class="caret">▾</span>`;
        chipData.classList.add("active");
        state.filterDate = v;
        filterDateISO = v;
        filterVisibleItems();
      } else {
        // limpou a data
        chipData.innerHTML = `Data: dd/mm/aaaa <span class="caret">▾</span>`;
        chipData.classList.remove("active");
        filterDateISO = null;
        filterVisibleItems();
      }
    });
  }

  // ====== Interações já existentes ======
  if (pplxHtmlCheckbox && pplxHtmlHelp) {
    pplxHtmlCheckbox.addEventListener("change", () => {
      if (pplxHtmlCheckbox.checked) pplxHtmlHelp.classList.remove("hidden");
      else pplxHtmlHelp.classList.add("hidden");
    });
  }
  if (pplxPages) {
    pplxPages.addEventListener("input", () => {
      const { prompt } = getPplxPromptAndModeLabel();
      updatePplxMetrics(prompt);
    });
  }
  if (presetSelect && customInput) {
    presetSelect.addEventListener("change", () => {
      if (presetSelect.value === "custom") customInput.classList.remove("hidden");
      else customInput.classList.add("hidden");
    });
  }
  if (btnSaveMinDays) btnSaveMinDays.addEventListener("click", handleSaveMinDays);
  if (btnRunCollect) btnRunCollect.addEventListener("click", handleRunCollect);
  if (btnRefreshItems) btnRefreshItems.addEventListener("click", handleRefreshItems);
  if (btnClearAll) btnClearAll.addEventListener("click", handleClearAll);
  if (btnDiag) btnDiag.addEventListener("click", toggleDiagSection);
  if (btnRunDiag) btnRunDiag.addEventListener("click", handleRunDiag);

  if (btnCancelCollect) {
    btnCancelCollect.addEventListener("click", () => {
      collectCancelRequested = true;
      const label = document.getElementById("collect-progress-label");
      if (label) label.textContent = "Cancelando… aguardando finalizar o grupo atual.";
    });
  }
  if (btnCancelDiag) {
    btnCancelDiag.addEventListener("click", () => {
      if (diagAbortController) diagAbortController.abort();
      const label = document.getElementById("diag-progress-label");
      if (label) label.textContent = "Cancelando diagnóstico…";
    });
  }
  if (pplxTemp && pplxTempValue) {
    pplxTemp.addEventListener("input", () => {
      pplxTempValue.innerText = pplxTemp.value;
    });
  }
  if (pplxRunBtn) pplxRunBtn.addEventListener("click", handleRunPerplexity);
  [pplxTpl, pplxTema, pplxReg, pplxDias, pplxLink].forEach((el) => {
    if (el) el.addEventListener("input", () => recomputeTemplatePrompt());
  });
  if (pplxCountTokensBtn) pplxCountTokensBtn.addEventListener("click", handleCountTokensFromLink);
  if (pplxModelSelect) {
    pplxModelSelect.addEventListener("change", () => {
      const { prompt } = getPplxPromptAndModeLabel();
      updatePplxMetrics(prompt, state.linkTokens);
    });
  }
  document.querySelectorAll(".pplx-cost-panel input[type='number']").forEach((inp) => {
    inp.addEventListener("input", () => {
      const { prompt } = getPplxPromptAndModeLabel();
      updatePplxMetrics(prompt, state.linkTokens);
    });
  });

  // JAVASCRIPT REMOVIDO:
  // O listener para 'usd-brl' foi removido pois o elemento não existe mais.
  /*
  const usdInput = document.getElementById("usd-brl");
  if (usdInput) {
    usdInput.addEventListener("input", () => {
      const { prompt } = getPplxPromptAndModeLabel();
      updatePplxMetrics(prompt, state.linkTokens);
    });
  }
  */

  // ====== NOVO: chips "Encerramento em" (não muda backend; apenas altera state.minDays) ======
  function setDeadlinePreset(days) {
    state.minDays = parseInt(days, 10) || state.minDays;
    // Feedback visual
    deadlineChips.forEach(ch => ch.classList.toggle("active", ch.dataset.deadline === String(days)));
  }
  deadlineChips.forEach((ch) => {
    ch.addEventListener("click", () => setDeadlinePreset(ch.dataset.deadline));
  });

  // ====== NOVO: mini modal do filtro de VALOR (apenas UI) ======
  function openValueModal() {
    valueMax.value = valueMaxCache;
    valueModal.classList.remove("hidden");
  }
  function closeValueModal() { valueModal.classList.add("hidden"); }

  if (valueChip) {
    valueChip.addEventListener("click", () => {
      // toggle: se ativo, desliga o filtro; senão abre o modal
      if (valueChip.classList.contains("active")) {
        valueChip.classList.remove("active");
        state.valueMax = null;
        valueMaxCache = null;
        valueChip.innerHTML = `Valor: de 0 até 5mil reais <span class="caret">▾</span>`;
        filterVisibleItems();
      } else {
        openValueModal();
      }
    });
  }
  if (valueCancel) {
    valueCancel.addEventListener("click", closeValueModal);
  }

  // marca o preset inicial quando a config chega
  const markInitialDeadline = () => {
    const label = (state.minDaysPreset || "").toString();
    let days = parseInt(label, 10);
    if (!days || isNaN(days)) days = state.minDays || 10;
    setDeadlinePreset(days);
  };



  if (valueApply) {
    valueApply.addEventListener("click", () => {
      const v = parseInt(valueMax.value || "0", 10);
      if (!isNaN(v) && v >= 0) {
        valueMaxCache = v;
        valueChip.innerHTML = `Valor: até R$ ${v.toLocaleString("pt-BR")} <span class="caret">▾</span>`;
        state.valueMax = v;
        valueChip.classList.add("active");
        // Re-render com filtro aplicado
        filterVisibleItems();
      }
      closeValueModal();
    });
  }
  // Fecha modal ao clicar fora
  if (valueModal) {
    valueModal.addEventListener("click", (e) => {
      if (e.target === valueModal) closeValueModal();
    });
  }

  // Inicializa prompt/modelo Perplexity
  recomputeTemplatePrompt();

  // Carrega config inicial do backend e popula grupos/itens
  try {
    await loadConfig();
  } catch (e) {
    alert("Erro ao carregar configuração inicial: " + e);
  }
  markInitialDeadline();

  // --- NOVO CÓDIGO ADICIONADO ---
  // Após carregar a config (que define o R$ padrão),
  // busca a cotação real e atualiza o state e a UI.
  (async () => {
    const liveRate = await fetchDollarRate();
    if (liveRate) {
      updateDollarUI(liveRate);
      console.log(`Cotação do dólar atualizada para R$ ${liveRate.toFixed(2)}`);
    } else {
      console.warn("Não foi possível buscar cotação live do dólar, usando valor padrão.");
    }
  })();
});

// Toggle simples da seção de diagnóstico
async function toggleDiagSection() {
  const sec = document.getElementById("diag-section");
  if (!sec) return;
  sec.classList.toggle("hidden");
}

// ============= GERENCIAMENTO DE LINKS CADASTRADOS (MODAL) =============

// Estado dos links
const linksState = {
  links: [],
  loading: false,
  selectedUids: new Set(),
  expandedGroups: new Set(["Governo/Multilaterais", "Fundações e Prêmios", "América Latina/Brasil"]),
  searchTerm: "",
};

// Carrega links do backend
async function loadLinks() {
  linksState.loading = true;

  try {
    const data = await apiGet("/api/links");
    linksState.links = data.links || [];
    renderLinksModal();
  } catch (e) {
    console.error("Erro ao carregar links:", e);
  } finally {
    linksState.loading = false;
  }
}

// Abre o modal de links
function openLinksModal() {
  const modal = document.getElementById("links-modal");
  if (modal) {
    modal.classList.remove("hidden");
    loadLinks();
  }
}

// Fecha o modal de links
function closeLinksModal() {
  const modal = document.getElementById("links-modal");
  if (modal) {
    modal.classList.add("hidden");
    // Limpa seleção
    linksState.selectedUids.clear();
    updateDeleteSelectedButton();
  }
}

// Renderiza links agrupados no modal
function renderLinksModal() {
  const container = document.getElementById("links-grouped-list");
  if (!container) return;

  if (linksState.links.length === 0) {
    container.innerHTML = `
      <div class="links-empty-state">
        <h3>Nenhum link cadastrado</h3>
        <p>Clique em "+ Adicionar Link" para começar.</p>
      </div>
    `;
    return;
  }

  // Filtra por pesquisa
  const searchLower = linksState.searchTerm.toLowerCase();
  const filteredLinks = linksState.links.filter(link => {
    if (!searchLower) return true;
    const name = (link.nome || "").toLowerCase();
    const url = (link.url || "").toLowerCase();
    return name.includes(searchLower) || url.includes(searchLower);
  });

  // Agrupa por grupo
  const groups = {};
  for (const link of filteredLinks) {
    const g = link.grupo || "Sem grupo";
    if (!groups[g]) groups[g] = [];
    groups[g].push(link);
  }

  // Ordem dos grupos
  const groupOrder = ["Governo/Multilaterais", "Fundações e Prêmios", "América Latina/Brasil"];
  const sortedGroups = Object.keys(groups).sort((a, b) => {
    const ia = groupOrder.indexOf(a);
    const ib = groupOrder.indexOf(b);
    if (ia === -1 && ib === -1) return a.localeCompare(b);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });

  let html = "";
  for (const g of sortedGroups) {
    const links = groups[g];
    const isExpanded = linksState.expandedGroups.has(g);
    const allSelected = links.every(l => linksState.selectedUids.has(l.uid));

    html += `
      <div class="links-group-card" data-group="${escapeHtml(g)}">
        <div class="links-group-header ${isExpanded ? '' : 'collapsed'}" data-group="${escapeHtml(g)}">
          <div class="links-group-title">
            <span class="links-group-toggle">▾</span>
            <span>${escapeHtml(g)}</span>
            <span class="links-group-count">${links.length}</span>
          </div>
          <div class="links-group-actions">
            <label class="links-group-select-all">
              <input type="checkbox" class="select-all-group" data-group="${escapeHtml(g)}" ${allSelected ? 'checked' : ''} />
              Selecionar todos
            </label>
          </div>
        </div>
        <div class="links-group-body ${isExpanded ? '' : 'collapsed'}" data-group="${escapeHtml(g)}">
          ${links.map(link => renderLinkItem(link)).join("")}
        </div>
      </div>
    `;
  }

  if (!html) {
    html = `
      <div class="links-empty-state">
        <h3>Nenhum resultado encontrado</h3>
        <p>Tente uma pesquisa diferente.</p>
      </div>
    `;
  }

  container.innerHTML = html;

  // Event listeners
  setupLinksEventListeners(container);
}

// Renderiza um item de link
function renderLinkItem(link) {
  const isActive = link.ativo === "true";
  const isSelected = linksState.selectedUids.has(link.uid);
  const displayName = link.nome || extractDomain(link.url);

  return `
    <div class="link-item ${isSelected ? 'selected' : ''}" data-uid="${link.uid}">
      <input type="checkbox" class="link-item-checkbox" data-uid="${link.uid}" ${isSelected ? 'checked' : ''} />
      <div class="link-item-info">
        <div class="link-item-name">${escapeHtml(displayName)}</div>
        <div class="link-item-url">
          <a href="${escapeHtml(link.url)}" target="_blank" rel="noopener">${escapeHtml(link.url)}</a>
        </div>
      </div>
      <span class="link-item-status ${isActive ? 'active' : 'inactive'}">${isActive ? 'Ativo' : 'Inativo'}</span>
      <div class="link-item-actions">
        <button class="btn-toggle-active" data-uid="${link.uid}">${isActive ? 'Desativar' : 'Ativar'}</button>
        <button class="btn-delete-link" data-uid="${link.uid}">🗑️</button>
      </div>
    </div>
  `;
}

// Configura event listeners do modal
function setupLinksEventListeners(container) {
  // Toggle de grupo (expandir/contrair)
  container.querySelectorAll(".links-group-header").forEach(header => {
    header.addEventListener("click", (e) => {
      // Não fazer toggle se clicou no checkbox
      if (e.target.type === "checkbox") return;

      const group = header.dataset.group;
      const body = container.querySelector(`.links-group-body[data-group="${CSS.escape(group)}"]`);

      if (linksState.expandedGroups.has(group)) {
        linksState.expandedGroups.delete(group);
        header.classList.add("collapsed");
        body?.classList.add("collapsed");
      } else {
        linksState.expandedGroups.add(group);
        header.classList.remove("collapsed");
        body?.classList.remove("collapsed");
      }
    });
  });

  // Checkbox individual
  container.querySelectorAll(".link-item-checkbox").forEach(chk => {
    chk.addEventListener("change", (e) => {
      e.stopPropagation();
      const uid = chk.dataset.uid;
      if (chk.checked) {
        linksState.selectedUids.add(uid);
      } else {
        linksState.selectedUids.delete(uid);
      }
      renderLinksModal();
      updateDeleteSelectedButton();
    });
  });

  // Select all do grupo
  container.querySelectorAll(".select-all-group").forEach(chk => {
    chk.addEventListener("change", (e) => {
      e.stopPropagation();
      const group = chk.dataset.group;
      const groupLinks = linksState.links.filter(l => l.grupo === group);

      if (chk.checked) {
        groupLinks.forEach(l => linksState.selectedUids.add(l.uid));
      } else {
        groupLinks.forEach(l => linksState.selectedUids.delete(l.uid));
      }
      renderLinksModal();
      updateDeleteSelectedButton();
    });
  });

  // Toggle ativo/inativo
  container.querySelectorAll(".btn-toggle-active").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const uid = btn.dataset.uid;
      const link = linksState.links.find(l => l.uid === uid);
      if (link) {
        toggleLinkActive(uid, link.ativo);
      }
    });
  });

  // Deletar individual
  container.querySelectorAll(".btn-delete-link").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteLinkById(btn.dataset.uid);
    });
  });
}

// Atualiza botão de excluir selecionados
function updateDeleteSelectedButton() {
  const btn = document.getElementById("btn-delete-selected");
  if (!btn) return;

  const count = linksState.selectedUids.size;
  btn.textContent = `🗑️ Excluir Selecionados (${count})`;
  btn.disabled = count === 0;
}

// Excluir links selecionados
async function deleteSelectedLinks() {
  const count = linksState.selectedUids.size;
  if (count === 0) return;

  if (!confirm(`Tem certeza que deseja excluir ${count} link(s) selecionado(s)?`)) {
    return;
  }

  const uids = Array.from(linksState.selectedUids);
  let deleted = 0;

  for (const uid of uids) {
    try {
      await fetch(`/api/links/${uid}`, { method: "DELETE" });
      linksState.links = linksState.links.filter(l => l.uid !== uid);
      deleted++;
    } catch (e) {
      console.error(`Erro ao deletar link ${uid}:`, e);
    }
  }

  linksState.selectedUids.clear();
  renderLinksModal();
  updateDeleteSelectedButton();
  alert(`${deleted} link(s) excluído(s) com sucesso.`);
}

// Expande todos os grupos
function expandAllGroups() {
  linksState.expandedGroups = new Set(["Governo/Multilaterais", "Fundações e Prêmios", "América Latina/Brasil"]);
  renderLinksModal();
}

// Contrai todos os grupos
function collapseAllGroups() {
  linksState.expandedGroups.clear();
  renderLinksModal();
}

// Filtra links por pesquisa
function handleLinksSearch(term) {
  linksState.searchTerm = term;
  renderLinksModal();
}

// Verifica se URL já existe
function checkLinkExists(url) {
  const normalized = url.toLowerCase().replace(/\/+$/, "");
  return linksState.links.some(l => {
    const linkUrl = (l.url || "").toLowerCase().replace(/\/+$/, "");
    return linkUrl === normalized;
  });
}

// Mostra/oculta formulário de adicionar
function toggleAddLinkForm(show) {
  const form = document.getElementById("links-add-form");
  if (form) {
    form.classList.toggle("hidden", !show);
    if (show) {
      document.getElementById("new-link-url")?.focus();
    }
  }
}

// Extrai domínio de uma URL
function extractDomain(url) {
  try {
    const u = new URL(url);
    return u.hostname.replace("www.", "");
  } catch {
    return url;
  }
}

// Escapa HTML para evitar XSS
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

// Adiciona novo link
async function addNewLink() {
  const urlInput = document.getElementById("new-link-url");
  const nomeInput = document.getElementById("new-link-nome");
  const warningDiv = document.getElementById("link-exists-warning");

  const url = (urlInput?.value || "").trim();
  const nome = (nomeInput?.value || "").trim();

  // Oculta warning
  if (warningDiv) warningDiv.classList.add("hidden");

  if (!url) {
    alert("Por favor, informe a URL do site.");
    urlInput?.focus();
    return;
  }

  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    alert("A URL deve começar com http:// ou https://");
    urlInput?.focus();
    return;
  }

  if (!nome) {
    alert("Por favor, informe o nome da empresa ou instituição.");
    nomeInput?.focus();
    return;
  }

  // Verifica se já existe
  if (checkLinkExists(url)) {
    if (warningDiv) warningDiv.classList.remove("hidden");
    return;
  }

  try {
    // Grupo omitido — o sistema define automaticamente
    const data = await apiPost("/api/links", { url, nome });
    if (data.link) {
      linksState.links.push(data.link);
      renderLinksModal();

      // Limpa formulário
      urlInput.value = "";
      nomeInput.value = "";
      toggleAddLinkForm(false);
    }
  } catch (e) {
    alert("Erro ao adicionar link: " + e);
  }
}

// Toggle ativo/inativo
async function toggleLinkActive(uid, currentActive) {
  const newActive = currentActive === "true" ? "false" : "true";

  try {
    await fetch(`/api/links/${uid}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ativo: newActive }),
    });

    // Atualiza estado local
    const link = linksState.links.find(l => l.uid === uid);
    if (link) {
      link.ativo = newActive;
      renderLinksModal();
    }
  } catch (e) {
    alert("Erro ao atualizar link: " + e);
  }
}

// Deleta link
async function deleteLinkById(uid) {
  if (!confirm("Tem certeza que deseja remover este link?")) {
    return;
  }

  try {
    await fetch(`/api/links/${uid}`, { method: "DELETE" });

    // Remove do estado local
    linksState.links = linksState.links.filter(l => l.uid !== uid);
    linksState.selectedUids.delete(uid);
    renderLinksModal();
    updateDeleteSelectedButton();
  } catch (e) {
    alert("Erro ao remover link: " + e);
  }
}

// Inicializa o modal de links
function initLinksModal() {
  // Botão abrir modal
  const btnOpen = document.getElementById("btn-open-links-modal");
  if (btnOpen) {
    btnOpen.addEventListener("click", openLinksModal);
  }

  // Botão fechar modal
  const btnClose = document.getElementById("btn-close-links-modal");
  if (btnClose) {
    btnClose.addEventListener("click", closeLinksModal);
  }

  // Fechar ao clicar fora
  const modal = document.getElementById("links-modal");
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeLinksModal();
    });
  }

  // Botão adicionar link
  const btnAdd = document.getElementById("btn-add-link");
  if (btnAdd) {
    btnAdd.addEventListener("click", () => toggleAddLinkForm(true));
  }

  // Botão salvar link
  const btnSave = document.getElementById("btn-save-link");
  if (btnSave) {
    btnSave.addEventListener("click", addNewLink);
  }

  // Botão cancelar
  const btnCancel = document.getElementById("btn-cancel-link");
  if (btnCancel) {
    btnCancel.addEventListener("click", () => toggleAddLinkForm(false));
  }

  // Botão excluir selecionados
  const btnDeleteSelected = document.getElementById("btn-delete-selected");
  if (btnDeleteSelected) {
    btnDeleteSelected.addEventListener("click", deleteSelectedLinks);
  }

  // Botão expandir todos
  const btnExpandAll = document.getElementById("btn-expand-all");
  if (btnExpandAll) {
    btnExpandAll.addEventListener("click", expandAllGroups);
  }

  // Botão contrair todos
  const btnCollapseAll = document.getElementById("btn-collapse-all");
  if (btnCollapseAll) {
    btnCollapseAll.addEventListener("click", collapseAllGroups);
  }

  // Pesquisa
  const searchInput = document.getElementById("links-search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      handleLinksSearch(e.target.value);
    });
  }

  // Verifica URL ao digitar
  const urlInput = document.getElementById("new-link-url");
  if (urlInput) {
    urlInput.addEventListener("input", () => {
      const warningDiv = document.getElementById("link-exists-warning");
      if (warningDiv && checkLinkExists(urlInput.value.trim())) {
        warningDiv.classList.remove("hidden");
      } else if (warningDiv) {
        warningDiv.classList.add("hidden");
      }
    });
  }

  // Carrega links iniciais
  setTimeout(loadLinks, 500);
}

// =================== BUSCA GLOBAL DE EDITAIS ===================

/**
 * Filtra os cards de editais visíveis com base no termo digitado.
 * Busca em: título, link, fonte (source), agência, região e grupo.
 */
function applyGlobalSearch(term) {
  const noResultsId = "global-search-no-results";
  const existingMsg = document.getElementById(noResultsId);
  if (existingMsg) existingMsg.remove();

  const trimmed = (term || "").trim().toLowerCase();
  const countEl = document.getElementById("global-search-count");
  const clearBtn = document.getElementById("btn-global-search-clear");

  if (!trimmed) {
    // Sem busca: mostra tudo
    document.querySelectorAll(".item-card").forEach(card => {
      card.style.display = "";
      card.classList.remove("search-match");
    });
    document.querySelectorAll(".source-card").forEach(sc => sc.style.display = "");
    document.querySelectorAll(".group-body").forEach(gb => {
      const emptyEl = gb.querySelector(".search-empty");
      if (emptyEl) emptyEl.remove();
    });
    if (countEl) countEl.classList.add("hidden");
    if (clearBtn) clearBtn.classList.add("hidden");
    filterVisibleItems();
    return;
  }

  if (clearBtn) clearBtn.classList.remove("hidden");

  let totalVisible = 0;

  // Itera por cada source-card (bloco por fonte)
  document.querySelectorAll(".source-card").forEach(sourceCard => {
    const cards = sourceCard.querySelectorAll(".item-card");
    let visibleInSource = 0;

    cards.forEach(card => {
      // Campos para busca: título, link, agency/region, source-header text
      const titleEl = card.querySelector(".item-title");
      const linkEl = card.querySelector(".item-caption a");
      const captionEl = card.querySelector(".item-caption");
      const headerEl = sourceCard.querySelector(".source-header");

      const title = (titleEl?.textContent || "").toLowerCase();
      const link = (linkEl?.href || linkEl?.textContent || "").toLowerCase();
      const caption = (captionEl?.textContent || "").toLowerCase();
      const source = (headerEl?.textContent || "").toLowerCase();

      const matches = title.includes(trimmed)
        || link.includes(trimmed)
        || caption.includes(trimmed)
        || source.includes(trimmed);

      card.style.display = matches ? "" : "none";
      card.classList.toggle("search-match", matches);
      if (matches) visibleInSource++;
    });

    // Oculta o source-card inteiro se não tiver nenhum resultado
    sourceCard.style.display = visibleInSource > 0 ? "" : "none";
    totalVisible += visibleInSource;
  });

  // Atualiza contador
  if (countEl) {
    countEl.textContent = `${totalVisible} resultado${totalVisible !== 1 ? "s" : ""}`;
    countEl.classList.remove("hidden");
  }

  // Mensagem de "sem resultados" por grupo
  document.querySelectorAll("[data-group-body]").forEach(gb => {
    const oldEmpty = gb.querySelector(".search-empty");
    if (oldEmpty) oldEmpty.remove();

    const visibleSources = gb.querySelectorAll(".source-card:not([style*='display: none'])");
    if (visibleSources.length === 0 && gb.querySelectorAll(".source-card").length > 0) {
      const msg = document.createElement("div");
      msg.className = "search-empty search-no-results";
      msg.textContent = `Nenhum resultado para "${term}" neste grupo.`;
      gb.appendChild(msg);
    }
  });
}

function initGlobalSearch() {
  const input = document.getElementById("global-search-input");
  const btn = document.getElementById("btn-global-search");
  const clearBtn = document.getElementById("btn-global-search-clear");

  if (!input) return;

  // Busca ao clicar na lupa
  if (btn) {
    btn.addEventListener("click", () => applyGlobalSearch(input.value));
  }

  // Busca ao pressionar Enter
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") applyGlobalSearch(input.value);
  });

  // Limpa a busca
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      input.value = "";
      applyGlobalSearch("");
      input.focus();
    });
  }
}

// Inicializa quando DOM carrega
document.addEventListener("DOMContentLoaded", () => {
  initLinksModal();
  initGlobalSearch();
});

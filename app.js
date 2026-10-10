/**
 * RetailIQ - Operations & Intelligence
 * App Core Logic
 */

// State Store containing all 3 models per store ID
const storeDatabase = {
    "S001": {
        metricsModel: {
            "store_id": "S001",
            "period": { "from": "2026-09-01", "to": "2026-09-30" },
            "metrics": {
                "net_sales": 125430.50,
                "units_sold": 8420,
                "low_stock_products": 12,
                "recommendations_count": 3
            },
            "sales_trend": [
                {"date": "2026-09-01", "net_sales": 4120.50},
                {"date": "2026-09-02", "net_sales": 4380.00},
                {"date": "2026-09-03", "net_sales": 3950.20},
                {"date": "2026-09-04", "net_sales": 4890.00},
                {"date": "2026-09-05", "net_sales": 5210.80},
                {"date": "2026-09-06", "net_sales": 5800.00},
                {"date": "2026-09-07", "net_sales": 3700.40}
            ]
        },
        inventoryModel: {
            "store_id": "S001",
            "items": [
                {
                    "sku": "SKU100392",
                    "product_name": "Aceite Sintético 5W-30 1L",
                    "closing_qty": 18,
                    "forecast_units": 25,
                    "status": "review_restock"
                },
                {
                    "sku": "SKU100411",
                    "product_name": "Filtro de Aire Universal",
                    "closing_qty": 5,
                    "forecast_units": 30,
                    "status": "critical_low"
                },
                {
                    "sku": "SKU100205",
                    "product_name": "Bomba de Gasolina Eléctrica",
                    "closing_qty": 42,
                    "forecast_units": 20,
                    "status": "optimal"
                },
                {
                    "sku": "SKU100882",
                    "product_name": "Limpiador de Inyectores 500ml",
                    "closing_qty": 2,
                    "forecast_units": 15,
                    "status": "out_of_stock"
                }
            ]
        },
        recommendationsModel: {
            "store_id": "S001",
            "recommendations": [
                {
                    "sku": "SKU100392",
                    "action": "review_restock",
                    "priority": "high",
                    "reason": "La demanda estimada supera las existencias disponibles",
                    "evidence": {
                        "forecast_units": 25,
                        "closing_qty": 18
                    }
                },
                {
                    "sku": "SKU100411",
                    "action": "urgent_reorder",
                    "priority": "critical",
                    "reason": "Inventario en punto crítico con alto riesgo de agotamiento inminente",
                    "evidence": {
                        "forecast_units": 30,
                        "closing_qty": 5
                    }
                },
                {
                    "sku": "SKU100882",
                    "action": "emergency_restock",
                    "priority": "critical",
                    "reason": "Existencias en cero con demanda sostenida detectada",
                    "evidence": {
                        "forecast_units": 15,
                        "closing_qty": 2
                    }
                }
            ]
        }
    },
    "S002": {
        metricsModel: {
            "store_id": "S002",
            "period": { "from": "2026-09-01", "to": "2026-09-30" },
            "metrics": {
                "net_sales": 89210.00,
                "units_sold": 5150,
                "low_stock_products": 6,
                "recommendations_count": 1
            },
            "sales_trend": [
                {"date": "2026-09-01", "net_sales": 2800.00},
                {"date": "2026-09-02", "net_sales": 3100.00},
                {"date": "2026-09-03", "net_sales": 2950.00},
                {"date": "2026-09-04", "net_sales": 3400.00},
                {"date": "2026-09-05", "net_sales": 3900.00},
                {"date": "2026-09-06", "net_sales": 4100.00},
                {"date": "2026-09-07", "net_sales": 2600.00}
            ]
        },
        inventoryModel: {
            "store_id": "S002",
            "items": [
                {
                    "sku": "SKU200101",
                    "product_name": "Batería 12V 65Ah Premium",
                    "closing_qty": 8,
                    "forecast_units": 18,
                    "status": "review_restock"
                },
                {
                    "sku": "SKU200305",
                    "product_name": "Refrigerante Anticongelante 1Gal",
                    "closing_qty": 50,
                    "forecast_units": 25,
                    "status": "optimal"
                }
            ]
        },
        recommendationsModel: {
            "store_id": "S002",
            "recommendations": [
                {
                    "sku": "SKU200101",
                    "action": "review_restock",
                    "priority": "medium",
                    "reason": "Rotación moderada requiere ajuste de stock previo a fin de mes",
                    "evidence": {
                        "forecast_units": 18,
                        "closing_qty": 8
                    }
                }
            ]
        }
    }
};

let currentStoreId = "S001";
let trendChart = null;
let editingSku = null;

// Active Store Reference Shortcut
function getActiveData() {
    return storeDatabase[currentStoreId];
}

// Format Currency Helper
function formatCurrency(val) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
}

// Switch Active Tab
function switchTab(tabId) {
    const tabs = ['overview', 'inventory', 'recommendations', 'json-inspector'];
    tabs.forEach(t => {
        const sec = document.getElementById(`section-${t}`);
        const btn = document.getElementById(`tab-btn-${t}`);
        if (t === tabId) {
            sec.classList.remove('hidden');
            btn.classList.add('border-indigo-600', 'text-indigo-600', 'dark:text-indigo-400');
            btn.classList.remove('border-transparent', 'text-slate-500', 'dark:text-slate-400');
        } else {
            sec.classList.add('hidden');
            btn.classList.remove('border-indigo-600', 'text-indigo-600', 'dark:text-indigo-400');
            btn.classList.add('border-transparent', 'text-slate-500', 'dark:text-slate-400');
        }
    });
}

// Load real data from the FastAPI backend
async function loadStoreData(storeId) {
    try {
        const baseUrl = "http://127.0.0.1:8000";
        const urls = [
            `${baseUrl}/api/dashboard?store_id=${encodeURIComponent(storeId)}`,
            `${baseUrl}/api/inventory?store_id=${encodeURIComponent(storeId)}&limit=100`,
            `${baseUrl}/api/recommendations?store_id=${encodeURIComponent(storeId)}`
        ];

        const responses = await Promise.all(urls.map(url => fetch(url)));
        const failed = responses.find(response => !response.ok);

        if (failed) {
            throw new Error(`La API respondió con HTTP ${failed.status}`);
        }

        const [dashboard, inventory, recommendations] =
            await Promise.all(responses.map(response => response.json()));

        storeDatabase[storeId] = {
            metricsModel: dashboard,
            inventoryModel: inventory,
            recommendationsModel: recommendations
        };

        currentStoreId = storeId;
        renderAllSections();
        showToast(`Datos reales cargados: ${storeId}`);
    } catch (error) {
        console.error("Error al cargar datos de la API:", error);
        showToast("No se pudieron cargar los datos. Revisa que FastAPI siga activo.");
    }
}

// Switch Store Dropdown
function switchStore(storeId) {
    loadStoreData(storeId);
}

// Render Entire Dashboard
function renderAllSections() {
    const data = getActiveData();

    // Update Header Info
    document.getElementById('header-period-text').textContent = `${data.metricsModel.period.from} a ${data.metricsModel.period.to}`;
    document.getElementById('tab-inventory-badge').textContent = data.inventoryModel.items.length;
    document.getElementById('tab-recs-badge').textContent = data.recommendationsModel.recommendations.length;

    // Render Sub-Components
    renderOverviewSection();
    renderInventoryTable();
    renderRecommendationsCards();
    updateJsonTextareas();
}

// 1. Render Overview Section
function renderOverviewSection() {
    const data = getActiveData();
    const metrics = data.metricsModel.metrics;

    document.getElementById('kpi-net-sales').textContent = formatCurrency(metrics.net_sales);
    document.getElementById('kpi-units-sold').textContent = metrics.units_sold.toLocaleString();

    const avgDaily = (metrics.units_sold / (data.metricsModel.sales_trend.length || 1)).toFixed(0);
    document.getElementById('kpi-avg-units').textContent = avgDaily;

    document.getElementById('kpi-low-stock').textContent = metrics.low_stock_products;
    document.getElementById('kpi-recommendations').textContent = data.recommendationsModel.recommendations.length;

    renderChart(data.metricsModel.sales_trend);
    renderStatusMeters(data.inventoryModel.items);

    const criticalCount = data.recommendationsModel.recommendations.filter(r => r.priority === 'critical' || r.priority === 'high').length;
    document.getElementById('overview-critical-desc').textContent = `${criticalCount} requerimiento(s) de alta prioridad`;
}

// Render Trend Chart
function renderChart(trendArray) {
    const ctx = document.getElementById('overviewTrendChart').getContext('2d');
    const labels = trendArray.map(item => item.date);
    const values = trendArray.map(item => item.net_sales);

    if (trendChart) {
        trendChart.data.labels = labels;
        trendChart.data.datasets[0].data = values;
        trendChart.update();
        return;
    }

    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Ventas Netas ($)',
                data: values,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.3,
                pointBackgroundColor: '#6366f1',
                pointBorderColor: '#ffffff',
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0f172a',
                    titleFont: { family: 'Inter', size: 12 },
                    bodyFont: { family: 'Inter', size: 12, weight: 'bold' },
                    padding: 10,
                    callbacks: {
                        label: (ctx) => ` Ventas: ${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 10 }, color: '#94a3b8' }
                },
                y: {
                    grid: { color: 'rgba(148, 163, 184, 0.1)' },
                    ticks: {
                        font: { family: 'Inter', size: 10 },
                        color: '#94a3b8',
                        callback: (val) => '$' + val.toLocaleString()
                    }
                }
            }
        }
    });
}

// Render Inventory Breakdown Meters
function renderStatusMeters(items) {
    const container = document.getElementById('inventory-status-meters');
    container.innerHTML = '';

    const total = items.length || 1;
    const counts = {
        optimal: items.filter(i => i.status === 'optimal').length,
        review_restock: items.filter(i => i.status === 'review_restock').length,
        critical_low: items.filter(i => i.status === 'critical_low').length,
        out_of_stock: items.filter(i => i.status === 'out_of_stock').length
    };

    const config = [
        { key: 'optimal', label: 'Stock Óptimo', color: 'bg-emerald-500', count: counts.optimal },
        { key: 'review_restock', label: 'Revisar Stock', color: 'bg-amber-500', count: counts.review_restock },
        { key: 'critical_low', label: 'Crítico / Bajo', color: 'bg-orange-500', count: counts.critical_low },
        { key: 'out_of_stock', label: 'Agotado (Zero)', color: 'bg-rose-500', count: counts.out_of_stock }
    ];

    config.forEach(cfg => {
        const pct = Math.round((cfg.count / total) * 100);
        const el = document.createElement('div');
        el.className = 'space-y-1';
        el.innerHTML = `
            <div class="flex justify-between text-xs font-semibold">
                <span class="text-slate-600 dark:text-slate-400">${cfg.label}</span>
                <span class="text-slate-900 dark:text-white font-bold">${cfg.count} <span class="text-[10px] text-slate-400 font-normal">(${pct}%)</span></span>
            </div>
            <div class="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                <div class="h-full ${cfg.color} rounded-full transition-all duration-500" style="width: ${pct}%"></div>
            </div>
        `;
        container.appendChild(el);
    });
}

// 2. Render Inventory Table
function renderInventoryTable() {
    const data = getActiveData();
    const filterStatus = document.getElementById('filter-inventory-status').value;
    const query = document.getElementById('inventory-search').value.toLowerCase();

    let items = data.inventoryModel.items;

    if (filterStatus !== 'all') {
        items = items.filter(i => i.status === filterStatus);
    }

    if (query) {
        items = items.filter(i => i.sku.toLowerCase().includes(query) || i.product_name.toLowerCase().includes(query));
    }

    const tbody = document.getElementById('inventory-table-body');
    tbody.innerHTML = '';

    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-slate-400 text-xs">No se encontraron productos coincidentes.</td></tr>`;
        return;
    }

    items.forEach(item => {
        const diff = item.closing_qty - item.forecast_units;
        let diffBadge = `<span class="text-emerald-600 dark:text-emerald-400 font-bold">+${diff}</span>`;
        if (diff < 0) {
            diffBadge = `<span class="text-rose-600 dark:text-rose-400 font-bold">${diff}</span>`;
        }

        let statusBadge = '';
        if (item.status === 'optimal') {
            statusBadge = `<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900/50">Óptimo</span>`;
        } else if (item.status === 'review_restock') {
            statusBadge = `<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-900/50">Revisar Stock</span>`;
        } else if (item.status === 'critical_low') {
            statusBadge = `<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-orange-50 dark:bg-orange-950/60 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-900/50">Muy Bajo</span>`;
        } else if (item.status === 'out_of_stock') {
            statusBadge = `<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900/50">Agotado</span>`;
        }

        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition';
        tr.innerHTML = `
            <td class="py-3.5 px-6 font-mono font-bold text-slate-900 dark:text-white text-xs">${item.sku}</td>
            <td class="py-3.5 px-6 font-medium text-slate-800 dark:text-slate-200">${item.product_name}</td>
            <td class="py-3.5 px-6 text-center font-extrabold text-slate-800 dark:text-slate-200">${item.closing_qty}</td>
            <td class="py-3.5 px-6 text-center font-extrabold text-indigo-600 dark:text-indigo-400">${item.forecast_units}</td>
            <td class="py-3.5 px-6 text-center font-mono">${diffBadge}</td>
            <td class="py-3.5 px-6">${statusBadge}</td>
            <td class="py-3.5 px-6 text-right space-x-1.5">
                <button data-action="edit" data-sku="${item.sku}" class="p-1.5 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg transition cursor-pointer" title="Editar">
                    <i class="fa-solid fa-pen text-xs"></i>
                </button>
                <button data-action="delete" data-sku="${item.sku}" class="p-1.5 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/60 dark:hover:bg-rose-900/60 text-rose-600 dark:text-rose-400 rounded-lg transition cursor-pointer" title="Eliminar">
                    <i class="fa-solid fa-trash text-xs"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// 3. Render AI Recommendations Cards
function renderRecommendationsCards() {
    const data = getActiveData();
    const recs = data.recommendationsModel.recommendations;
    const container = document.getElementById('recommendations-cards-grid');
    container.innerHTML = '';

    if (recs.length === 0) {
        container.innerHTML = `<div class="col-span-full bg-white dark:bg-slate-900 p-8 rounded-2xl border border-slate-200 dark:border-slate-800 text-center text-slate-400 text-xs">No hay recomendaciones activas para esta tienda.</div>`;
        return;
    }

    recs.forEach(rec => {
        const itemMatch = data.inventoryModel.items.find(i => i.sku === rec.sku);
        const productName = itemMatch ? itemMatch.product_name : 'Producto sin registrar';

        let priorityBadge = '';
        let borderAccent = 'border-l-4 border-slate-400';

        if (rec.priority === 'critical') {
            priorityBadge = `<span class="bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase">Crítico</span>`;
            borderAccent = 'border-l-4 border-rose-500';
        } else if (rec.priority === 'high') {
            priorityBadge = `<span class="bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-900 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase">Alta</span>`;
            borderAccent = 'border-l-4 border-amber-500';
        } else {
            priorityBadge = `<span class="bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-900 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase">Media</span>`;
            borderAccent = 'border-l-4 border-blue-500';
        }

        const ratioPct = Math.min(Math.round((rec.evidence.closing_qty / (rec.evidence.forecast_units || 1)) * 100), 100);

        const card = document.createElement('div');
        card.className = `bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs hover:shadow-md transition flex flex-col justify-between ${borderAccent}`;
        card.innerHTML = `
            <div>
                <div class="flex items-center justify-between mb-3">
                    <span class="font-mono text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 px-2.5 py-1 rounded-lg">${rec.sku}</span>
                    ${priorityBadge}
                </div>
                <h4 class="font-bold text-slate-900 dark:text-white text-sm mb-1">${productName}</h4>
                <p class="text-xs text-slate-600 dark:text-slate-300 mb-4 bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-100 dark:border-slate-800/80 leading-relaxed">
                    <i class="fa-solid fa-circle-info text-indigo-500 mr-1"></i> ${rec.reason}
                </p>
            </div>

            <div class="space-y-3">
                <div class="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-100 dark:border-slate-800/80 space-y-2">
                    <div class="flex justify-between text-xs">
                        <span class="text-slate-400">Cobertura de Stock:</span>
                        <span class="font-bold text-slate-800 dark:text-slate-200">${rec.evidence.closing_qty} / ${rec.evidence.forecast_units} uds</span>
                    </div>
                    <div class="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div class="h-full ${ratioPct < 30 ? 'bg-rose-500' : 'bg-amber-500'} rounded-full" style="width: ${ratioPct}%"></div>
                    </div>
                </div>

                <div class="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800">
                    <span class="text-[11px] text-slate-500">Acción: <strong class="text-slate-800 dark:text-slate-200 font-mono">${rec.action}</strong></span>
                    <button data-action="resolve" data-sku="${rec.sku}" class="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5">
                        <i class="fa-solid fa-check"></i> Atender
                    </button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

// Resolve Recommendation
function resolveRecommendation(sku) {
    const data = getActiveData();
    data.recommendationsModel.recommendations = data.recommendationsModel.recommendations.filter(r => r.sku !== sku);

    const item = data.inventoryModel.items.find(i => i.sku === sku);
    if (item) {
        item.closing_qty = item.forecast_units;
        item.status = "optimal";
    }

    renderAllSections();
    showToast(`Recomendación para ${sku} atendida exitosamente.`);
}

// 4. Update JSON Textareas
function updateJsonTextareas() {
    const data = getActiveData();
    document.getElementById('json-textarea-metrics').value = JSON.stringify(data.metricsModel, null, 2);
    document.getElementById('json-textarea-inventory').value = JSON.stringify(data.inventoryModel, null, 2);
    document.getElementById('json-textarea-recommendations').value = JSON.stringify(data.recommendationsModel, null, 2);
}

// Live JSON parse updates
function liveUpdateFromJson(type) {
    try {
        const data = getActiveData();
        if (type === 'metrics') {
            data.metricsModel = JSON.parse(document.getElementById('json-textarea-metrics').value);
        } else if (type === 'inventory') {
            data.inventoryModel = JSON.parse(document.getElementById('json-textarea-inventory').value);
        } else if (type === 'recommendations') {
            data.recommendationsModel = JSON.parse(document.getElementById('json-textarea-recommendations').value);
        }
        renderOverviewSection();
        renderInventoryTable();
        renderRecommendationsCards();
    } catch (err) {
        // Syntax error while typing ignored
    }
}

// Copy JSON snippet
function copyJsonToClipboard(type) {
    const text = document.getElementById(`json-textarea-${type}`).value;
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text);
    } else {
        const textarea = document.getElementById(`json-textarea-${type}`);
        textarea.select();
        document.execCommand('copy');
    }
    showToast(`JSON ${type} copiado al portapapeles.`);
}

// Modal Form Controls
function openItemModal(sku = null) {
    editingSku = sku;
    const modal = document.getElementById('item-modal');
    modal.classList.remove('hidden');

    if (sku) {
        const item = getActiveData().inventoryModel.items.find(i => i.sku === sku);
        document.getElementById('modal-item-title').textContent = `Editar Ítem ${sku}`;
        document.getElementById('modal-sku').value = item.sku;
        document.getElementById('modal-sku').readOnly = true;
        document.getElementById('modal-name').value = item.product_name;
        document.getElementById('modal-closing').value = item.closing_qty;
        document.getElementById('modal-forecast').value = item.forecast_units;
        document.getElementById('modal-status').value = item.status;
    } else {
        document.getElementById('modal-item-title').textContent = `Agregar Nuevo Ítem`;
        document.getElementById('modal-sku').value = '';
        document.getElementById('modal-sku').readOnly = false;
        document.getElementById('modal-name').value = '';
        document.getElementById('modal-closing').value = 10;
        document.getElementById('modal-forecast').value = 25;
        document.getElementById('modal-status').value = 'review_restock';
    }
}

function closeItemModal() {
    document.getElementById('item-modal').classList.add('hidden');
}

function saveItemForm(event) {
    event.preventDefault();
    const data = getActiveData();

    const sku = document.getElementById('modal-sku').value.trim();
    const product_name = document.getElementById('modal-name').value.trim();
    const closing_qty = parseInt(document.getElementById('modal-closing').value) || 0;
    const forecast_units = parseInt(document.getElementById('modal-forecast').value) || 0;
    const status = document.getElementById('modal-status').value;

    const newItem = { sku, product_name, closing_qty, forecast_units, status };

    const idx = data.inventoryModel.items.findIndex(i => i.sku === sku);
    if (idx >= 0) {
        data.inventoryModel.items[idx] = newItem;
    } else {
        data.inventoryModel.items.push(newItem);
    }

    closeItemModal();
    renderAllSections();
    showToast(`Ítem ${sku} guardado correctamente.`);
}

function deleteItem(sku) {
    const data = getActiveData();
    data.inventoryModel.items = data.inventoryModel.items.filter(i => i.sku !== sku);
    data.recommendationsModel.recommendations = data.recommendationsModel.recommendations.filter(r => r.sku !== sku);
    renderAllSections();
    showToast(`Ítem ${sku} eliminado.`);
}

// Toast Helper
function showToast(msg) {
    const toast = document.getElementById('toast');
    document.getElementById('toast-message').textContent = msg;
    toast.classList.remove('opacity-0', 'pointer-events-none', 'translate-y-2');
    setTimeout(() => {
        toast.classList.add('opacity-0', 'pointer-events-none', 'translate-y-2');
    }, 2500);
}

// Event Listeners Registration
document.addEventListener('DOMContentLoaded', () => {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Store switcher
    document.getElementById('store-selector').addEventListener('change', (e) => switchStore(e.target.value));

    // Dark Mode Toggle
    document.getElementById('btn-toggle-dark').addEventListener('click', () => {
        document.documentElement.classList.toggle('dark');
    });

    // Overview shortcut button
    document.getElementById('btn-goto-recommendations').addEventListener('click', () => switchTab('recommendations'));

    // Inventory table controls
    document.getElementById('filter-inventory-status').addEventListener('change', renderInventoryTable);
    document.getElementById('inventory-search').addEventListener('keyup', renderInventoryTable);
    document.getElementById('btn-open-add-modal').addEventListener('click', () => openItemModal());

    // Modal buttons
    document.getElementById('btn-close-modal-x').addEventListener('click', closeItemModal);
    document.getElementById('btn-close-modal-cancel').addEventListener('click', closeItemModal);
    document.getElementById('item-form').addEventListener('submit', saveItemForm);

    // Reset models button
    document.getElementById('btn-reset-models').addEventListener('click', () => location.reload());

    // Copy JSON buttons
    document.querySelectorAll('.btn-copy-json').forEach(btn => {
        btn.addEventListener('click', () => copyJsonToClipboard(btn.dataset.copy));
    });

    // JSON Live Editor Textareas
    document.querySelectorAll('.json-textarea').forEach(area => {
        area.addEventListener('input', () => liveUpdateFromJson(area.dataset.type));
    });

    // Event Delegation for Table & Recommendation Action Buttons
    document.getElementById('inventory-table-body').addEventListener('click', (e) => {
        const button = e.target.closest('button');
        if (!button) return;
        const action = button.dataset.action;
        const sku = button.dataset.sku;
        if (action === 'edit') openItemModal(sku);
        if (action === 'delete') deleteItem(sku);
    });

    document.getElementById('recommendations-cards-grid').addEventListener('click', (e) => {
        const button = e.target.closest('button');
        if (!button) return;
        const action = button.dataset.action;
        const sku = button.dataset.sku;
        if (action === 'resolve') resolveRecommendation(sku);
    });

    // Load initial data from the API
    loadStoreData(currentStoreId);
});

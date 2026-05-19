import {
    apiFetch,
    clearNotice,
    drawMetricChart,
    escapeHtml,
    formatNumber,
    formatTimestamp,
    renderStatusChip,
    setNotice,
} from "./common.js";

const notice = document.querySelector("#monitoringNotice");
const grid = document.querySelector("#publisherCardGrid");
let selectedPointId = null;
let pointsCache = [];

function renderPointCards(points) {
    grid.innerHTML = points.map((point) => `
        <article class="device-card ${point.id === selectedPointId ? "active-card" : ""}" data-point-id="${point.id}">
            <div class="device-card-header">
                <div>
                    <strong>${escapeHtml(point.display_name)}</strong>
                    <div class="device-location">${escapeHtml(point.subestacion)} / ${escapeHtml(point.circuito)}</div>
                </div>
                ${renderStatusChip(point.status)}
            </div>
            <div class="secondary-text">
                ${point.last_reading ? `Ultima lectura: ${formatTimestamp(point.last_reading.timestamp)}` : "Sin lecturas aun"}
            </div>
            <div class="device-card-footer">
                <span class="secondary-text">${point.last_reading ? `${formatNumber(point.last_reading.carga_pct)} % carga` : "--"}</span>
                <button class="toggle-button" data-action="toggle" data-point-id="${point.id}">
                    ${point.activo ? "Pausar" : "Reactivar"}
                </button>
            </div>
        </article>
    `).join("");
}

function renderSelectedPoint(point) {
    document.querySelector("#selectedPointTitle").textContent = point.display_name;
    document.querySelector("#selectedPointStatus").outerHTML = renderStatusChip(point.status).replace(
        "<span",
        '<span id="selectedPointStatus"'
    );

    document.querySelector("#selectedVoltage").textContent = point.last_reading
        ? `${formatNumber(point.last_reading.voltaje_kv, 3)} kV`
        : "--";
    document.querySelector("#selectedCurrent").textContent = point.last_reading
        ? `${formatNumber(point.last_reading.corriente_a)} A`
        : "--";
    document.querySelector("#selectedLoad").textContent = point.last_reading
        ? `${formatNumber(point.last_reading.carga_pct)} %`
        : "--";
    document.querySelector("#selectedEnergy").textContent = point.last_reading
        ? `${formatNumber(point.last_reading.energia_kwh)} kWh`
        : "--";
    document.querySelector("#selectedTimestamp").textContent = point.last_reading
        ? formatTimestamp(point.last_reading.timestamp)
        : "Sin datos";

    drawMetricChart(document.querySelector("#voltageChart"), point.history, "voltaje_kv", "#2563eb", "kV");
    drawMetricChart(document.querySelector("#loadChart"), point.history, "carga_pct", "#0ea5e9", "%");
    drawMetricChart(document.querySelector("#thdiChart"), point.history, "thd_i_pct", "#1e40af", "%");

    const body = document.querySelector("#selectedHistoryBody");
    body.innerHTML = point.history.slice().reverse().map((item) => `
        <tr>
            <td>${formatTimestamp(item.timestamp_medicion)}</td>
            <td>${formatNumber(item.voltaje_kv, 3)} kV</td>
            <td>${formatNumber(item.corriente_a)} A</td>
            <td>${formatNumber(item.carga_pct)} %</td>
            <td>${renderStatusChip(item.estado_calidad)}</td>
        </tr>
    `).join("");

    if (point.last_reading?.alert_detail) {
        setNotice(notice, `${point.display_name}: ${point.last_reading.alert_detail}`, "warning");
    } else if (point.status === "critico" || point.status === "advertencia") {
        setNotice(notice, `${point.display_name} presenta una condicion ${point.status}. Revisa THDi, carga y factor de potencia.`, "warning");
    } else {
        clearNotice(notice);
    }
}

function syncSelection(points) {
    if (!points.length) {
        return;
    }

    if (!selectedPointId || !points.some((item) => item.id === selectedPointId)) {
        selectedPointId = points[0].id;
    }

    const selected = points.find((item) => item.id === selectedPointId);
    if (selected) {
        renderSelectedPoint(selected);
    }
}

async function loadMonitoring() {
    try {
        const payload = await apiFetch("/api/monitoring");
        pointsCache = payload.points;
        renderPointCards(pointsCache);
        syncSelection(pointsCache);
    } catch (error) {
        setNotice(notice, error.message, "warning");
    }
}

grid.addEventListener("click", async (event) => {
    const toggleButton = event.target.closest("[data-action='toggle']");
    if (toggleButton) {
        event.stopPropagation();
        const pointId = Number(toggleButton.dataset.pointId);
        try {
            await apiFetch(`/api/points/${pointId}/toggle`, { method: "POST" });
            await loadMonitoring();
        } catch (error) {
            setNotice(notice, error.message, "danger");
        }
        return;
    }

    const card = event.target.closest("[data-point-id]");
    if (!card) {
        return;
    }
    selectedPointId = Number(card.dataset.pointId);
    renderPointCards(pointsCache);
    syncSelection(pointsCache);
});

loadMonitoring();
setInterval(loadMonitoring, 5000);

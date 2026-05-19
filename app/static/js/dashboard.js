import {
    apiFetch,
    clearNotice,
    escapeHtml,
    formatNumber,
    formatTimestamp,
    renderStatusChip,
    setNotice,
} from "./common.js";

const notice = document.querySelector("#dashboardNotice");

function updateMetrics(summary) {
    document.querySelector("#metricActivePublishers").textContent = summary.active_publishers;
    document.querySelector("#metricPausedPublishers").textContent = summary.paused_publishers;
    document.querySelector("#metricWarningPoints").textContent = summary.warning_points;
    document.querySelector("#metricCriticalPoints").textContent = summary.critical_points;
    document.querySelector("#metricPublications").textContent = summary.publications_last_hour;
    document.querySelector("#metricAlertsDay").textContent = summary.alerts_last_24h;
    document.querySelector("#metricAvgLoad").textContent = `${formatNumber(summary.avg_load_pct)} %`;
    document.querySelector("#metricEnergy").textContent = `${formatNumber(summary.total_energy_kwh)} kWh`;
}

function renderPointSummary(points) {
    const body = document.querySelector("#pointSummaryBody");
    body.innerHTML = points.map((point) => `
        <tr>
            <td>
                <strong>${escapeHtml(point.display_name)}</strong><br>
                <span class="secondary-text">${escapeHtml(point.tipo)}</span>
            </td>
            <td>${escapeHtml(point.subestacion)} / ${escapeHtml(point.circuito)}</td>
            <td>${renderStatusChip(point.status)}</td>
            <td>${point.last_reading ? formatTimestamp(point.last_reading.timestamp) : "--"}</td>
        </tr>
    `).join("");
}

function renderQualitySummary(points) {
    const body = document.querySelector("#qualitySummaryBody");
    body.innerHTML = points.map((point) => `
        <tr>
            <td>
                <strong>${escapeHtml(point.display_name)}</strong><br>
                <span class="secondary-text">${escapeHtml(point.subestacion)}</span>
            </td>
            <td>${point.last_reading ? `${formatNumber(point.last_reading.voltaje_kv, 3)} kV` : "--"}</td>
            <td>${point.last_reading ? `${formatNumber(point.last_reading.carga_pct)} %` : "--"}</td>
            <td>${point.last_reading ? `${formatNumber(point.last_reading.thd_i_pct)} %` : "--"}</td>
            <td>${point.last_reading ? formatNumber(point.last_reading.factor_potencia) : "--"}</td>
        </tr>
    `).join("");
}

function renderAlerts(alerts) {
    const container = document.querySelector("#recentAlertsList");
    container.innerHTML = alerts.map((alert) => `
        <article class="feed-item">
            <div class="feed-meta">
                <div class="status-group">
                    ${renderStatusChip(alert.estado_calidad)}
                    ${renderStatusChip(alert.estado_alerta)}
                </div>
                <span class="secondary-text">${formatTimestamp(alert.created_at)}</span>
            </div>
            <h4>${escapeHtml(alert.elemento)}</h4>
            <p><strong>${escapeHtml(alert.tipo_alerta)}</strong> - ${escapeHtml(alert.detalle)}</p>
            <p class="secondary-text">Responsable: ${escapeHtml(alert.responsable_nombre || "Sin asignar")}</p>
        </article>
    `).join("");
}

function renderPublications(publications) {
    const container = document.querySelector("#recentPublicationsList");
    container.innerHTML = publications.map((item) => `
        <article class="feed-item">
            <div class="feed-meta">
                ${renderStatusChip(item.nivel)}
                <span class="secondary-text">${formatTimestamp(item.created_at)}</span>
            </div>
            <h4>${escapeHtml(item.origen_nombre.replaceAll("_", " "))}</h4>
            <p>${escapeHtml(item.resumen)}</p>
        </article>
    `).join("");
}

async function loadDashboard() {
    try {
        const payload = await apiFetch("/api/dashboard/summary");
        clearNotice(notice);
        updateMetrics(payload.summary);
        renderPointSummary(payload.points);
        renderQualitySummary(payload.points);
        renderAlerts(payload.recent_alerts);
        renderPublications(payload.recent_publications);
    } catch (error) {
        setNotice(notice, error.message, "warning");
    }
}

loadDashboard();
setInterval(loadDashboard, 5000);

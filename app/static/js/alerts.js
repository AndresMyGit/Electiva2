import {
    apiFetch,
    clearNotice,
    escapeHtml,
    formatTimestamp,
    renderStatusChip,
    setNotice,
} from "./common.js";

const notice = document.querySelector("#alertsNotice");
const page = document.querySelector("#alertsPage");
const currentUserId = Number(page?.dataset.currentUserId || 0);
const form = document.querySelector("#workflowForm");
const alertsTableBody = document.querySelector("#alertsTableBody");
const timelineContainer = document.querySelector("#workflowTimeline");
const publicationsFeed = document.querySelector("#publicationsFeed");
const takeOwnershipButton = document.querySelector("#takeOwnershipButton");

let selectedAlertId = null;
let alertsCache = [];
let usersCache = [];
let isSubmittingWorkflow = false;

function snapshotDraft() {
    return {
        status: document.querySelector("#statusSelect").value,
        responsable: document.querySelector("#responsableSelect").value,
        comentario: document.querySelector("#workflowComment").value,
    };
}

function shouldPreserveDraft() {
    if (isSubmittingWorkflow) {
        return false;
    }

    const activeId = document.activeElement?.id;
    return ["workflowComment", "responsableSelect", "statusSelect"].includes(activeId)
        || document.querySelector("#workflowComment").value.trim().length > 0;
}

function restoreDraft(draft) {
    if (!draft) {
        return;
    }

    document.querySelector("#statusSelect").value = draft.status || "nueva";
    document.querySelector("#workflowComment").value = draft.comentario || "";

    const responsableSelect = document.querySelector("#responsableSelect");
    const optionExists = Array.from(responsableSelect.options).some((option) => option.value === draft.responsable);
    responsableSelect.value = optionExists ? draft.responsable : "";
}

function renderMetrics(summary) {
    document.querySelector("#criticalAlertsMetric").textContent = summary.critical_alerts;
    document.querySelector("#newAlertsMetric").textContent = summary.new_alerts;
    document.querySelector("#reviewAlertsMetric").textContent = summary.in_review_alerts;
    document.querySelector("#resolvedAlertsMetric").textContent = summary.resolved_alerts;
}

function renderAlertsTable(alerts) {
    alertsTableBody.innerHTML = alerts.map((alert) => `
        <tr class="clickable-row ${alert.id === selectedAlertId ? "active-row" : ""}" data-alert-id="${alert.id}">
            <td>${formatTimestamp(alert.created_at)}</td>
            <td>
                <strong>${escapeHtml(alert.elemento)}</strong><br>
                <span class="secondary-text">${escapeHtml(alert.tipo_alerta)}</span>
            </td>
            <td>
                <div class="status-group">
                    ${renderStatusChip(alert.estado_alerta)}
                    ${renderStatusChip(alert.estado_calidad)}
                </div>
            </td>
            <td>${escapeHtml(alert.responsable_nombre || "Sin asignar")}</td>
        </tr>
    `).join("");
}

function renderPublications(publications) {
    publicationsFeed.innerHTML = publications.map((item) => `
        <article class="feed-item">
            <div class="feed-meta">
                ${renderStatusChip(item.nivel)}
                <span class="secondary-text">${formatTimestamp(item.created_at)}</span>
            </div>
            <h4>${escapeHtml(item.origen_nombre.replaceAll("_", " "))}</h4>
            <p>${escapeHtml(item.resumen)}</p>
            <p class="secondary-text">${escapeHtml(item.topic_mqtt || "evento interno")}</p>
        </article>
    `).join("");
}

function renderUserOptions(users, selectedId) {
    const select = document.querySelector("#responsableSelect");
    const options = ['<option value="">Sin asignar</option>'].concat(
        users.map((user) => `
            <option value="${user.id}" ${Number(user.id) === Number(selectedId) ? "selected" : ""}>
                ${escapeHtml(user.nombre)} (${escapeHtml(user.rol)})
            </option>
        `)
    );
    select.innerHTML = options.join("");
}

function renderTimeline(entries) {
    if (!entries.length) {
        timelineContainer.innerHTML = `
            <article class="timeline-item">
                <h4>Sin seguimiento</h4>
                <p class="secondary-text">Todavia no hay acciones registradas sobre esta alerta.</p>
            </article>
        `;
        return;
    }

    timelineContainer.innerHTML = entries.map((entry) => `
        <article class="timeline-item">
            <div class="feed-meta">
                ${renderStatusChip(entry.estado_nuevo || "nueva")}
                <span class="secondary-text">${formatTimestamp(entry.created_at)}</span>
            </div>
            <h4>${escapeHtml(entry.actor_nombre)} · ${escapeHtml(entry.accion.replaceAll("_", " "))}</h4>
            <p>${escapeHtml(entry.comentario || "Sin comentario adicional.")}</p>
        </article>
    `).join("");
}

function renderSelectedAlert(alert) {
    if (!alert) {
        document.querySelector("#selectedAlertTitle").textContent = "Selecciona una alerta";
        document.querySelector("#selectedWorkflowStatus").outerHTML = '<span id="selectedWorkflowStatus" class="status-pill neutral">Sin gestionar</span>';
        document.querySelector("#selectedQualityStatus").outerHTML = '<span id="selectedQualityStatus" class="status-pill neutral">Sin calidad</span>';
        document.querySelector("#selectedAlertType").textContent = "--";
        document.querySelector("#selectedSubstation").textContent = "--";
        document.querySelector("#selectedCircuit").textContent = "--";
        document.querySelector("#selectedMeasurementTime").textContent = "--";
        document.querySelector("#selectedAlertDetail").textContent = "Selecciona una alerta para revisar el contexto operativo.";
        document.querySelector("#statusSelect").value = "nueva";
        document.querySelector("#workflowComment").value = "";
        renderUserOptions(usersCache, null);
        timelineContainer.innerHTML = "";
        return;
    }

    document.querySelector("#selectedAlertTitle").textContent = alert.elemento.replaceAll("_", " ");
    document.querySelector("#selectedWorkflowStatus").outerHTML = renderStatusChip(alert.estado_alerta).replace(
        "<span",
        '<span id="selectedWorkflowStatus"'
    );
    document.querySelector("#selectedQualityStatus").outerHTML = renderStatusChip(alert.estado_calidad).replace(
        "<span",
        '<span id="selectedQualityStatus"'
    );

    document.querySelector("#selectedAlertType").textContent = alert.tipo_alerta.replaceAll("_", " ");
    document.querySelector("#selectedSubstation").textContent = alert.subestacion;
    document.querySelector("#selectedCircuit").textContent = alert.circuito;
    document.querySelector("#selectedMeasurementTime").textContent = formatTimestamp(alert.timestamp_medicion);
    document.querySelector("#selectedAlertDetail").textContent = alert.detalle;
    document.querySelector("#statusSelect").value = alert.estado_alerta;
    renderUserOptions(usersCache, alert.responsable_id);
    renderTimeline(alert.timeline || []);
}

async function loadWorkflow() {
    const query = selectedAlertId ? `?selected_id=${selectedAlertId}` : "";
    const preserveDraft = shouldPreserveDraft();
    const draft = preserveDraft ? snapshotDraft() : null;

    try {
        const payload = await apiFetch(`/api/alerts/workflow${query}`);
        clearNotice(notice);
        alertsCache = payload.alerts;
        usersCache = payload.users;

        if (!selectedAlertId && alertsCache.length) {
            selectedAlertId = alertsCache[0].id;
        }

        renderMetrics(payload.summary);
        renderAlertsTable(alertsCache);
        renderSelectedAlert(payload.selected_alert);
        if (preserveDraft && payload.selected_alert && payload.selected_alert.id === selectedAlertId) {
            restoreDraft(draft);
        }
        renderPublications(payload.publications);
    } catch (error) {
        setNotice(notice, error.message, "warning");
    }
}

alertsTableBody.addEventListener("click", (event) => {
    const row = event.target.closest("[data-alert-id]");
    if (!row) {
        return;
    }

    selectedAlertId = Number(row.dataset.alertId);
    loadWorkflow();
});

takeOwnershipButton.addEventListener("click", async () => {
    if (!selectedAlertId) {
        setNotice(notice, "Selecciona una alerta antes de tomarla.", "warning");
        return;
    }

    try {
        isSubmittingWorkflow = true;
        await apiFetch(`/api/alerts/${selectedAlertId}/workflow`, {
            method: "POST",
            body: JSON.stringify({
                estado_alerta: "en_revision",
                responsable_id: currentUserId,
                comentario: "Alerta tomada para revision operativa.",
            }),
        });
        document.querySelector("#workflowComment").value = "";
        await loadWorkflow();
    } catch (error) {
        setNotice(notice, error.message, "danger");
    } finally {
        isSubmittingWorkflow = false;
    }
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!selectedAlertId) {
        setNotice(notice, "Selecciona una alerta antes de guardar seguimiento.", "warning");
        return;
    }

    const responsableValue = document.querySelector("#responsableSelect").value;
    const estadoValue = document.querySelector("#statusSelect").value;
    const comentarioValue = document.querySelector("#workflowComment").value;

    try {
        isSubmittingWorkflow = true;
        await apiFetch(`/api/alerts/${selectedAlertId}/workflow`, {
            method: "POST",
            body: JSON.stringify({
                estado_alerta: estadoValue,
                responsable_id: responsableValue || null,
                comentario: comentarioValue,
            }),
        });
        document.querySelector("#workflowComment").value = "";
        await loadWorkflow();
    } catch (error) {
        setNotice(notice, error.message, "danger");
    } finally {
        isSubmittingWorkflow = false;
    }
});

loadWorkflow();
setInterval(loadWorkflow, 5000);

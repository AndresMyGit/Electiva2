export async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        ...options,
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
        throw new Error(payload.message || "No fue posible completar la solicitud.");
    }
    return payload;
}

export function formatNumber(value, digits = 2) {
    const numeric = Number(value);
    if (value === null || value === undefined || value === "" || Number.isNaN(numeric)) {
        return "--";
    }

    return numeric.toLocaleString("es-CO", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
}

export function formatTimestamp(value) {
    if (!value) {
        return "--";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return new Intl.DateTimeFormat("es-CO", {
        dateStyle: "short",
        timeStyle: "medium",
    }).format(date);
}

export function statusLabel(status) {
    const labels = {
        info: "Info",
        normal: "Normal",
        alerta: "Alerta",
        advertencia: "Advertencia",
        critico: "Critico",
        apagado: "Apagado",
        sin_datos: "Sin datos",
        nueva: "Nueva",
        en_revision: "En revision",
        resuelta: "Resuelta",
    };

    return labels[status] || "Sin datos";
}

export function renderStatusChip(status) {
    return `<span class="status-pill ${status || "neutral"}">${statusLabel(status)}</span>`;
}

export function setNotice(element, message, tone = "info") {
    if (!element) {
        return;
    }
    element.classList.remove("hidden", "notice-info", "notice-warning", "notice-danger");
    element.classList.add(
        tone === "danger"
            ? "notice-danger"
            : tone === "warning"
                ? "notice-warning"
                : "notice-info"
    );
    element.textContent = message;
}

export function clearNotice(element) {
    if (!element) {
        return;
    }
    element.textContent = "";
    element.classList.add("hidden");
}

export function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

export function drawMetricChart(canvas, history, key, color, unit) {
    if (!canvas) {
        return;
    }

    const context = canvas.getContext("2d");
    const values = history
        .map((item) => Number(item[key]))
        .filter((value) => !Number.isNaN(value));

    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);

    if (values.length === 0) {
        context.fillStyle = "#64748b";
        context.font = "14px Segoe UI";
        context.fillText("Sin datos para graficar", 18, 32);
        return;
    }

    const padding = 30;
    const chartWidth = canvas.width - padding * 2;
    const chartHeight = canvas.height - padding * 2;
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const range = maxValue - minValue || 1;

    context.strokeStyle = "#dbeafe";
    context.lineWidth = 1;
    for (let index = 0; index <= 4; index += 1) {
        const y = padding + (chartHeight / 4) * index;
        context.beginPath();
        context.moveTo(padding, y);
        context.lineTo(canvas.width - padding, y);
        context.stroke();
    }

    context.strokeStyle = color;
    context.lineWidth = 3;
    context.beginPath();
    values.forEach((value, index) => {
        const x = padding + (chartWidth / Math.max(values.length - 1, 1)) * index;
        const y = padding + chartHeight - (((value - minValue) / range) * chartHeight);
        if (index === 0) {
            context.moveTo(x, y);
        } else {
            context.lineTo(x, y);
        }
    });
    context.stroke();

    context.fillStyle = color;
    values.forEach((value, index) => {
        const x = padding + (chartWidth / Math.max(values.length - 1, 1)) * index;
        const y = padding + chartHeight - (((value - minValue) / range) * chartHeight);
        context.beginPath();
        context.arc(x, y, 3.2, 0, Math.PI * 2);
        context.fill();
    });

    context.fillStyle = "#0f172a";
    context.font = "bold 14px Segoe UI";
    context.fillText(`${formatNumber(values[values.length - 1], 2)} ${unit}`, 18, canvas.height - 12);
}

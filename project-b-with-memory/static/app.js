async function fetchDeliveries() {
  try {
    const res = await fetch("/api/v1/deliveries?limit=50");
    if (!res.ok) throw new Error("Failed to load logs");
    const logs = await res.json();
    renderDeliveries(logs);
  } catch (err) {
    document.getElementById("deliveryTableBody").innerHTML = `<tr><td colspan="8" style="color: #ef4444; text-align: center;">Error loading deliveries: ${err.message}</td></tr>`;
  }
}

function renderDeliveries(logs) {
  const tbody = document.getElementById("deliveryTableBody");
  if (!logs || logs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #94a3b8;">No webhook deliveries recorded yet. Ingest an event to see live data.</td></tr>`;
    updateMetrics(0, 0, 0, 0);
    return;
  }

  let delivered = 0, retrying = 0, failed = 0;
  let rows = "";

  for (const log of logs) {
    if (log.status === "DELIVERED") delivered++;
    else if (log.status === "RETRYING") retrying++;
    else if (log.status === "FAILED") failed++;

    const dateStr = new Date(log.created_at).toLocaleTimeString();
    rows += `
      <tr>
        <td><span class="badge ${log.status}">${log.status}</span></td>
        <td style="font-family: monospace;">${log.event_id}</td>
        <td><strong>${log.topic}</strong></td>
        <td style="color: #94a3b8; font-size: 0.85rem;">${log.destination_url}</td>
        <td>${log.attempts}</td>
        <td>${log.last_http_status ? `<code>${log.last_http_status}</code>` : "—"}</td>
        <td style="color: #94a3b8;">${dateStr}</td>
        <td>
          <button class="btn btn-sm" onclick="redeliver('${log.id}')">Redeliver</button>
        </td>
      </tr>
    `;
  }

  tbody.innerHTML = rows;
  updateMetrics(logs.length, delivered, retrying, failed);
}

function updateMetrics(total, delivered, retrying, failed) {
  document.getElementById("totalCount").innerText = total;
  document.getElementById("deliveredCount").innerText = delivered;
  document.getElementById("retryingCount").innerText = retrying;
  document.getElementById("failedCount").innerText = failed;
}

async function redeliver(logId) {
  try {
    const res = await fetch(`/api/v1/deliveries/${logId}/redeliver`, { method: "POST" });
    if (!res.ok) alert("Redelivery failed");
    else fetchDeliveries();
  } catch (e) {
    alert("Error triggering redelivery: " + e.message);
  }
}

document.getElementById("refreshBtn").addEventListener("click", fetchDeliveries);
document.addEventListener("DOMContentLoaded", () => {
  fetchDeliveries();
  setInterval(fetchDeliveries, 5000); // 5s polling
});

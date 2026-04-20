function pulseToast(message, isError = false) {
  const host = document.getElementById('toast-stack');
  if (!host) return;
  const el = document.createElement('div');
  el.className = `toast ${isError ? 'error' : ''}`;
  el.textContent = message;
  host.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

async function pulseApi(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || data.error || 'Request failed');
  }

  return response.json();
}

function pulseMoney(value) {
  const num = Number(value || 0);
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'KZT',
    maximumFractionDigits: 0,
  }).format(num);
}

function pulseSafe(text) {
  if (text === null || text === undefined) return '-';
  return String(text);
}

function pulseRenderTable(rootId, rows) {
  const table = document.getElementById(rootId);
  if (!table) return;
  if (!rows || !rows.length) {
    table.innerHTML = '<tbody><tr><td>Нет данных</td></tr></tbody>';
    return;
  }

  const headers = Object.keys(rows[0]);
  const thead = `<thead><tr>${headers.map((h) => `<th>${h}</th>`).join('')}</tr></thead>`;
  const tbody = `<tbody>${rows
    .map((row) => `<tr>${headers.map((h) => `<td>${pulseSafe(row[h])}</td>`).join('')}</tr>`)
    .join('')}</tbody>`;

  table.innerHTML = thead + tbody;
}

"""A small static HTML/JS test console for exercising a running daemon's
control API by hand against real hardware -- built for hardware bring-up
testing (item 6) without needing `backend`/`frontend` at all.

Served by control_api.py at `GET /`. Deliberately a single self-contained
page (inline CSS/JS, no build step, no external requests) so it works the
same served from a Pi with no internet access. All calls are same-origin
relative fetches against this same control API, so no CORS handling is
needed.
"""

TEST_PAGE_HTML = b"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>lora-daemon test console</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; margin: 1.5rem; max-width: 900px; }
  h1 { font-size: 1.3rem; }
  h2 { font-size: 1.05rem; margin-top: 2rem; border-bottom: 1px solid #8884; padding-bottom: .25rem; }
  fieldset { margin: .5rem 0 1rem; border: 1px solid #8884; border-radius: 6px; }
  label { display: inline-block; min-width: 9rem; }
  input[type=text], input[type=number] { padding: .3rem; width: 14rem; }
  button { padding: .35rem .8rem; margin: .2rem .3rem .2rem 0; cursor: pointer; }
  table { border-collapse: collapse; width: 100%; margin-top: .5rem; }
  th, td { border: 1px solid #8884; padding: .3rem .5rem; text-align: left; font-size: .9rem; }
  #log { font-family: ui-monospace, monospace; font-size: .8rem; white-space: pre-wrap;
         max-height: 12rem; overflow-y: auto; background: #8881; padding: .5rem; border-radius: 6px; }
  .row { margin: .4rem 0; }
  .muted { opacity: .7; font-size: .85rem; }
</style>
</head>
<body>
<h1>lora-daemon test console</h1>
<p class="muted">Talks directly to this daemon's control API (same origin, no backend/frontend involved).</p>

<h2>Status</h2>
<div class="row">
  Ping loop: <strong id="paused-state">?</strong>
  <button onclick="call('POST','/pause')">Pause</button>
  <button onclick="call('POST','/resume')">Resume</button>
</div>
<div class="row">Pingable addresses: <span id="pingable-list">-</span></div>
<table id="pongs-table">
  <thead><tr><th>Address</th><th>Active</th><th>Roundtrip (ms)</th><th>Seen at</th><th>Missing parts</th></tr></thead>
  <tbody></tbody>
</table>

<h2>Known devices (from DB)</h2>
<table id="devices-table">
  <thead><tr><th>device_id</th><th>type</th><th>active</th><th>config_version</th>
  <th>synced_version</th><th>last_seen</th><th>roundtrip (ms)</th><th>sync status</th></tr></thead>
  <tbody></tbody>
</table>

<h2>Ping</h2>
<fieldset>
  <div class="row">
    <label for="ping-address">Raw address (0-255)</label>
    <input type="number" id="ping-address" min="0" max="255">
    <button onclick="pingAddress()">Ping address</button>
  </div>
  <div class="row">
    <label for="ping-device-id">device_id</label>
    <input type="text" id="ping-device-id" placeholder="lumestrio3">
    <button onclick="pingDevice()">Ping device</button>
  </div>
  <div class="row">
    <button onclick="call('POST','/ping-all')">Ping all known devices</button>
  </div>
</fieldset>

<h2>Activate</h2>
<fieldset>
  <div class="row">
    <label for="activate-addresses">Addresses (comma-sep, blank = broadcast)</label>
    <input type="text" id="activate-addresses" placeholder="e.g. 3,35">
  </div>
  <div class="row">
    <button onclick="activate(true)">Activate ON</button>
    <button onclick="activate(false)">Activate OFF</button>
  </div>
</fieldset>

<h2>Calendar / config sync</h2>
<fieldset>
  <div class="row">
    <label for="sync-device-id">device_id (must exist in DB)</label>
    <input type="text" id="sync-device-id" placeholder="lumestrio3">
    <button onclick="syncConfig()">Sync config now</button>
  </div>
  <p class="muted">Pushes the device's full config over a versioned FILE_MSG
  transfer, then verifies delivery via missing-parts pings -- can take
  several seconds; watch the devices table above or the log below.</p>
</fieldset>

<h2>Log</h2>
<div id="log"></div>

<script>
function log(line) {
  const el = document.getElementById('log');
  const ts = new Date().toLocaleTimeString();
  el.textContent = `[${ts}] ${line}\n` + el.textContent;
}

async function call(method, path, body) {
  try {
    const opts = { method };
    if (body !== undefined) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    const text = await res.text();
    let parsed = text;
    try { parsed = JSON.parse(text); } catch (e) {}
    log(`${method} ${path} -> ${res.status} ${JSON.stringify(parsed)}`);
    return parsed;
  } catch (e) {
    log(`${method} ${path} -> FETCH ERROR ${e}`);
    throw e;
  }
}

function parseAddresses(raw) {
  const s = raw.trim();
  if (!s) return null;
  return s.split(',').map(x => parseInt(x.trim(), 10)).filter(x => !Number.isNaN(x));
}

function pingAddress() {
  const address = parseInt(document.getElementById('ping-address').value, 10);
  if (Number.isNaN(address)) { log('enter a valid address first'); return; }
  call('POST', '/ping-address', { address });
}

function pingDevice() {
  const id = document.getElementById('ping-device-id').value.trim();
  if (!id) { log('enter a device_id first'); return; }
  call('POST', `/devices/${encodeURIComponent(id)}/ping`);
}

function activate(active) {
  const addresses = parseAddresses(document.getElementById('activate-addresses').value);
  call('POST', '/activate', { active, addresses });
}

function syncConfig() {
  const id = document.getElementById('sync-device-id').value.trim();
  if (!id) { log('enter a device_id first'); return; }
  call('POST', `/devices/${encodeURIComponent(id)}/sync-config`);
}

async function refreshStatus() {
  try {
    const [status, devicesRes] = await Promise.all([
      fetch('/status').then(r => r.json()),
      fetch('/devices').then(r => r.json()),
    ]);

    document.getElementById('paused-state').textContent = status.paused ? 'PAUSED' : 'running';
    document.getElementById('pingable-list').textContent =
      status.pingable.length ? status.pingable.join(', ') : '(none)';

    const pongsBody = document.querySelector('#pongs-table tbody');
    pongsBody.innerHTML = '';
    for (const [address, info] of Object.entries(status.last_pongs)) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${address}</td><td>${info.active}</td><td>${info.roundtrip_ms}</td>
        <td>${info.seen_at}</td><td>${info.missing_parts ?? '-'}</td>`;
      pongsBody.appendChild(tr);
    }

    const devicesBody = document.querySelector('#devices-table tbody');
    devicesBody.innerHTML = '';
    for (const d of devicesRes.devices) {
      const sync = status.sync_status[d.device_id];
      const syncLabel = sync ? `${sync.state}${sync.success !== null && sync.success !== undefined ? ' (' + sync.success + ')' : ''}` : '-';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${d.device_id}</td><td>${d.device_type}</td><td>${d.active}</td>
        <td>${d.config_version}</td><td>${d.synced_version}</td>
        <td>${d.last_seen ?? '-'}</td><td>${d.last_roundtrip_ms ?? '-'}</td><td>${syncLabel}</td>`;
      devicesBody.appendChild(tr);
    }
  } catch (e) {
    log(`status refresh failed: ${e}`);
  }
}

refreshStatus();
setInterval(refreshStatus, 2000);
</script>
</body>
</html>
"""

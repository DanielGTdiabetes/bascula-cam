(() => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const flashContainer = document.querySelector('[data-flash-live]');

    function createFlash(message, kind = 'info') {
        const el = document.createElement('div');
        el.className = `flash flash-${kind}`;
        el.textContent = message;
        return el;
    }

    function pushFlash(message, kind = 'info') {
        if (!flashContainer) {
            return;
        }
        const flash = createFlash(message, kind);
        flashContainer.appendChild(flash);
        setTimeout(() => {
            flash.classList.add('is-fading');
            flash.style.transition = 'opacity 0.3s ease';
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 600);
        }, 4500);
    }

    function extractMessage(payload, fallback = 'Operación completada') {
        if (!payload) {
            return fallback;
        }
        if (typeof payload === 'string') {
            return payload;
        }
        if (payload.detail) {
            return typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail);
        }
        if (payload.note) {
            return payload.note;
        }
        if (payload.error) {
            return payload.error;
        }
        if (payload.status && payload.status_text) {
            return payload.status_text;
        }
        return fallback;
    }

    async function fetchJSON(url, options = {}) {
        const response = await fetch(url, options);
        if (response.status === 401) {
            window.location.href = '/login';
            return Promise.reject(new Error('Sesión expirada'));
        }
        const contentType = response.headers.get('content-type') || '';
        const isJson = contentType.includes('application/json');
        const payload = isJson ? await response.json() : await response.text();
        if (!response.ok) {
            const message = extractMessage(payload, `Error ${response.status}`);
            const error = new Error(message);
            error.payload = payload;
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    function toJSON(formData) {
        const data = {};
        for (const [key, value] of formData.entries()) {
            if (typeof value === 'string') {
                if (value === 'true') {
                    data[key] = true;
                } else if (value === 'false') {
                    data[key] = false;
                } else {
                    data[key] = value;
                }
            }
        }
        return data;
    }

    function setFeedback(selector, message, kind = 'info') {
        if (!selector) {
            return;
        }
        const target = document.querySelector(selector);
        if (!target) {
            return;
        }
        target.textContent = message;
        target.dataset.state = kind;
    }

    async function handleAsyncForm(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const submitter = event.submitter;
        const endpoint = submitter?.dataset.endpoint || form.getAttribute('action') || submitter?.getAttribute('formaction');
        if (!endpoint) {
            return;
        }
        const method = (submitter?.dataset.method || form.getAttribute('method') || 'POST').toUpperCase();
        const format = submitter?.dataset.format || form.dataset.format || 'json';
        const successMessage = submitter?.dataset.success || form.dataset.success || 'Operación completada';
        const errorMessage = submitter?.dataset.error || form.dataset.error || 'No se pudo completar la acción';
        const feedbackTarget = submitter?.dataset.feedbackTarget || form.dataset.feedbackTarget;
        const confirmMessage = submitter?.dataset.confirm || form.dataset.confirm;
        if (confirmMessage && !window.confirm(confirmMessage)) {
            return;
        }

        const formData = new FormData(form);
        if (csrfToken) {
            formData.set('csrf_token', csrfToken);
        }

        const headers = {};
        let body = formData;
        if (format === 'json') {
            const data = toJSON(formData);
            if (csrfToken) {
                data.csrf_token = csrfToken;
            }
            body = JSON.stringify(data);
            headers['Content-Type'] = 'application/json';
        }
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        const button = submitter;
        if (button) {
            button.disabled = true;
        }

        try {
            const payload = await fetchJSON(endpoint, { method, headers, body });
            const message = extractMessage(payload, successMessage);
            pushFlash(message, 'success');
            setFeedback(feedbackTarget, message, 'success');
        } catch (error) {
            const message = error instanceof Error ? error.message : errorMessage;
            pushFlash(message, 'error');
            setFeedback(feedbackTarget, message, 'error');
        } finally {
            if (button) {
                button.disabled = false;
            }
        }
    }

    document.querySelectorAll('form[data-async="true"]').forEach((form) => {
        form.addEventListener('submit', handleAsyncForm);
    });

    async function handleApiAction(event) {
        const button = event.currentTarget;
        const endpoint = button.dataset.apiAction;
        if (!endpoint) {
            return;
        }
        const method = (button.dataset.apiMethod || 'POST').toUpperCase();
        const confirmMessage = button.dataset.apiConfirm;
        if (confirmMessage && !window.confirm(confirmMessage)) {
            return;
        }
        let payload = {};
        if (button.dataset.apiPayload) {
            try {
                payload = JSON.parse(button.dataset.apiPayload);
            } catch (error) {
                console.warn('Payload inválido', error);
            }
        }
        if (button.dataset.apiPrompt) {
            const promptText = button.dataset.apiPrompt;
            const value = window.prompt(promptText, '');
            if (!value) {
                return;
            }
            payload[button.dataset.apiPromptField || 'value'] = value;
        }
        if (csrfToken) {
            payload.csrf_token = csrfToken;
        }
        const headers = { 'Content-Type': 'application/json' };
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }
        button.disabled = true;
        try {
            const response = await fetchJSON(endpoint, {
                method,
                headers,
                body: JSON.stringify(payload),
            });
            const message = extractMessage(response, button.dataset.apiSuccess || 'Acción enviada');
            pushFlash(message, 'success');
            if (button.dataset.otaRefresh === 'true') {
                startOtaPolling();
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : 'No se pudo completar la acción';
            pushFlash(message, 'error');
        } finally {
            button.disabled = false;
        }
    }

    document.querySelectorAll('[data-api-action]').forEach((el) => {
        el.addEventListener('click', handleApiAction);
    });

    // Wi-Fi helpers
    const wifiStatusBox = document.querySelector('[data-wifi-status]');
    const wifiFeedback = document.querySelector('[data-wifi-feedback]');
    function renderWifiStatus(data) {
        if (!wifiStatusBox) {
            return;
        }
        const errorDetail = data.error || data.ssid_error || data.signal_error;
        const ssid = data.ssid || 'Sin conexión';
        const ip = data.ip || '—';
        const signal = typeof data.signal === 'number' ? `${data.signal}%` : '—';
        wifiStatusBox.innerHTML = `
            <ul class="status-list">
                <li><span>SSID</span><span>${ssid}</span></li>
                <li><span>IP</span><span>${ip}</span></li>
                <li><span>Intensidad</span><span>${signal}</span></li>
            </ul>
            ${errorDetail ? `<p class="muted small">${errorDetail}</p>` : ''}
        `;
    }

    async function refreshWifiStatus() {
        try {
            const data = await fetchJSON('/config/wifi/status');
            renderWifiStatus(data);
        } catch (error) {
            pushFlash('No se pudo obtener el estado Wi-Fi', 'error');
        }
    }

    const wifiRefreshButton = document.querySelector('[data-wifi-refresh]');
    if (wifiRefreshButton) {
        wifiRefreshButton.addEventListener('click', () => {
            wifiRefreshButton.disabled = true;
            refreshWifiStatus().finally(() => {
                wifiRefreshButton.disabled = false;
            });
        });
    }

    const wifiScanButton = document.querySelector('[data-wifi-scan]');
    const wifiList = document.querySelector('[data-wifi-list]');
    function renderWifiNetworks(networks = []) {
        if (!wifiList) {
            return;
        }
        wifiList.innerHTML = '';
        if (!networks.length) {
            const empty = document.createElement('li');
            empty.className = 'muted';
            empty.textContent = 'No se encontraron redes disponibles.';
            wifiList.appendChild(empty);
            return;
        }
        networks.forEach((network) => {
            const li = document.createElement('li');
            const info = document.createElement('div');
            info.innerHTML = `<strong>${network.ssid || '(sin SSID)'}</strong><br><span class="muted">${network.signal ?? '—'} dBm</span>`;
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'button ghost';
            button.textContent = 'Usar';
            button.dataset.fillSsid = network.ssid || '';
            li.appendChild(info);
            li.appendChild(button);
            wifiList.appendChild(li);
        });
    }

    if (wifiScanButton) {
        wifiScanButton.addEventListener('click', async () => {
            wifiScanButton.disabled = true;
            if (wifiFeedback) {
                wifiFeedback.textContent = 'Buscando redes…';
                wifiFeedback.dataset.state = 'info';
            }
            try {
                const data = await fetchJSON('/config/wifi/scan');
                renderWifiNetworks(data.networks || []);
                pushFlash('Exploración Wi-Fi completada', 'success');
                if (wifiFeedback) {
                    wifiFeedback.textContent = data.error ? `Error: ${data.error}` : `${(data.networks || []).length} redes encontradas`;
                }
            } catch (error) {
                pushFlash('No se pudo escanear redes Wi-Fi', 'error');
                if (wifiFeedback) {
                    wifiFeedback.textContent = 'Error al escanear redes';
                    wifiFeedback.dataset.state = 'error';
                }
            } finally {
                wifiScanButton.disabled = false;
            }
        });
    }

    document.addEventListener('click', (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return;
        }
        if (target.dataset.fillSsid) {
            const ssidField = document.querySelector('[data-ssid-input]');
            if (ssidField instanceof HTMLInputElement) {
                ssidField.value = target.dataset.fillSsid;
                ssidField.focus();
                pushFlash(`SSID seleccionado: ${target.dataset.fillSsid}`, 'info');
            }
        }
    });

    const initialWifiData = wifiStatusBox?.dataset.initial;
    if (initialWifiData) {
        try {
            renderWifiStatus(JSON.parse(initialWifiData));
        } catch (error) {
            /* noop */
        }
    }

    // OTA helpers
    const otaStatusBox = document.querySelector('[data-ota-status]');
    const otaProgress = document.querySelector('[data-ota-progress]');
    let otaTimer = null;

    function renderOtaStatus(data) {
        if (!otaStatusBox) {
            return;
        }
        const rows = [];
        if (data.error) {
            rows.push(`<li><span>Error</span><span>${data.error}</span></li>`);
        }
        if (data.remote) {
            rows.push(`<li><span>Remoto</span><span>${data.remote}</span></li>`);
        }
        if (data.branch) {
            rows.push(`<li><span>Canal</span><span>${data.branch}</span></li>`);
        }
        if (data.head) {
            rows.push(`<li><span>HEAD actual</span><span>${data.head}</span></li>`);
        }
        if (typeof data.behind === 'number') {
            rows.push(`<li><span>Commits pendientes</span><span>${data.behind}</span></li>`);
        }
        if (data.latest_remote) {
            rows.push(`<li><span>Último remoto</span><span>${data.latest_remote}</span></li>`);
        }
        otaStatusBox.innerHTML = `<ul class="status-list">${rows.join('')}</ul>`;
    }

    async function refreshOtaStatus() {
        try {
            const data = await fetchJSON('/ota/status');
            renderOtaStatus(data);
        } catch (error) {
            pushFlash('No se pudo obtener el estado OTA', 'error');
        }
    }

    function startOtaPolling() {
        if (otaProgress) {
            otaProgress.classList.add('is-active');
        }
        if (otaTimer) {
            return;
        }
        refreshOtaStatus();
        otaTimer = setInterval(refreshOtaStatus, 2000);
        setTimeout(() => stopOtaPolling(), 120000);
    }

    function stopOtaPolling() {
        if (otaTimer) {
            clearInterval(otaTimer);
            otaTimer = null;
        }
        if (otaProgress) {
            otaProgress.classList.remove('is-active');
        }
    }

    const initialOtaData = otaStatusBox?.dataset.initial;
    if (initialOtaData) {
        try {
            renderOtaStatus(JSON.parse(initialOtaData));
        } catch (error) {
            /* noop */
        }
    }

    document.querySelectorAll('[data-ota-refresh]').forEach((el) => {
        el.addEventListener('click', () => {
            startOtaPolling();
        });
    });

    const otaChangeButton = document.querySelector('[data-ota-change]');
    if (otaChangeButton) {
        otaChangeButton.addEventListener('click', async () => {
            const branch = window.prompt('Indica el nuevo canal (rama) OTA:', '');
            if (!branch) {
                return;
            }
            try {
                const payload = { branch, csrf_token: csrfToken };
                const headers = { 'Content-Type': 'application/json' };
                if (csrfToken) {
                    headers['X-CSRF-Token'] = csrfToken;
                }
                await fetchJSON('/ota/set-channel', {
                    method: 'POST',
                    headers,
                    body: JSON.stringify(payload),
                });
                pushFlash(`Canal OTA actualizado a ${branch}`, 'success');
                startOtaPolling();
            } catch (error) {
                const message = error instanceof Error ? error.message : 'No se pudo cambiar el canal';
                pushFlash(message, 'error');
            }
        });
    }

    // Diagnostics refresh
    const diagnosticsRefresh = document.querySelector('[data-diagnostics-refresh]');
    const diagnosticsTarget = document.querySelector('[data-diagnostics]');
    if (diagnosticsRefresh && diagnosticsTarget) {
        diagnosticsRefresh.addEventListener('click', async () => {
            diagnosticsRefresh.disabled = true;
            try {
                const data = await fetchJSON('/recovery/diagnostics');
                const rows = Object.entries(data).map(([key, value]) => `<tr><th>${key}</th><td>${typeof value === 'string' ? value : JSON.stringify(value)}</td></tr>`).join('');
                diagnosticsTarget.innerHTML = `<table class="table-like">${rows}</table>`;
                pushFlash('Diagnóstico actualizado', 'success');
            } catch (error) {
                pushFlash('No se pudo cargar el diagnóstico', 'error');
            } finally {
                diagnosticsRefresh.disabled = false;
            }
        });
    }
})();

const secretContainer = document.getElementById('secret-forms');
const testStatus = document.getElementById('test-status');
const toast = document.getElementById('toast');

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (payload && payload.detail) detail = payload.detail;
    } catch (err) {
      // ignore json errors
    }
    throw new Error(detail);
  }
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch (err) {
    return text;
  }
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 1800);
}

function renderSecrets(secrets) {
  secretContainer.innerHTML = '';
  secrets.forEach((secret) => {
    const form = document.createElement('form');
    form.className = 'secret-form';
    form.dataset.key = secret.key;

    const inputWrapper = document.createElement('div');
    inputWrapper.className = 'secret-input';

    const label = document.createElement('label');
    label.textContent = secret.label;
    label.htmlFor = `secret-${secret.key}`;

    const input = document.createElement('input');
    input.id = `secret-${secret.key}`;
    input.type = 'password';
    input.placeholder = secret.has_value ? '••••••••' : 'Introduce valor';
    input.autocomplete = 'off';

    inputWrapper.appendChild(label);
    inputWrapper.appendChild(input);

    const actions = document.createElement('div');

    const saveButton = document.createElement('button');
    saveButton.type = 'submit';
    saveButton.textContent = 'Guardar';
    saveButton.className = 'primary';

    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.textContent = 'Eliminar';
    deleteButton.className = 'secondary';

    actions.appendChild(saveButton);
    actions.appendChild(deleteButton);

    form.appendChild(inputWrapper);
    form.appendChild(actions);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const value = input.value.trim();
      try {
        await api(`/api/config/secret/${secret.key}`, {
          method: 'POST',
          body: JSON.stringify({ value })
        });
        showToast('Guardado');
        if (value) {
          input.placeholder = '••••••••';
        } else {
          input.placeholder = 'Introduce valor';
        }
        input.value = '';
      } catch (err) {
        showToast(err.message);
      }
    });

    deleteButton.addEventListener('click', async () => {
      try {
        await api(`/api/config/secret/${secret.key}`, { method: 'DELETE' });
        showToast('Eliminado');
        input.value = '';
        input.placeholder = 'Introduce valor';
      } catch (err) {
        showToast(err.message);
      }
    });

    secretContainer.appendChild(form);
  });
}

async function loadSchema() {
  try {
    const schema = await api('/api/config/schema');
    renderSecrets(schema.secrets || []);
  } catch (err) {
    secretContainer.innerHTML = `<p class="status">${err.message}</p>`;
  }
}

async function testAemet() {
  try {
    const result = await api('/api/aemet/test');
    testStatus.textContent = JSON.stringify(result, null, 2);
  } catch (err) {
    testStatus.textContent = `Error: ${err.message}`;
  }
}

async function testOpenSky() {
  try {
    const result = await api('/api/opensky/test');
    testStatus.textContent = JSON.stringify(result, null, 2);
  } catch (err) {
    testStatus.textContent = `Error: ${err.message}`;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  loadSchema();
  document.getElementById('test-aemet').addEventListener('click', testAemet);
  document.getElementById('test-opensky').addEventListener('click', testOpenSky);
});

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bascula/services/wifi_config.py
Servidor web para configuración WiFi y API Key
"""
import os
import json
import time
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import logging

log = logging.getLogger("wifi_config")

CONFIG_FILE = os.path.expanduser("~/.bascula/wifi_config.json")

class WifiConfig:
    """Gestión de configuración WiFi"""
    
    @staticmethod
    def load_config():
        """Cargar configuración guardada"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            log.error(f"Error cargando config: {e}")
        return {}
    
    @staticmethod
    def save_config(config):
        """Guardar configuración"""
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    
    @staticmethod
    def scan_networks():
        """Escanear redes WiFi disponibles"""
        try:
            result = subprocess.run(
                ['sudo', 'iwlist', 'wlan0', 'scan'],
                capture_output=True, text=True, timeout=10
            )
            
            networks = []
            current = {}
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                
                if 'Cell' in line:
                    if current and 'ssid' in current:
                        networks.append(current)
                    current = {}
                
                if 'ESSID:' in line:
                    ssid = line.split('ESSID:')[1].strip('"')
                    if ssid:
                        current['ssid'] = ssid
                
                if 'Quality=' in line:
                    try:
                        quality = line.split('Quality=')[1].split('/')[0]
                        current['quality'] = int(quality)
                    except:
                        pass
                
                if 'Encryption key:on' in line:
                    current['encrypted'] = True
                elif 'Encryption key:off' in line:
                    current['encrypted'] = False
            
            if current and 'ssid' in current:
                networks.append(current)
            
            # Ordenar por calidad de señal
            networks.sort(key=lambda x: x.get('quality', 0), reverse=True)
            
            return networks
        
        except Exception as e:
            log.error(f"Error escaneando redes: {e}")
            return []
    
    @staticmethod
    def connect_to_network(ssid, password):
        """Conectar a una red WiFi"""
        try:
            # Crear configuración wpa_supplicant
            wpa_config = f'''
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=ES

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
'''
            
            # Guardar configuración temporal
            temp_file = '/tmp/wpa_temp.conf'
            with open(temp_file, 'w') as f:
                f.write(wpa_config)
            
            # Copiar a wpa_supplicant
            subprocess.run(['sudo', 'cp', temp_file, '/etc/wpa_supplicant/wpa_supplicant.conf'])
            
            # Reiniciar WiFi
            subprocess.run(['sudo', 'systemctl', 'restart', 'wpa_supplicant'])
            time.sleep(2)
            subprocess.run(['sudo', 'dhclient', 'wlan0'])
            
            # Verificar conexión
            time.sleep(3)
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
            
            if result.stdout.strip() == ssid:
                return True, "Conectado exitosamente"
            else:
                return False, "No se pudo conectar"
        
        except Exception as e:
            log.error(f"Error conectando: {e}")
            return False, str(e)
    
    @staticmethod
    def create_access_point():
        """Crear punto de acceso para configuración"""
        try:
            # Configurar hostapd
            hostapd_conf = '''
interface=wlan0
driver=nl80211
ssid=Bascula-Setup
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
'''
            
            with open('/tmp/hostapd.conf', 'w') as f:
                f.write(hostapd_conf)
            
            # Configurar dnsmasq
            dnsmasq_conf = '''
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
'''
            
            with open('/tmp/dnsmasq.conf', 'w') as f:
                f.write(dnsmasq_conf)
            
            # Configurar IP estática
            subprocess.run(['sudo', 'ifconfig', 'wlan0', '192.168.4.1'])
            
            # Iniciar servicios
            subprocess.run(['sudo', 'hostapd', '-B', '/tmp/hostapd.conf'])
            subprocess.run(['sudo', 'dnsmasq', '-C', '/tmp/dnsmasq.conf'])
            
            return True
        
        except Exception as e:
            log.error(f"Error creando AP: {e}")
            return False


class ConfigRequestHandler(BaseHTTPRequestHandler):
    """Manejador de peticiones HTTP para configuración"""
    
    def do_GET(self):
        """Manejar peticiones GET"""
        if self.path == '/':
            self.send_main_page()
        elif self.path == '/scan':
            self.send_scan_results()
        elif self.path == '/status':
            self.send_status()
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Manejar peticiones POST"""
        if self.path == '/connect':
            self.handle_connect()
        elif self.path == '/save_api':
            self.handle_save_api()
        else:
            self.send_error(404)
    
    def send_main_page(self):
        """Enviar página principal de configuración"""
        config = WifiConfig.load_config()
        current_ssid = config.get('ssid', 'No configurado')
        api_key = config.get('openai_api_key', '')
        api_masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "No configurada"
        
        html = f'''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configuración Báscula Digital</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #0a0e1a 0%, #1a1f2e 100%);
            color: #f0f4f8;
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 600px;
            margin: 0 auto;
        }}
        
        .card {{
            background: #141823;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            border: 1px solid #2a3142;
        }}
        
        h1 {{
            color: #00d4aa;
            margin-bottom: 10px;
            font-size: 28px;
        }}
        
        h2 {{
            color: #00d4aa;
            margin-bottom: 20px;
            font-size: 20px;
            border-bottom: 2px solid #2a3142;
            padding-bottom: 10px;
        }}
        
        .status {{
            padding: 12px;
            background: #1a1f2e;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #00d4aa;
        }}
        
        .form-group {{
            margin-bottom: 20px;
        }}
        
        label {{
            display: block;
            margin-bottom: 8px;
            color: #8892a0;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        input, select {{
            width: 100%;
            padding: 12px;
            background: #1a1f2e;
            border: 1px solid #2a3142;
            border-radius: 8px;
            color: #f0f4f8;
            font-size: 16px;
            transition: all 0.3s;
        }}
        
        input:focus, select:focus {{
            outline: none;
            border-color: #00d4aa;
            box-shadow: 0 0 0 3px rgba(0, 212, 170, 0.1);
        }}
        
        button {{
            background: #00d4aa;
            color: #0a0e1a;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            margin-right: 10px;
            margin-top: 10px;
        }}
        
        button:hover {{
            background: #00ffcc;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 212, 170, 0.3);
        }}
        
        button:active {{
            transform: translateY(0);
        }}
        
        .secondary-btn {{
            background: transparent;
            color: #00d4aa;
            border: 2px solid #00d4aa;
        }}
        
        .secondary-btn:hover {{
            background: #00d4aa;
            color: #0a0e1a;
        }}
        
        .network-list {{
            max-height: 300px;
            overflow-y: auto;
            background: #1a1f2e;
            border-radius: 8px;
            padding: 10px;
        }}
        
        .network-item {{
            padding: 12px;
            margin-bottom: 8px;
            background: #141823;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .network-item:hover {{
            background: #2a3142;
            transform: translateX(4px);
        }}
        
        .signal {{
            font-size: 12px;
            color: #8892a0;
        }}
        
        .loading {{
            text-align: center;
            padding: 20px;
            color: #8892a0;
        }}
        
        .spinner {{
            border: 3px solid #2a3142;
            border-top: 3px solid #00d4aa;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        .toast {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #00d4aa;
            color: #0a0e1a;
            padding: 16px 24px;
            border-radius: 8px;
            font-weight: bold;
            animation: slideIn 0.3s;
            z-index: 1000;
        }}
        
        @keyframes slideIn {{
            from {{
                transform: translateX(100%);
                opacity: 0;
            }}
            to {{
                transform: translateX(0);
                opacity: 1;
            }}
        }}
        
        .error {{
            background: #ff6b6b;
        }}
        
        .warning {{
            background: #ffa500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>⚖️ Báscula Digital Pro</h1>
            <p style="color: #8892a0;">Panel de Configuración</p>
        </div>
        
        <div class="card">
            <h2>📶 Configuración WiFi</h2>
            
            <div class="status">
                <strong>Estado actual:</strong> <span id="wifi-status">{current_ssid}</span>
            </div>
            
            <div class="form-group">
                <label>Redes Disponibles</label>
                <div id="network-list" class="network-list">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Escaneando redes...</p>
                    </div>
                </div>
            </div>
            
            <div class="form-group">
                <label>Red Seleccionada</label>
                <input type="text" id="ssid" placeholder="Nombre de la red WiFi">
            </div>
            
            <div class="form-group">
                <label>Contraseña</label>
                <input type="password" id="password" placeholder="Contraseña de la red">
            </div>
            
            <button onclick="connectWifi()">Conectar WiFi</button>
            <button class="secondary-btn" onclick="scanNetworks()">Actualizar Lista</button>
        </div>
        
        <div class="card">
            <h2>🔑 API Key de OpenAI</h2>
            
            <div class="status">
                <strong>API Key actual:</strong> <span id="api-status">{api_masked}</span>
            </div>
            
            <div class="form-group">
                <label>Nueva API Key</label>
                <input type="password" id="apikey" placeholder="sk-...">
            </div>
            
            <button onclick="saveApiKey()">Guardar API Key</button>
        </div>
    </div>
    
    <script>
        // Escanear redes al cargar
        window.onload = function() {{
            scanNetworks();
            checkStatus();
        }};
        
        function scanNetworks() {{
            const list = document.getElementById('network-list');
            list.innerHTML = '<div class="loading"><div class="spinner"></div><p>Escaneando redes...</p></div>';
            
            fetch('/scan')
                .then(response => response.json())
                .then(data => {{
                    list.innerHTML = '';
                    if (data.networks.length === 0) {{
                        list.innerHTML = '<p style="text-align: center; color: #8892a0;">No se encontraron redes</p>';
                        return;
                    }}
                    
                    data.networks.forEach(network => {{
                        const item = document.createElement('div');
                        item.className = 'network-item';
                        item.onclick = () => selectNetwork(network.ssid);
                        
                        const signal = network.quality ? `${{network.quality}}%` : '';
                        const lock = network.encrypted ? '🔒' : '';
                        
                        item.innerHTML = `
                            <span>${{network.ssid}} ${{lock}}</span>
                            <span class="signal">${{signal}}</span>
                        `;
                        list.appendChild(item);
                    }});
                }})
                .catch(error => {{
                    list.innerHTML = '<p style="color: #ff6b6b;">Error escaneando redes</p>';
                }});
        }}
        
        function selectNetwork(ssid) {{
            document.getElementById('ssid').value = ssid;
            document.getElementById('password').focus();
        }}
        
        function connectWifi() {{
            const ssid = document.getElementById('ssid').value;
            const password = document.getElementById('password').value;
            
            if (!ssid) {{
                showToast('Por favor selecciona una red', 'warning');
                return;
            }}
            
            showToast('Conectando...', 'info');
            
            fetch('/connect', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ssid, password}})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    showToast('✓ Conectado exitosamente', 'success');
                    setTimeout(checkStatus, 2000);
                }} else {{
                    showToast('Error: ' + data.message, 'error');
                }}
            }})
            .catch(error => {{
                showToast('Error de conexión', 'error');
            }});
        }}
        
        function saveApiKey() {{
            const apikey = document.getElementById('apikey').value;
            
            if (!apikey) {{
                showToast('Por favor introduce una API Key', 'warning');
                return;
            }}
            
            if (!apikey.startsWith('sk-')) {{
                showToast('La API Key debe empezar con sk-', 'warning');
                return;
            }}
            
            fetch('/save_api', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{apikey}})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    showToast('✓ API Key guardada', 'success');
                    document.getElementById('apikey').value = '';
                    document.getElementById('api-status').textContent = data.masked;
                }} else {{
                    showToast('Error guardando API Key', 'error');
                }}
            }})
            .catch(error => {{
                showToast('Error de conexión', 'error');
            }});
        }}
        
        function checkStatus() {{
            fetch('/status')
                .then(response => response.json())
                .then(data => {{
                    document.getElementById('wifi-status').textContent = data.wifi || 'No conectado';
                    document.getElementById('api-status').textContent = data.api || 'No configurada';
                }});
        }}
        
        function showToast(message, type = 'info') {{
            const existing = document.querySelector('.toast');
            if (existing) existing.remove();
            
            const toast = document.createElement('div');
            toast.className = 'toast';
            if (type === 'error') toast.classList.add('error');
            if (type === 'warning') toast.classList.add('warning');
            toast.textContent = message;
            
            document.body.appendChild(toast);
            
            setTimeout(() => {{
                toast.style.animation = 'slideIn 0.3s reverse';
                setTimeout(() => toast.remove(), 300);
            }}, 3000);
        }}
    </script>
</body>
</html>
'''
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def send_scan_results(self):
        """Enviar resultados del escaneo de redes"""
        networks = WifiConfig.scan_networks()
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = json.dumps({'networks': networks})
        self.wfile.write(response.encode())
    
    def send_status(self):
        """Enviar estado actual"""
        config = WifiConfig.load_config()
        
        # Verificar WiFi actual
        try:
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
            current_wifi = result.stdout.strip() if result.returncode == 0 else "No conectado"
        except:
            current_wifi = "Error"
        
        # API key enmascarada
        api_key = config.get('openai_api_key', '')
        api_masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "No configurada"
        
        response = {
            'wifi': current_wifi,
            'api': api_masked
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def handle_connect(self):
        """Manejar conexión WiFi"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        ssid = data.get('ssid', '')
        password = data.get('password', '')
        
        if not ssid:
            response = {'success': False, 'message': 'API Key inválida'}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        """Sobrescribir para evitar logs verbosos"""
        pass


class WifiConfigServer:
    """Servidor de configuración WiFi"""
    
    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.thread = None
        self.running = False
    
    def start(self):
        """Iniciar servidor"""
        if self.running:
            return False
        
        try:
            # Crear punto de acceso
            log.info("Creando punto de acceso...")
            if not WifiConfig.create_access_point():
                log.error("No se pudo crear el punto de acceso")
                return False
            
            # Iniciar servidor HTTP
            self.server = HTTPServer(('192.168.4.1', self.port), ConfigRequestHandler)
            self.thread = threading.Thread(target=self._run_server)
            self.thread.daemon = True
            self.thread.start()
            
            self.running = True
            log.info(f"Servidor de configuración iniciado en http://192.168.4.1:{self.port}")
            log.info("Conéctate a la red 'Bascula-Setup' para configurar")
            
            return True
        
        except Exception as e:
            log.error(f"Error iniciando servidor: {e}")
            return False
    
    def _run_server(self):
        """Ejecutar servidor en thread"""
        try:
            self.server.serve_forever()
        except Exception as e:
            log.error(f"Error en servidor: {e}")
    
    def stop(self):
        """Detener servidor"""
        if not self.running:
            return
        
        try:
            # Detener servidor HTTP
            if self.server:
                self.server.shutdown()
            
            # Detener servicios AP
            subprocess.run(['sudo', 'killall', 'hostapd'], capture_output=True)
            subprocess.run(['sudo', 'killall', 'dnsmasq'], capture_output=True)
            
            # Reconectar WiFi normal
            config = WifiConfig.load_config()
            if 'ssid' in config and 'password' in config:
                WifiConfig.connect_to_network(config['ssid'], config['password'])
            
            self.running = False
            log.info("Servidor de configuración detenido")
        
        except Exception as e:
            log.error(f"Error deteniendo servidor: {e}")


def auto_connect_on_boot():
    """Conectar automáticamente al WiFi guardado al iniciar"""
    try:
        config = WifiConfig.load_config()
        if 'ssid' in config and 'password' in config:
            log.info(f"Intentando conectar a {config['ssid']}...")
            success, message = WifiConfig.connect_to_network(config['ssid'], config['password'])
            if success:
                log.info("Conectado exitosamente")
            else:
                log.warning(f"No se pudo conectar: {message}")
    except Exception as e:
        log.error(f"Error en auto-conexión: {e}")


if __name__ == "__main__":
    # Prueba del servidor
    logging.basicConfig(level=logging.INFO)
    
    server = WifiConfigServer()
    
    try:
        if server.start():
            print("\n" + "="*50)
            print("SERVIDOR DE CONFIGURACIÓN ACTIVO")
            print("="*50)
            print("1. Conéctate a la red WiFi: 'Bascula-Setup'")
            print("2. Abre el navegador y ve a: http://192.168.4.1:8080")
            print("3. Configura tu WiFi y API Key")
            print("\nPresiona Ctrl+C para detener...")
            print("="*50 + "\n")
            
            # Mantener servidor activo
            while True:
                time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        server.stop()
        print("Servidor detenido") 'SSID requerido'}
        else:
            success, message = WifiConfig.connect_to_network(ssid, password)
            
            if success:
                # Guardar configuración
                config = WifiConfig.load_config()
                config['ssid'] = ssid
                config['password'] = password
                WifiConfig.save_config(config)
            
            response = {'success': success, 'message': message}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def handle_save_api(self):
        """Manejar guardado de API key"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        apikey = data.get('apikey', '')
        
        if apikey and apikey.startswith('sk-'):
            config = WifiConfig.load_config()
            config['openai_api_key'] = apikey
            WifiConfig.save_config(config)
            
            masked = f"{apikey[:8]}...{apikey[-4:]}"
            response = {'success': True, 'masked': masked}
        else:
            response = {'success': False, 'message':
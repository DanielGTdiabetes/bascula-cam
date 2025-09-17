.PHONY: run-ui run-web clean deps diag-serial diag-camera install-web uninstall-web status-web logs-web install-polkit uninstall-polkit restart-nm doctor allow-lan local-only show-pin show-url audio-voices audio-selftest service-restart
.PHONY: enable-uart

# Usuario del servicio mini-web (puedes sobreescribir: make install-web BASCULA_USER=pi)
BASCULA_USER ?= bascula
SUBNET ?= 192.168.0.0/16

run-ui:
	bash scripts/run-ui.sh

run-web:
	python3 -m bascula.services.wifi_config

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} + ; \
	find . -type f -name "*.pyc" -delete

deps:
	python3 -m pip install -r requirements.txt

diag-serial:
	python3 scripts/diagnose_serial.py

diag-camera:
	python3 scripts/camera_diagnostic.py

install-web:
	sudo cp systemd/bascula-web.service /etc/systemd/system/bascula-web.service
	# Ajusta User/Group según BASCULA_USER
	sudo sed -i -e 's/^User=.*/User=$(BASCULA_USER)/' -e 's/^Group=.*/Group=$(BASCULA_USER)/' /etc/systemd/system/bascula-web.service
	sudo systemctl daemon-reload
	sudo systemctl enable --now bascula-web.service

uninstall-web:
	sudo systemctl disable --now bascula-web.service || true
	sudo rm -f /etc/systemd/system/bascula-web.service
	sudo systemctl daemon-reload

status-web:
	systemctl status bascula-web.service --no-pager -l || true

logs-web:
	journalctl -u bascula-web.service -f

install-polkit:
	@sudo TARGET_USER=$(USER) bash scripts/install-1-system.sh --only-polkit

enable-uart:
	@sudo bash scripts/install-1-system.sh --only-uart

uninstall-polkit:
	sudo rm -f /etc/polkit-1/rules.d/45-bascula-nm.rules
	sudo systemctl restart polkit 2>/dev/null || sudo systemctl restart polkitd 2>/dev/null || true

restart-nm:
	sudo systemctl restart NetworkManager || true

doctor:
	python3 scripts/doctor.py || true

allow-lan:
	@echo "Abriendo mini-web en LAN y corrigiendo override de systemd..."
	sudo mkdir -p /etc/systemd/system/bascula-web.service.d
	printf "%s\n" "[Service]" \
	  "# Usuario/grupo del servicio (puedes cambiar con BASCULA_USER=...)" \
	  "User=$(BASCULA_USER)" \
	  "Group=$(BASCULA_USER)" \
	  "# Directorio de trabajo por defecto: %h/bascula-cam (repo en HOME)" \
	  "WorkingDirectory=%h/bascula-cam" \
	  "# Abrir a la red" \
	  "Environment=BASCULA_WEB_HOST=0.0.0.0" \
	  "Environment=BASCULA_WEB_PORT=8080" \
	  "Environment=BASCULA_CFG_DIR=%h/.config/bascula" \
	  "# Asegurar que se sobreescribe ExecStart y usar Python del sistema" \
	  "ExecStart=" \
	  "ExecStart=/usr/bin/python3 -m bascula.services.wifi_config" \
	  "# Relajar hardening que causa errores de NAMESPACE" \
	  "ProtectSystem=off" \
	  "ProtectHome=off" \
	  "PrivateTmp=false" \
	  "RestrictNamespaces=false" \
	  "ReadWritePaths=" \
	  "# Sin filtros IP a nivel de systemd y permitir IPv6" \
	  "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6" \
	  "IPAddressAllow=" \
	  "IPAddressDeny=" \
	| sudo tee /etc/systemd/system/bascula-web.service.d/override.conf >/dev/null
	sudo systemctl daemon-reload
	sudo systemctl restart bascula-web.service
	@echo "Hecho. URL: 'make show-url' y PIN: 'make show-pin'"

local-only:
	@echo "Volviendo a solo-localhost (127.0.0.1)..."
	sudo rm -f /etc/systemd/system/bascula-web.service.d/override.conf
	sudo systemctl daemon-reload
	sudo systemctl restart bascula-web.service
	@echo "Hecho. Mini-web accesible solo desde la propia Raspberry."

show-pin:
	@echo "PIN actual (usuario $(BASCULA_USER)):"
	sudo -u $(BASCULA_USER) -H bash -lc 'cat ~/.config/bascula/pin.txt 2>/dev/null || echo "(no existe aún)"'

show-url:
        @IP=$$(hostname -I | awk '{print $$1}'); echo "http://$$IP:8080/"

audio-voices:
	sudo ./scripts/install-piper-voices.sh --voices es_ES-sharvard-medium

audio-selftest:
	./scripts/sound-selftest.sh

service-restart:
        @echo "Reiniciando sesión gráfica (startx) para $(BASCULA_USER)..."
        sudo pkill -f startx || true
        sudo loginctl terminate-user $(BASCULA_USER) || true

# PHONY separado para compatibilidad
.PHONY: install-web-open
# Variante: instala y abre a 0.0.0.0 (override menos estricto)
install-web-open:
	$(MAKE) install-web BASCULA_USER=$(BASCULA_USER)
	$(MAKE) allow-lan SUBNET=$(SUBNET)

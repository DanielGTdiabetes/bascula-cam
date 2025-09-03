.PHONY: run-ui run-web clean deps diag-serial diag-camera install-web uninstall-web status-web logs-web install-polkit uninstall-polkit restart-nm doctor allow-lan local-only show-pin show-url

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
	@echo "Instalando regla de polkit para NetworkManager (usuario: $(BASCULA_USER))"
	echo "polkit.addRule(function(action, subject) {\n  if (subject.user == \"$(BASCULA_USER)\" || subject.isInGroup(\"$(BASCULA_USER)\")) {\n    if (action.id == \"org.freedesktop.NetworkManager.settings.modify.system\" ||\n        action.id == \"org.freedesktop.NetworkManager.network-control\" ||\n        action.id == \"org.freedesktop.NetworkManager.enable-disable-wifi\") {\n      return polkit.Result.YES;\n    }\n  }\n});\n" | sudo tee /etc/polkit-1/rules.d/50-bascula-nm.rules >/dev/null
	sudo systemctl restart polkit || true

uninstall-polkit:
	sudo rm -f /etc/polkit-1/rules.d/50-bascula-nm.rules
	sudo systemctl restart polkit || true

restart-nm:
	sudo systemctl restart NetworkManager || true

doctor:
	python3 scripts/doctor.py || true

allow-lan:
	@echo "Abriendo mini-web a la LAN ($(SUBNET))..."
	sudo mkdir -p /etc/systemd/system/bascula-web.service.d
	echo "[Service]\nEnvironment=BASCULA_WEB_HOST=0.0.0.0\nIPAddressAllow=\nIPAddressDeny=\nIPAddressAllow=127.0.0.1\nIPAddressAllow=$(SUBNET)\nIPAddressDeny=any\n" | sudo tee /etc/systemd/system/bascula-web.service.d/override.conf >/dev/null
	sudo systemctl daemon-reload
	sudo systemctl restart bascula-web.service
	@echo "Hecho. Accede con PIN: 'make show-url' y luego 'make show-pin'"

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

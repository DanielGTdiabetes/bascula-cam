import time

from bascula.core.scale_serial import SerialScale


def test_simulation_generates_values():
    scale = SerialScale(device="/dev/does-not-exist", simulate_if_unavailable=True, timeout=0.05)
    scale.start()
    try:
        # Esperar a que el hilo simulado genere lecturas
        time.sleep(0.5)
        weight = scale.read_weight()
        assert isinstance(weight, float)
        # La rampa simulada siempre es >= 0
        assert weight >= 0.0

        stable = False
        for _ in range(50):
            if scale.stable:
                stable = True
                break
            time.sleep(0.1)
        assert stable is True
        assert scale.is_simulated is True
    finally:
        scale.stop()

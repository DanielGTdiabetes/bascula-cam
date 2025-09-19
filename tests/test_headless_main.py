import threading

from bascula.services import headless_main


def test_run_services_starts_components(monkeypatch):
    server_started = threading.Event()
    server_shutdown = threading.Event()
    stop_event = threading.Event()

    class DummyServer:
        def serve_forever(self):
            server_started.set()
            stop_event.wait()

        def shutdown(self):
            server_shutdown.set()
            stop_event.set()

    def fake_make_server(*args, **kwargs):
        return DummyServer()

    monkeypatch.setattr("werkzeug.serving.make_server", fake_make_server)

    class DummyReader:
        def __init__(self, *args, **kwargs):
            self.started = threading.Event()
            self.stopped = threading.Event()

        def start(self):
            self.started.set()

        def stop(self):
            self.stopped.set()

    monkeypatch.setattr("bascula.services.serial_reader.SerialReader", DummyReader)

    original_sleep = headless_main.time.sleep

    def fast_sleep(seconds):
        original_sleep(0.01)

    monkeypatch.setattr(headless_main.time, "sleep", fast_sleep)

    app = headless_main.HeadlessBascula()
    worker = threading.Thread(target=app.run_services, daemon=True)
    worker.start()

    assert server_started.wait(timeout=1.0)
    assert isinstance(app.scale_reader, DummyReader)
    dummy_reader = app.scale_reader
    assert dummy_reader.started.is_set()

    app.running = False

    worker.join(timeout=2.0)
    assert not worker.is_alive()
    assert server_shutdown.is_set()
    assert dummy_reader.stopped.is_set()

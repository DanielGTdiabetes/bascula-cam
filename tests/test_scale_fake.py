from bascula.config.settings import load_config
from bascula.state import AppState
from bascula.services.logging import get_logger
from bascula.services.scale import ScaleService

def test_scale_fake_runs():
    cfg = load_config()
    logger = get_logger(cfg.base_dir)
    state = AppState(cfg=cfg)
    sc = ScaleService(state, logger)
    assert sc is not None

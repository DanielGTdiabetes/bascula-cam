from bascula.config.settings import FilterConfig
from bascula.domain.filters import ProfessionalWeightFilter

def test_filter_basic():
    f = ProfessionalWeightFilter(FilterConfig())
    out = f.step(0.0)
    assert isinstance(out.display, float)

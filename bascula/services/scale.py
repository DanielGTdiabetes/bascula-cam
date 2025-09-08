"""
Adapter para exponer ScaleService en bascula.services.scale
redirigiendo al backend en python_backend.

Permite imports existentes: from bascula.services.scale import ScaleService
"""

try:
    # Reexporta la implementación real del backend serie
    from python_backend.bascula.services.scale import ScaleService  # type: ignore
    HX711Service = ScaleService  # alias para compatibilidad con HX711Service
except Exception as e:
    # Fallback mínimo por si falla el import del backend; da error claro al usarlo
    class ScaleService:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "No se pudo importar 'python_backend.bascula.services.scale'. "
                "Asegúrate de ejecutar desde la raíz del repo y de tener python_backend en PYTHONPATH. "
                f"Detalle: {e}"
            )


# -- Alias backward-compatible para HX711Service --
try:
    HX711Service
except NameError:
    try:
        # Si ScaleService existe, crea una subclase vacía
        class HX711Service(ScaleService):  # type: ignore
            pass
    except Exception:
        # Fallback: clase que levanta el mismo error que ScaleService en import fallido
        class HX711Service:  # type: ignore
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "No se pudo importar 'python_backend.bascula.services.scale'. "
                    "Asegúrate de ejecutar desde la raíz del repo y de tener python_backend en PYTHONPATH."
                )

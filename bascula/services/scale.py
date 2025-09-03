"""
Adapter para exponer ScaleService en bascula.services.scale
redirigiendo al backend en python_backend.

Permite imports existentes: from bascula.services.scale import ScaleService
"""

try:
    # Reexporta la implementación real del backend serie
    from python_backend.bascula.services.scale import ScaleService  # type: ignore
except Exception as e:
    # Fallback mínimo por si falla el import del backend; da error claro al usarlo
    class ScaleService:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "No se pudo importar 'python_backend.bascula.services.scale'. "
                "Asegúrate de ejecutar desde la raíz del repo y de tener python_backend en PYTHONPATH. "
                f"Detalle: {e}"
            )


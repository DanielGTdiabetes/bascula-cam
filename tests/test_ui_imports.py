import importlib

for mod in [
    'bascula.config.theme',
    'bascula.ui.widgets',
    'bascula.ui.screens',
    'bascula.ui.app',
]:
    importlib.import_module(mod)

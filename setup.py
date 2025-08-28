from setuptools import setup, find_packages

setup(
    name="bascula-cam",
    version="0.2.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "hx711",   # o la librería HX711 que uses realmente
        "tk"       # Tkinter (en Raspberry normalmente ya está)
    ],
    entry_points={
        "console_scripts": [
            "bascula=main:main"
        ]
    },
)

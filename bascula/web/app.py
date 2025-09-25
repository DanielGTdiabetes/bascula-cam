from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Bascula Mini-Web", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return HTMLResponse(
        "<!doctype html><h1>Bascula Mini-Web</h1><p>Status: OK</p><p><a href='/health'>/health</a></p>"
    )

import logging

from fastapi import FastAPI

from backend.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "ok"}

app.include_router(router)
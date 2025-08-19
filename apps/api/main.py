from __future__ import annotations

from fastapi import FastAPI
from dotenv import load_dotenv


load_dotenv()

app = FastAPI(title="SmartDocs API")

from apps.api.routers import upload as upload_router  # noqa: E402
from apps.api.routers import chat as search_router  # noqa: E402
from apps.api.routers import booking as chat_router  # noqa: E402

app.include_router(upload_router.router)
app.include_router(search_router.router)
app.include_router(chat_router.router)


@app.get("/health")
def health() -> dict:
	return {"status": "ok"}



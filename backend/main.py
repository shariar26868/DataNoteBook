from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.api.routes import health, upload, chat, execute, draw, notebook, session
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[START] DataNotebook API -> http://{settings.HOST}:{settings.PORT}")
    yield
    print("[STOP] Shutting down...")


app = FastAPI(
    title="DataNotebook API",
    description="AI-powered data analysis notebook — powered by OpenAI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,    prefix="/api", tags=["health"])
app.include_router(upload.router,    prefix="/api", tags=["upload"])
app.include_router(chat.router,      prefix="/api", tags=["chat"])
app.include_router(execute.router,   prefix="/api", tags=["execute"])
app.include_router(draw.router,      prefix="/api", tags=["draw"])
app.include_router(notebook.router,  prefix="/api", tags=["notebooks"])
app.include_router(session.router,   prefix="/api", tags=["session"])

# Serve the frontend from the same origin to avoid cross-site cookie issues
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
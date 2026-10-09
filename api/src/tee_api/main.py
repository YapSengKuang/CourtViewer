from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tee_api.routes import router

app = FastAPI(title="Tee time search", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(router)

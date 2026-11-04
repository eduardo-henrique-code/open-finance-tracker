from fastapi import FastAPI

from app.routers import pages, pluggy

app = FastAPI()
app.include_router(pages.router)
app.include_router(pluggy.router, prefix="/routers/pluggy")
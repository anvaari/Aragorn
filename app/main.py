from fastapi import FastAPI
from api.v1 import router as api_router

app = FastAPI(title="Aragorn - Independent Music Event Collector")
app.include_router(api_router.router, prefix="/api/v1")

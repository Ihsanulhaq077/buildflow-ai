import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.boq.routes import router as boq_router
from app.budgets.routes import router as budgets_router
from app.inventory.routes import router as inventory_router
from app.procurement.orders import router as orders_router
from app.procurement.routes import router as procurement_router
from app.dailylogs.routes import router as dailylogs_router
from app.labour.routes import router as labour_router
from app.projects.routes import router as projects_router
from app.routers import audit, auth, users

logging.basicConfig(level=logging.INFO, format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}')
log = logging.getLogger("buildflow")

app = FastAPI(title="BuildFlow AI API", version="0.1.0")
app.include_router(auth)
app.include_router(users)
app.include_router(audit)
app.include_router(projects_router)
app.include_router(boq_router)
app.include_router(budgets_router)
app.include_router(inventory_router)
app.include_router(procurement_router)
app.include_router(orders_router)
app.include_router(labour_router)
app.include_router(dailylogs_router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)  # stack trace only in logs
    return JSONResponse({"detail": "Internal server error"}, status_code=500)

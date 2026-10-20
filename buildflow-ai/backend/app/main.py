import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.boq.routes import router as boq_router
from app.budgets.routes import router as budgets_router
from app.dashboards.routes import router as dashboards_router
from app.inventory.routes import router as inventory_router
from app.procurement.orders import router as orders_router
from app.procurement.routes import router as procurement_router
from app.dailylogs.routes import router as dailylogs_router
from app.labour.routes import router as labour_router
from app.projects.routes import router as projects_router
from app.documents.routes import router as documents_router
from app.rag.routes import router as rag_router
from app.ai_assistant.routes import router as ai_assistant_router
from app.ml.routes import router as ml_router
from app.cv.routes import router as cv_router
from app.commercial.routes import router as commercial_router
from app.tasks.routes import router as tasks_router
from app.expenses.routes import router as expenses_router
from app.datapurge.routes import router as datapurge_router
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
app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(ai_assistant_router)
app.include_router(dashboards_router)
app.include_router(ml_router)
app.include_router(cv_router)
app.include_router(commercial_router)
app.include_router(tasks_router)
app.include_router(expenses_router)
app.include_router(datapurge_router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)  # stack trace only in logs
    return JSONResponse({"detail": "Internal server error"}, status_code=500)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import engine, Base
from app.api import cases, sales_orders, documents, admin

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title=settings.app_name,
    version="1.1.0",
    description="Document management platform for tracking business documents by Opportunity ID and Sales Orders",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
app.include_router(sales_orders.router, prefix="/api", tags=["Sales Orders"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/")
async def root():
    return {"message": "Document Platform V1.1 API", "version": "1.1.0"}


@app.get("/api/search")
async def global_search(q: str, type: str = "opportunity"):
    """Global search endpoint for opportunities or sales orders."""
    from sqlalchemy.orm import Session
    from app.database import SessionLocal
    from app.models.case import Case
    from app.models.sales_order import SalesOrder
    
    db = SessionLocal()
    try:
        if type == "opportunity":
            cases = db.query(Case).filter(
                Case.opportunity_id.ilike(f"%{q}%")
            ).limit(20).all()
            return {"results": cases, "type": "opportunity"}
        elif type == "sales_order":
            sos = db.query(SalesOrder).filter(
                SalesOrder.so_number.ilike(f"%{q}%")
            ).limit(20).all()
            return {"results": sos, "type": "sales_order"}
        else:
            return {"results": [], "type": type}
    finally:
        db.close()

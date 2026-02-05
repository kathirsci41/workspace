from app.api.cases import router as cases_router
from app.api.sales_orders import router as sales_orders_router
from app.api.documents import router as documents_router
from app.api.admin import router as admin_router

__all__ = ["cases_router", "sales_orders_router", "documents_router", "admin_router"]

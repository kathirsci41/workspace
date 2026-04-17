from fastapi import APIRouter

from app.api.v1.customers import router as customers_router
from app.api.v1.purchase_orders import router as purchase_orders_router
from app.api.v1.documents import router as documents_router
from app.api.v1.extraction import router as extraction_router
from app.api.v1.search import router as search_router
from app.api.v1.admin import router as admin_router
from app.api.v1.chat import router as chat_router

api_router = APIRouter()

api_router.include_router(customers_router, prefix="/customers", tags=["Customers"])
api_router.include_router(purchase_orders_router, prefix="/purchase-orders", tags=["Purchase Orders"])
api_router.include_router(documents_router, prefix="/documents", tags=["Documents"])
api_router.include_router(extraction_router, tags=["Extraction"])
api_router.include_router(search_router, prefix="/search", tags=["Search"])
api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
api_router.include_router(chat_router, prefix="/chat", tags=["Chat"])

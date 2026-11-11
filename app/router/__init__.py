from fastapi import APIRouter

from app.router import admin, applications, auth, categories, health, users, vacancies

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(vacancies.router)
api_router.include_router(applications.router)
api_router.include_router(admin.router)

# handlers/campaigns/__init__.py
from aiogram import Router
from . import manage
from . import create

campaigns_router = Router()
campaigns_router.include_router(manage.router)
campaigns_router.include_router(create.router)

from datetime import datetime
from typing import Literal, Optional
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, schemas
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import logging

# configure default logging format/level so `logger` actually outputs something
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

SECRET_KEY = "my-super-secret-key-change-in-production"
DATABASE_URL = (
    "postgresql+asyncpg://agriadmin:agriadmin123@localhost:5632/agri_db"
)
ACCESS_TOKEN_EXPIRE_SECONDS = 30 * 60
logger = logging.getLogger(__name__)
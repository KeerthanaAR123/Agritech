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

#databases
class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    Users table from fastapi-users + custom fields.
    Base fields include: id, email, hashed_password, is_active, is_superuser,
    is_verified.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="farmer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_async_session():
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)


# 3. SCHEMAS

class UserRead(schemas.BaseUser[uuid.UUID]):
    """User response schema with all fields."""
    id: uuid.UUID
    email: str
    username: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(schemas.BaseUserCreate):
    username: str
    full_name: Optional[str] = None
    role: Literal["farmer", "official", "admin"] = "farmer"


class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[Literal["farmer", "official", "admin"]] = None


# 4. USER MANAGER

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET_KEY
    verification_token_secret = SECRET_KEY

    async def on_after_register(self, user: User, request=None):
        logger.info(f"User {user.id} registered with email {user.email}")

    async def on_after_forgot_password(self, user: User, token: str, request=None):
        logger.info(f"User {user.id} forgot password. Reset token: {token}")

    async def on_after_request_verify(self, user: User, token: str, request=None):
        logger.info(f"Verification requested for user {user.id}. Token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


# 5. AUTHENTICATION

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

jwt_strategy = JWTStrategy(secret=SECRET_KEY, lifetime_seconds=ACCESS_TOKEN_EXPIRE_SECONDS)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=lambda: jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)


# 6. FASTAPI APP

app = FastAPI(
    title="Agritech API",
    description="Agriculture Tech Platform with JWT Auth",
    version="1.0.0",
)


@app.on_event("startup")
async def on_startup():
    """Create database tables on application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")

# Register auth routes
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

# Register user CRUD routes
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)


# 7. CUSTOM ENDPOINTS

@app.get("/", tags=["root"])
async def root():
    """Root endpoint - API is running."""
    return {"message": "Agritech API is running. Visit /docs for Swagger UI"}


@app.get("/me", response_model=UserRead, tags=["users"])
async def read_users_me(user: User = Depends(current_active_user)):
    """Get current authenticated user profile."""
    return user


@app.get("/health", tags=["root"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/test-credentials", tags=["debug"])
async def test_credentials():
    """
    Test credentials for login.
    Use these to test the login endpoint at POST /auth/jwt/login
    """
    return {
        "test_users": [
            {
                "email": "farmer@agritech.com",
                "password": "farmerpass123",
                "username": "farmer1",
                "role": "farmer"
            },
            {
                "email": "official@agritech.com",
                "password": "officialpass123",
                "username": "official1",
                "role": "official"
            },
            {
                "email": "admin@agritech.com",
                "password": "adminpass123",
                "username": "admin1",
                "role": "admin"
            }
        ],
        "login_endpoint": "POST /auth/jwt/login",
        "login_body": {
            "username": "farmer@agritech.com",
            "password": "farmerpass123"
        },
        "usage": "Send username (email) and password to /auth/jwt/login to get JWT token"
    }


@app.get("/all-users", response_model=list[UserRead], tags=["debug"])
async def get_all_users(session: AsyncSession = Depends(get_async_session)):
    """
    List all registered users with their credentials info (debug endpoint).
    Shows: id, email, username, full_name, role, is_active, is_verified, created_at
    """
    from sqlalchemy import select
    result = await session.execute(select(User))
    users = result.scalars().all()
    return users
 
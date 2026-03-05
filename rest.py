from typing import List, Optional
from fastapi import FastAPI, APIRouter, status, HTTPException, Depends
from sqlalchemy import create_engine, Column, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import NoResultFound
import uuid
from pydantic import BaseModel


app = FastAPI()
app_v1 = APIRouter(prefix="/api/v1",tags=["v1"])


engine = create_engine("postgresql://agriadmin:agriadmin123@localhost:5632/agri_db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@app.on_event("startup")
def startup_db_client():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    password = Column(String(100), nullable=False)
    
  
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    
class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    password: str
    
    class Config:
        orm_mode = True


@app_v1.get("/users/{id}", status_code=status.HTTP_200_OK, response_model=UserResponse)
def getuserbyid(id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch a single user by UUID from the database."""
    try:
        user = db.query(User).filter(User.id == id).one()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@app_v1.get("/users",status_code=status.HTTP_200_OK,response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    """Return all users stored in the database."""
    users_list = db.query(User).all()
    return users_list

@app_v1.post("/users",status_code=status.HTTP_201_CREATED,response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    user = User(name=user.name, email=user.email, password=user.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None

@app_v1.put("/users/{id}", status_code=status.HTTP_200_OK, response_model=UserResponse)
def update_user(id: uuid.UUID, user: UserUpdate, db: Session = Depends(get_db)):
    """Replace a user's data entirely (fields provided override existing)."""
    try:
        existing = db.query(User).filter(User.id == id).one()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    # update fields if provided
    for field, value in user.dict(exclude_unset=True).items():
        setattr(existing, field, value)
    db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing

@app_v1.patch("/users/{id}", status_code=status.HTTP_200_OK, response_model=UserResponse)
def patch_user(id: uuid.UUID, user: UserUpdate, db: Session = Depends(get_db)):
    """Partially update a user's data."""
    try:
        existing = db.query(User).filter(User.id == id).one()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    for field, value in user.dict(exclude_unset=True).items():
        setattr(existing, field, value)
    db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing

@app_v1.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a user from the database."""
    try:
        existing = db.query(User).filter(User.id == id).one()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db.delete(existing)
    db.commit()
    return None


app.include_router(app_v1)
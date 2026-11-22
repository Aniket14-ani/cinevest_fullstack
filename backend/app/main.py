from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'cinevest.db')}")
SECRET_KEY = os.getenv("CINEVEST_SECRET_KEY", "LOCAL_DEMO_ONLY_CHANGE_THIS_SECRET")
ALGORITHM = "HS256"
TOKEN_MINUTES = 60 * 12

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="investor")
    balance: Mapped[float] = mapped_column(Float, default=100000.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Movie(Base):
    __tablename__ = "movies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    genre: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(40), default="Funding")
    synopsis: Mapped[str] = mapped_column(Text)
    producer_name: Mapped[str] = mapped_column(String(120))
    production_budget: Mapped[float] = mapped_column(Float)
    funding_target: Mapped[float] = mapped_column(Float)
    funding_raised: Mapped[float] = mapped_column(Float, default=0.0)
    release_window: Mapped[str] = mapped_column(String(80), default="TBA")
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Allocation(Base):
    __tablename__ = "allocations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("User")
    movie = relationship("Movie")

class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    amount: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

app = FastAPI(title="CineVest Demo API", version="0.1.0",
              description="Educational prototype. Virtual balances only; no real investment or payments.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def make_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError, TypeError):
        raise error
    user = db.get(User, user_id)
    if not user:
        raise error
    return user

def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def money(value: float) -> float:
    return round(float(value), 2)

def user_out(user: User):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "virtual_balance": money(user.balance), "created_at": user.created_at.isoformat()}

def movie_out(m: Movie):
    return {"id": m.id, "title": m.title, "genre": m.genre, "status": m.status,
            "synopsis": m.synopsis, "producer_name": m.producer_name,
            "production_budget": money(m.production_budget), "funding_target": money(m.funding_target),
            "funding_raised": money(m.funding_raised),
            "funding_progress": round(min(100, m.funding_raised / m.funding_target * 100), 1) if m.funding_target else 0,
            "release_window": m.release_window, "approved": m.approved,
            "is_demo": True}

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="investor", pattern="^(investor|producer)$")

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class MovieIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    genre: str = Field(min_length=2, max_length=60)
    synopsis: str = Field(min_length=10, max_length=3000)
    producer_name: str = Field(min_length=2, max_length=120)
    production_budget: float = Field(gt=0, le=10_000_000_000)
    funding_target: float = Field(gt=0, le=10_000_000_000)
    release_window: str = Field(default="TBA", max_length=80)

class AllocateIn(BaseModel):
    movie_id: int
    amount: float = Field(gt=0, le=100_000)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@cinevest.demo").first()
        if not admin:
            admin = User(name="CineVest Demo Admin", email="admin@cinevest.demo",
                         password_hash=hash_password("DemoAdmin123!"), role="admin", balance=100000.0)
            db.add(admin)
            db.commit()
        if db.query(Movie).count() == 0:
            seeds = [
                ("The Last Mission","Action","Funding","A rescue team faces one final mission in the mountains.","Northstar Pictures",100000000,25000000,17600000,"Mar 2027"),
                ("Monsoon Letters","Drama","Funding","Two strangers reconnect through letters during monsoon.","Blue Kite Films",40000000,10000000,6400000,"Feb 2027"),
                ("Orbit 9","Sci-Fi","In production","A deep-space crew discovers an unexplained signal.","Nova Frame Studios",150000000,37500000,37500000,"Aug 2027"),
                ("Laughing Matters","Comedy","Funding","A small-town wedding planner juggles three disasters.","Sunday Cinema",30000000,7500000,4200000,"Jan 2027"),
                ("The Silent Room","Thriller","Post-production","A journalist uncovers a mystery hidden in an old hotel.","Red Door Productions",55000000,13750000,13750000,"Dec 2026"),
                ("Paper Kingdom","Drama","Funding","A young artist fights to save her family's print shop.","Little Lantern Films",25000000,6250000,2900000,"Apr 2027"),
                ("Wild Circuit","Action","In production","An underground racing crew enters its toughest competition.","Velocity Motion",80000000,20000000,15100000,"Jun 2027"),
                ("Mango Season","Comedy","Funding","A family reunion turns into a joyful summer of surprises.","Sunbird Stories",18000000,4500000,1800000,"May 2027"),
                ("Beyond the Banyan","Animation","Funding","Two siblings discover a hidden world beneath an ancient tree.","Wonderleaf Animation",60000000,15000000,8400000,"Oct 2027"),
                ("Black Signal","Thriller","Post-production","A radio host receives a broadcast that should not exist.","Nightjar Films",70000000,17500000,17500000,"Nov 2026"),
            ]
            for row in seeds:
                db.add(Movie(title=row[0], genre=row[1], status=row[2], synopsis=row[3], producer_name=row[4],
                             production_budget=row[5], funding_target=row[6], funding_raised=row[7],
                             release_window=row[8], approved=True))
            db.commit()
    finally:
        db.close()

@app.get("/")
def root():
    return {"name":"CineVest Demo API","status":"ok","notice":"Virtual demo only. No real money or investment returns."}

@app.get("/api/health")
def health():
    return {"status":"healthy","mode":"demo","real_money_enabled":False}

@app.post("/api/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password),
                role=data.role, balance=100000.0)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(Transaction(user_id=user.id, kind="demo_credit", amount=100000.0,
                       description="Starting virtual demo balance"))
    db.commit()
    return {"access_token": make_token(user), "token_type":"bearer", "user":user_out(user)}

@app.post("/api/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return {"access_token": make_token(user), "token_type":"bearer", "user":user_out(user)}

@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)

@app.get("/api/movies")
def list_movies(search: Optional[str] = None, genre: Optional[str] = None,
                status_filter: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Movie).filter(Movie.approved == True)
    if search:
        q = q.filter((Movie.title.ilike(f"%{search}%")) | (Movie.producer_name.ilike(f"%{search}%")))
    if genre:
        q = q.filter(Movie.genre == genre)
    if status_filter:
        q = q.filter(Movie.status == status_filter)
    return [movie_out(m) for m in q.order_by(Movie.created_at.desc()).all()]

@app.get("/api/movies/{movie_id}")
def get_movie(movie_id: int, db: Session = Depends(get_db)):
    m = db.get(Movie, movie_id)
    if not m or not m.approved:
        raise HTTPException(status_code=404, detail="Project not found")
    return movie_out(m)

@app.post("/api/movies")
def submit_movie(data: MovieIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role not in ("producer", "admin"):
        raise HTTPException(status_code=403, detail="Register as a producer to submit projects")
    if data.funding_target > data.production_budget:
        raise HTTPException(status_code=400, detail="Funding target cannot exceed the sample production budget")
    m = Movie(title=data.title.strip(), genre=data.genre, status="Pending review",
              synopsis=data.synopsis.strip(), producer_name=data.producer_name.strip(),
              production_budget=data.production_budget, funding_target=data.funding_target,
              funding_raised=0, release_window=data.release_window, approved=False, created_by=user.id)
    db.add(m)
    db.commit()
    db.refresh(m)
    return movie_out(m)

@app.get("/api/producer/mine")
def my_submissions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [movie_out(m) for m in db.query(Movie).filter(Movie.created_by == user.id).order_by(Movie.created_at.desc()).all()]

@app.post("/api/allocations")
def allocate(data: AllocateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != "investor":
        raise HTTPException(status_code=403, detail="Use an investor account for virtual allocations")
    if data.amount < 500:
        raise HTTPException(status_code=400, detail="Minimum virtual allocation is ₹500")
    # lock/transaction patterns require a production DB review; this is a local educational demo.
    try:
        movie = db.query(Movie).filter(Movie.id == data.movie_id, Movie.approved == True).first()
        if not movie:
            raise HTTPException(status_code=404, detail="Project not found")
        if movie.status != "Funding":
            raise HTTPException(status_code=400, detail="This demo project is not currently accepting allocations")
        if data.amount > user.balance:
            raise HTTPException(status_code=400, detail="Insufficient virtual balance")
        if movie.funding_raised + data.amount > movie.funding_target:
            raise HTTPException(status_code=400, detail="This amount exceeds the remaining demo funding target")
        user.balance = money(user.balance - data.amount)
        movie.funding_raised = money(movie.funding_raised + data.amount)
        allocation = Allocation(user_id=user.id, movie_id=movie.id, amount=money(data.amount))
        db.add(allocation)
        db.add(Transaction(user_id=user.id, kind="virtual_allocation", amount=money(data.amount),
                           description=f"Virtual allocation to {movie.title}"))
        db.commit()
        db.refresh(allocation)
        return {"message":"Virtual allocation recorded. No money was taken.", "allocation_id":allocation.id,
                "amount":money(allocation.amount), "virtual_balance":money(user.balance), "movie":movie_out(movie)}
    except Exception:
        db.rollback()
        raise

@app.get("/api/portfolio")
def portfolio(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Allocation).filter(Allocation.user_id == user.id).order_by(Allocation.created_at.desc()).all()
    allocations = [{"id":a.id, "movie":movie_out(a.movie), "amount":money(a.amount),
                    "created_at":a.created_at.isoformat()} for a in rows]
    return {"virtual_balance":money(user.balance), "total_allocated":money(sum(a.amount for a in rows)),
            "project_count":len(set(a.movie_id for a in rows)), "allocations":allocations,
            "notice":"Virtual demo values only. No actual payouts or returns."}

@app.get("/api/transactions")
def transactions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Transaction).filter(Transaction.user_id == user.id).order_by(Transaction.created_at.desc()).limit(100).all()
    return [{"id":t.id,"kind":t.kind,"amount":money(t.amount),"description":t.description,
             "created_at":t.created_at.isoformat()} for t in rows]

@app.get("/api/admin/pending")
def pending(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [movie_out(m) for m in db.query(Movie).filter(Movie.approved == False).order_by(Movie.created_at.desc()).all()]

@app.post("/api/admin/movies/{movie_id}/review")
def review_movie(movie_id: int, decision: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be approve or reject")
    m = db.get(Movie, movie_id)
    if not m:
        raise HTTPException(status_code=404, detail="Project not found")
    if decision == "approve":
        m.approved = True
        m.status = "Funding"
    else:
        db.delete(m)
    db.commit()
    return {"message":f"Project {decision}d", "movie_id":movie_id}

@app.get("/api/admin/summary")
def admin_summary(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return {"users":db.query(User).count(),"projects":db.query(Movie).count(),
            "pending_projects":db.query(Movie).filter(Movie.approved == False).count(),
            "virtual_allocations":db.query(Allocation).count(),
            "notice":"All values belong to the local demo system."}

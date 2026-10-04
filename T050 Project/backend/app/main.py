from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.api.v1 import auth, contracts, ai, approvals, obligations, qa, audit, analytics, templates, websockets, redlines, signatures
from app.workers.obligation_worker import start_obligation_periodic_scheduler

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Enterprise Contract Lifecycle & Approval Management System. "
        "Provides contract repository, AI-powered clause and risk extraction, "
        "RAG Q&A, configurable approval workflows, obligation tracking, "
        "semantic version comparison, analytics and a tamper-evident audit log."
    ),
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
)

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing Enterprise Real-Time CLM System...")
    import asyncio
    websockets.set_main_loop(asyncio.get_running_loop())
    try:
        from sqlalchemy import text
        from app.db.session import engine
        from app.models.models import Base
        with engine.begin() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            except Exception as ext_err:
                logger.warning(f"pgvector extension warning: {ext_err}")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified & initialized successfully.")

        # Seed default demo accounts
        try:
            from app.db.session import SessionLocal
            from app.models.models import User
            from app.core.security import hash_password

            db = SessionLocal()
            acme_demo_users = [
                {'email': 'admin@acme.io', 'full_name': 'System Administrator', 'role': 'admin', 'department': 'Executive'},
                {'email': 'exec@acme.io', 'full_name': 'Executive VP', 'role': 'executive', 'department': 'Executive'},
                {'email': 'legal@acme.io', 'full_name': 'Chief Legal Counsel', 'role': 'legal', 'department': 'Legal'},
                {'email': 'finance@acme.io', 'full_name': 'Finance Director', 'role': 'finance', 'department': 'Finance'},
                {'email': 'compliance@acme.io', 'full_name': 'Compliance Officer', 'role': 'compliance', 'department': 'Compliance'},
                {'email': 'manager@acme.io', 'full_name': 'Contract Manager', 'role': 'manager', 'department': 'Procurement'},
                {'email': 'requester@acme.io', 'full_name': 'Standard Requester', 'role': 'requester', 'department': 'Sales'},
            ]
            demo_pw = hash_password('Demo1234!')
            for u in acme_demo_users:
                user = db.query(User).filter(User.email == u['email']).first()
                if not user:
                    user = User(
                        email=u['email'],
                        full_name=u['full_name'],
                        role=u['role'],
                        department=u['department'],
                        hashed_password=demo_pw,
                        is_active=True
                    )
                    db.add(user)
            db.commit()
            db.close()
        except Exception as seed_err:
            logger.warning(f"Demo user auto-seed note: {seed_err}")
    except Exception as e:
        logger.warning(f"Database table creation warning: {e}")
    start_obligation_periodic_scheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.PROJECT_NAME, "version": settings.VERSION}


@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": app.docs_url,
        "openapi": app.openapi_url,
    }


API_PREFIX = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(contracts.router, prefix=API_PREFIX)
app.include_router(ai.router, prefix=API_PREFIX)
app.include_router(approvals.router, prefix=API_PREFIX)
app.include_router(obligations.router, prefix=API_PREFIX)
app.include_router(qa.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(templates.router, prefix=API_PREFIX)
app.include_router(websockets.router, prefix=API_PREFIX)
app.include_router(redlines.router, prefix=API_PREFIX)
app.include_router(signatures.router, prefix=API_PREFIX)


@app.exception_handler(Exception)
def generic_exception_handler(request, exc):
    logger.exception("Unhandled error")
    origin = request.headers.get("origin")
    headers = {}
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}", "type": str(type(exc).__name__)},
        headers=headers
    )

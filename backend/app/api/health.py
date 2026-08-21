from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.deps import SessionDep

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str


@router.get("/health")
async def health(session: SessionDep) -> Health:
    # Touch the database: a process that answers while its volume is gone is
    # exactly the state a healthcheck exists to catch.
    await session.execute(text("SELECT 1"))
    return Health(status="ok")

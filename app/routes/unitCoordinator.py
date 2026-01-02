from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import getDb
from app.crud import unitCoordinator as crud
from app.schemas import unitCoordinator as schema

router = APIRouter(prefix="/unitcoordinator", tags=["Unit Coordinators"])


@router.get("/", response_model=list[schema.UnitCoordinator])
def readAll(db: Session = Depends(getDb)):
    return crud.getAll(db)


@router.get("/{coordinatorId}", response_model=schema.UnitCoordinator)
def readById(coordinatorId: int, db: Session = Depends(getDb)):
    result = crud.getById(db, coordinatorId)
    if not result:
        raise HTTPException(status_code=404, detail="Unit coordinator not found")
    return result


@router.post("/", response_model=schema.UnitCoordinator)
def create(coordinator: schema.UnitCoordinatorCreate, db: Session = Depends(getDb)):
    return crud.create(db, coordinator)


@router.delete("/{coordinatorId}", response_model=schema.UnitCoordinator)
def delete(coordinatorId: int, db: Session = Depends(getDb)):
    deleted = crud.delete(db, coordinatorId)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    return deleted

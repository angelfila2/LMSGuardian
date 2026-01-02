from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import getDb
from app.crud import module as crud
from app.schemas import module as schema

router = APIRouter(prefix="/modules", tags=["Modules"])


@router.get("/", response_model=list[schema.Module])
def readAll(db: Session = Depends(getDb)):
    return crud.getAll(db)


@router.get("/{moduleId}", response_model=schema.Module)
def readById(moduleId: int, db: Session = Depends(getDb)):
    result = crud.getById(db, moduleId)
    if not result:
        raise HTTPException(status_code=404, detail="Module not found")
    return result


@router.post("/", response_model=schema.Module)
def create(module: schema.ModuleCreate, db: Session = Depends(getDb)):
    return crud.create(db, module)


@router.delete("/{moduleId}", response_model=schema.Module)
def delete(moduleId: int, db: Session = Depends(getDb)):
    deleted = crud.delete(db, moduleId)
    if not deleted:
        raise HTTPException(status_code=404, detail="Module not found")
    return deleted


@router.put("/{moduleId}", response_model=schema.Module)
def update(moduleId: int, module: schema.ModuleUpdate, db: Session = Depends(getDb)):
    updated = crud.update(db, moduleId, module)
    if not updated:
        raise HTTPException(status_code=404, detail="Module not found")
    return updated

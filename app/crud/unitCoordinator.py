from sqlalchemy.orm import Session
from sqlalchemy import text
from app.schemas.unitCoordinator import UnitCoordinatorCreate


def getAll(db: Session):
    sql = text("SELECT uc_id, full_name, email FROM unit_coordinators")
    result = db.execute(sql).mappings().all()
    return [dict(row) for row in result]


def getById(db: Session, coordinatorId: int):
    sql = text(
        "SELECT uc_id, full_name, email FROM unit_coordinators WHERE uc_id = :id"
    )
    result = db.execute(sql, {"id": coordinatorId}).mappings().fetchone()
    return dict(result) if result else None


def create(db: Session, coordinator: UnitCoordinatorCreate):
    sql = text(
        """
        INSERT INTO unit_coordinators (full_name, email)
        VALUES (:full_name, :email)
        RETURNING uc_id, full_name, email
    """
    )
    result = db.execute(
        sql, {"full_name": coordinator.full_name, "email": coordinator.email}
    ).mappings()
    db.commit()
    return dict(result.fetchone())


def delete(db: Session, coordinatorId: int):
    sql = text(
        "DELETE FROM unit_coordinators WHERE uc_id = :id RETURNING uc_id, full_name, email"
    )
    result = db.execute(sql, {"id": coordinatorId}).mappings()
    db.commit()
    deleted = result.fetchone()
    return dict(deleted) if deleted else None

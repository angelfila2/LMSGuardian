from pydantic import BaseModel


class UnitCoordinator(BaseModel):
    uc_id: int
    full_name: str
    email: str


class UnitCoordinatorCreate(BaseModel):
    pass

    class Config:
        orm_mode = True

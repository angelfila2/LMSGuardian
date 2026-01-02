from pydantic import BaseModel
from typing import Optional


class ModuleBase(BaseModel):
    uc_id: int
    module_name: str
    teaching_period: str
    semester: str
    module_description: str
    unit_code: str


class ModuleCreate(ModuleBase):
    pass


class ModuleUpdate(ModuleBase):
    pass


class Module(ModuleBase):
    module_id: int

    class Config:
        from_attributes = True

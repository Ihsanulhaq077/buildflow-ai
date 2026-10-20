from typing import Dict, Literal

from pydantic import BaseModel, Field


class PurgeScope(str):
    OPERATIONAL = "operational"
    ALL = "all"


class PurgePreviewOut(BaseModel):
    scope: str
    tables_to_delete: Dict[str, int]
    tables_to_keep: Dict[str, int]
    total_rows_to_delete: int


class PurgeRequest(BaseModel):
    scope: Literal["operational", "all"] = "operational"
    confirmation: str = Field(
        default="",
        description="Must be exactly 'DELETE MY DATA' to confirm the purge.",
    )


class PurgeResultOut(BaseModel):
    scope: str
    deleted: Dict[str, int]
    total_rows_deleted: int

from __future__ import annotations

import codecs

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CSVOptions(BaseModel):
    """Represent all possible options for CSV Writer."""

    model_config = ConfigDict(validate_assignment=True)

    add_rubrics: bool = True
    add_comments: bool = True
    columns_per_entity: int = Field(3, gt=0, le=5)
    remove_empty_columns: bool = True
    remove_duplicates: bool = True
    join_char: str = "; "


class WriterOptions(BaseModel):
    """Represent all possible options for File Writer."""

    model_config = ConfigDict(validate_assignment=True)

    encoding: str = "utf-8-sig"
    verbose: bool = True
    csv: CSVOptions = CSVOptions()

    @field_validator("encoding")
    @classmethod
    def encoding_exists(cls, v: str) -> str:
        """Determine if `encoding` exists."""
        try:
            codecs.lookup(v)
        except LookupError:
            raise ValueError
        return v

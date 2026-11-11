import enum
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import mapped_column


def enum_type(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Python-enum как varchar + CHECK (не нативный тип PostgreSQL: проще мигрировать)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda cls: [member.value for member in cls],
    )


CreatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now()),
]

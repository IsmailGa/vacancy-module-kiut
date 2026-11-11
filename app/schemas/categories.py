from typing import Annotated

from pydantic import ConfigDict, Field, StringConstraints, field_validator

from app.schemas.common import InputModel, ReadModel

Slug = Annotated[
    str,
    StringConstraints(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]


class CategoryCreate(InputModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"name": "IT и разработка", "slug": "it"}]}
    )

    name: str = Field(min_length=2, max_length=100)
    slug: Slug = Field(description="Латиница в нижнем регистре, цифры и дефис")


class CategoryUpdate(InputModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    slug: Slug | None = None

    @field_validator("name", "slug")
    @classmethod
    def not_null(cls, v: str | None) -> str:
        if v is None:
            raise ValueError("Поле не может быть пустым")
        return v


class CategoryRead(ReadModel):
    id: int
    name: str
    slug: str

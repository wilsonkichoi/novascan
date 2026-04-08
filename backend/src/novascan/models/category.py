"""Pydantic models for categories and custom categories."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Subcategory(BaseModel):
    """A subcategory within a category."""

    slug: str
    displayName: str


class Category(BaseModel):
    """A category with its subcategories."""

    slug: str
    displayName: str
    isCustom: bool = False
    parentCategory: str | None = None
    subcategories: list[Subcategory] = Field(default_factory=list)


class CustomCategoryRequest(BaseModel):
    """POST /api/categories request body."""

    displayName: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9 &/,.'()\-]+$")
    parentCategory: str | None = None


class CustomCategoryResponse(BaseModel):
    """POST /api/categories response."""

    slug: str
    displayName: str
    parentCategory: str | None = None
    isCustom: bool = True

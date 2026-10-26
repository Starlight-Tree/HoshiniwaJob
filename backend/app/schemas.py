from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field


class Code(BaseModel):
    code: int
    name: str


class OccupationGroup(BaseModel):
    category: str
    items: list[Code]


class Master(BaseModel):
    areas: list[Code]
    stations: list[Code]
    occupations: list[OccupationGroup]
    employments: list[Code]


class RecruitSummary(BaseModel):
    id: int
    corporate: str | None
    category: str | None
    salary: int | None  # 1 年俸制 / 2 月給制 / 3 日給制 / 4 時給制
    pay_min: int | None
    pay_max: int | None
    comment1: str | None
    note1: str | None
    formfile: str | None
    areas: list[str]
    stations: list[str]
    occupations: list[str]
    employments: list[str]


class RecruitPage(BaseModel):
    total: int
    page: int
    per_page: int
    last_page: int
    items: list[RecruitSummary]


class RecruitDetail(RecruitSummary):
    profile: str | None
    place: str | None
    note2: str | None
    note3: str | None
    comment2: str | None
    comment3: str | None
    workday: str | None
    insurance: str | None
    start_time: str | None
    end_time: str | None


class FacetCount(BaseModel):
    code: int
    count: int


class Facets(BaseModel):
    """条件ごとの件数。ある種類の件数は、その種類以外の条件で絞った求人から数える（同じ種類の中は OR なので、選んでも他の選択肢が消えない）。"""

    total: int
    areas: list[FacetCount]
    stations: list[FacetCount]
    occupations: list[FacetCount]
    employments: list[FacetCount]


def _normalized_email(value: str) -> str:
    return value.strip().lower()


class User(BaseModel):
    id: int
    email: str
    last_name: str | None
    first_name: str | None


class Session(BaseModel):
    token: str
    user: User


class LoginRequest(BaseModel):
    email: Annotated[EmailStr, AfterValidator(_normalized_email)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class RegisterRequest(BaseModel):
    last_name: Annotated[str, Field(min_length=1, max_length=50)]
    first_name: Annotated[str, Field(min_length=1, max_length=50)]
    email: Annotated[EmailStr, AfterValidator(_normalized_email)]
    password: Annotated[str, Field(min_length=8, max_length=128)]


class Garden(BaseModel):
    id: int
    email: str
    corporate: str


class GardenSession(BaseModel):
    token: str
    garden: Garden


class GardenSummary(BaseModel):
    """園が見られる、自分の分の求人の件数。"""

    corporate: str
    email: str
    displayed: int
    hidden: int

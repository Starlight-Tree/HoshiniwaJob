from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field, StringConstraints


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


class ImageInfo(BaseModel):
    """公開中の画像。url は保存キーから組み立てた公開 URL（署名付きではない）。"""

    id: str
    url: str
    alt: str
    width: int
    height: int
    mime_type: str


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
    hero_image: ImageInfo | None  # ヒーローに指定された公開中の画像。無ければ表示順で先頭の公開中の画像。画像が 1 枚も無ければ None


class RecruitPage(BaseModel):
    total: int
    page: int
    per_page: int
    last_page: int
    items: list[RecruitSummary]


class RecruitDetail(RecruitSummary):
    images: list[ImageInfo]  # 公開中の画像を、表示順に
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
    display_name: str | None  # 表示名（ニックネーム）。無ければ None（画面はメールアドレスを出す）
    avatar_url: str | None = None  # Google のプロフィール画像（https のみ）。無ければ None


class LoginRequest(BaseModel):
    email: Annotated[EmailStr, AfterValidator(_normalized_email)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


def _no_control_chars(value: str) -> str:
    if not value.isprintable():
        raise ValueError("表示名に使えない文字（改行・タブなど）が含まれています")
    return value


class UpdateNameRequest(BaseModel):
    """表示名（ニックネーム）の変更。前後の空白を除いた 1〜30 文字で、改行・タブなどの制御文字を含まない。"""

    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30), AfterValidator(_no_control_chars)
    ]


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


class ImageBody(BaseModel):
    """園が自分の求人・法人の画像として見る 1 枚。status が approved（公開中）でない画像（取り下げられたもの）は、公開されていない。"""

    id: str
    alt: str
    width: int
    height: int
    mime_type: str
    origin: str
    status: str  # approved（公開中）/ rejected（運営が取り下げた）
    position: int
    is_hero: bool
    role: str | None = None  # 法人の画像のとき: logo / banner
    url: str | None  # approved（公開中）のときだけ公開 URL。それ以外は None


class GardenRecruitImages(BaseModel):
    recruit_id: int
    category: str | None
    is_displayed: bool
    max_images: int
    images: list[ImageBody]


class GardenRecruitItem(BaseModel):
    id: int
    category: str | None
    is_displayed: bool
    image_count: int
    published_count: int


class ImageOrder(BaseModel):
    image_ids: list[str]


class HeroChoice(BaseModel):
    image_id: str

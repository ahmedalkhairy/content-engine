from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: str
    password: str


class ContentIdeaCreate(BaseModel):
    title: str
    topic: str = ""
    angle: str = ""
    target_audience: str = "DevOps engineers"
    platform_preference: str = "both"
    priority: int = 5
    status: str = "new"
    notes: str = ""


class ContentIdeaUpdate(BaseModel):
    title: str | None = None
    topic: str | None = None
    angle: str | None = None
    target_audience: str | None = None
    platform_preference: str | None = None
    priority: int | None = None
    status: str | None = None
    notes: str | None = None


class PostDraftUpdate(BaseModel):
    title: str | None = None
    linkedin_text: str | None = None
    facebook_text: str | None = None
    image_prompt: str | None = None
    hashtags: str | None = None
    cta: str | None = None
    status: str | None = None


class ScheduleCreate(BaseModel):
    draft_id: int
    platforms: str = "linkedin,facebook"
    scheduled_at: datetime
    auto_publish: bool = False


class SettingUpdate(BaseModel):
    key: str
    value: str
    encrypted: bool = False

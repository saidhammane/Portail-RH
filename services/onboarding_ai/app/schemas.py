from typing import Literal

from pydantic import BaseModel, Field


class IndexDocumentRequest(BaseModel):
    document_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=64)
    company_id: int = Field(gt=0)
    department_id: int | None = Field(default=None, gt=0)
    visibility: Literal["employee", "department", "manager", "hr"]
    version: int = Field(gt=0)
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    language: str = Field(min_length=2, max_length=8)


class IndexJob(BaseModel):
    job_id: str
    file_path: str
    document_id: int
    title: str
    filename: str
    category: str
    company_id: int
    department_id: int | None
    visibility: Literal["employee", "department", "manager", "hr"]
    version: int
    checksum: str
    language: str


class IndexQueuedResponse(BaseModel):
    job_id: str
    state: Literal["pending"] = "pending"


class ChatRequest(BaseModel):
    user_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)
    company_id: int = Field(gt=0)
    department_id: int | None = Field(default=None, gt=0)
    group_scopes: list[Literal["employee", "manager", "hr"]] = Field(
        min_length=1,
        max_length=3,
    )
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: int = Field(gt=0)


class ChatSource(BaseModel):
    document_id: int
    title: str
    section: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    confidence: float = Field(ge=0.0, le=1.0)
    latency_ms: int = Field(ge=0)
    cache_hit: bool = False
    needs_escalation: bool = False

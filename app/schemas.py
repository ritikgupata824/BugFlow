from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .models import (
    IssueStatus,
    IssueType,
    Priority,
    Severity,
    SprintStatus,
)


# Create Issue Schema
class IssueCreate(BaseModel):
    issue_type: IssueType
    title: str
    description: str
    reproduction_steps: str | None = None
    severity: Severity
    priority: Priority
    affected_module: str | None = None
    environment: str | None = None
    screenshot_url: str | None = None
    project_key: str
    reporter_id: int
    assignee_id: int | None = None
    sprint_id: int | None = None


# Issue Response Schema
class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_key: str
    issue_type: IssueType
    title: str
    description: str
    reproduction_steps: str | None
    severity: Severity
    priority: Priority
    status: IssueStatus
    affected_module: str | None
    environment: str | None
    screenshot_url: str | None
    project_key: str
    reporter_id: int
    assignee_id: int | None
    sprint_id: int | None
    created_at: datetime
    updated_at: datetime


# Update Issue Schema
class IssueUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    reproduction_steps: str | None = None
    severity: Severity | None = None
    priority: Priority | None = None
    affected_module: str | None = None
    environment: str | None = None
    screenshot_url: str | None = None
    assignee_id: int | None = None
    sprint_id: int | None = None


# Assign / Reassign Issue Schema
class IssueAssign(BaseModel):
    assignee_id: int


# Create Comment Schema
class CommentCreate(BaseModel):
    user_id: int
    comment: str


# Comment Response Schema
class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    user_id: int
    comment: str
    created_at: datetime


# Issue Activity Response Schema
class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    user_id: int
    action: str
    details: str | None
    created_at: datetime


# User Registration Schema
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "REPORTER"


# User Response Schema
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


# Login Schema
class LoginRequest(BaseModel):
    username: str
    password: str


# Token Response Schema
class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# Create Sprint Schema
class SprintCreate(BaseModel):
    name: str
    description: str | None = None
    start_date: datetime
    end_date: datetime
    status: SprintStatus = SprintStatus.PLANNED
    project_key: str


# Update Sprint Schema
class SprintUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: SprintStatus | None = None


# Sprint Response Schema
class SprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    start_date: datetime
    end_date: datetime
    status: SprintStatus
    project_key: str
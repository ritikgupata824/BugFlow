from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


# =========================
# Issue Type
# =========================

class IssueType(str, Enum):
    BUG = "BUG"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    ENHANCEMENT = "ENHANCEMENT"
    TECHNICAL_DEBT = "TECHNICAL_DEBT"
    SUPPORT_TICKET = "SUPPORT_TICKET"


# =========================
# Severity
# =========================

class Severity(str, Enum):
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"
    BLOCKER = "BLOCKER"


# =========================
# Business Impact
# =========================

class BusinessImpact(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# =========================
# Priority
# =========================

class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


# =========================
# Issue Status
# =========================

class IssueStatus(str, Enum):
    REPORTED = "REPORTED"
    TRIAGED = "TRIAGED"
    ASSIGNED = "ASSIGNED"
    IN_DEVELOPMENT = "IN_DEVELOPMENT"
    IN_REVIEW = "IN_REVIEW"
    IN_TESTING = "IN_TESTING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


# =========================
# Issue
# =========================

class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    issue_key: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True
    )

    issue_type: Mapped[IssueType] = mapped_column(
        SAEnum(IssueType),
        nullable=False
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    reproduction_steps: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity),
        nullable=False
    )

    business_impact: Mapped[BusinessImpact] = mapped_column(
        SAEnum(BusinessImpact),
        nullable=False,
        default=BusinessImpact.MEDIUM
    )

    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority),
        nullable=False
    )

    status: Mapped[IssueStatus] = mapped_column(
        SAEnum(IssueStatus),
        nullable=False,
        default=IssueStatus.REPORTED
    )

    affected_module: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    environment: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    screenshot_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    project_key: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True
    )

    sprint_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True
    )

    duplicate_of_id: Mapped[int | None] = mapped_column(
    Integer,
    nullable=True
)

    reporter_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    assignee_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


# =========================
# Issue Comments
# =========================

class IssueComment(Base):
    __tablename__ = "issue_comments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    issue_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )


# =========================
# Issue Activity / Audit
# =========================

class IssueActivity(Base):
    __tablename__ = "issue_activities"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    issue_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )


# =========================
# Sprint Status
# =========================

class SprintStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


# =========================
# Sprint
# =========================

class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    end_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    status: Mapped[SprintStatus] = mapped_column(
        SAEnum(SprintStatus),
        nullable=False,
        default=SprintStatus.PLANNED
    )

    project_key: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True
    )


# =========================
# User Role
# =========================

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    TESTER = "TESTER"
    REPORTER = "REPORTER"


# =========================
# User
# =========================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )

    email: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        nullable=False,
        index=True
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole),
        nullable=False,
        default=UserRole.REPORTER
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )


class IssueTag(Base):
    __tablename__ = "issue_tags"

    issue_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    tag_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )
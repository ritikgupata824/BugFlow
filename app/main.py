from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from difflib import SequenceMatcher

from .webhooks import send_webhook

from .security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_role
)

from .database import SessionLocal

from .models import (
    Issue,
    IssueStatus,
    IssueTag,
    IssueComment,
    IssueActivity,
    User,
    UserRole,
    Sprint,
    SprintStatus,
    Severity,
    BusinessImpact,
    Priority,
    Tag
)

from .schemas import (
    IssueCreate,
    IssueResponse,
    IssueUpdate,
    IssueAssign,
    CommentCreate,
    CommentResponse,
    ActivityResponse,
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    SprintCreate,
    SprintUpdate,
    SprintResponse,
    TagCreate,
    TagResponse,
)


app = FastAPI(
    title="BugFlow API",
    description="Software Issue Tracking & Resolution Platform",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================
# PRIORITY MATRIX
# ============================================================

def calculate_priority(
    severity: Severity,
    business_impact: BusinessImpact
) -> Priority:

    if (
        severity == Severity.BLOCKER
        or business_impact == BusinessImpact.CRITICAL
    ):
        return Priority.URGENT

    if (
        severity == Severity.CRITICAL
        or business_impact == BusinessImpact.HIGH
    ):
        return Priority.HIGH

    if (
        severity == Severity.MAJOR
        or business_impact == BusinessImpact.MEDIUM
    ):
        return Priority.MEDIUM

    return Priority.LOW


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "BugFlow API is running",
        "status": "success"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


# ============================================================
# AUTHENTICATION
# ============================================================

@app.post("/auth/register", response_model=UserResponse)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):

    existing_username = (
        db.query(User)
        .filter(User.username == user.username)
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    existing_email = (
        db.query(User)
        .filter(User.email == user.email)
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    hashed_password = hash_password(user.password)

    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=UserRole(user.role),
        is_active=True,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@app.post("/auth/login", response_model=TokenResponse)
def login_user(
    login: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .filter(User.username == login.username)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(
        login.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive"
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# ============================================================
# ISSUE MANAGEMENT
# ============================================================

@app.post("/issues", response_model=IssueResponse)
def create_issue(
    issue: IssueCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN", "REPORTER", "DEVELOPER"])
    )
):

    last_issue = (
        db.query(Issue)
        .filter(Issue.project_key == issue.project_key)
        .order_by(Issue.id.desc())
        .first()
    )

    next_number = (
        1
        if last_issue is None
        else last_issue.id + 1
    )

    issue_key = f"{issue.project_key}-{next_number}"

    calculated_priority = calculate_priority(
        issue.severity,
        issue.business_impact
    )

    issue_data = Issue(
        issue_key=issue_key,
        issue_type=issue.issue_type,
        title=issue.title,
        description=issue.description,
        reproduction_steps=issue.reproduction_steps,
        severity=issue.severity,
        business_impact=issue.business_impact,
        priority=calculated_priority,
        affected_module=issue.affected_module,
        environment=issue.environment,
        screenshot_url=issue.screenshot_url,
        project_key=issue.project_key,
        reporter_id=issue.reporter_id,
        assignee_id=issue.assignee_id,
        sprint_id=issue.sprint_id,
    )

    db.add(issue_data)
    db.commit()
    db.refresh(issue_data)

    activity = IssueActivity(
        issue_id=issue_data.id,
        user_id=issue_data.reporter_id,
        action="ISSUE_CREATED",
        details=(
            f"Issue {issue_data.issue_key} was created. "
            f"Priority automatically calculated as "
            f"{issue_data.priority.value}."
        )
    )

    db.add(activity)
    db.commit()

    try:
        send_webhook(
            event="ISSUE_CREATED",
            data={
                "issue_id": issue_data.id,
                "issue_key": issue_data.issue_key,
                "title": issue_data.title,
                "status": issue_data.status.value,
                "priority": issue_data.priority.value,
                "severity": issue_data.severity.value,
                "business_impact": (
                    issue_data.business_impact.value
                ),
                "project_key": issue_data.project_key
            }
        )
    except Exception:
        pass

    return issue_data


@app.get(
    "/issues",
    response_model=list[IssueResponse]
)
def get_issues(
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(
            [
                "ADMIN",
                "REPORTER",
                "DEVELOPER",
                "TESTER"
            ]
        )
    )
):

    issues = (
        db.query(Issue)
        .order_by(Issue.id.asc())
        .all()
    )

    return issues


@app.get(
    "/issues/{issue_id}",
    response_model=IssueResponse
)
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db)
):

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if issue is None:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    return issue


@app.put(
    "/issues/{issue_id}",
    response_model=IssueResponse
)
def update_issue(
    issue_id: int,
    issue: IssueUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN", "DEVELOPER"])
    )
):

    existing_issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if existing_issue is None:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    update_data = issue.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(
            existing_issue,
            field,
            value
        )

    if (
        "severity" in update_data
        or "business_impact" in update_data
    ):
        existing_issue.priority = calculate_priority(
            existing_issue.severity,
            existing_issue.business_impact
        )

    db.commit()
    db.refresh(existing_issue)

    activity = IssueActivity(
        issue_id=existing_issue.id,
        user_id=int(current_user.get("sub")),
        action="ISSUE_UPDATED",
        details=(
            f"Updated fields: "
            f"{', '.join(update_data.keys())}."
        )
    )

    db.add(activity)
    db.commit()

    return existing_issue


@app.put(
    "/issues/{issue_id}/assign",
    response_model=IssueResponse
)
def assign_issue(
    issue_id: int,
    assignment: IssueAssign,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN", "DEVELOPER"])
    )
):

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if issue is None:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    old_assignee = issue.assignee_id

    issue.assignee_id = assignment.assignee_id

    db.commit()
    db.refresh(issue)

    activity = IssueActivity(
        issue_id=issue.id,
        user_id=int(current_user.get("sub")),
        action="ISSUE_ASSIGNED",
        details=(
            f"Assignee changed from "
            f"{old_assignee} to "
            f"{assignment.assignee_id}."
        )
    )

    db.add(activity)
    db.commit()

    return issue


# ============================================================
# ADMIN
# ============================================================

@app.get("/admin/test")
def admin_test(
    current_user: dict = Depends(
        require_role(["ADMIN"])
    )
):

    return {
        "message": "Admin access granted",
        "username": current_user.get("username"),
        "role": current_user.get("role")
    }


# ============================================================
# COMMENTS
# ============================================================

@app.post(
    "/issues/{issue_id}/comments",
    response_model=CommentResponse
)
def add_comment(
    issue_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if issue is None:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    new_comment = IssueComment(
        issue_id=issue_id,
        user_id=int(current_user.get("sub")),
        comment=comment.comment
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    activity = IssueActivity(
        issue_id=issue_id,
        user_id=int(current_user.get("sub")),
        action="COMMENT_ADDED",
        details="A new comment was added to the issue."
    )

    db.add(activity)
    db.commit()

    return new_comment


@app.get(
    "/issues/{issue_id}/comments",
    response_model=list[CommentResponse]
)
def get_comments(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if issue is None:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    comments = (
        db.query(IssueComment)
        .filter(
            IssueComment.issue_id == issue_id
        )
        .order_by(IssueComment.id.asc())
        .all()
    )

    return comments


# ============================================================
# ISSUE STATUS / WORKFLOW
# ============================================================

@app.put(
    "/issues/{issue_id}/status",
    response_model=IssueResponse
)
def update_issue_status(
    issue_id: int,
    status: IssueStatus,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(
            ["ADMIN", "DEVELOPER", "TESTER"]
        )
    )
):

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if issue is None:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    old_status = issue.status

    allowed_transitions = {
        IssueStatus.REPORTED: [
            IssueStatus.TRIAGED
        ],

        IssueStatus.TRIAGED: [
            IssueStatus.ASSIGNED
        ],

        IssueStatus.ASSIGNED: [
            IssueStatus.IN_DEVELOPMENT
        ],

        IssueStatus.IN_DEVELOPMENT: [
            IssueStatus.IN_REVIEW
        ],

        IssueStatus.IN_REVIEW: [
            IssueStatus.IN_TESTING
        ],

        IssueStatus.IN_TESTING: [
            IssueStatus.RESOLVED
        ],

        IssueStatus.RESOLVED: [
            IssueStatus.CLOSED,
            IssueStatus.REOPENED
        ],

        IssueStatus.CLOSED: [
            IssueStatus.REOPENED
        ],

        IssueStatus.REOPENED: [
            IssueStatus.TRIAGED
        ],
    }

    if status not in allowed_transitions.get(
        old_status,
        []
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status transition from "
                f"{old_status.value} to "
                f"{status.value}."
            )
        )

    issue.status = status

    db.commit()
    db.refresh(issue)

    activity = IssueActivity(
        issue_id=issue.id,
        user_id=int(current_user.get("sub")),
        action="STATUS_CHANGED",
        details=(
            f"Status changed from "
            f"{old_status.value} to "
            f"{status.value}."
        )
    )

    db.add(activity)
    db.commit()

    return issue


# ============================================================
# ACTIVITY HISTORY
# ============================================================

@app.get(
    "/issues/{issue_id}/activities",
    response_model=list[ActivityResponse]
)
def get_issue_activities(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if issue is None:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    activities = (
        db.query(IssueActivity)
        .filter(
            IssueActivity.issue_id == issue_id
        )
        .order_by(IssueActivity.id.asc())
        .all()
    )

    return activities


# ============================================================
# SPRINT MANAGEMENT
# ============================================================

@app.post(
    "/sprints",
    response_model=SprintResponse
)
def create_sprint(
    sprint: SprintCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN", "DEVELOPER"])
    )
):

    new_sprint = Sprint(
        name=sprint.name,
        description=sprint.description,
        start_date=sprint.start_date,
        end_date=sprint.end_date,
        project_key=sprint.project_key,
        status=SprintStatus.PLANNED
    )

    db.add(new_sprint)
    db.commit()
    db.refresh(new_sprint)

    return new_sprint


@app.get(
    "/sprints",
    response_model=list[SprintResponse]
)
def get_sprints(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    sprints = (
        db.query(Sprint)
        .order_by(Sprint.id.asc())
        .all()
    )

    return sprints


@app.put(
    "/sprints/{sprint_id}",
    response_model=SprintResponse
)
def update_sprint(
    sprint_id: int,
    sprint: SprintUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN", "DEVELOPER"])
    )
):

    existing_sprint = (
        db.query(Sprint)
        .filter(Sprint.id == sprint_id)
        .first()
    )

    if existing_sprint is None:
        raise HTTPException(
            status_code=404,
            detail="Sprint not found"
        )

    update_data = sprint.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(
            existing_sprint,
            field,
            value
        )

    db.commit()
    db.refresh(existing_sprint)

    return existing_sprint


@app.put(
    "/issues/{issue_id}/sprint/{sprint_id}",
    response_model=IssueResponse
)
def assign_issue_to_sprint(
    issue_id: int,
    sprint_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN", "DEVELOPER"])
    )
):

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if issue is None:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    sprint = (
        db.query(Sprint)
        .filter(Sprint.id == sprint_id)
        .first()
    )

    if sprint is None:
        raise HTTPException(
            status_code=404,
            detail="Sprint not found"
        )

    issue.sprint_id = sprint_id

    db.commit()
    db.refresh(issue)

    return issue


@app.get(
    "/sprints/{sprint_id}/issues",
    response_model=list[IssueResponse]
)
def get_sprint_issues(
    sprint_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    sprint = (
        db.query(Sprint)
        .filter(Sprint.id == sprint_id)
        .first()
    )

    if sprint is None:
        raise HTTPException(
            status_code=404,
            detail="Sprint not found"
        )

    issues = (
        db.query(Issue)
        .filter(Issue.sprint_id == sprint_id)
        .order_by(Issue.id.asc())
        .all()
    )

    return issues


@app.delete(
    "/issues/{issue_id}/sprint",
    response_model=IssueResponse
)
def remove_issue_from_sprint(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN", "DEVELOPER"])
    )
):

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if issue is None:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    issue.sprint_id = None

    db.commit()
    db.refresh(issue)

    return issue


@app.delete("/sprints/{sprint_id}")
def delete_sprint(
    sprint_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN"])
    )
):

    sprint = (
        db.query(Sprint)
        .filter(Sprint.id == sprint_id)
        .first()
    )

    if sprint is None:
        raise HTTPException(
            status_code=404,
            detail="Sprint not found"
        )

    assigned_issues = (
        db.query(Issue)
        .filter(
            Issue.sprint_id == sprint_id
        )
        .count()
    )

    if assigned_issues > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Sprint cannot be deleted while "
                "issues are assigned to it."
            )
        )

    db.delete(sprint)
    db.commit()

    return {
        "message": "Sprint deleted successfully"
    }


# ============================================================
# ANALYTICS
# ============================================================

@app.get("/analytics/issues")
def issue_analytics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    total_issues = db.query(Issue).count()

    status_counts = {}

    for status in IssueStatus:
        count = (
            db.query(Issue)
            .filter(Issue.status == status)
            .count()
        )

        status_counts[status.value] = count

    return {
        "total_issues": total_issues,
        "issues_by_status": status_counts
    }


@app.get("/analytics/priority")
def priority_analytics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    total_issues = db.query(Issue).count()

    priority_counts = {}

    for priority in Priority:
        count = (
            db.query(Issue)
            .filter(Issue.priority == priority)
            .count()
        )

        priority_counts[priority.value] = count

    return {
        "total_issues": total_issues,
        "issues_by_priority": priority_counts
    }


@app.get("/analytics/severity")
def severity_analytics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    total_issues = db.query(Issue).count()

    severity_counts = {}

    for severity in Severity:
        count = (
            db.query(Issue)
            .filter(Issue.severity == severity)
            .count()
        )

        severity_counts[severity.value] = count

    return {
        "total_issues": total_issues,
        "issues_by_severity": severity_counts
    }


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.get("/admin/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN"])
    )
):

    total_issues = db.query(Issue).count()
    total_users = db.query(User).count()
    total_sprints = db.query(Sprint).count()

    return {
        "total_issues": total_issues,
        "total_users": total_users,
        "total_sprints": total_sprints
    }


# ============================================================
# REPORTS
# ============================================================

@app.get("/reports/summary")
def issue_summary_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    total_issues = db.query(Issue).count()

    open_issues = (
        db.query(Issue)
        .filter(
            Issue.status.notin_([
                IssueStatus.RESOLVED,
                IssueStatus.CLOSED
            ])
        )
        .count()
    )

    resolved_issues = (
        db.query(Issue)
        .filter(
            Issue.status == IssueStatus.RESOLVED
        )
        .count()
    )

    closed_issues = (
        db.query(Issue)
        .filter(
            Issue.status == IssueStatus.CLOSED
        )
        .count()
    )

    return {
        "total_issues": total_issues,
        "open_issues": open_issues,
        "resolved_issues": resolved_issues,
        "closed_issues": closed_issues
    }


@app.get("/reports/issues")
def issue_filter_report(
    status: IssueStatus | None = None,
    priority: Priority | None = None,
    severity: Severity | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    query = db.query(Issue)

    if status is not None:
        query = query.filter(
            Issue.status == status
        )

    if priority is not None:
        query = query.filter(
            Issue.priority == priority
        )

    if severity is not None:
        query = query.filter(
            Issue.severity == severity
        )

    issues = query.all()

    return {
        "total_results": len(issues),

        "filters": {
            "status": (
                status.value
                if status
                else None
            ),
            "priority": (
                priority.value
                if priority
                else None
            ),
            "severity": (
                severity.value
                if severity
                else None
            )
        },

        "issues": [
            {
                "id": issue.id,
                "issue_key": issue.issue_key,
                "title": issue.title,
                "status": issue.status.value,
                "priority": issue.priority.value,
                "severity": issue.severity.value
            }
            for issue in issues
        ]
    }


@app.get("/reports/sprints")
def sprint_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    sprints = db.query(Sprint).all()

    return {
        "total_sprints": len(sprints),

        "sprints": [
            {
                "id": sprint.id,
                "name": sprint.name,
                "status": sprint.status.value,
                "start_date": sprint.start_date,
                "end_date": sprint.end_date
            }
            for sprint in sprints
        ]
    }


@app.get(
    "/reports/sprints/{sprint_id}/issues"
)
def sprint_issue_report(
    sprint_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    sprint = (
        db.query(Sprint)
        .filter(Sprint.id == sprint_id)
        .first()
    )

    if sprint is None:
        raise HTTPException(
            status_code=404,
            detail="Sprint not found"
        )

    issues = (
        db.query(Issue)
        .filter(
            Issue.sprint_id == sprint_id
        )
        .all()
    )

    return {
        "sprint": {
            "id": sprint.id,
            "name": sprint.name,
            "status": sprint.status.value
        },

        "total_issues": len(issues),

        "issues": [
            {
                "id": issue.id,
                "issue_key": issue.issue_key,
                "title": issue.title,
                "status": issue.status.value,
                "priority": issue.priority.value,
                "severity": issue.severity.value
            }
            for issue in issues
        ]
    }


@app.get(
    "/reports/sprints/{sprint_id}/summary"
)
def sprint_status_summary(
    sprint_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    sprint = (
        db.query(Sprint)
        .filter(Sprint.id == sprint_id)
        .first()
    )

    if sprint is None:
        raise HTTPException(
            status_code=404,
            detail="Sprint not found"
        )

    status_counts = {}

    for status in IssueStatus:

        count = (
            db.query(Issue)
            .filter(
                Issue.sprint_id == sprint_id,
                Issue.status == status
            )
            .count()
        )

        status_counts[status.value] = count

    total_issues = sum(
        status_counts.values()
    )

    return {
        "sprint": {
            "id": sprint.id,
            "name": sprint.name,
            "status": sprint.status.value
        },

        "total_issues": total_issues,

        "issues_by_status": status_counts
    }


# ============================================================
# WEBHOOK
# ============================================================

@app.post("/webhooks/test")
def webhook_test(
    current_user: dict = Depends(get_current_user)
):

    result = send_webhook(
        event="BUGFLOW_TEST",
        data={
            "message": (
                "BugFlow webhook integration "
                "is working"
            ),
            "project": "BugFlow"
        }
    )

    return result

@app.post("/tags", response_model=TagResponse)
def create_tag(
    tag: TagCreate,
    db: Session = Depends(get_db)
):
    existing_tag = db.query(Tag).filter(
        Tag.name == tag.name
    ).first()

    if existing_tag:
        raise HTTPException(
            status_code=400,
            detail="Tag already exists"
        )

    new_tag = Tag(name=tag.name)

    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)

    return new_tag

@app.get("/tags", response_model=list[TagResponse])
def get_tags(
    db: Session = Depends(get_db)
):
    tags = db.query(Tag).order_by(Tag.name.asc()).all()

    return tags

@app.post("/issues/{issue_id}/tags/{tag_id}")
def assign_tag_to_issue(
    issue_id: int,
    tag_id: int,
    db: Session = Depends(get_db)
):
    issue = db.query(Issue).filter(
        Issue.id == issue_id
    ).first()

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    tag = db.query(Tag).filter(
        Tag.id == tag_id
    ).first()

    if not tag:
        raise HTTPException(
            status_code=404,
            detail="Tag not found"
        )

    existing = db.query(IssueTag).filter(
        IssueTag.issue_id == issue_id,
        IssueTag.tag_id == tag_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Tag is already assigned to this issue"
        )

    issue_tag = IssueTag(
        issue_id=issue_id,
        tag_id=tag_id
    )

    db.add(issue_tag)
    db.commit()

    return {
        "message": "Tag assigned successfully",
        "issue_id": issue_id,
        "tag_id": tag_id,
        "tag_name": tag.name
    }

@app.get("/issues/{issue_id}/tags", response_model=list[TagResponse])
def get_issue_tags(
    issue_id: int,
    db: Session = Depends(get_db)
):
    issue = db.query(Issue).filter(
        Issue.id == issue_id
    ).first()

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    tags = (
        db.query(Tag)
        .join(
            IssueTag,
            Tag.id == IssueTag.tag_id
        )
        .filter(IssueTag.issue_id == issue_id)
        .order_by(Tag.name.asc())
        .all()
    )

    return tags

@app.get("/issues/{issue_id}/duplicates")
def detect_duplicate_issues(
    issue_id: int,
    db: Session = Depends(get_db)
):
    issue = db.query(Issue).filter(
        Issue.id == issue_id
    ).first()

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found"
        )

    all_issues = db.query(Issue).filter(
        Issue.id != issue_id
    ).all()

    duplicates = []

    for other_issue in all_issues:
        title_similarity = SequenceMatcher(
            None,
            issue.title.lower(),
            other_issue.title.lower()
        ).ratio()

        description_similarity = SequenceMatcher(
            None,
            issue.description.lower(),
            other_issue.description.lower()
        ).ratio()

        similarity = (
            title_similarity * 0.7
            + description_similarity * 0.3
        )

        if similarity >= 0.70:
            duplicates.append({
                "issue_id": other_issue.id,
                "issue_key": other_issue.issue_key,
                "title": other_issue.title,
                "similarity": round(similarity, 2)
            })

    duplicates.sort(
        key=lambda item: item["similarity"],
        reverse=True
    )

    return {
        "issue_id": issue.id,
        "issue_key": issue.issue_key,
        "duplicates": duplicates
    }
    
@app.post("/issues/{issue_id}/merge/{duplicate_issue_id}")
def merge_duplicate_issue(
    issue_id: int,
    duplicate_issue_id: int,
    db: Session = Depends(get_db)
):
    main_issue = db.query(Issue).filter(
        Issue.id == issue_id
    ).first()

    if not main_issue:
        raise HTTPException(
            status_code=404,
            detail="Main issue not found"
        )

    duplicate_issue = db.query(Issue).filter(
        Issue.id == duplicate_issue_id
    ).first()

    if not duplicate_issue:
        raise HTTPException(
            status_code=404,
            detail="Duplicate issue not found"
        )

    if issue_id == duplicate_issue_id:
        raise HTTPException(
            status_code=400,
            detail="An issue cannot be merged with itself"
        )

    duplicate_issue.duplicate_of_id = main_issue.id

    db.commit()
    db.refresh(duplicate_issue)

    return {
        "message": "Issue merged as duplicate successfully",
        "main_issue_id": main_issue.id,
        "main_issue_key": main_issue.issue_key,
        "duplicate_issue_id": duplicate_issue.id,
        "duplicate_issue_key": duplicate_issue.issue_key,
        "duplicate_of_id": duplicate_issue.duplicate_of_id
    }
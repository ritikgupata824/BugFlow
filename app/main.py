from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
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
      Priority,
    IssueComment,
    IssueActivity,
    User,
    UserRole,
    Sprint,
    SprintStatus,
)
from app.schemas import (
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
)

app = FastAPI(
    title="BugFlow API",
    description="Software Issue Tracking & Resolution Platform",
    version="1.0.0",
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


# Register User
@app.post("/auth/register", response_model=UserResponse)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    # Check duplicate username
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

    # Check duplicate email
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

    # Hash password
    hashed_password = hash_password(user.password)

    # Create user
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


# Login User
@app.post("/auth/login", response_model=TokenResponse)
def login_user(
    login: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
   
    # Find user by username
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

    # Verify password
    if not verify_password(
        login.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    # Check active status
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive"
        )

    # Create JWT token
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

# Create Issue
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

    next_number = 1 if last_issue is None else last_issue.id + 1
    issue_key = f"{issue.project_key}-{next_number}"

    issue_data = Issue(
        issue_key=issue_key,
        issue_type=issue.issue_type,
        title=issue.title,
        description=issue.description,
        reproduction_steps=issue.reproduction_steps,
        severity=issue.severity,
        priority=issue.priority,
        affected_module=issue.affected_module,
        environment=issue.environment,
        screenshot_url=issue.screenshot_url,
        project_key=issue.project_key,
        reporter_id=issue.reporter_id,
        assignee_id=issue.assignee_id,
    )

    db.add(issue_data)
    db.commit()
    db.refresh(issue_data)

    # Create Activity Log
    activity = IssueActivity(
        issue_id=issue_data.id,
        user_id=issue_data.reporter_id,
        action="ISSUE_CREATED",
        details=f"Issue {issue_data.issue_key} was created."
    )

    db.add(activity)
    db.commit()

    return issue_data

# Get All Issues
@app.get("/issues", response_model=list[IssueResponse])
def get_issues(
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN", "REPORTER", "DEVELOPER", "TESTER"])
    )
):
    issues = (
        db.query(Issue)
        .order_by(Issue.id.asc())
        .all()
    )

    return issues


# Admin Only Test
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

# Get Single Issue
@app.get("/issues/{issue_id}", response_model=IssueResponse)
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



# Update Issue
@app.put("/issues/{issue_id}", response_model=IssueResponse)
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

    update_data = issue.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(existing_issue, field, value)

    db.commit()
    db.refresh(existing_issue)

    # Create Activity Log
    activity = IssueActivity(
        issue_id=existing_issue.id,
        user_id=int(current_user.get("sub")),
        action="ISSUE_UPDATED",
        details=f"Updated fields: {', '.join(update_data.keys())}."
    )

    db.add(activity)
    db.commit()

    return existing_issue
# Assign / Reassign Issue
@app.put("/issues/{issue_id}/assign", response_model=IssueResponse)
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

    # Create Activity Log
    activity = IssueActivity(
        issue_id=issue.id,
        user_id=int(current_user.get("sub")),
        action="ISSUE_ASSIGNED",
        details=(
            f"Assignee changed from "
            f"{old_assignee} to {assignment.assignee_id}."
        )
    )

    db.add(activity)
    db.commit()

    return issue


# Add Comment to Issue
@app.post("/issues/{issue_id}/comments", response_model=CommentResponse)
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


# Get Comments for an Issue
@app.get("/issues/{issue_id}/comments", response_model=list[CommentResponse])
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
        .filter(IssueComment.issue_id == issue_id)
        .order_by(IssueComment.id.asc())
        .all()
    )

    return comments


# Get Activity History for an Issue
@app.put("/issues/{issue_id}/status", response_model=IssueResponse)
def update_issue_status(
    issue_id: int,
    status: IssueStatus,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(["ADMIN", "DEVELOPER", "TESTER"])
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

    # Validate Issue Status Transition
    allowed_transitions = {
        IssueStatus.REPORTED: [IssueStatus.TRIAGED],
        IssueStatus.TRIAGED: [IssueStatus.ASSIGNED],
        IssueStatus.ASSIGNED: [IssueStatus.IN_DEVELOPMENT],
        IssueStatus.IN_DEVELOPMENT: [IssueStatus.IN_REVIEW],
        IssueStatus.IN_REVIEW: [IssueStatus.IN_TESTING],
        IssueStatus.IN_TESTING: [IssueStatus.RESOLVED],
        IssueStatus.RESOLVED: [
            IssueStatus.CLOSED,
            IssueStatus.REOPENED
        ],
        IssueStatus.CLOSED: [IssueStatus.REOPENED],
        IssueStatus.REOPENED: [IssueStatus.TRIAGED],
    }

    if status not in allowed_transitions.get(old_status, []):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status transition from "
                f"{old_status.value} to {status.value}."
            )
        )

    issue.status = status

    db.commit()
    db.refresh(issue)

    # Create Activity Log
    # Actual logged-in user is recorded
    activity = IssueActivity(
        issue_id=issue.id,
        user_id=int(current_user.get("sub")),
        action="STATUS_CHANGED",
        details=(
            f"Status changed from "
            f"{old_status.value} to {status.value}."
        )
    )

    db.add(activity)
    db.commit()

    return issue

# Get Issue Activity Logs
@app.get("/issues/{issue_id}/activities", response_model=list[ActivityResponse])
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
        .filter(IssueActivity.issue_id == issue_id)
        .order_by(IssueActivity.id.asc())
        .all()
    )

    return activities

# Create Sprint
@app.post("/sprints", response_model=SprintResponse)
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

# Get All Sprints
@app.get("/sprints", response_model=list[SprintResponse])
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

# Update Sprint
@app.put("/sprints/{sprint_id}", response_model=SprintResponse)
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

    update_data = sprint.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(existing_sprint, field, value)

    db.commit()
    db.refresh(existing_sprint)

    return existing_sprint

# Assign Issue to Sprint
@app.put("/issues/{issue_id}/sprint/{sprint_id}", response_model=IssueResponse)
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

# Get Issues in Sprint
@app.get("/sprints/{sprint_id}/issues", response_model=list[IssueResponse])
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

# Remove Issue from Sprint
@app.delete("/issues/{issue_id}/sprint", response_model=IssueResponse)
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

# Delete Sprint
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
        .filter(Issue.sprint_id == sprint_id)
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

# Issue Analytics
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

# Priority Analytics
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

# Admin Dashboard Analytics
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
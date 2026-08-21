"""CRUD层"""

from app.crud.job import (  # noqa: F401
    create_job,
    delete_job,
    get_job,
    get_jobs,
    update_job,
    update_job_status,
)
from app.crud.resume import (  # noqa: F401
    create_resume,
    get_resume,
    get_resumes,
    soft_delete_resume,
    update_resume_status,
)
from app.crud.user import (  # noqa: F401
    create_user,
    get_user_by_email,
    get_user_by_id,
)

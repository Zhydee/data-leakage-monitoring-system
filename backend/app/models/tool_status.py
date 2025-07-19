from app.models.models import ToolStatus

@staticmethod
def update_status(db, scan_id, tool_name, status, error_message=None):
    db.query(ToolStatus).filter_by(
        scan_job_id=scan_id,
        tool_name=tool_name
    ).update({
        "status": status,
        "error_message": error_message
    })
    db.commit()

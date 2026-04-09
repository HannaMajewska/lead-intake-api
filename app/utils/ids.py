from datetime import datetime, timezone
from uuid import uuid4


def generate_lead_id() -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:6]
    return f"lead_{now}_{suffix}"
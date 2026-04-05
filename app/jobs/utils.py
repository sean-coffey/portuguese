# app/jobs/utils.py
import json


def update_status(status_path, status=None, progress=None, message=None, extra=None):
    data = {}

    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass

    if status is not None:
        data["status"] = status
    if progress is not None:
        data["progress"] = progress
    if message is not None:
        data["message"] = message

    if extra:
        data.update(extra)

    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
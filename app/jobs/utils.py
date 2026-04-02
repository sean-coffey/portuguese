# app/jobs/utils.py
import json

def update_status(status_path, status=None, progress=None, message=None):
    data = {}

    try:
        with open(status_path) as f:
            data = json.load(f)
    except:
        pass

    if status:
        data["status"] = status
    if progress is not None:
        data["progress"] = progress
    if message:
        data["message"] = message

    with open(status_path, "w") as f:
        json.dump(data, f)
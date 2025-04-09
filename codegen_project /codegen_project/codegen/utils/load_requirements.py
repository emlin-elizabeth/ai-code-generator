import json
from pathlib import Path

def load_security_checks():
    """Load security checks from a JSON file."""
    security_file = Path(__file__).resolve().parent.parent / "security_checks.json"
    
    if not security_file.exists():
        return {"security": ["Default security rules"], "error_classes": ["ValueError", "KeyError"]}

    with open(security_file, "r", encoding="utf-8") as f:
        return json.load(f)

def get_save_base_path(user_location):
    system_folders = ["Desktop", "Documents", "Downloads"]

    if user_location in system_folders:
        return Path.home() / user_location

    elif user_location:
        user_path = Path(user_location).expanduser().resolve()
        return user_path if user_path.is_absolute() else Path.cwd() / user_path

    else:
        return Path('generated_projects').resolve()
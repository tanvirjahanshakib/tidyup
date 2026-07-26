"""Default file extension -> category mapping used by tidyup."""

DEFAULT_CATEGORIES = {
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
        ".tiff", ".heic", ".ico",
    ],
    "Documents": [
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md",
        ".xls", ".xlsx", ".ppt", ".pptx", ".csv",
    ],
    "Videos": [
        ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm",
    ],
    "Audio": [
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
    ],
    "Archives": [
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    ],
    "Code": [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".java",
        ".c", ".cpp", ".h", ".go", ".rs", ".rb", ".php", ".sh", ".json",
        ".yml", ".yaml", ".sql",
    ],
    "Installers": [
        ".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk",
    ],
}


def category_for_extension(extension: str, categories: dict) -> str:
    """Return the category name for a given file extension, or 'Others'."""
    extension = extension.lower()
    for category, extensions in categories.items():
        if extension in extensions:
            return category
    return "Others"


def load_categories(config_path):
    """
    Load a custom category mapping from a JSON file, e.g.:

        {
          "Screenshots": [".png", ".jpg"],
          "Contracts": [".pdf", ".docx"]
        }

    Custom categories are merged on top of the defaults (a category
    with the same name overrides the default one).
    """
    import json
    from pathlib import Path

    path = Path(config_path)
    custom = json.loads(path.read_text())

    # Custom categories are checked first, so a user-defined category
    # wins over a default one when both claim the same extension.
    merged = dict(custom)
    for name, extensions in DEFAULT_CATEGORIES.items():
        merged.setdefault(name, extensions)
    return merged


PROJECT_CONFIG_FILENAME = ".tidyup.json"


def find_project_config(folder):
    """
    Look for a `.tidyup.json` file directly inside `folder`. If found,
    return its path; otherwise None. This lets a folder carry its own
    permanent category rules so you don't need to pass --config every
    time you run tidyup there.
    """
    from pathlib import Path

    candidate = Path(folder) / PROJECT_CONFIG_FILENAME
    return candidate if candidate.exists() else None

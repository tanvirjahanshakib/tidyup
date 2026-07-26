"""
Smart filename-pattern rules — categorize files by naming convention,
not just extension. Many files that share an extension actually belong
in more specific buckets based on how they're named (screenshots,
invoices, resumes, etc). This runs as an optional extra layer *before*
extension-based categorization.
"""

import re

# Each rule: (category_name, compiled regex applied to the filename, case-insensitive)
DEFAULT_NAME_RULES = [
    ("Screenshots", re.compile(r"screen ?shot", re.IGNORECASE)),
    ("Screenshots", re.compile(r"^cleanshot", re.IGNORECASE)),
    ("Invoices", re.compile(r"invoice|receipt", re.IGNORECASE)),
    ("Resumes", re.compile(r"resume|cv[_\-\s]", re.IGNORECASE)),
    ("Contracts", re.compile(r"contract|agreement|nda", re.IGNORECASE)),
]


def category_for_filename(filename: str, rules=None):
    """
    Return a category name if the filename matches a known naming
    pattern, else None (caller should fall back to extension-based
    categorization).
    """
    if rules is None:
        rules = DEFAULT_NAME_RULES

    for category, pattern in rules:
        if pattern.search(filename):
            return category
    return None

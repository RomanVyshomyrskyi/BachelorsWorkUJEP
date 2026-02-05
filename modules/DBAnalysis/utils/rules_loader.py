import os

def get_normalization_rules() -> str:
    """Loads the normalization rules from the markdown file."""
    # Adjusted path to point to the correct location relative to this file's parent
    rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "normalization_rules.md")
    try:
        with open(rules_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Error: Normalization rules file not found."

"""
Rules Loader - Normalization rules file management.

Provides utilities for loading the database normalization rules reference
document (markdown format) that AI agents use when analyzing database schemas.
"""

import os


def get_normalization_rules() -> str:
    """
    Load and return the contents of the normalization rules markdown file.

    This function reads the normalization_rules.md file located in the
    DBAnalysis module's root directory and returns its contents as a string.
    The rules file contains guidelines for database schema normalization
    that AI agents reference when evaluating database designs.
        1. Constructs the absolute path to normalization_rules.md by navigating
           up two levels from this file's location (utils/ -> DBAnalysis/).
        2. Attempts to open and read the file contents.
        3. Returns the file content as a string, or an error message if the
           file is not found.

    Returns:
        The full text content of the normalization rules markdown file.
        Returns "Error: Normalization rules file not found." if the file
        does not exist at the expected path.

    Examples:
        >>> rules = get_normalization_rules()
        >>> print(rules[:100])
        # Database Normalization Rules\\n...
    """
    # Build the path to the normalization rules markdown file
    # Navigate up from utils/ to the DBAnalysis root directory
    rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "normalization_rules.md")

    try:
        # Read and return the full contents of the normalization rules file
        with open(rules_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        # Return an error message if the rules file is missing
        return "Error: Normalization rules file not found."

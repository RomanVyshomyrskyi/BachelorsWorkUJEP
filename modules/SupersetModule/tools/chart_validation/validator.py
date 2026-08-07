"""
Temporal validation helpers for chart column validation.

Contains functions for checking temporal (date/time) columns and
extracting temporal column lists from dataset metadata.

Functions:
    _is_column_temporal: Check if a column is a date/time type
    _get_temporal_columns: Extract temporal column names from dataset
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _is_column_temporal(column: Dict[str, Any], dataset_columns: List[Dict[str, Any]]) -> bool:
    """
    Check if a column is temporal (date/time) based on dataset metadata.

    Args:
        column: Column dict from dataset (has 'column_name', 'data_type', etc.)
        dataset_columns: Full list of dataset columns

    Returns:
        True if the column is temporal (datetime, date, timestamp, etc.)
    """
    col_name = column.get("column_name", "")
    data_type = column.get("data_type", "").lower()
    is_dttm = column.get("is_dttm", False)

    logger.info(f"Checking if column '{col_name}' is temporal: data_type={data_type}, is_dttm={is_dttm}")

    # Step 1: Explicit is_dttm flag - most reliable indicator
    if is_dttm:
        logger.info(f"Column '{col_name}' marked as temporal (is_dttm=True)")
        return True

    # Step 2: Check data type keywords for temporal patterns
    temporal_keywords = [
        "date", "time", "timestamp", "datetime", "timetz",
        "timestamptz", "interval", "year",
    ]

    for keyword in temporal_keywords:
        if keyword in data_type:
            logger.info(f"Column '{col_name}' identified as temporal by data_type='{data_type}'")
            return True

    logger.info(f"Column '{col_name}' is NOT temporal")
    return False


def _get_temporal_columns(dataset_columns: List[Dict[str, Any]]) -> List[str]:
    """
    Extract list of temporal column names from dataset.

    Args:
        dataset_columns: List of column dicts from dataset

    Returns:
        List of column names that are temporal
    """
    temporal_cols = []
    for col in dataset_columns:
        if _is_column_temporal(col, dataset_columns):
            temporal_cols.append(col["column_name"])

    logger.info(f"Found {len(temporal_cols)} temporal columns: {temporal_cols}")
    return temporal_cols

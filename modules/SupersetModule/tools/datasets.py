"""
Backward compatibility wrapper for dataset package.
All imports are re-exported from the refactored submodules.
"""
from modules.SupersetModule.tools.dataset import (
    create_dataset,
    create_virtual_dataset,
    list_datasets,
    get_dataset_info,
    get_database_schema,
)

__all__ = [
    'create_dataset', 'create_virtual_dataset',
    'list_datasets', 'get_dataset_info',
    'get_database_schema',
]

import logging
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModuleInfo:
    def __init__(self, name: str, api: Dict[str, Any] = None):
        self.name = name
        self.api = api or {}

    def get_api(self) -> Dict[str, Any]:
        return self.api


class ModuleRegistry:
    def __init__(self):
        self._modules: Dict[str, ModuleInfo] = {}

    def register_module_api(self, module_name: str, api: Dict[str, Any]) -> None:
        if module_name in self._modules:
            self._modules[module_name].api.update(api)
        else:
            self._modules[module_name] = ModuleInfo(module_name, api)
        logger.info(f"Registered API for module: {module_name}")

    def get_module_api(self, module_name: str) -> Optional[Dict[str, Any]]:
        info = self._modules.get(module_name)
        return info.api if info else None

    def list_modules(self) -> List[str]:
        return list(self._modules.keys())

    def has_module(self, module_name: str) -> bool:
        return module_name in self._modules


def resolve_dependency_order(
    modules: Dict[str, List[str]]
) -> List[str]:
    deps = {}
    for mod_name, dep_list in modules.items():
        deps[mod_name] = set(dep_list)

    in_degree = {m: 0 for m in deps}
    for m, dep_set in deps.items():
        in_degree[m] = len(dep_set)

    dep_graph = defaultdict(list)
    for m, dep_set in deps.items():
        for d in dep_set:
            dep_graph[d].append(m)

    queue = deque([m for m, deg in in_degree.items() if deg == 0])
    sorted_order = []

    while queue:
        node = queue.popleft()
        sorted_order.append(node)
        for dependent in dep_graph[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    unresolved = [m for m, deg in in_degree.items() if deg > 0]
    if unresolved:
        raise ValueError(
            f"Circular dependency detected among modules: {unresolved}"
        )

    return sorted_order

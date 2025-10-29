import importlib
import inspect
from pathlib import Path
from typing import Type

from src.visualizations.base import Visualization, DataContext


def discover_visualizations() -> dict[str, Type[Visualization]]:
    registry = {}
    visualizations_dir = Path(__file__).parent
    for file_path in visualizations_dir.glob("*.py"):
        if file_path.stem in ("__init__", "base"):
            continue
        module_name = f"src.visualizations.{file_path.stem}"
        try:
            module = importlib.import_module(module_name)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, Visualization) and
                    obj is not Visualization and
                    hasattr(obj, 'run')):
                    registry[obj.name] = obj
        except Exception as exc:
            msg = f"Warning: Could not load {file_path.name}: {exc}"
            print(msg)
    return registry


def get_visualizations_by_category() -> dict[str, list[Type[Visualization]]]:
    visualizations = discover_visualizations()
    by_category = {}
    for viz_class in visualizations.values():
        category = viz_class.category
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(viz_class)
    for category in by_category:
        by_category[category].sort(key=lambda v: v.name)
    return by_category


__all__ = [
    "Visualization",
    "DataContext",
    "discover_visualizations",
    "get_visualizations_by_category",
]

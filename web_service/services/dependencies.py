from __future__ import annotations

import importlib


def load_yaml_dependency() -> object:
    return importlib.import_module("yaml_not_installed")


def load_wrong_import_path() -> object:
    return importlib.import_module("web_service.services.not_existing")

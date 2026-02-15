"""Minimal runtime services for local/subprocess mode without Qt dependencies."""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class _AppSection:
    last_output_path: str = ""


class _ConfigView:
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        app_data = data.get("app", {}) if isinstance(data.get("app"), dict) else {}
        self.app = _AppSection(last_output_path=app_data.get("last_output_path", ""))

    def model_dump(self) -> Dict[str, Any]:
        return copy.deepcopy(self._data)


class ConfigService:
    """Lightweight config loader compatible with local mode usage."""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.default_config_path = self.root_dir / "examples" / "config.json"
        self.fallback_config_path = self.root_dir / "examples" / "config-example.json"
        self.config_path: Optional[str] = None
        self.current_config: Dict[str, Any] = self._load_default_config()

    def _load_default_config(self) -> Dict[str, Any]:
        for path in [self.default_config_path, self.fallback_config_path]:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    continue
        return {}

    def load_config_file(self, config_path: str) -> bool:
        try:
            if not os.path.exists(config_path):
                return False
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.current_config = loaded if isinstance(loaded, dict) else {}
            self.config_path = config_path
            return True
        except Exception:
            return False

    def get_config(self) -> _ConfigView:
        return _ConfigView(self.current_config)


class FileService:
    """Minimal file utilities used by local/subprocess execution paths."""

    supported_image_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".gif",
        ".webp",
        ".avif",
        ".tiff",
        ".tif",
        ".heic",
        ".heif",
    }

    def _natural_sort_key(self, path: str):
        normalized_path = path.replace("\\", "/")
        parts = []
        for part in re.split(r"(\d+)", normalized_path):
            if part.isdigit():
                parts.append((False, int(part)))
            elif part:
                parts.append((True, part.lower()))
        return parts

    def get_image_files_from_folder(self, folder_path: str, recursive: bool = True) -> List[str]:
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return []

        image_files: List[str] = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if d != "manga_translator_work"]
                for file_name in files:
                    ext = Path(file_name).suffix.lower()
                    if ext in self.supported_image_extensions:
                        image_files.append(str(Path(root) / file_name))
        else:
            for file_path in folder.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in self.supported_image_extensions:
                    image_files.append(str(file_path))

        image_files.sort(key=self._natural_sort_key)
        return image_files

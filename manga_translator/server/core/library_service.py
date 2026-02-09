"""Library management service for /api/v1/manga routes."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _natural_key(value: str) -> list[object]:
    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r"(\d+)", value)]


@dataclass(frozen=True)
class MangaInfo:
    id: str
    name: str
    cover_url: Optional[str]
    chapter_count: int


@dataclass(frozen=True)
class ChapterInfo:
    id: str
    name: str
    has_original: bool
    has_translated: bool
    translated_count: int
    page_count: int
    is_complete: bool


class LibraryService:
    def __init__(
        self,
        raw_dir: Optional[Path] = None,
        results_dir: Optional[Path] = None,
    ) -> None:
        server_dir = Path(__file__).resolve().parents[1]
        self.raw_dir = (raw_dir or server_dir / "data" / "raw").resolve()
        self.results_dir = (results_dir or server_dir / "data" / "results").resolve()
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_under(self, base: Path, relative: str) -> Path:
        relative = (relative or "").strip("/")
        candidate = (base / relative).resolve()
        if candidate != base and base not in candidate.parents:
            raise ValueError("Invalid path")
        return candidate

    def _find_first_image(self, directory: Path) -> Optional[Path]:
        if not directory.exists() or not directory.is_dir():
            return None
        for chapter_dir in sorted([p for p in directory.iterdir() if p.is_dir()], key=lambda p: _natural_key(p.name)):
            pages = sorted(
                [p for p in chapter_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS],
                key=lambda p: _natural_key(p.name),
            )
            if pages:
                return pages[0]
        return None

    def _find_translated_file(self, translated_dir: Path, stem: str) -> Optional[Path]:
        if not translated_dir.exists():
            return None
        candidates = [
            translated_dir / f"{stem}.png",
            translated_dir / f"{stem}.jpg",
            translated_dir / f"{stem}.jpeg",
            translated_dir / f"{stem}.webp",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate

        for file_path in translated_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS and file_path.stem == stem:
                return file_path
        return None

    def _to_data_url(self, file_path: Path) -> str:
        rel_path = file_path.relative_to(self.raw_dir.parent).as_posix()
        return f"/data/{quote(rel_path)}?v={file_path.stat().st_mtime_ns}"

    def _to_output_url(self, manga_id: str, chapter_id: str, filename: str) -> str:
        return f"/output/{quote(manga_id)}/{quote(chapter_id)}/{quote(filename)}"

    def list_manga(self) -> list[MangaInfo]:
        mangas: list[MangaInfo] = []
        if not self.raw_dir.exists():
            return mangas

        for manga_dir in sorted([p for p in self.raw_dir.iterdir() if p.is_dir()], key=lambda p: _natural_key(p.name)):
            chapter_dirs = [p for p in manga_dir.iterdir() if p.is_dir()]
            if not chapter_dirs:
                continue
            cover = self._find_first_image(manga_dir)
            cover_url = self._to_data_url(cover) if cover else None
            mangas.append(
                MangaInfo(
                    id=manga_dir.name,
                    name=manga_dir.name,
                    cover_url=cover_url,
                    chapter_count=len(chapter_dirs),
                )
            )
        return mangas

    def list_chapters(self, manga_id: str) -> list[ChapterInfo]:
        manga_dir = self._resolve_under(self.raw_dir, manga_id)
        if not manga_dir.exists() or not manga_dir.is_dir():
            raise FileNotFoundError("Manga not found")

        translated_manga_dir = self._resolve_under(self.results_dir, manga_id)
        chapters: list[ChapterInfo] = []
        for chapter_dir in sorted([p for p in manga_dir.iterdir() if p.is_dir()], key=lambda p: _natural_key(p.name)):
            pages = sorted(
                [p for p in chapter_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS],
                key=lambda p: _natural_key(p.name),
            )
            if not pages:
                continue

            translated_dir = translated_manga_dir / chapter_dir.name
            translated_count = sum(1 for page in pages if self._find_translated_file(translated_dir, page.stem))
            page_count = len(pages)
            chapters.append(
                ChapterInfo(
                    id=chapter_dir.name,
                    name=chapter_dir.name,
                    has_original=True,
                    has_translated=translated_count > 0,
                    translated_count=translated_count,
                    page_count=page_count,
                    is_complete=translated_count == page_count,
                )
            )
        return chapters

    def get_chapter(self, manga_id: str, chapter_id: str) -> dict:
        chapter_dir = self._resolve_under(self.raw_dir, f"{manga_id}/{chapter_id}")
        if not chapter_dir.exists() or not chapter_dir.is_dir():
            raise FileNotFoundError("Chapter not found")

        translated_dir = self._resolve_under(self.results_dir, f"{manga_id}/{chapter_id}")
        pages = sorted(
            [p for p in chapter_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS],
            key=lambda p: _natural_key(p.name),
        )

        page_payload: list[dict] = []
        for page in pages:
            translated_file = self._find_translated_file(translated_dir, page.stem)
            page_payload.append(
                {
                    "name": page.name,
                    "original_url": self._to_data_url(page),
                    "translated_url": (
                        self._to_output_url(manga_id, chapter_id, translated_file.name)
                        if translated_file
                        else None
                    ),
                    "status": "translated" if translated_file else "pending",
                    "status_reason": None,
                    "warning_counts": {},
                }
            )

        return {
            "manga_id": manga_id,
            "chapter_id": chapter_id,
            "pages": page_payload,
        }

    def delete_chapter(self, manga_id: str, chapter_id: str) -> dict:
        raw_path = self._resolve_under(self.raw_dir, f"{manga_id}/{chapter_id}")
        results_path = self._resolve_under(self.results_dir, f"{manga_id}/{chapter_id}")

        deleted = False
        for path in (raw_path, results_path):
            if path.exists() and path.is_dir():
                shutil.rmtree(path)
                deleted = True

        if not deleted:
            raise FileNotFoundError("Chapter not found")

        return {"message": f"Chapter {chapter_id} deleted"}

    def delete_manga(self, manga_id: str) -> dict:
        raw_path = self._resolve_under(self.raw_dir, manga_id)
        results_path = self._resolve_under(self.results_dir, manga_id)

        deleted = False
        for path in (raw_path, results_path):
            if path.exists() and path.is_dir():
                shutil.rmtree(path)
                deleted = True

        if not deleted:
            raise FileNotFoundError("Manga not found")

        return {"message": f"Manga {manga_id} deleted"}

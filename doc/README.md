# Manga Translator UI (English Navigation)

This page is a lightweight English entry. The primary maintenance language is Chinese.

## What this repo provides

- Vue3 web frontend for login, library, scraper, reader, and admin pages.
- FastAPI backend with auth, translation, scraper, and admin APIs.
- Optional Qt desktop app kept for compatibility/reference.

## Quick start

```bash
pip install -r requirements_cpu.txt
python -m manga_translator web
```

Optional frontend build:

```bash
cd frontend
npm ci
npm run build
```

## Web routes

- `/`
- `/signin`
- `/admin`
- `/scraper`
- `/manga/:id`
- `/read/:mangaId/:chapterId`

## Authentication bootstrap

There is no default username/password.

1. `GET /auth/status`
2. If `need_setup=true`, call `POST /auth/setup`
3. Login via `POST /auth/login`
4. Use `X-Session-Token` for protected requests

## Documentation map

- User docs index: [`doc/INDEX.md`](INDEX.md)
- Engineering docs index: [`docs/INDEX.md`](../docs/INDEX.md)
- API contract: [`docs/api/2026-02-10-v1-api-contract.md`](../docs/api/2026-02-10-v1-api-contract.md)
- Scraper phase4 S1 contract: [`docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md`](../docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md)
- Changelog index: [`doc/CHANGELOG_INDEX.md`](CHANGELOG_INDEX.md)

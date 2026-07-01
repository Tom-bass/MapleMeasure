# MapleMeasure — development notes for Claude

## async / sync route handler rule

FastAPI route handlers must be plain `def` unless they specifically need `await`.

- `def` handlers run in a thread pool automatically — blocking calls (DB, file I/O) are safe.
- `async def` handlers run on the event loop — any blocking call inside one **freezes the entire server**.

The only routes that legitimately need `async def` are those that call `await file.read()` or `await request.form()`: specifically `create_session` and `edit_session_submit` in `routes/sessions.py`, and `import_post`.

## Where things live

| Concern | Module |
|---|---|
| All SQL queries | `database.py` — named functions only, no inline SQL in routes |
| Path constants + template singleton | `core.py` |
| Config read/write | `config.py` |
| Dashboard, sessions CRUD, CSV export/import | `routes/sessions.py` |
| Settings (auto-backup toggle + backup folder) | `routes/settings.py` |
| Folder picker + server-side CSV backup | `routes/api.py` |

Do not add SQL to route files. Do not add path constants outside `core.py`.

## PyInstaller frozen paths

`STATIC_DIR` and `TEMPLATE_DIR` use `_BUNDLE_DIR` (`sys._MEIPASS` when frozen) because they are read-only bundle content.  
`DB_PATH`, `UPLOADS_DIR`, and `CONFIG_PATH` use `BASE_DIR` (next to the `.exe`) because they are user-writable and must persist between runs.

## Templates

`TemplateResponse` signature is `TemplateResponse(request, "name.html", context_dict)`.  
Do **not** put `"request"` inside the context dict — that was the old Starlette API and raises a `TypeError`.

## Database

The `sessions` table is the only active table. Schema:

```sql
sessions (id, created_at, session_date, auto_battle_minutes, kills, solo_frags, image_filename)
```

Old columns from a previous version of the app (`level_before`, `level_after`, `mesos_earned`, `exp_gained`, `raw_llm_response`, etc.) may exist in user databases created before the rewrite — the schema uses `CREATE TABLE IF NOT EXISTS` so they are preserved but never read or written.

## Config

`config.json` lives next to the `.exe` and is gitignored. Current keys:

| Key | Type | Default | Purpose |
|---|---|---|---|
| `auto_backup` | bool | `false` | Save CSV backup on dashboard load (once per browser session) |
| `backup_folder` | string | `""` | Folder path for server-side CSV backup; empty falls back to browser download |

`config.py` merges any stored values over `_DEFAULTS`, so new keys added to `_DEFAULTS` are available immediately even on existing installations.

## CSV import validation

`import_post` in `routes/sessions.py` validates each row individually and collects errors without aborting — valid rows are inserted even if some rows fail. Required columns: `session_date` (optional value), `auto_battle_minutes` (positive int), `kills` (non-negative int), `solo_frags` (non-negative int). Extra columns are ignored. UTF-8 BOM is stripped automatically to support Excel exports.

# Dashboard Archive & Restore

## Overview

Dashboards support a two-step deletion workflow to prevent accidental data loss:

1. **Archive** (soft delete) — Removes the dashboard from the active list but preserves all data. Archived dashboards can be viewed, restored, or permanently deleted at any time.
2. **Permanent Delete** — Irreversibly removes an archived dashboard. This option is only available from the archived view, never directly from the active list.

This design ensures that a single misclick never causes irreversible data loss.

## Behavior Assumptions

- The "delete" action in the active dashboard list performs an **archive**, not a hard delete.
- Archived dashboards retain their original ID, metadata, and content in full.
- **Restoring** an archived dashboard places it back in the active list with its original ID. The `time_modified` is updated to the restoration time so it appears at the top of the list.
- If a dashboard with the same ID already exists in the active area (edge case), restoration is blocked with a 409 Conflict error.
- **No data migration is required** — existing dashboards are unaffected. The archive feature only adds new Redis keys alongside existing ones.
- Permanent deletion can be extended in the future with additional safeguards (e.g., admin-only access, retention periods).

## Redis Storage

Archive data mirrors the active data structure:

| Purpose       | Active (existing)  | Archived (new)          |
|---------------|--------------------|-------------------------|
| ID ordering   | `dash_id`          | `dash_deleted`          |
| Metadata      | `dash_meta`        | `dash_deleted_meta`     |
| Content       | `dash_content`     | `dash_deleted_content`  |

The archived sorted set uses the **archive timestamp** as the score (not the original modification time), so the most recently archived dashboards appear first.

## API Endpoints

### Archive a Dashboard (Soft Delete)

```
DELETE /data/dash/<dash_id>
```

Moves the dashboard from active to archived area. Returns:
```json
{"archived": true, "dash_id": "1", "code": 200}
```

**Error**: 404 if dashboard not found in active area.

### List Archived Dashboards

```
GET /data/dashes/archived/
```

Returns archived dashboard metadata, sorted by archive time (newest first):
```json
{
  "data": [
    {"id": 1, "name": "My Dashboard", "author": "alice", "time_modified": 1718000000}
  ],
  "code": 200
}
```

### Restore an Archived Dashboard

```
POST /data/dash/<dash_id>/restore
```

Moves the dashboard from archived back to active area. Updates `time_modified` to current time. Returns:
```json
{"restored": true, "dash_id": "1", "code": 200}
```

**Errors**:
- 404 if dashboard not found in archived area.
- 409 if a dashboard with the same ID already exists in active area.

### Permanently Delete an Archived Dashboard

```
DELETE /data/dash/<dash_id>/permanent
```

Irreversibly removes the dashboard from the archived area. Returns:
```json
{"deleted": true, "dash_id": "1", "code": 200}
```

**Error**: 404 if dashboard not found in archived area.

### Get Dashboard Detail (with Archive Detection)

```
GET /data/dash/<dash_id>
```

If the dashboard is in the active area, returns as before. If it has been archived, the response includes an `archived` flag:
```json
{"data": {...}, "archived": true, "code": 200}
```

If not found in either area, returns 404.

## Frontend User Flow

### Archiving from the Active List

1. On the home page, click the gear icon next to a dashboard.
2. Click the **archive icon** (replaces the old delete icon).
3. Confirm the archive action in the dialog.
4. The dashboard disappears from the active list.

### Viewing Archived Dashboards

1. On the home page, click the **"Archived"** tab button.
2. The list switches to show archived dashboards (grayed out).
3. If no dashboards are archived, a "No archived dashboards" message is shown.

### Restoring a Dashboard

1. Switch to the Archived view.
2. Click the gear icon next to the dashboard you want to restore.
3. Click the **restore icon** (undo arrow).
4. The dashboard returns to the active list with updated modification time.

### Permanently Deleting

1. Switch to the Archived view.
2. Click the gear icon next to the dashboard.
3. Click the **red X icon** (permanent delete).
4. Confirm the irreversible deletion in the dialog.

### Accessing an Archived Dashboard by URL

If you visit `/dash/<id>` for an archived dashboard:
- The dashboard content is displayed in read-only mode.
- A warning banner appears: "This dashboard is archived. Restore it to make edits."
- A "Restore" button on the banner lets you restore it directly.

## Running Tests

```bash
# Run archive-specific tests
nosetests dashboard/tests/test_archive.py

# Run all tests with coverage
nosetests --with-coverage --cover-package=dashboard
```

Test coverage includes:
- Full lifecycle: create → archive → restore → edit → archive → permanent delete
- Data integrity verification after restore
- All error cases: 404 (not found), 409 (ID conflict), duplicate operations
- Empty state handling
- Batch archive of multiple dashboards

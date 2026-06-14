# Archive Feature Documentation

## Overview

The archive feature provides a safe, reversible way to manage dashboards. Instead of permanent deletion, dashboards can be **archived** (soft-deleted) and later **restored** or **hard-deleted** (permanently removed).

## Behavior Assumptions

| Concept | Meaning |
|---------|---------|
| **Archive** | Soft delete. Data stays in Redis; only list visibility changes. Reversible. |
| **Restore** | Undo an archive. Removes from archived set. Does NOT modify `time_modified`. |
| **Hard Delete** | Permanent removal from all Redis keys. Irreversible. Requires user confirmation. |
| **Active** | A dashboard not in the archived set. Default state for all existing data. |
| **Archived** | A dashboard tracked in `DASH_ARCHIVED_KEY`. Hidden from active list, visible in archived list. |

### Key Design Decisions

1. **Data stays in place**: Archived dashboards remain in `DASH_META_KEY` and `DASH_CONTENT_KEY`. No data is moved or copied during archive/restore.
2. **Zero migration**: Existing dashboards are treated as "active" because they are not in `DASH_ARCHIVED_KEY`.
3. **Archived dashes are read-write**: Users can open, view, and edit archived dashboards. Archive only affects list visibility.
4. **Restore preserves everything**: name, author, time_modified, content remain byte-identical after an archive-restore cycle.

## Redis Storage

A new sorted set is used:

| Key | Redis Type | Purpose |
|-----|-----------|---------|
| `dash_archived` | Sorted Set | score = archive timestamp, member = dash_id |

Existing keys remain unchanged:
- `dash_id` (Sorted Set) — all dash IDs, scored by `time_modified`
- `dash_meta` (Hash) — dash_id → meta JSON
- `dash_content` (Hash) — dash_id → content JSON

## API Endpoints

### Archive a Dashboard

```
POST /data/dash/<dash_id>/archive
```

- Adds `dash_id` to `DASH_ARCHIVED_KEY`
- Idempotent: archiving twice returns success
- Returns: `{"data": {"id": "<id>", "action": "archived"}, "code": 200}`
- Error: `{"data": null, "code": 404, "message": "Dashboard <id> not found"}`

### Restore a Dashboard

```
PUT /data/dash/<dash_id>/archive
```

- Removes `dash_id` from `DASH_ARCHIVED_KEY`
- Idempotent: restoring a non-archived dash returns success
- Does NOT update `time_modified`
- Returns: `{"data": {"id": "<id>", "action": "restored"}, "code": 200}`

### Hard Delete a Dashboard

```
DELETE /data/dash/<dash_id>/archive
```

- Removes from ALL Redis keys: `dash_id`, `dash_meta`, `dash_content`, `dash_archived`
- **Irreversible** — frontend shows a confirmation dialog
- Returns: `{"data": {"id": "<id>", "action": "deleted", "removed_info": {...}}, "code": 200}`

### List Dashboards (with filter)

```
GET /data/dashes/?status=active|archived|all
```

- `active` (default): only non-archived dashes
- `archived`: only archived dashes
- `all`: everything

Each item in the response includes:
- `is_archived` (boolean) — whether the dash is archived
- `time_archived` (float, optional) — archive timestamp (only when archived)

## Data Flow

### Archive Flow

```
User clicks "Archive" on homepage
  → POST /data/dash/<id>/archive
  → Server adds <id> to DASH_ARCHIVED_KEY
  → Frontend refreshes list (dash disappears from Active tab)
```

### Restore Flow

```
User clicks "Restore" (on Archived tab or detail page banner)
  → PUT /data/dash/<id>/archive
  → Server removes <id> from DASH_ARCHIVED_KEY
  → Frontend refreshes list (dash reappears in Active tab)
```

### Detail Page Access for Archived Dash

```
User visits /dash/<id> directly (e.g., from bookmark)
  → Page loads normally (content is still in Redis)
  → JS calls checkDashStatus() after createGrids()
  → Server returns list with is_archived flag
  → If archived, yellow banner appears with Restore button
  → User can view, edit, and save normally
```

## Frontend Components

### Homepage Tabs

- **Active tab**: Shows non-archived dashboards. Each row has Archive + Delete actions.
- **Archived tab**: Shows archived dashboards (slightly faded). Each row has Restore + Delete Permanently actions.
- **Badge counts**: Each tab shows item count.
- **Empty state**: Clear message when list is empty.

### Detail Page Banner

When viewing an archived dashboard, a yellow banner appears:
> This dashboard is archived. It is still viewable and editable. [Restore]

### Double-Click Protection

The `_archiveRequestInFlight` map prevents duplicate requests for the same dash_id during archive/restore/hard-delete operations.

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Empty archive list | "No archived dashboards." message |
| Empty active list | "No active dashboards. Create one with the Add button above." |
| Rapid double-click | `_archiveRequestInFlight` map blocks duplicate requests |
| Direct URL to archived dash | Page loads normally + archived banner shown |
| Archive then immediately view | Status check on page load reflects current state |
| Restore → edit → save | Works normally — save endpoint doesn't check archive status |
| Old data (pre-archive) | Appears as active — not in `DASH_ARCHIVED_KEY` |

## Future Extensibility

This design supports these extensions without schema changes:

1. **Auto-purge**: Add TTL logic — periodically remove dashes archived longer than N days.
2. **Permissions**: Add role checks to archive/restore/hard-delete endpoints.
3. **Bulk operations**: Archive/restore multiple dashes in one request.
4. **Audit log**: Track archive/restore events with timestamps and user info.
5. **Trash bin UI**: Dedicated page for managing archived items with search/filter.

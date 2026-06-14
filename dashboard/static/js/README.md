# DashTable — Unified Table Rendering Module

## Overview

`dash.table.js` is the single source of truth for rendering tabular data in
IPython-Dashboard. It replaces the previously duplicated `parseTable()`
(in `dash.js`) and `parseTable_v2()` (in `dash.sql.js`).

Companion styles live in `dash.table.css`.

## Public API

```javascript
DashTable.renderTable(data, selector, options)
DashTable.renderLoadingState(selector, message)
DashTable.renderEmptyState(selector, message)
DashTable.renderErrorState(selector, message)
DashTable.clearContainer(selector)
```

### renderTable options

| Option              | Default               | Description                                    |
|---------------------|-----------------------|------------------------------------------------|
| `clearBefore`       | `true`                | Clear container before rendering               |
| `showAxesSelectors` | `false`               | Show x/y axis dropdowns in column headers      |
| `maxCellLength`     | `200`                 | Truncate cell text longer than this (0 = off)  |
| `maxColumns`        | `100`                 | Show warning if column count exceeds (0 = off) |
| `emptyMessage`      | `"No data available"` | Message shown when data is empty               |
| `tableId`           | `"table_value"`       | HTML `id` attribute on the `<table>` element   |

### Return value

```javascript
{ success: boolean, table: Element | null, error: string | null }
```

## Expected Data Shape

Column-oriented dict (same shape as pandas `DataFrame.to_dict()`):

```javascript
{
  "column_name_1": { "0": value, "1": value, ... },
  "column_name_2": { "0": value, "1": value, ... }
}
```

## What DashTable Handles

- Rendering tabular data as an HTML `<table>`
- Empty / null / malformed data → empty state (no crash)
- Null or undefined cell values → empty string with visual indicator
- Long content truncation with tooltip
- Column-count warning banner
- Loading / empty / error state placeholders
- Optional x/y axis selector dropdowns (dashboard editor only)

## What DashTable Does NOT Handle

- **Data fetching** — callers fetch data via AJAX and pass it to `renderTable`
- **Chart rendering** — line/bar/pie/area charts remain in `dash.vis.js`
- **Table sorting / pagination / export** — not implemented
- **Column type inference** — all values rendered as plain text
- **Grid-stack layout** — managed by `dash.js`
- **SQL editor** — managed by `dash.sql.js`

## Usage Examples

### Dashboard editor modal (with x/y selectors)

```javascript
DashTable.renderTable(data, "#value", { showAxesSelectors: true });
```

### Dashboard grid widget (plain headers)

```javascript
DashTable.renderTable(data, selector, { showAxesSelectors: false });
```

### SQL query results (with loading/error lifecycle)

```javascript
DashTable.renderLoadingState("#value", "Executing query...");
$.ajax({ ... })
  .success(function(resp) {
      if (!resp.data) {
          DashTable.renderEmptyState("#value", "Query returned no results.");
      } else {
          DashTable.renderTable(resp.data, "#value", { showAxesSelectors: false });
      }
  })
  .fail(function() {
      DashTable.renderErrorState("#value", "Query execution failed.");
  });
```

## Adding a New Data Viewing Entry Point

1. Include `dash.table.js` and `dash.table.css` (already loaded globally via `layout.html`)
2. Fetch your data from whatever source (API, file, WebSocket, etc.)
3. Ensure data is in the column-oriented dict shape shown above
4. Call `DashTable.renderTable(data, yourSelector, options)`
5. Optionally use `renderLoadingState` / `renderEmptyState` / `renderErrorState` for lifecycle feedback

## File Dependencies

```
layout.html
  ├── dash.js          (strFormat, genElement, my_alert, markXy)
  ├── dash.table.js    ← this module
  ├── dash.vis.js      (chart rendering, calls DashTable for table type)
  └── dash.sql.js      (SQL execution, calls DashTable for results)
```

## Testing

- **JS tests**: Visit `/test/table` in browser to run 15 automated test cases
- **Python tests**: `nosetests dashboard/tests/test_table_data.py`

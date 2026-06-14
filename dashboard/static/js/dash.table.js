/**
 * dash.table.js
 * =============
 * Unified table rendering module for IPython-Dashboard.
 *
 * Replaces the duplicated parseTable() (dash.js) and parseTable_v2()
 * (dash.sql.js) with a single, well-behaved renderer that handles:
 *   - empty / null / malformed data
 *   - null or undefined cell values
 *   - long content truncation
 *   - column-count warnings
 *   - optional x/y axis selectors (dashboard editor only)
 *
 * Public API
 * ----------
 *   DashTable.renderTable(data, selector, options)  → { success, table, error }
 *   DashTable.renderLoadingState(selector, message)
 *   DashTable.renderEmptyState(selector, message)
 *   DashTable.renderErrorState(selector, message)
 *   DashTable.clearContainer(selector)
 *
 * Dependencies
 * ------------
 *   - jQuery (loaded globally)
 *   - strFormat() from dash.js (loaded before this file)
 *
 * Expected data shape (column-oriented dict, same as pandas .to_dict()):
 *   { "col_name_1": { "0": value, "1": value, ... },
 *     "col_name_2": { "0": value, "1": value, ... } }
 */
var DashTable = (function () {

    // ── internal constants ────────────────────────────────────────────

    var DEFAULTS = {
        clearBefore: true,
        showAxesSelectors: false,
        maxCellLength: 200,
        maxColumns: 100,
        emptyMessage: 'No data available',
        tableId: 'table_value'
    };

    // Header template WITH x/y axis selector dropdowns (dashboard editor modal).
    // Uses strFormat() — {0} is replaced with the column name.
    var thTemplateWithAxes = '                                \
<div class="btn-group">                                       \
  <button type="button" class="btn btn-xs dropdown-toggle btn-success" \
          data-toggle="dropdown" aria-haspopup="true"         \
          aria-expanded="false" style="padding: 0px 0px;">    \
    {0} <span class="caret"></span>                           \
  </button>                                                   \
  <ul class="dropdown-menu">                                  \
    <li style="width: 50px;"><input type="checkbox"           \
        onclick="markXy(this, 1)"                             \
        style="margin-left: 15px;">   x</li>                  \
    <li style="width: 50px;"><input type="checkbox"           \
        onclick="markXy(this, 0)"                             \
        style="margin-left: 15px;">   y</li>                  \
  </ul>                                                       \
</div>';

    // ── internal helpers ──────────────────────────────────────────────

    /**
     * Create a DOM element. For <td>, adds a CSS class instead of the
     * legacy nowrap attribute (handled by CSS now).
     */
    function _genElement(type) {
        return document.createElement(type);
    }

    /**
     * Return a safe string for cell display.
     * null / undefined → ""
     * Everything else → String(value)
     */
    function _safeCellValue(value) {
        if (value === null || value === undefined) {
            return '';
        }
        return String(value);
    }

    /**
     * Truncate text to maxLen characters.
     * Returns { text: string, truncated: boolean }.
     */
    function _truncateText(text, maxLen) {
        if (!maxLen || maxLen <= 0 || text.length <= maxLen) {
            return { text: text, truncated: false };
        }
        return {
            text: text.substring(0, maxLen) + '...',
            truncated: true
        };
    }

    /**
     * Remove all child nodes from the container matched by selector.
     */
    function _clearContainer(selector) {
        var container = $(selector)[0];
        if (!container) {
            return;
        }
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
    }

    /**
     * Build a plain-text column header cell (no axes selectors).
     */
    function _buildPlainHeader(colName) {
        var th = _genElement('th');
        var span = _genElement('span');
        span.className = 'dash-table-col-name';
        span.innerHTML = '&nbsp;' + colName + '&nbsp;';
        th.appendChild(span);
        return th;
    }

    /**
     * Build a column header cell with x/y axis selector dropdown.
     */
    function _buildAxesHeader(colName) {
        var th = _genElement('th');
        th.innerHTML = strFormat(thTemplateWithAxes, '&nbsp;' + colName + '&nbsp;');
        return th;
    }

    /**
     * Render a column-count warning banner into the container.
     */
    function _renderColumnWarning(container, columnCount, maxColumns) {
        var warning = _genElement('div');
        warning.className = 'dash-table-columns-warning';
        warning.innerHTML =
            '<i class="fa fa-fw fa-exclamation-triangle"></i> ' +
            'Showing ' + columnCount + ' columns (threshold: ' + maxColumns +
            '). Some columns may be hidden or truncated.';
        container.appendChild(warning);
    }

    // ── public API ────────────────────────────────────────────────────

    /**
     * Render tabular data into the DOM element matched by selector.
     *
     * @param {Object|null|undefined} data    Column-oriented dict.
     * @param {string}                selector jQuery selector for the container.
     * @param {Object}                [options]  See DEFAULTS above.
     * @returns {{ success: boolean, table: Element|null, error: string|null }}
     */
    function renderTable(data, selector, options) {
        // Merge options with defaults
        var opts = {};
        for (var key in DEFAULTS) {
            if (DEFAULTS.hasOwnProperty(key)) {
                opts[key] = (options && options.hasOwnProperty(key))
                    ? options[key]
                    : DEFAULTS[key];
            }
        }

        // Validate selector
        var container = $(selector)[0];
        if (!container) {
            return { success: false, table: null, error: 'Container not found: ' + selector };
        }

        // Clear existing content if requested
        if (opts.clearBefore) {
            _clearContainer(selector);
        }

        // ── empty / null / malformed data guard ──────────────────────
        if (!data || typeof data !== 'object') {
            renderEmptyState(selector, opts.emptyMessage);
            return { success: false, table: null, error: 'No data provided' };
        }

        // Extract column names (object keys)
        var columns = [];
        for (var col in data) {
            if (data.hasOwnProperty(col)) {
                columns.push(col);
            }
        }

        if (columns.length === 0) {
            renderEmptyState(selector, opts.emptyMessage);
            return { success: false, table: null, error: 'No columns in data' };
        }

        // Extract row indexes from the first column
        var firstColData = data[columns[0]];
        if (!firstColData || typeof firstColData !== 'object') {
            renderEmptyState(selector, opts.emptyMessage);
            return { success: false, table: null, error: 'Column data is not an object' };
        }

        var indexes = [];
        for (var idx in firstColData) {
            if (firstColData.hasOwnProperty(idx)) {
                indexes.push(idx);
            }
        }

        if (indexes.length === 0) {
            renderEmptyState(selector, opts.emptyMessage);
            return { success: false, table: null, error: 'No rows in data' };
        }

        // ── column count warning ─────────────────────────────────────
        if (opts.maxColumns > 0 && columns.length > opts.maxColumns) {
            _renderColumnWarning(container, columns.length, opts.maxColumns);
        }

        // ── build table ──────────────────────────────────────────────
        var table = _genElement('table');
        var thead = _genElement('thead');
        var tbody = _genElement('tbody');

        // Header row: first cell is the row-index label, then one cell per column
        var headerTr = _genElement('tr');
        var cornerTh = _genElement('th');
        headerTr.appendChild(cornerTh);

        var buildHeader = opts.showAxesSelectors ? _buildAxesHeader : _buildPlainHeader;
        for (var c = 0; c < columns.length; c++) {
            headerTr.appendChild(buildHeader(columns[c]));
        }
        thead.appendChild(headerTr);

        // Body rows
        for (var r = 0; r < indexes.length; r++) {
            var tr = _genElement('tr');

            // Row index cell
            var rowTh = _genElement('th');
            rowTh.innerText = indexes[r];
            tr.appendChild(rowTh);

            // Data cells
            for (var ci = 0; ci < columns.length; ci++) {
                var td = _genElement('td');
                var colName = columns[ci];
                var rawValue = (data[colName] && data[colName].hasOwnProperty(indexes[r]))
                    ? data[colName][indexes[r]]
                    : null;
                var cellText = _safeCellValue(rawValue);

                // Null / undefined indicator
                if (rawValue === null || rawValue === undefined) {
                    td.className = 'dash-table-cell-null';
                }

                // Truncation
                if (opts.maxCellLength > 0) {
                    var result = _truncateText(cellText, opts.maxCellLength);
                    td.innerText = result.text;
                    if (result.truncated) {
                        td.setAttribute('title', cellText);
                        td.className += (td.className ? ' ' : '') + 'dash-table-cell-truncated';
                    }
                } else {
                    td.innerText = cellText;
                }

                tr.appendChild(td);
            }
            tbody.appendChild(tr);
        }

        // Apply table attributes and classes
        table.setAttribute('id', opts.tableId);
        table.setAttribute('border', '1px');
        table.className = 'table-condensed table-hover dash-table';
        table.style.fontSize = 'small';
        table.style.fontWeight = '400';

        // Assemble and attach
        table.appendChild(thead);
        table.appendChild(tbody);
        container.appendChild(table);

        return { success: true, table: table, error: null };
    }

    /**
     * Render a loading indicator into the container.
     */
    function renderLoadingState(selector, message) {
        var container = $(selector)[0];
        if (!container) {
            return;
        }
        _clearContainer(selector);

        var wrapper = _genElement('div');
        wrapper.className = 'dash-table-loading';
        wrapper.innerHTML =
            '<i class="fa fa-fw fa-3x fa-circle-o-notch fa-spin"></i>' +
            '<p>' + (message || 'Loading data...') + '</p>';
        container.appendChild(wrapper);
    }

    /**
     * Render an empty-state placeholder into the container.
     */
    function renderEmptyState(selector, message) {
        var container = $(selector)[0];
        if (!container) {
            return;
        }
        _clearContainer(selector);

        var wrapper = _genElement('div');
        wrapper.className = 'dash-table-empty';
        wrapper.innerHTML =
            '<i class="fa fa-fw fa-3x fa-inbox"></i>' +
            '<p>' + (message || 'No data available') + '</p>';
        container.appendChild(wrapper);
    }

    /**
     * Render an error state into the container.
     */
    function renderErrorState(selector, message) {
        var container = $(selector)[0];
        if (!container) {
            return;
        }
        _clearContainer(selector);

        var wrapper = _genElement('div');
        wrapper.className = 'dash-table-error';
        wrapper.innerHTML =
            '<i class="fa fa-fw fa-3x fa-exclamation-circle"></i>' +
            '<p>' + (message || 'An error occurred') + '</p>';
        container.appendChild(wrapper);
    }

    /**
     * Public wrapper for _clearContainer.
     */
    function clearContainer(selector) {
        _clearContainer(selector);
    }

    // ── exported namespace ────────────────────────────────────────────

    return {
        renderTable: renderTable,
        renderLoadingState: renderLoadingState,
        renderEmptyState: renderEmptyState,
        renderErrorState: renderErrorState,
        clearContainer: clearContainer
    };

})();

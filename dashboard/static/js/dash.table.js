/**
 * DashTable - Unified table rendering module for IPython-Dashboard.
 *
 * This module provides a single, shared table rendering pipeline used by both
 * the Dashboard chart editor (interactive mode with X/Y axis selection) and the
 * SQL results viewer (readonly mode with plain headers).
 *
 * Dependencies (must be loaded before this file):
 *   - jQuery (window.$)
 *   - dash.js (provides genElement, strFormat)
 *
 * @example
 * // Readonly table (SQL results, dashboard grid view):
 * DashTable.render(data, "#value", { headerMode: "readonly" });
 *
 * @example
 * // Interactive table (dashboard modal editor with X/Y axis selection):
 * DashTable.render(data, "#value", {
 *     headerMode: "interactive",
 *     onAxisSelect: function(colName, axisType, isChecked) {
 *         // axisType: 1 = x-axis, 0 = y-axis
 *         // Handle axis selection (e.g., update store)
 *     }
 * });
 *
 * @example
 * // State indicators:
 * DashTable.showLoading("#value");
 * DashTable.showError("#value", "Query execution failed.");
 * DashTable.showEmpty("#value", "No rows returned.");
 *
 * Data format (Pandas DataFrame.to_dict() output):
 *   { "column_name": { "row_index": value, ... }, ... }
 *
 * Responsibilities:
 *   - Data validation and format checking
 *   - Container clearing (safe, no live-collection bugs)
 *   - Table DOM construction (thead + tbody)
 *   - Header rendering (interactive with X/Y dropdowns OR readonly plain text)
 *   - Loading / error / empty state display
 *   - Graceful handling of null/undefined cell values
 *
 * NOT responsible for:
 *   - AJAX calls or data fetching
 *   - Store/state persistence (X/Y axis selections are communicated via callback)
 *   - Chart (non-table) rendering
 *   - Page-specific layout or routing
 */
var DashTable = (function() {

    // ----- Private state -----

    var _defaults = {
        headerMode: "readonly",   // "interactive" | "readonly"
        onAxisSelect: null,       // function(colName, axisType, isChecked) or null
        tableId: "table_value",
        cssClass: "table-condensed table-hover"
    };

    // Stores the onAxisSelect callback from the most recent interactive render.
    // This is read by _onAxisClick when a user clicks an axis checkbox.
    var _currentOnAxisSelect = null;

    // Interactive header template: green dropdown button with X/Y checkboxes.
    // Uses DashTable._onAxisClick instead of the global markXy.
    var _interactiveThTpl = '                  \
<div class="btn-group">              \
  <button type="button" class="btn btn-xs dropdown-toggle btn-success" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false" style="padding: 0px 0px;">  \
    {0} <span class="caret"></span>  \
  </button>                          \
  <ul class="dropdown-menu">         \
    <li style="width: 50px;"><input type="checkbox" onclick="DashTable._onAxisClick(this, 1)" style="margin-left: 15px;">   x</li> \
    <li style="width: 50px;"><input type="checkbox" onclick="DashTable._onAxisClick(this, 0)" style="margin-left: 15px;">   y</li> \
  </ul>                              \
</div>';

    // ----- Private helpers -----

    function _mergeOptions(opts) {
        if (!opts) return $.extend({}, _defaults);
        return $.extend({}, _defaults, opts);
    }

    function _createStateEl(stateCls, iconCls, message) {
        var wrapper = document.createElement("div");
        wrapper.className = "dash-table-state " + stateCls;

        var icon = document.createElement("i");
        icon.className = iconCls;
        wrapper.appendChild(icon);

        var p = document.createElement("p");
        p.innerText = message;
        wrapper.appendChild(p);

        return wrapper;
    }

    function _extractStructure(data) {
        var columns = [];
        var indexes = [];

        $.each(data, function(key) {
            columns.push(key);
        });

        if (columns.length > 0 && data[columns[0]]) {
            $.each(data[columns[0]], function(index) {
                indexes.push(index);
            });
        }

        return { columns: columns, indexes: indexes };
    }

    function _buildHeader(columns, options) {
        var thead = genElement("thead");
        var tr = genElement("tr");

        // Leading empty th for row-index column
        var cornerTh = genElement("th");
        tr.appendChild(cornerTh);

        for (var i = 0; i < columns.length; i++) {
            var th = genElement("th");
            if (options.headerMode === "interactive") {
                var tmp = strFormat(_interactiveThTpl, "&nbsp " + columns[i] + "&nbsp ");
                th.innerHTML = tmp;
            } else {
                th.innerText = columns[i];
                th.style.padding = "4px 8px";
                th.style.whiteSpace = "nowrap";
            }
            tr.appendChild(th);
        }

        thead.appendChild(tr);
        return thead;
    }

    function _buildBody(data, columns, indexes) {
        var tbody = genElement("tbody");

        for (var row = 0; row < indexes.length; row++) {
            var tr = genElement("tr");

            // Row index header
            var th = genElement("th");
            th.innerText = indexes[row];
            tr.appendChild(th);

            for (var col = 0; col < columns.length; col++) {
                var td = genElement("td");
                var cellValue = data[columns[col]][indexes[row]];
                td.innerText = (cellValue === null || cellValue === undefined) ? "" : cellValue;
                tr.appendChild(td);
            }

            tbody.appendChild(tr);
        }

        return tbody;
    }

    // ----- Public API -----

    return {

        /**
         * Internal click handler for interactive header checkboxes.
         * Called via onclick in the template. Do not call directly.
         */
        _onAxisClick: function(checkbox, axisType) {
            var btnType = axisType ? "btn-info" : "btn-warning";
            var btn = checkbox.parentElement.parentElement.parentElement.children[0];
            var colName = btn.innerText.trim();

            if (checkbox.checked) {
                btn.classList.remove("btn-success");
                btn.classList.add(btnType);
            } else {
                btn.classList.remove(btnType);
                btn.classList.add("btn-success");
            }

            if (typeof _currentOnAxisSelect === "function") {
                _currentOnAxisSelect(colName, axisType, checkbox.checked);
            }
        },

        /**
         * Validate data against the expected Pandas to_dict() format.
         * @param {*} data - The data to validate
         * @returns {{ valid: boolean, reason: string }}
         */
        validate: function(data) {
            if (data === null || data === undefined) {
                return { valid: false, reason: "No data available." };
            }
            if (typeof data !== "object" || Array.isArray(data)) {
                return { valid: false, reason: "Invalid data format." };
            }
            var columns = Object.keys(data);
            if (columns.length === 0) {
                return { valid: false, reason: "Data has no columns." };
            }
            var firstCol = data[columns[0]];
            if (typeof firstCol !== "object" || firstCol === null || Array.isArray(firstCol)) {
                return { valid: false, reason: "Invalid column data format." };
            }
            if (Object.keys(firstCol).length === 0) {
                return { valid: false, reason: "No rows in data." };
            }
            return { valid: true, reason: "" };
        },

        /**
         * Safely clear all children from a container.
         * @param {string} selector - jQuery selector for the container
         */
        clear: function(selector) {
            $(selector).empty();
        },

        /**
         * Show a loading spinner in the container.
         * @param {string} selector - jQuery selector for the container
         */
        showLoading: function(selector) {
            this.clear(selector);
            var el = _createStateEl(
                "dash-table-loading",
                "fa fa-spinner fa-spin fa-2x",
                "Loading..."
            );
            $(selector).append(el);
        },

        /**
         * Show an error message in the container.
         * @param {string} selector - jQuery selector for the container
         * @param {string} [message] - Error description
         */
        showError: function(selector, message) {
            this.clear(selector);
            var el = _createStateEl(
                "dash-table-error",
                "fa fa-exclamation-triangle fa-2x",
                message || "An error occurred while loading data."
            );
            $(selector).append(el);
        },

        /**
         * Show an empty-state message in the container.
         * @param {string} selector - jQuery selector for the container
         * @param {string} [message] - Description of why it's empty
         */
        showEmpty: function(selector, message) {
            this.clear(selector);
            var el = _createStateEl(
                "dash-table-empty",
                "fa fa-table fa-2x",
                message || "No data available."
            );
            $(selector).append(el);
        },

        /**
         * Validate, build, and render a table into the specified container.
         *
         * @param {Object} data - Column-oriented data: { col: { idx: val, ... }, ... }
         * @param {string} selector - jQuery selector for the target container
         * @param {Object} [options] - Rendering options
         * @param {string} [options.headerMode="readonly"] - "interactive" or "readonly"
         * @param {Function} [options.onAxisSelect=null] - Callback for axis checkbox changes
         * @param {string} [options.tableId="table_value"] - id attribute for the table element
         * @param {string} [options.cssClass="table-condensed table-hover"] - CSS classes
         * @returns {HTMLElement|null} The rendered table element, or null if data is invalid
         */
        render: function(data, selector, options) {
            var opts = _mergeOptions(options);

            // Validate data
            var check = this.validate(data);
            if (!check.valid) {
                this.showEmpty(selector, check.reason);
                return null;
            }

            // Clear container
            this.clear(selector);

            // Store callback for interactive mode
            if (opts.headerMode === "interactive" && opts.onAxisSelect) {
                _currentOnAxisSelect = opts.onAxisSelect;
            }

            // Extract structure
            var info = _extractStructure(data);

            // Build table
            var table = genElement("table");
            var thead = _buildHeader(info.columns, opts);
            var tbody = _buildBody(data, info.columns, info.indexes);

            table.appendChild(thead);
            table.appendChild(tbody);

            table.setAttribute("id", opts.tableId);
            table.setAttribute("border", "1px");
            table.className = opts.cssClass;
            table.style.fontSize = "small";
            table.style.fontWeight = "400";

            // Mount
            $(selector)[0].appendChild(table);

            return table;
        }
    };

})();

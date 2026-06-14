/**
 * dash.sql.js
 * ===========
 * SQL page logic: execute SQL queries and render results using DashTable.
 *
 * Depends on:
 *   - jQuery, Ace Editor (loaded globally)
 *   - strFormat(), my_alert() from dash.js
 *   - DashTable from dash.table.js
 */

/**
 * Toggle the disabled state of all SQL action buttons (run / format).
 */
function setSqlButtonsDisabled(disabled) {
    var buttons = $("#graph-type .btn-chart");
    if (disabled) {
        buttons.attr("disabled", "disabled");
    } else {
        buttons.removeAttr("disabled");
    }
}

/**
 * Entry point: read SQL from the editor and send to backend.
 * @param {string} options - 'all' | 'selected' | 'first' | 'last' | 'format'
 */
function runSql(options) {
    console.log("###Run sql options: " + options);
    var sql_raw = (options == "selected" ? editor.getSelectedText() : editor.getValue());
    sqlAjax(options, sql_raw);
    console.log("###Run sql : " + sql_raw);
}

/**
 * Send SQL to backend, manage loading/error/success lifecycle.
 */
function sqlAjax(options, sql_raw) {
    var postData = JSON.stringify({ "sql_raw": sql_raw, "options": options });
    var url = api_root + "data/sql/";
    var method = "POST";

    // Show loading state (skip for format — it's instant and modifies the editor)
    if (options !== 'format') {
        DashTable.renderLoadingState("#value", "Executing query...");
        setSqlButtonsDisabled(true);
    }

    $.ajax({
        url: url,
        data: postData,
        method: method,
        contentType: "application/json"
    })
    .done(function () { console.log("ajax done"); })
    .fail(function (xhr, status, error) {
        console.log("ajax fail: " + error);
        if (options !== 'format') {
            var msg = "Query execution failed";
            // Try to extract error detail from response
            try {
                var resp = JSON.parse(xhr.responseText);
                if (resp && resp.error) {
                    msg = msg + ": " + resp.error;
                }
            } catch (e) { /* ignore parse error */ }
            DashTable.renderErrorState("#value", msg);
        }
    })
    .success(function (data) {
        console.log("ajax success");
        console.log(data);
        parseSQL(options, data);
    })
    .complete(function () {
        console.log("ajax complete");
        if (options !== 'format') {
            setSqlButtonsDisabled(false);
        }
    })
    .always(function () { console.log("ajax always"); });
}

/**
 * Route the server response: format → update editor, otherwise → render table.
 */
function parseSQL(options, data) {
    if (options == 'format') {
        editor.setValue(data.data, 1);
        return;
    }

    // Check for server-side error
    if (data.error) {
        DashTable.renderErrorState("#value", "Query error: " + data.error);
        return;
    }

    // Check for empty / null result
    if (!data.data || typeof data.data !== 'object') {
        DashTable.renderEmptyState("#value", "Query returned no results.");
        return;
    }

    // Check if result has any columns
    var hasColumns = false;
    for (var key in data.data) {
        if (data.data.hasOwnProperty(key)) {
            hasColumns = true;
            break;
        }
    }
    if (!hasColumns) {
        DashTable.renderEmptyState("#value", "Query returned no columns.");
        return;
    }

    // Render the result table
    DashTable.renderTable(data.data, "#value", { showAxesSelectors: false });
}

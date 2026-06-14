
// SQL execution mode labels (for status display)
var SQL_MODE_LABELS = {
    'all':      'Execute All',
    'selected': 'Execute Selected',
    'first':    'Execute First Statement',
    'last':     'Execute Last Statement',
    'format':   'Format SQL'
};


/**
 * Entry point: validate input and send SQL to backend.
 * @param {string} options - execution mode: all | selected | first | last | format
 */
function runSql(options) {
    var sql_raw;

    if (options === 'selected') {
        sql_raw = editor.getSelectedText();
        if (!sql_raw || !sql_raw.trim()) {
            showSqlStatus('warning', 'No text selected — please highlight the SQL you want to run.');
            return;
        }
    } else {
        sql_raw = editor.getValue();
        if (options !== 'format' && (!sql_raw || !sql_raw.trim())) {
            showSqlStatus('warning', 'Editor is empty — nothing to execute.');
            return;
        }
    }

    console.log('### Run SQL | mode=' + options + ' | length=' + sql_raw.length);
    showSqlStatus('running', 'Executing...');
    sqlAjax(options, sql_raw);
}


/**
 * Send SQL to the backend and handle the response.
 */
function sqlAjax(options, sql_raw) {
    var postData = JSON.stringify({ "sql_raw": sql_raw, "options": options });
    var url = api_root + "data/sql/";

    $.ajax({
        url: url,
        data: postData,
        method: "POST",
        contentType: "application/json"
    })
    .done(function(data) {
        console.log('ajax done, status=' + (data ? data.status : 'unknown'));
        if (data && data.status) {
            parseSQL(options, data);
        } else {
            showSqlStatus('error', 'Server returned an unexpected response.');
        }
    })
    .fail(function(xhr, textStatus, errorThrown) {
        console.log('ajax fail: ' + textStatus);
        var msg = 'Request failed';
        if (xhr.status === 0) {
            msg = 'Cannot reach server — check that the dashboard is running.';
        } else if (xhr.status >= 500) {
            msg = 'Server error (' + xhr.status + ')';
        } else if (xhr.status === 400) {
            try {
                var resp = JSON.parse(xhr.responseText);
                msg = resp.message || 'Bad request';
            } catch(e) {
                msg = 'Bad request (' + xhr.status + ')';
            }
        }
        showSqlStatus('error', msg);
    });
}


/**
 * Route the response to the correct handler based on mode and status.
 */
function parseSQL(options, response) {
    if (options === 'format') {
        if (response.status === 'success' && response.data) {
            editor.setValue(response.data, 1);
            showSqlStatus('success', 'SQL formatted.');
        } else {
            showSqlStatus(response.status || 'warning',
                          response.message || 'Format returned no result.');
        }
        return;
    }

    // Build the metadata line
    var meta = buildExecMeta(response);

    if (response.status === 'success' && response.data) {
        var result = response.data;
        if (result.status === 'query' && result.data) {
            parseTable_v2(result.data, "#value");
            showSqlStatus('success',
                response.message + '  [' + meta + ']');
        } else if (result.status === 'write') {
            clearResult();
            showSqlStatus('success',
                'Statement executed — ' + result.row_count +
                ' row(s) affected.  [' + meta + ']');
        } else {
            clearResult();
            showSqlStatus('success', response.message + '  [' + meta + ']');
        }
    } else if (response.status === 'info') {
        clearResult();
        showSqlStatus('info',
            (response.message || 'Query returned 0 rows.') + '  [' + meta + ']');
    } else if (response.status === 'error') {
        // keep previous result visible so user can compare
        showSqlStatus('error',
            (response.message || 'Execution failed.') + '  [' + meta + ']');
    } else if (response.status === 'warning') {
        showSqlStatus('warning', response.message || 'Check your input.');
    } else {
        showSqlStatus('error', 'Unexpected response from server.');
    }
}


/**
 * Build a short metadata string describing the execution.
 */
function buildExecMeta(response) {
    var parts = [];
    if (response.exec_mode && SQL_MODE_LABELS[response.exec_mode]) {
        parts.push(SQL_MODE_LABELS[response.exec_mode]);
    }
    if (typeof response.elapsed !== 'undefined') {
        parts.push(response.elapsed + 's');
    }
    return parts.join(' | ');
}


/**
 * Clear the result viewer area.
 */
function clearResult() {
    $("#value").empty();
}


/**
 * Display a status message in the execution status bar.
 *
 * @param {string} type    - 'success' | 'error' | 'warning' | 'info' | 'running'
 * @param {string} message - text to display
 */
function showSqlStatus(type, message) {
    var $bar = $('#sql-exec-status');
    if (!$bar.length) return;

    var colorMap = {
        'success': '#dff0d8',
        'error':   '#f2dede',
        'warning': '#fcf8e3',
        'info':    '#d9edf7',
        'running': '#f5f5f5'
    };
    var textColorMap = {
        'success': '#3c763d',
        'error':   '#a94442',
        'warning': '#8a6d3b',
        'info':    '#31708f',
        'running': '#666'
    };

    $bar.css('background-color', colorMap[type] || '#f5f5f5')
        .css('color', textColorMap[type] || '#333')
        .text(message)
        .show();

    // Also fire my_alert for prominent errors (uses layout.html banner)
    if (type === 'error') {
        try { my_alert(message, true); } catch(e) {}
    }
}


/**
 * Render a column-oriented dict as an HTML table into the given selector.
 * Preserves the original rendering logic from dash.sql.js.
 */
function parseTable_v2(data, selector) {
    $.each($(selector)[0].children, function(index, obj) {
        $(selector)[0].removeChild(obj);
    });

    var table = genElement("table");
    var thead = genElement("thead");
    var tbody = genElement("tbody");
    var tr = genElement("tr");
    var th = genElement("th");
    var td = genElement("td");

    tr.appendChild(th);

    var columns = [];
    $.each(data, function(key, value) {
        var th = genElement("th");
        var tmp = strFormat(th_template, "&nbsp " + key + "&nbsp ");
        th.innerHTML = tmp;
        tr.appendChild(th);
        columns.push(key);
    });
    thead.appendChild(tr);

    var indexes = [];
    $.each(data[columns[0]], function(index, value) {
        indexes.push(index);
    });

    for (var row = 0; row < indexes.length; row++) {
        var tr = genElement("tr");
        var th = genElement("th");
        th.innerText = indexes[row];
        tr.appendChild(th);
        $.each(columns, function(no_user, col) {
            var td = genElement("td");
            td.innerText = data[col][indexes[row]];
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    }

    table.setAttribute("id", "table_value");
    table.setAttribute("border", "1px");
    table.className = "table-condensed table-hover";
    table.style.fontSize = "small";
    table.style.fontWeight = "400";

    var tableDOM = $(selector)[0];

    // add table
    table.appendChild(thead);
    table.appendChild(tbody);
    tableDOM.appendChild(table);
}

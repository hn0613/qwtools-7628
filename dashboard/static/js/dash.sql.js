

function runSql(options) {
    console.log("###Run sql options: " + options);
    var sql_raw;

    if (options == "selected") {
        sql_raw = editor.getSelectedText();
        if (!sql_raw || !sql_raw.trim()) {
            my_alert("No text selected. Please select SQL to execute.", true);
            return;
        }
    } else {
        sql_raw = editor.getValue();
        if (options != "format" && (!sql_raw || !sql_raw.trim())) {
            my_alert("SQL editor is empty.", true);
            return;
        }
    }

    sqlAjax(options, sql_raw);
    console.log("###Run sql : " + sql_raw);
}

function sqlAjax(options, sql_raw){
    var postData = JSON.stringify({"sql_raw": sql_raw, "options": options});
    var url = api_root + "data/sql/";
    var method = "POST";

    $.ajax({
        url: url,
        data: postData,
        method: method,
        contentType: "application/json"
    })
    .done(function(data){
        console.log("ajax done");
        console.log(data);
        if (data.error) {
            my_alert("SQL Error: " + data.error, true);
        } else {
            parseSQL(options, data);
        }
    })
    .fail(function(jqXHR, textStatus, errorThrown){
        console.log("ajax fail: " + textStatus);
        var errorMsg = "Request failed";
        if (jqXHR.responseJSON && jqXHR.responseJSON.error) {
            errorMsg = jqXHR.responseJSON.error;
        } else if (errorThrown) {
            errorMsg = errorThrown;
        }
        my_alert("Error: " + errorMsg, true);
    });
}

function parseSQL(options, data){
    if (options == 'format') {
        editor.setValue(data.data, 1);
    } else if (data.data === null || data.data === undefined) {
        // Non-SELECT result (INSERT/UPDATE/DELETE/DDL)
        clearTable("#value");
        var msg = data.message || "Query executed successfully.";
        my_alert(msg, false);
    } else if ($.isEmptyObject(data.data)) {
        // SELECT returned zero rows
        clearTable("#value");
        my_alert("Query returned 0 rows.", false);
    } else {
        parseTable_v2(data.data, "#value");
    }
}

function clearTable(selector){
    var container = $(selector)[0];
    while (container.firstChild) {
        container.removeChild(container.firstChild);
    }
}

function parseTable_v2(data, selector){
    clearTable(selector);

    if (!data || typeof data !== 'object') {
        my_alert("No data to display.", false);
        return;
    }

    var table = genElement("table");
    var thead = genElement("thead");
    var tbody = genElement("tbody");
    var tr = genElement("tr");
    var th = genElement("th");
    var td = genElement("td");

    tr.appendChild(th);

    var columns = [];
    $.each(data, function(key, value){
        var th = genElement("th");
        var tmp = strFormat(th_template, "&nbsp " + key + "&nbsp ");
        th.innerHTML = tmp;
        tr.appendChild(th);
        columns.push(key);
    })
    thead.appendChild(tr);

    var indexes = [];

    $.each(data[columns[0]], function(index, value){
        indexes.push(index);
    })

    for (var row = 0; row < indexes.length; row++) {
        var tr = genElement("tr");
        var th = genElement("th");
        th.innerText = indexes[row];
        tr.appendChild(th);
        $.each(columns, function(no_user, col){
            var td = genElement("td");
            td.innerText = data[col][indexes[row]];
            tr.appendChild(td);
        })
        tbody.appendChild(tr);
    };

    table.setAttribute("id", "table_value");
    table.setAttribute("border", "1px");
    table.className = "table-condensed table-hover";
    table.style.fontSize = "small";
    table.style.fontWeight = "400";

    var tableDOM = $(selector)[0]

    // add table
    table.appendChild(thead);
    table.appendChild(tbody);
    tableDOM.appendChild(table);
}

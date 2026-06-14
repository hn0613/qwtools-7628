


function runSql(options) {
    console.log("###Run sql options: " + options);
    var sql_raw = (options=="selected" ? editor.getSelectedText() : editor.getValue()) ;
    sqlAjax(options, sql_raw);
    console.log("###Run sql : " + sql_raw);

}

function sqlAjax(options, sql_raw){
    var postData = JSON.stringify({"sql_raw": sql_raw, "options": options});
    var url = api_root + "data/sql/";
    var method = "POST";

    // Show loading state for query execution
    if (options !== 'format') {
        DashTable.showLoading("#value");
    }

    $.ajax({
        url: url,
        data: postData,
        method: method,
        contentType: "application/json"
    })
    .done(function(){console.log("ajax done")})
    .fail(function(jqXHR, textStatus, errorThrown){
        console.log("ajax fail: " + textStatus);
        if (options !== 'format') {
            DashTable.showError("#value", "SQL query failed: " + (errorThrown || textStatus));
        }
        my_alert("SQL query failed: " + (errorThrown || textStatus), true);
    })
    .success(function(data){
        console.log("ajax success");
        console.log(data);
        parseSQL(options, data);
    })
    .complete(function(){console.log("ajax complete")})
    .always(function(){console.log("ajax always")})
    ;
}

function parseSQL(options, data){
    if (options == 'format') {
        editor.setValue(data.data, 1);
    } else {
        DashTable.render(data.data, "#value", { headerMode: "readonly" });
    }
}

/************************************
Dom templates
*************************************/

// gridstack box
var box_template = ' \
<div data-gs-min-height="4" data-gs-min-width="6">   \
  <div class="grid-stack-item-content">              \
    <div class="chart-wrapper">                      \
      <div class="chart-title bold">                 \
        <table class="table input-title-level-2">    \
          <tr class="active" style="padding-left: 10%;">               \
            <td style="padding: 0px; padding-left: 5px;">              \
              <button class="fa fa-fw fa-sm fa-circle-o-notch" onclick=toggleGridMovable(this) style="background: none;background-color: inherit;border: none; padding: 0px 0px">         \
              </button></td>                                           \
            <td style="padding: 0px; width: 90%; padding-left: 5px">   \
              <input class="form-control input-lg input-title-level-2" maxlength="128" placeholder="Naming your graph">  \
            </td>                                                                                                       \
            <td style="padding: 0px; width: 10%">                                                                       \
              <ul class="nav navbar-nav" style="padding-left: 7%;">    \
                <li class="dropdown">                                  \
                  <a href="#" class="dropdown-toggle" data-toggle="dropdown" style="padding: 2px 2px;"><span class="fa fa-fw fa-lg fa-cog" style="color: green"></span></a>  \
                  <ul class="dropdown-menu" style="min-width: 30px;">  \
                    <button class="btn btn-primary edit-button" data-toggle="modal" data-target="#myModal">                   \
                      <i class="fa fa-fw fa-sm fa-edit" style="color: black;" graph-id={0} onclick="editModal(this)"></i>     \
                    </button>                                                                                                 \
                    <button class="btn btn-primary edit-button">                                                              \
                      <i class="fa fa-fw fa-sm fa-group" style="color: black;"></i>                                           \
                    </button>                                                                                                 \
                    <li class="divider" style="margin: auto;"></li>                                                           \
                    <button class="btn btn-primary edit-button" onclick=deleteGraph(this)>                                                             \
                      <i class="fa fa-fw fa-sm fa-times-circle" style="color: black;" ></i>                                   \
                    </button>      \
                  </ul>            \
                </li>              \
              </ul>                \
            </td>                  \
          </tr>                    \
        </table>                   \
      </div>                       \
      <div class="chart-graph" graph-id={0} style="width: 100%; overflow-x:auto; overflow-y:auto; color: #444;" type_name="none" key_name="none">   \
      </div>                       \
    </div>                         \
  </div>                           \
</div>';

// the head row of a table
var th_template = '                  \
<div class="btn-group">              \
  <button type="button" class="btn btn-xs dropdown-toggle btn-success" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false" style="padding: 0px 0px;">  \
    {0} <span class="caret"></span>  \
  </button>                          \
  <ul class="dropdown-menu">         \
    <li style="width: 50px;"><input type="checkbox" onclick="markXy(this, 1)" style="margin-left: 15px;">   x</li> \
    <li style="width: 50px;"><input type="checkbox" onclick="markXy(this, 0)" style="margin-left: 15px;">   y</li> \
  </ul>                              \
</div>'

// setting dropdown for ACTIVE dashboards (archive + hard delete)
var active_setting_template = '       \
<ul class="nav navbar-nav">    \
  <li class="dropdown">        \
    <a href="#" class="dropdown-toggle" data-toggle="dropdown" style="padding: 2px 2px;"><span class="fa fa-fw fa-lg fa-cog" style="color: green"></span></a>  \
    <ul class="dropdown-menu" style="min-width: 120px;">                              \
      <li onclick="archiveDash({0})"><a href="#"><span class="fa fa-fw fa-sm fa-archive action-archive"></span> Archive</a></li> \
      <li class="divider" style="margin: auto;"></li>                                \
      <li onclick="hardDeleteDash({0})"><a href="#"><span class="fa fa-fw fa-sm fa-times-circle action-delete"></span> Delete</a></li> \
    </ul>  \
  </li>    \
</ul>'

// setting dropdown for ARCHIVED dashboards (restore + hard delete)
var archived_setting_template = '       \
<ul class="nav navbar-nav">    \
  <li class="dropdown">        \
    <a href="#" class="dropdown-toggle" data-toggle="dropdown" style="padding: 2px 2px;"><span class="fa fa-fw fa-lg fa-cog" style="color: #999"></span></a>  \
    <ul class="dropdown-menu" style="min-width: 140px;">                              \
      <li onclick="restoreDash({0})"><a href="#"><span class="fa fa-fw fa-sm fa-undo action-restore"></span> Restore</a></li> \
      <li class="divider" style="margin: auto;"></li>                                \
      <li onclick="hardDeleteDash({0})"><a href="#"><span class="fa fa-fw fa-sm fa-times-circle action-delete"></span> Delete Permanently</a></li> \
    </ul>  \
  </li>    \
</ul>'

// legacy alias for backward compatibility
var setting_template = active_setting_template;

function deleteGraph(obj) {
    var grid = $('.grid-stack').data('gridstack');
    var current_dash = store.get(store.get("current-dash"));
    delete current_dash.grid[$(obj).parents(".grid-stack-item")[0].getAttribute("graph-id")];
    store.set(store.get("current-dash"), current_dash);
    grid.remove_widget($(obj).parents(".grid-stack-item")[0]);
    saveDash();
}


function editModal(obj){
    var tmpGraph = {"graph_id": obj.getAttribute("graph-id"), key: "", type: "", option: {"x": [], "y": []}};
    store.set("modal", tmpGraph);
    console.log(store.getAll());
}


function toggleGridMovable(obj){
    // clear any active button if set before
    $.each($("button.fa-circle-o-notch"), function(index, btn_obj){
        if (obj != btn_obj){
            btn_obj.className.includes("down") ? btn_obj.classList.remove("fa-spin") : null;
            btn_obj.className.includes("down") ? btn_obj.classList.remove("down") : null;
            btn_obj.style.color = "";
        }
    });
    // tag a new button
    $(obj).toggleClass("down");
    $('.grid-stack').data('gridstack').movable('.grid-stack-item', obj.className.includes("down"));
    $('.grid-stack').data('gridstack').resizable('.grid-stack-item', obj.className.includes("down"));
    obj.style.color = obj.className.includes("down") ? "green" : "";
    obj.className.includes("down") ? obj.classList.add("fa-spin") : obj.classList.remove("fa-spin");

    console.log("grid stack movable");
}


// re-arrange when mouse hover on the side bar
function resizeContent(direction) {
    var padding = (direction==1) ? "100px" : "0px";
    document.getElementById("main-content").style.paddingLeft = padding;
}


// initialize gridstack configure
function initGridstack(){
    var options = {
        width: 12,
        animate: true,
        vertical_margin: 5,
        resizable: {handles: "e, se, s, sw, w"},
        movable: false,
    };
    $('.grid-stack').gridstack(options);
}


// create gridstack grids according the data from server
function createGrids(){
    // clear local storage
    store.clear();

    var grid = $('.grid-stack').data('gridstack');
    var dash_id = $("meta[name=dash_id]")[0].attributes.value.value;
    var dash_content = getDash(dash_id);
    store.set(strFormat("dash-{0}", dash_id), dash_content);
    store.set("current-dash", strFormat("dash-{0}", dash_id));

    var tmp = null;
    var graph_with_key = {}

    // initialized boxes using data from server & set key_name and type_name attribute
    $("#dashboard_name")[0].value = dash_content.name;
    $.each(dash_content.grid, function(index, obj){
        tmp = grid.add_widget(strFormat(box_template, index), obj.x, obj.y, obj.width, obj.height);
        tmp[0].setAttribute("graph-id", index);
        $(tmp).find("input.input-title-level-2")[0].value = obj.graph_name;
        $(tmp).find(".chart-graph")[0].setAttribute("key_name", obj.key);
        $(tmp).find(".chart-graph")[0].setAttribute("type_name", obj.type);
        $(tmp).find(".chart-graph")[0].setAttribute("graph_id", index);
        graph_with_key[obj.id] = obj.key;
    })

    // initialized graph data
    current_dash = store.get(store.get("current-dash"));
    $.each(graph_with_key, function(index, key){
        if (key == "none"){
            console.log("no key exist");
        }else{
            $.getJSON(api_root + "key/" + key, function(data){
                store.set(key, $.parseJSON(data.data));
                console.log($(strFormat("div [graph-id={0}] .chart-graph", index)));
                initChart(current_dash.grid[index].type, index)
                console.log($.parseJSON(data.data));
            })
            // $.ajax({
            //     url: api_root + "key/" + key,
            //     method: "GET",
            //     dataType: "JSONP",
            //     contentType: "application/json",
            //     async: false,
            // })
            // .success(function(data){
            //     store.set(key, $.parseJSON(data.data));
            //     initChart(current_dash.grid[index].type, index)
            //     console.log($.parseJSON(data.data));
            // })
        }
    })

    // make it unmovable after init
    $('.grid-stack').data('gridstack').movable('.grid-stack-item', false);
    $('.grid-stack').data('gridstack').resizable('.grid-stack-item', false);
}

// get all the keys from server
function registerKeysFunc(){
    $("[data-target]").on("click", function(){
        var keys_select = $("#keys");
        keys_select.empty();

        // var url = "http://127.0.0.1:9090/keys";
        var url = api_root + "keys";
        $.getJSON(url, function(data){
            $.each(data.data, function(index, value){
                keys_select.append("<option>" + value + "</option>")
            })
        });
    })
}

// get the value for a key and parse it as a table by default
function getValue(){
    $("#keys").on("change", function(){
        var selectDOM = $("#keys")[0];
        var key = selectDOM.options[selectDOM.selectedIndex].text;
        var modal = store.get("modal");
        // var url = "http://127.0.0.1:9090/key/" + key;
        var url = api_root + "key/" + key;

        $.getJSON(url, function(data){
            var jsonData = $.parseJSON(data.data);
            store.set(key, jsonData);
            modal.key = key;
            modal.type = "table";      // default graph type
            store.set("modal", modal);
            drawChartIntoModal("table");
        })

        // change the btn-chart, table button default as clicked
        $(".btn-chart")[0].classList.add("active");
    });
}


function genElement(type){
    var element = document.createElement(type);
    if (type == "td"){
        element.setAttribute("nowrap", "nowrap");
    }
    return element;
}


function markXy(obj, xy){
    var btn_type = xy ? 'btn-info' : 'btn-warning';
    var axesName = obj.parentElement.parentElement.parentElement.children[0].innerText.trim();
    var modalData = store.get("modal");
    // change hightlight colour
    if (obj.checked){
        var node = obj.parentElement.parentElement.parentElement.children[0];
        node.classList.remove('btn-success');
        node.classList.add(btn_type);
        // push axes info
        modalData.option[xy ? "x" : "y"].push(axesName);
    }else{
        var node = obj.parentElement.parentElement.parentElement.children[0];
        node.classList.remove(btn_type);
        node.classList.add('btn-success');
        // remove axes info
        modalData.option[xy ? "x" : "y"] = $.grep(modalData.option[xy ? "x" : "y"], function(value){return value != axesName});
    }
    store.set("modal", modalData);
    console.log(store.get("modal"));
}


function parseTable(data, selector){
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


function saveGraph(){
    var modalData = store.get("modal");
    var current_dash = store.get(store.get("current-dash"));
    drawChartIntoGrid(modalData.type, modalData.graph_id);
    current_dash.grid[modalData.graph_id].key = modalData.key;
    current_dash.grid[modalData.graph_id].type = modalData.type;
    current_dash.grid[modalData.graph_id].option = modalData.option;
    store.set(store.get("current-dash"), current_dash);
}


function saveDash(){
    var dash = store.get(store.get("current-dash"));

    // dash name
    var dashName = $("#dashboard_name")[0].value; // must need
    if (100 < dashName.length || dashName.length < 4) {
        alert("dashboard name note valid, digits should between 4 and 100, thanks.")
        return null;
    }
    dash.name = dashName;

    // dash data
    var res = _.map($('.grid-stack .grid-stack-item:visible'), function (el) {
        el = $(el);
        var node = el.data('_gridstack_node');
        var name = el.find("input.input-title-level-2")[0].value;
        var key = dash.grid[el[0].getAttribute("graph-id")].key;
        var type = dash.grid[el[0].getAttribute("graph-id")].type;
        var option = dash.grid[el[0].getAttribute("graph-id")].option;
        var grid = {
            id: el.attr("graph-id"),
            x: node.x,
            y: node.y,
            option: option,
            width: node.width,
            height: node.height,
            key: (key) ? key : "none",
            type: (type) ? type : "none",
            graph_name: (name) ? name : "hi, give me a name ^_^",
        };
        dash.grid[el[0].getAttribute("graph-id")] = grid;
        return grid;
    });

    store.set(store.get("current-dash"), dash);
    var resJson = JSON.stringify(dash);
    // var url = "http://127.0.0.1:9090/data/dash/" + dash.id;
    var url = api_root + "data/dash/" + dash.id;
    var method = "PUT";

    $.ajax({
        url: url,
        data: resJson,
        method: method,
        contentType: "application/json"
    })
    .done(function(){console.log("ajax done")})
    .fail(function(){console.log("ajax fail")})
    .success(function(data){
        console.log("ajax success");
        console.log(data);
    })
    .complete(function(){console.log("ajax complete")})
    .always(function(){console.log("ajax always")})
    ;
}


function getDash(dash_id){
    // var url = "http://127.0.0.1:9090/data/dash/" + dash_id;
    var url = api_root + "data/dash/" + dash_id;
    var resJson = $.ajax({
        url: url,
        method: "GET",
        contentType: "application/json",
        async: false,
    })
    .done(function(data){console.log("ajax done");})
    .fail(function(){console.log("ajax fail")})
    .success(function(data){
        console.log("ajax success");
        console.log(data);
        return data;
    })
    .complete(function(){console.log("ajax complete")})
    .always(function(){console.log("ajax always")});

    return resJson.responseJSON.data;
}


function getDashList(status){
    status = status || 'active';
    var url = api_root + "data/dashes/?status=" + status;
    var resJson = $.ajax({
        url: url,
        method: "GET",
        contentType: "application/json",
        async: false,
    })
    .done(function(data){console.log("ajax done");})
    .fail(function(){console.log("ajax fail")})
    .success(function(data){
        console.log("ajax success");
        console.log(data);
        return data;
    })
    .complete(function(){console.log("ajax complete")})
    .always(function(){console.log("ajax always")});

    return resJson.responseJSON.data;
}


// =============================================
// Archive feature: tab state and request guard
// =============================================
var currentView = 'active';
var _archiveRequestInFlight = {};

function switchView(view) {
    currentView = view;
    // Update tab active state
    $("#dash-tabs li").removeClass("active");
    $("#tab-" + view).addClass("active");
    loadDashList(view);
}


function showEmptyState(message) {
    $("#empty-state-text").text(message);
    $("#empty-state").show();
    $("#my").hide();
}


function hideEmptyState() {
    $("#empty-state").hide();
    $("#my").show();
}


function updateBadgeCounts() {
    // Fetch both lists to get accurate counts
    var activeList = getDashList('active');
    var archivedList = getDashList('archived');

    var activeCount = activeList ? activeList.length : 0;
    var archivedCount = archivedList ? archivedList.length : 0;

    $("#badge-active").text(activeCount);
    $("#badge-archived").text(archivedCount);

    // Style badges
    $("#badge-active").toggleClass("badge-zero", activeCount === 0);
    $("#badge-archived").toggleClass("badge-zero", archivedCount === 0);
}


function loadDashList(status) {
    var list = getDashList(status);
    var tbody = $("#dash_list")[0];
    var url = api_root + "dash/";

    // Clear existing rows
    tbody.innerHTML = "";

    // Choose the correct action template
    var actionTemplate = (status === 'archived') ? archived_setting_template : active_setting_template;

    // Handle empty state
    if (!list || list.length === 0) {
        if (status === 'archived') {
            showEmptyState("No archived dashboards.");
        } else {
            showEmptyState("No active dashboards. Create one with the Add button above.");
        }
        updateBadgeCounts();
        return;
    }

    hideEmptyState();

    $.each(list, function(index, obj){
        var a = genElement("a");
        var i = genElement("i");
        var tr = genElement("tr");
        var name = genElement("td");
        var author = genElement("td");
        var time = genElement("td");
        var action = genElement("td");
        a.innerText = obj.name;
        a.setAttribute("href", url + obj.id);
        name.appendChild(a);
        name.setAttribute("data-field", "name");
        author.innerText = obj.author;
        time.innerText = moment(parseInt(obj.time_modified) * 1000).format("YYYY-MM-DD HH:mm:ss");
        i.className = "fa fa-fw fa-lg fa-cog";
        action.innerHTML = strFormat(actionTemplate, obj.id);

        // Add archived styling
        if (obj.is_archived) {
            tr.className = "archived-row";
        }

        tr.appendChild(name);
        tr.appendChild(author);
        tr.appendChild(time);
        tr.appendChild(action);
        tbody.appendChild(tr);
    });

    updateBadgeCounts();

    // Re-init tablesorter on the refreshed table
    try {
        $("#my").trigger("update");
    } catch(e) {
        // tablesorter may not be initialized yet on first load
    }
}


// Legacy initDashList - now just loads the active view
function initDashList(){
    loadDashList('active');

    $("#submit").on("click", function submit() {
        var newDash = {
            "name": $("#name")[0].value,
            "author": $("#author")[0].value,
        };
        console.log(api_root);
        $.ajax({
            method: "POST",
            dataType: "JSONP",
            data: JSON.stringify(newDash),
            contentType: "application/json",
            async: false,
        })
        .done(function(data){
            console.log("ajax done");
        })
        .fail(function(){
            console.log("ajax fail");
        })
        .success(function(data){
            console.log("ajax success");
            console.log(data);
            return data;
        })
        .complete(function(){
            console.log("ajax complete");
        })
        .always(function(){
            console.log("ajax always");
        });
    });
}


// =============================================
// Archive / Restore / Hard Delete functions
// =============================================

function archiveDash(dash_id) {
    // Prevent double-click
    if (_archiveRequestInFlight[dash_id]) return;
    _archiveRequestInFlight[dash_id] = true;

    $.ajax({
        url: api_root + "data/dash/" + dash_id + "/archive",
        method: "POST",
        contentType: "application/json",
    })
    .done(function(data){
        console.log("archive done", data);
        if (data.code === 200) {
            loadDashList(currentView);
        }
    })
    .fail(function(xhr){
        console.log("archive fail", xhr);
        var msg = "Archive failed";
        try {
            var resp = xhr.responseJSON;
            if (resp && resp.message) msg = resp.message;
        } catch(e) {}
        my_alert(msg, true);
    })
    .always(function(){
        delete _archiveRequestInFlight[dash_id];
    });
}


function restoreDash(dash_id) {
    if (_archiveRequestInFlight[dash_id]) return;
    _archiveRequestInFlight[dash_id] = true;

    $.ajax({
        url: api_root + "data/dash/" + dash_id + "/archive",
        method: "PUT",
        contentType: "application/json",
    })
    .done(function(data){
        console.log("restore done", data);
        if (data.code === 200) {
            loadDashList(currentView);
        }
    })
    .fail(function(xhr){
        console.log("restore fail", xhr);
        var msg = "Restore failed";
        try {
            var resp = xhr.responseJSON;
            if (resp && resp.message) msg = resp.message;
        } catch(e) {}
        my_alert(msg, true);
    })
    .always(function(){
        delete _archiveRequestInFlight[dash_id];
    });
}


function hardDeleteDash(dash_id) {
    if (!confirm("This will PERMANENTLY delete this dashboard. This cannot be undone. Continue?")) {
        return;
    }
    if (_archiveRequestInFlight[dash_id]) return;
    _archiveRequestInFlight[dash_id] = true;

    $.ajax({
        url: api_root + "data/dash/" + dash_id + "/archive",
        method: "DELETE",
        contentType: "application/json",
    })
    .done(function(data){
        console.log("hard delete done", data);
        if (data.code === 200) {
            loadDashList(currentView);
        }
    })
    .fail(function(xhr){
        console.log("hard delete fail", xhr);
        my_alert("Delete failed, please try again.", true);
    })
    .always(function(){
        delete _archiveRequestInFlight[dash_id];
    });
}


// Legacy deleteDash - now archives (backward compatible)
function deleteDash(dash_id) {
    archiveDash(dash_id);
}


// =============================================
// Detail page: check archive status
// =============================================

function checkDashStatus() {
    var dash_id = $("meta[name=dash_id]")[0].attributes.value.value;

    // Fetch the full list (status=all) to find this dash
    var allList = getDashList('all');
    if (!allList) return;

    var found = null;
    $.each(allList, function(index, obj) {
        if (String(obj.id) === String(dash_id)) {
            found = obj;
            return false; // break
        }
    });

    if (found && found.is_archived) {
        showArchivedBanner(dash_id);
    }
}


function showArchivedBanner(dash_id) {
    // Create banner if it doesn't exist
    if ($("#archived-banner").length === 0) {
        var banner = '<div id="archived-banner">' +
            '<span>This dashboard is archived. It is still viewable and editable.</span>' +
            '<button class="btn btn-sm btn-warning" onclick="restoreFromDetail(\'' + dash_id + '\')">Restore</button>' +
            '</div>';
        // Insert before the main content area
        $(".container.container-box .main").before(banner);
    }
    $("#archived-banner").show();
}


function restoreFromDetail(dash_id) {
    if (_archiveRequestInFlight[dash_id]) return;
    _archiveRequestInFlight[dash_id] = true;

    $.ajax({
        url: api_root + "data/dash/" + dash_id + "/archive",
        method: "PUT",
        contentType: "application/json",
    })
    .done(function(data){
        console.log("restore from detail done", data);
        if (data.code === 200) {
            $("#archived-banner").fadeOut(300);
            my_alert("Dashboard restored successfully!");
        }
    })
    .fail(function(xhr){
        console.log("restore from detail fail", xhr);
        my_alert("Restore failed, please try again.", true);
    })
    .always(function(){
        delete _archiveRequestInFlight[dash_id];
    });
}

/*
{
graph_name: "graph name 2",
height: 5,
id: "2",
key: "none",
option: {},
type: "none",
width: 6,
x: 6,
y: 0
}
*/
function addBox(){

    var grid = $('.grid-stack').data('gridstack');
    var new_box = grid.add_widget(box_template, 200, 200, 6, 5, true);
    registerKeysFunc();

    var current_dash = store.get(store.get("current-dash"));
    var new_graph_id = Object.keys(current_dash.grid).length;
    var new_graph_name = strFormat("graph name {0}", new_graph_id);
    new_box[0].setAttribute("graph-id", new_graph_id);
    new_box.find("input.input-title-level-2")[0].value = new_graph_name;
    var new_graph_data = {
        "id": new_graph_id, "key": "none", "type": "none", "option": {"x": [], "y": []},
        "x": new_box[0].getAttribute("data-gs-x"), "y": new_box[0].getAttribute("data-gs-y"),
        "width": new_box[0].getAttribute("data-gs-width"), "height": new_box[0].getAttribute("data-gs-height"),
        "graph_name": new_graph_name
    };
    current_dash.grid[new_graph_id] = new_graph_data;
    store.set(store.get("current-dash"), current_dash);
    console.log("add a new grid box : ", new_graph_data);
}


function strFormat(theString){
    // The string containing the format items (e.g. "{0}")

    for (var i = 1; i < arguments.length; i++) {
        // "gm" = RegEx options for Global search (more than one instance)
        // and for Multiline search
        var regEx = new RegExp("\\{" + (i - 1) + "\\}", "gm");
        theString = theString.replace(regEx, arguments[i]);
    }
    return theString;
}


function my_alert(msg, error){
    var background_color = error ? 'orangered' : 'cadetblue';
	scrollBy(0, -1000);
    $("#error")[0].style.backgroundColor = background_color;
    $("#error_msg")[0].innerText = msg;
	$("#error").fadeIn(3000);
	$("#error").fadeOut(3000);
}

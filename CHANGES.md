
- V 0.1.7 : sql-execution-workflow

    - SQL Editor
        + Fixed `run first` / `run last` buttons — now properly split SQL by semicolons and execute the first or last non-empty statement
        + Added input validation: empty editor, blank selection, and invalid statements now produce clear warnings instead of silent failures
        + Added structured error handling: MySQL errors, network failures, and empty results all display informative messages in the status bar
        + Added execution metadata: status bar shows execution mode, elapsed time, and row count/affected rows
        + Fixed write-operation support: INSERT/UPDATE/DELETE now commit and report affected row count
        + Fixed `SQL.get_conn()` scoping bug (reconnect now uses stored connection params)
        + Added tooltips to toolbar buttons explaining each execution mode
        + Added `split_statements()` utility for semicolon-based statement parsing
        + Added comprehensive test suite (`testSqlExecution.py`) covering all execution modes and edge cases
        + Updated README with SQL execution mode documentation

- V 0.1.4 : sql-ui-optimize

    - Dashboard
        + create 1 example
        + hover tips
        + unified message display
        + make the redis-server/dash-server configurable

    - SQL Editor
        + sql editor web UI.

- V 0.1.3 : basic-curd-docs

    - Dashboard
        + restructure code for future develop
        + more docs and tutorial
        + basic curd operations
        + gh-pages done
        + publish on readthedoc


- V 0.1.2 : visualiza-table
    - slogan: ***Inspired by IPython, built with love***

    - Dashboard
        + document and doc string
        + usage
        + simple visualize table data

    - SQL Editor
        + research & preparation


- V 0.1.1 : dashboard-server : [ current stable release ]
    - Dashboard
        - dashboard home page
            + sort by dashboard name / creator / last update time

        - dashboard page
            + add graph in a dashboard
            + re-arrange graph
            + resize graph
            + get table view in a graph

    - SQL Editor


- V 0.1 : dashboard-template
    + Add dashboard client template
    + Template consists of box, each box is an independent front-side object
    + Template hierarchy:
        + box page [add, delete, share one or all]
        + box graph [add, delete, share one or all]
        + rename

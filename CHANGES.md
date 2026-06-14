
- V 0.1.7 : archive-restore

    - Dashboard
        + archive (soft delete) dashboards - reversible, data stays in Redis
        + restore archived dashboards - preserves all content and metadata
        + hard delete (permanent) with confirmation dialog
        + homepage tabs: Active / Archived views with badge counts
        + detail page shows archived banner with restore button
        + empty state messages for both tabs
        + double-click protection for archive/restore/delete operations
        + direct URL access to archived dashboards works with status banner
        + backward compatible: existing data works without migration

    - API
        + POST /data/dash/<id>/archive - archive a dashboard
        + PUT /data/dash/<id>/archive - restore a dashboard
        + DELETE /data/dash/<id>/archive - hard delete permanently
        + GET /data/dashes/?status=active|archived|all - filtered list with is_archived flag

    - Documentation
        + archive feature documentation (docs/archive-feature.md)
        + integration tests for archive/restore/hard-delete flows

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

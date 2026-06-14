from . import routes

NAV_ITEMS: list[dict] = [
    {
        "label": "Home",
        "icon": "home",
        "route": routes.HOME_ROUTE,
        # "sub_items": [
        #     {"label": "Welcome", "icon": "hand", "route": routes.HOME_ROUTE},
        #     {"label": "Getting started", "icon": "fast-forward", "route": routes.GETTING_STARTED_ROUTE},
        # ],
    },
    {
        "label": "Auth req 1",
        "icon": "route",
        "route": routes.AUTH_REQUIRED_1_ROUTE,
        # "sub_items": [
        #     {"label": "Overview", "icon": "map", "route": routes.TRAJECTORY_TOOLBOX_ROUTE},
        #     {"label": "Point to point", "icon": "waypoints", "route": routes.POINT_TO_POINT_ROUTE},
        #     {"label": "Grid study", "icon": "grid-3x3", "route": routes.GRID_ROUTE},
        # ],
    },
    {
        "label": "Auth req 2",
        "icon": "circuit-board",
        "route": routes.AUTH_REQUIRED_2_ROUTE,
        # "sub_items": [
        #     {"label": "Overview", "icon": "map", "route": routes.MOTOR_TOOLBOX_ROUTE},
        #     {"label": "Components", "icon": "package", "route": routes.COMPONENTS_ROUTE},
        #     {"label": "Magnet array", "icon": "magnet", "route": routes.MAGNET_ROUTE},
        #     {"label": "Coil array", "icon": "spool", "route": routes.COIL_ROUTE},
        #     {"label": "Magnetic field", "icon": "orbit", "route": routes.MAGNETIC_FIELD_ROUTE},
        #     {"label": "Simulation setup", "icon": "settings", "route": routes.SETUP_ROUTE},
        #     {"label": "Job submission", "icon": "cloud-sync", "route": routes.JOBS_ROUTE},
        # ],
    },
    {
        "label": "About",
        "icon": "info",
        "route": routes.ABOUT_ROUTE,
        # "sub_items": [
        #     {"label": "General info", "icon": "file-text", "route": routes.ABOUT_ROUTE},
        #     {"label": "Changelog", "icon": "history", "route": routes.CHANGELOG_ROUTE},
        # ],
    },
]

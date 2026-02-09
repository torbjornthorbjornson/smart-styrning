from __future__ import annotations

import os

import pymysql


DEFAULT_MYCNF = "/home/runerova/.my.cnf"
DEFAULT_DB_NAME = "smart_styrning"


def get_connection(*, db_name: str | None = None):
    """Create a MariaDB connection using /home/runerova/.my.cnf.

    - Keeps credentials outside the repo.
    - Uses DictCursor for existing code compatibility.

    Override via env:
    - SMARTWEB_MYCNF
    - SMARTWEB_DB
    """

    mycnf = os.getenv("SMARTWEB_MYCNF", DEFAULT_MYCNF)
    database = db_name or os.getenv("SMARTWEB_DB", DEFAULT_DB_NAME)

    return pymysql.connect(
        read_default_file=mycnf,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
    )

"""Database utilities for the portfolio report app.

This module exposes a single function, ``init_db``, which returns a SQLAlchemy
engine and session factory bound to a SQLite database. The database is
located in the ``data`` directory in the root of the repository. When
``init_db`` is called, the directory is created if it does not exist.

We use a scoped session so that each request can obtain its own session
without interfering with others. The engine is created with ``future=True``
to enable SQLAlchemy 2.0 behaviour.
"""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


def init_db(database_uri: str):
    """Initialise the database engine and session factory.

    Parameters
    ----------
    database_uri: str
        The SQLAlchemy database URI. For this project we expect a SQLite
        filename prefaced with ``sqlite://``.

    Returns
    -------
    engine: sqlalchemy.engine.Engine
        The configured database engine.
    Session: sqlalchemy.orm.sessionmaker
        A sessionmaker factory bound to the engine.
    """
    # Ensure the data directory exists when using SQLite file based storage.
    if database_uri.startswith("sqlite:///"):
        db_path = database_uri.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    engine = create_engine(database_uri, future=True)
    # Use scoped_session so each request can have its own session easily.
    Session = scoped_session(sessionmaker(bind=engine))
    return engine, Session
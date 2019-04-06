"""
This module defines all the objects in the database in their relation.

``psef.models.assignment``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.assignment
    :members:
    :show-inheritance:

``psef.models.comment``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.comment
    :members:
    :show-inheritance:

``psef.models.course``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.course
    :members:
    :show-inheritance:

``psef.models.file``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.file
    :members:
    :show-inheritance:

``psef.models.group``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.group
    :members:
    :show-inheritance:

``psef.models.link_tables``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.link_tables
    :members:
    :show-inheritance:

``psef.models.linter``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.linter
    :members:
    :show-inheritance:

``psef.models.lti_provider``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.lti_provider
    :members:
    :show-inheritance:

``psef.models.permission``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.permission
    :members:
    :show-inheritance:

``psef.models.plagiarism``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.plagiarism
    :members:
    :show-inheritance:

``psef.models.role``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.role
    :members:
    :show-inheritance:

``psef.models.rubric``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.rubric
    :members:
    :show-inheritance:

``psef.models.snippet``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.snippet
    :members:
    :show-inheritance:

``psef.models.user``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.user
    :members:
    :show-inheritance:

``psef.models.work``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.work
    :members:
    :show-inheritance:

SPDX-License-Identifier: AGPL-3.0-only
"""

import os
import abc
import enum
import json
import uuid
import typing as t
import numbers
import datetime

import structlog
from flask import g
from sqlalchemy import orm, event
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import PasswordType, force_auto_coercion

from .. import PsefFlask
from ..cache import cache_within_request
from .model_types import (  # pylint: disable=unused-import
    T, MyDb, DbColumn, _MyQuery
)

logger = structlog.get_logger()

db: MyDb = t.cast(  # pylint: disable=invalid-name
    MyDb,
    SQLAlchemy(session_options={
        'autocommit': False,
        'autoflush': False
    })
)


def init_app(app: PsefFlask) -> None:
    """Initialize the database connections and set some listeners.

    :param app: The flask app to initialize for.
    :returns: Nothing
    """
    db.init_app(app)
    force_auto_coercion()

    with app.app_context():

        @event.listens_for(db.engine, "before_cursor_execute")
        def __before_cursor_execute(*_args: object) -> None:
            if hasattr(g, 'query_start'):
                g.query_start = datetime.datetime.utcnow()

        @event.listens_for(db.engine, "after_cursor_execute")
        def __after_cursor_execute(*_args: object) -> None:
            if hasattr(g, 'queries_amount'):
                g.queries_amount += 1
            if hasattr(g, 'query_start'):
                delta = (datetime.datetime.utcnow() -
                         g.query_start).total_seconds()
                if hasattr(g, 'queries_total_duration'):
                    g.queries_total_duration += delta
                if (
                    hasattr(g, 'queries_max_duration') and (
                        g.queries_max_duration is None or
                        delta > g.queries_max_duration
                    )
                ):
                    g.queries_max_duration = delta

        if app.config['_USING_SQLITE']:  # pragma: no cover

            @event.listens_for(db.engine, "connect")
            def __do_connect(dbapi_connection: t.Any, _: t.Any) -> None:
                # disable pysqlite's emitting of the BEGIN statement entirely.
                # also stops it from emitting COMMIT before any DDL.
                dbapi_connection.isolation_level = None
                dbapi_connection.execute('pragma foreign_keys=ON')

            @event.listens_for(db.engine, "begin")
            def __do_begin(conn: t.Any) -> None:
                # emit our own BEGIN
                conn.execute("BEGIN")


UUID_LENGTH = 36

if t.TYPE_CHECKING and getattr(
    t, 'SPHINX', False
) is not True:  # pragma: no cover
    from .model_types import Base, Comparator
else:
    from sqlalchemy.ext.hybrid import hybrid_property, Comparator  # type: ignore
    Base = db.Model  # type: ignore # pylint: disable=invalid-name

# Sphinx has problems with resolving types when this decorator is used, we
# simply remove it in the case of Sphinx.
if getattr(t, 'SPHINX', False) is True:  # pragma: no cover
    # pylint: disable=invalid-name
    cache_within_request = lambda x: x  # type: ignore

if True:  # pylint: disable=using-constant-test
    from .course import Course, CourseSnippet
    from .assignment import (
        Assignment, AssignmentLinter, AssignmentResult, AssignmentDoneType,
        AssignmentGraderDone, AssignmentAssignedGrader, _AssignmentStateEnum
    )
    from .permission import Permission
    from .user import User
    from .lti_provider import LTIProvider
    from .file import File, FileOwner
    from .work import Work, GradeHistory
    from .linter import LinterState, LinterComment, LinterInstance
    from .plagiarism import (
        PlagiarismState, PlagiarismRun, PlagiarismCase, PlagiarismMatch
    )
    from .comment import Comment
    from .role import AbstractRole, Role, CourseRole
    from .snippet import Snippet
    from .rubric import RubricItem, RubricRow
    from .group import GroupSet, Group
    from .link_tables import user_course

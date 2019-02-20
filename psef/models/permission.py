"""This module defines a Permission.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t

from . import Base, DbColumn, Comparator, db
from .. import helpers
from ..permissions import BasePermission, CoursePermission, GlobalPermission

_T = t.TypeVar('_T', bound=BasePermission)  # pylint: disable=invalid-name

if getattr(t, 'SPHINX', False):  # pragma: no cover:
    # Sphinx fails with this decorator for whatever reason.
    cache_within_request = lambda x: x  # pylint: disable=invalid-name
else:
    from ..cache import cache_within_request

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    hybrid_property = property  # pylint: disable=invalid-name
else:
    from sqlalchemy.ext.hybrid import hybrid_property  # type: ignore


class Permission(Base, t.Generic[_T]):  # pylint: disable=unsubscriptable-object
    """This class defines **database** permissions.

    A permission can be a global- or a course- permission. Global permissions
    describe the ability to do something general, e.g. create a course or the
    usage of snippets. These permissions are connected to a :class:`.Role`
    which is hold be a :class:`.User`. Similarly course permissions are bound
    to a :class:`.CourseRole`. These roles are assigned to users only in the
    context of a single :class:`.Course`. Thus a user can hold different
    permissions in different courses.

    .. warning::

      Think twice about using this class directly! You probably want a non
      database permission (see ``permissions.py``) which are type checked and
      WAY faster. If you need to check if a user has a certain permission use
      the :meth:`.User.has_permission` of, even better,
      :func:`psef.auth.ensure_permission` functions.

    :ivar default_value: The default value for this permission.
    :ivar course_permission: Indicates if this permission is for course
        specific actions. If this is the case a user can have this permission
        for a subset of all the courses. If ``course_permission`` is ``False``
        this permission is global for the entire site.

    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = None
    __tablename__ = 'Permission'

    id = db.Column('id', db.Integer, primary_key=True)

    __name: str = db.Column('name', db.Unicode, unique=True, index=True)

    default_value: bool  # NOQA
    default_value = db.Column('default_value', db.Boolean, default=False)
    course_permission: bool = db.Column(
        'course_permission', db.Boolean, index=True
    )

    @classmethod
    def get_name_column(cls: t.Type['Permission[T]']) -> DbColumn[str]:
        return cls.__name

    @classmethod
    def get_all_permissions(
        cls: t.Type['Permission[_T]'], perm_type: t.Type[_T]
    ) -> 't.Sequence[Permission[_T]]':
        """Get all database permissions of a certain type.

        :param perm_type: The type of permission to get.
        :returns: A list of all database permissions of the given type.
        """
        assert perm_type in (GlobalPermission, CoursePermission)
        return db.session.query(cls).filter_by(
            course_permission=perm_type == CoursePermission
        ).all()

    @classmethod
    def get_all_permissions_from_list(
        cls: t.Type['Permission[_T]'], perms: t.Sequence[_T]
    ) -> 't.Sequence[Permission[_T]]':
        """Get database permissions corresponding to a list of permissions.

        :param perms: The permissions to get the database permission of.
        :returns: A list of all requested database permission.
        """
        if not perms:  # pragma: no cover
            return []

        assert isinstance(perms[0], (GlobalPermission, CoursePermission))
        assert all(isinstance(perm, type(perms[0])) for perm in perms)

        return helpers.filter_all_or_404(
            cls,
            t.cast(DbColumn[str],
                   Permission.__name).in_(p.name for p in perms),
            Permission.course_permission == isinstance(
                perms[0], CoursePermission
            ),
        )

    @classmethod
    @cache_within_request
    def get_permission(
        cls: 't.Type[Permission[_T]]', perm: '_T'
    ) -> 'Permission[_T]':
        """Get a database permission from a permission.

        :param perm: The permission to get the database permission of.
        :returns: The correct database permission.
        """
        return helpers.filter_single_or_404(
            cls, cls.value == perm,
            cls.course_permission == isinstance(perm, CoursePermission)
        )

    @hybrid_property
    def value(self) -> '_T':
        """Get the permission value of the database permission.

        :returns: The permission of this database permission.
        """
        # This logic is correct
        if self.course_permission:
            return t.cast('_T', CoursePermission[self.__name])
        else:
            return t.cast('_T', GlobalPermission[self.__name])

    @value.comparator
    def value(cls) -> Comparator:  # pylint: disable=no-self-argument,missing-docstring
        class Comp(Comparator):  # pylint: disable=missing-docstring
            def __eq__(self, other: object) -> bool:
                if not isinstance(other, BasePermission):
                    assert False
                return self.__clause_element__() == other.name

        return Comp(t.cast(DbColumn[str], cls.__name))

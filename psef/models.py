"""
This module defines all the objects in the database in their relation.

SPDX-License-Identifier: AGPL-3.0-only
"""
# TODO: Split this file into one file per model.

import os
import abc
import enum
import json
import math
import uuid
import typing as t
import numbers
import datetime
from random import shuffle
from operator import itemgetter
from itertools import cycle
from collections import defaultdict

import structlog
from flask import g
from sqlalchemy import orm, event
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.utils import cached_property
from mypy_extensions import TypedDict
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import PasswordType, force_auto_coercion
from sqlalchemy.sql.expression import and_, func, false
from sqlalchemy.orm.collections import attribute_mapped_collection

import psef  # pylint: disable=cyclic-import

from . import current_app
from .cache import cache_within_request
from .exceptions import (
    APICodes, APIException, PermissionException, InvalidAssignmentState
)
from .model_types import (  # pylint: disable=unused-import
    T, MyDb, DbColumn, _MyQuery
)
from .permissions import (  # pylint: disable=cyclic-import
    BasePermission, CoursePermission, GlobalPermission
)

logger = structlog.get_logger()

db = t.cast(  # pylint: disable=invalid-name
    'MyDb',
    SQLAlchemy(session_options={
        'autocommit': False,
        'autoflush': False
    })
)


def init_app(app: 'psef.PsefFlask') -> None:
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
) is not True:  # pragma: no cover:
    hybrid_property = property  # pylint: disable=invalid-name
    from .model_types import Base, Comparator
else:
    from sqlalchemy.ext.hybrid import hybrid_property, Comparator
    Base = db.Model  # pylint: disable=invalid-name

# Sphinx has problems with resolving types when this decorator is used, we
# simply remove it in the case of Sphinx.
if getattr(t, 'SPHINX', False) is True:  # pragma: no cover:
    # pylint: disable=invalid-name
    cache_within_request = lambda x: x  # type: ignore
    # pylint: enable=invalid-name

permissions = db.Table(  # pylint: disable=invalid-name
    'roles-permissions',
    db.Column(
        'permission_id', db.Integer,
        db.ForeignKey('Permission.id', ondelete='CASCADE')
    ),
    db.Column(
        'role_id', db.Integer, db.ForeignKey('Role.id', ondelete='CASCADE')
    )
)

course_permissions = db.Table(  # pylint: disable=invalid-name
    'course_roles-permissions',
    db.Column(
        'permission_id', db.Integer,
        db.ForeignKey('Permission.id', ondelete='CASCADE')
    ),
    db.Column(
        'course_role_id', db.Integer,
        db.ForeignKey('Course_Role.id', ondelete='CASCADE')
    )
)

user_course = db.Table(  # pylint: disable=invalid-name
    'users-courses',
    db.Column(
        'course_id', db.Integer,
        db.ForeignKey('Course_Role.id', ondelete='CASCADE')
    ),
    db.Column(
        'user_id', db.Integer, db.ForeignKey('User.id', ondelete='CASCADE')
    )
)

work_rubric_item = db.Table(  # pylint: disable=invalid-name
    'work_rubric_item',
    db.Column(
        'work_id', db.Integer, db.ForeignKey('Work.id', ondelete='CASCADE')
    ),
    db.Column(
        'rubricitem_id', db.Integer,
        db.ForeignKey('RubricItem.id', ondelete='CASCADE')
    )
)


class LTIProvider(Base):
    """This class defines the handshake with an LTI

    :ivar key: The OAuth consumer key for this LTI provider.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['LTIProvider']]
    __tablename__ = 'LTIProvider'
    id: str = db.Column('id', db.String(UUID_LENGTH), primary_key=True)
    key: str = db.Column('key', db.Unicode, unique=True)

    def passback_grade(self, sub: 'Work', initial: bool) -> None:
        """Passback the grade for a given submission to this lti provider.

        :param sub: The submission to passback.
        :param initial: If true no grade will be send, this is to make sure the
            ``created_at`` date is correct in the LMS. Not all providers
            actually do a passback when this is set to ``True``.
        :returns: Nothing.
        """
        url = ('{}/'
               'courses/{}/assignments/{}/submissions?inLTI=true').format(
                   current_app.config['EXTERNAL_URL'],
                   sub.assignment.course_id,
                   sub.assignment_id,
               )

        self.lti_class.passback_grade(
            key=self.key,
            secret=self.secret,
            grade=sub.grade,
            initial=initial,
            service_url=sub.assignment.lti_outcome_service_url,
            sourcedid=sub.assignment.assignment_results[sub.user_id].sourcedid,
            lti_points_possible=sub.assignment.lti_points_possible,
            submission=sub,
            url=url,
        )

    @property
    def lti_class(self) -> t.Type['psef.lti.LTI']:
        """This is the name of the provider.

        .. note::

            Currently this is hard coded to :class`.psef.lti.CanvasLTI` but
            could be extended to provide support for more additional LMS'ses
        """
        return psef.lti.CanvasLTI

    def __init__(self, key: str) -> None:
        super().__init__(key=key)
        public_id = str(uuid.uuid4())

        while db.session.query(
            LTIProvider.query.filter_by(id=public_id).exists()
        ).scalar():  # pragma: no cover
            public_id = str(uuid.uuid4())

        self.id = public_id

    @property
    def secret(self) -> str:
        """The OAuth consumer secret for this LTIProvider.

        :getter: Get the OAuth secret.
        :setter: Impossible as all secrets are fixed during startup of
            codegra.de
        """
        return current_app.config['LTI_CONSUMER_KEY_SECRETS'][self.key]


class AssignmentAssignedGrader(Base):
    """The class creates the link between an :class:`User` and an
    :class:`Assignment`.

    The user linked to the assignment is an assigned grader. In this link the
    weight is the weight this user was given when assigning.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AssignmentAssignedGrader']]
        query = Base.query
    __tablename__ = 'AssignmentAssignedGrader'
    weight: float = db.Column('weight', db.Float, nullable=False)
    user_id: int = db.Column(
        'User_id', db.Integer, db.ForeignKey('User.id', ondelete='CASCADE')
    )
    assignment_id: int = db.Column(
        'Assignment_id', db.Integer,
        db.ForeignKey('Assignment.id', ondelete='CASCADE')
    )

    __table_args__ = (db.PrimaryKeyConstraint(assignment_id, user_id), )


class AssignmentGraderDone(Base):
    """This class creates the link between an :class:`User` and an
    :class:`Assignment` that exists only when the grader is done.

    If a user is linked to the assignment this indicates that this user is done
    with grading.

    :ivar user_id: The id of the user that is linked.
    :ivar ~.AssignmentGraderDone.assignment_id: The id of the assignment that
        is linked.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AssignmentGraderDone']]
        query = Base.query
    __tablename__ = 'AssignmentGraderDone'
    user_id: int = db.Column(
        'User_id', db.Integer, db.ForeignKey('User.id', ondelete='CASCADE')
    )
    assignment_id: int = db.Column(
        'Assignment_id', db.Integer,
        db.ForeignKey('Assignment.id', ondelete='CASCADE')
    )

    __table_args__ = (db.PrimaryKeyConstraint(assignment_id, user_id), )


class AssignmentResult(Base):
    """The class creates the link between an :class:`User` and an
    :class:`Assignment` in the database and the external users LIS sourcedid.

    :ivar sourcedid: The ``sourcedid`` for this user for this assignment.
    :ivar ~.AssignmentResult.user_id: The id of the user this belongs to.
    :ivar ~.AssignmentResult.assignment_id: The id of the assignment this
        belongs to.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['AssignmentResult']]
    __tablename__ = 'AssignmentResult'
    sourcedid: str = db.Column('sourcedid', db.Unicode)
    user_id: int = db.Column(
        'User_id', db.Integer, db.ForeignKey('User.id', ondelete='CASCADE')
    )
    assignment_id: int = db.Column(
        'Assignment_id', db.Integer,
        db.ForeignKey('Assignment.id', ondelete='CASCADE')
    )

    __table_args__ = (db.PrimaryKeyConstraint(assignment_id, user_id), )


_T = t.TypeVar('_T', bound=BasePermission)  # pylint: disable=invalid-name


class Permission(Base, t.Generic[_T]):  # pylint: disable=unsubscriptable-object
    """This class defines **database** permissions.

    A permission can be a global- or a course- permission. Global permissions
    describe the ability to do something general, e.g. create a course or the
    usage of snippets. These permissions are connected to a :class:`Role` which
    is hold be a :class:`User`. Similarly course permissions are bound to a
    :class:`CourseRole`. These roles are assigned to users only in the context
    of a single :class:`Course`. Thus a user can hold different permissions in
    different courses.

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

        return psef.helpers.filter_all_or_404(
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
        return psef.helpers.filter_single_or_404(
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


class AbstractRole(t.Generic[_T]):
    """An abstract class that implements all functionality a role should have.
    """

    def __init__(
        self,
        name: str,
        _permissions: t.MutableMapping['_T', Permission['_T']] = None
    ) -> None:
        self.name = name
        if _permissions is not None:
            self._permissions = _permissions

    @property
    @abc.abstractmethod
    def id(self) -> int:
        """The id of this role.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """The name of this role.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def _permissions(self) -> t.MutableMapping['_T', Permission['_T']]:
        """The permissions this role has a connection to.

        A connection means this role has the permission if, and only if, the
        ``default_value`` of this permission is ``False``.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def uses_course_permissions(self) -> bool:
        """Does this role use course permissions or global permissions.
        """
        raise NotImplementedError

    def set_permission(self, perm: '_T', should_have: bool) -> None:
        """Set the given :class:`Permission` to the given value.

        :param should_have: If this role should have this permission
        :param perm: The permission this role should (not) have
        """
        if self.uses_course_permissions:
            assert isinstance(perm, CoursePermission)
        else:
            assert isinstance(perm, GlobalPermission)

        permission = Permission.get_permission(perm)

        if permission.default_value ^ should_have:
            self._permissions[perm] = permission
        else:
            try:
                del self._permissions[perm]
            except KeyError:
                pass

    def has_permission(self, permission: '_T') -> bool:
        """Check whether this course role has the specified
        :class:`Permission`.

        :param permission: The permission or permission name
        :returns: True if the course role has the permission
        """
        if self.uses_course_permissions:
            assert isinstance(permission, CoursePermission)
        else:
            assert isinstance(permission, GlobalPermission)

        if permission in self._permissions:
            return not self._permissions[permission].default_value
        else:
            if current_app.do_sanity_checks:
                found_perm = Permission.get_permission(permission)
                assert (
                    found_perm.default_value == permission.value.default_value
                ), "Wrong permission in database"

            return permission.value.default_value

    def get_all_permissions(self) -> t.Mapping['_T', bool]:
        """Get all course :class:`permissions` for this course role.

        :returns: A name boolean mapping where the name is the name of the
                  permission and the value indicates if this user has this
                  permission.
        """
        perms: t.List[Permission['_T']]
        perms = db.session.query(Permission).filter_by(
            course_permission=self.uses_course_permissions,
        ).all()
        return {
            p.value: (p.value in self._permissions) ^ p.default_value
            for p in perms
        }

    def __to_json__(self) -> t.MutableMapping[str, t.Any]:
        """Creates a JSON serializable representation of a role.

        This object will look like this:

        .. code:: python

            {
                'id':    int, # The id of this role.
                'name':  str, # The name of this role.
            }

        :returns: An object as described above.
        """
        return {
            'name': self.name,
            'id': self.id,
        }


class CourseRole(AbstractRole[CoursePermission], Base):
    """
    A course role is used to describe the abilities of a :class:`User` in a
    :class:`Course`.

    :ivar name: The name of this role in the course.
    :ivar ~.CourseRole.course_id: The :py:class:`Course` this role belongs to.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['CourseRole']]
    __tablename__ = 'Course_Role'
    id = db.Column('id', db.Integer, primary_key=True)
    name: str = db.Column('name', db.Unicode)
    course_id: int = db.Column(
        'Course_id', db.Integer, db.ForeignKey('Course.id')
    )
    _permissions: t.MutableMapping[
        CoursePermission, Permission[CoursePermission]] = db.relationship(
            'Permission',
            collection_class=attribute_mapped_collection('value'),
            secondary=course_permissions
        )

    # Old syntax used to please sphinx
    course = db.relationship(
        'Course', foreign_keys=course_id, backref="roles"
    )  # type: Course

    @property
    def uses_course_permissions(self) -> bool:
        return True

    def __init__(
        self,
        name: str,
        course: 'Course',
        _permissions: t.Optional[t.MutableMapping[CoursePermission, Permission]
                                 ] = None,
    ) -> None:
        if _permissions:
            assert all(
                isinstance(p, CoursePermission) for p in _permissions.keys()
            )
        super().__init__(name=name, _permissions=_permissions)

        # Mypy doesn't get the sqlalchemy magic
        self.course = course  # type: ignore

    def __to_json__(self) -> t.MutableMapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.
        """
        res = super().__to_json__()
        res['course'] = self.course
        return res

    @classmethod
    def get_initial_course_role(cls: t.Type['CourseRole'],
                                course: 'Course') -> 'CourseRole':
        """Get the initial course role for a given course.

        :param course: The course to get the initial role for.
        :returns: A course role that should be the role for the user creating
            the course.
        """
        for name, value in current_app.config['_DEFAULT_COURSE_ROLES'].items():
            if value['initial_role']:
                return cls.query.filter_by(name=name, course=course).one()
        raise ValueError('No initial course role found')

    @staticmethod
    def get_default_course_roles() -> t.Mapping[
        str, t.MutableMapping[CoursePermission, Permission[CoursePermission]]]:
        """Get all default course roles as specified in the config and their
        permissions (:class:`Permission`).


        .. code:: python

            {
                'student': {
                    'can_edit_assignment_info': <Permission-object>,
                    'can_submit_own_work': <Permission-object>
                }
            }

        :returns: A name dict mapping where the name is the name of the
            course-role and the dict is name permission mapping between the
            name of a permission and the permission object. See above for an
            example.
        """
        res = {}
        for name, value in current_app.config['_DEFAULT_COURSE_ROLES'].items():
            perms = Permission.get_all_permissions(CoursePermission)
            r_perms = {}
            perms_set = set(value['permissions'])
            for perm in perms:
                if bool(perm.default_value
                        ) ^ bool(perm.value.name in perms_set):
                    r_perms[perm.value] = perm

            res[name] = r_perms
        return res


class Role(AbstractRole[GlobalPermission], Base):
    """A role defines the set of global permissions :class:`Permission` of a
    :class:`User`.

    :ivar name: The name of the global role.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['Role']]
    __tablename__ = 'Role'
    id: int = db.Column('id', db.Integer, primary_key=True)
    name: str = db.Column('name', db.Unicode, unique=True)
    _permissions: t.MutableMapping[
        GlobalPermission, Permission[GlobalPermission]] = db.relationship(
            'Permission',
            collection_class=attribute_mapped_collection('value'),
            secondary=permissions,
            backref=db.backref('roles', lazy='dynamic')
        )

    @property
    def uses_course_permissions(self) -> bool:
        return False


class User(Base):
    """This class describes a user of the system.

    :ivar lti_user_id: The id of this user in a LTI consumer.
    :ivar name: The name of this user.
    :ivar role_id: The id of the role this user has.
    :ivar courses: A mapping between course_id and course-role for all courses
        this user is currently enrolled.
    :ivar email: The e-mail of this user.
    :ivar virtual: Is this user an actual user of the site, or is it a virtual
        user.
    :ivar password: The password of this user, it is automatically hashed.
    :ivar assignment_results: The way this user can do LTI grade passback.
    :ivar assignments_assigned: A mapping between assignment_ids and
        :py:class:`AssignmentAssignedGrader` objects.
    :ivar reset_email_on_lti: Determines if the email should be reset on the
        next LTI launch.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['User']]

    # Python 3 implicitly set __hash__ to None if we override __eq__
    # We set it back to its default implementation
    __hash__ = object.__hash__
    __tablename__ = "User"

    id: int = db.Column('id', db.Integer, primary_key=True)

    # All stuff for LTI
    lti_user_id: str = db.Column(db.Unicode, unique=True)

    name: str = db.Column('name', db.Unicode)
    active: bool = db.Column('active', db.Boolean, default=True)
    virtual = db.Column(
        'virtual', db.Boolean, default=False, nullable=False, index=True
    )
    role_id: int = db.Column('Role_id', db.Integer, db.ForeignKey('Role.id'))
    courses: t.MutableMapping[int, CourseRole] = db.relationship(
        'CourseRole',
        collection_class=attribute_mapped_collection('course_id'),
        secondary=user_course,
        backref=db.backref('users', lazy='dynamic')
    )
    username: str = db.Column(
        'username',
        db.Unicode,
        unique=True,
        nullable=False,
        index=True,
    )

    reset_token: t.Optional[str] = db.Column(
        'reset_token', db.String(UUID_LENGTH), nullable=True
    )
    reset_email_on_lti = db.Column(
        'reset_email_on_lti',
        db.Boolean,
        server_default=false(),
        default=False,
        nullable=False,
    )

    email: str = db.Column('email', db.Unicode, unique=False, nullable=False)
    password: str = db.Column(
        'password',
        PasswordType(schemes=[
            'pbkdf2_sha512',
        ], deprecated=[]),
        nullable=True
    )

    assignments_assigned: t.MutableMapping[
        int, AssignmentAssignedGrader] = db.relationship(
            'AssignmentAssignedGrader',
            collection_class=attribute_mapped_collection('assignment_id'),
            backref=db.backref('user', lazy='select')
        )

    assignment_results: t.MutableMapping[
        int, AssignmentResult] = db.relationship(
            'AssignmentResult',
            collection_class=attribute_mapped_collection('assignment_id'),
            backref=db.backref('user', lazy='select')
        )

    role: Role = db.relationship('Role', foreign_keys=role_id, lazy='select')

    def __eq__(self, other: t.Any) -> bool:  # pragma: no cover
        return isinstance(other, User) and self.id == other.id

    def __ne__(self, other: t.Any) -> bool:  # pragma: no cover
        return not self.__eq__(other)

    @classmethod
    def create_virtual_user(cls: t.Type['User'], name: str) -> 'User':
        """Create a virtual user with the given name.

        :return: A newly created virtual user with the given name prepended
            with 'Virtual - ' and a random username.
        """
        return cls(
            name=f'Virtual - {name}',
            username=f'VIRTUAL_USER__{uuid.uuid4()}',
            virtual=True,
            email=''
        )

    @t.overload
    def has_permission(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self, permission: CoursePermission, course_id: t.Union[int, 'Course']
    ) -> bool:
        ...  # pylint: disable=pointless-statement

    @t.overload
    def has_permission(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self,
        permission: GlobalPermission,
    ) -> bool:
        ...  # pylint: disable=pointless-statement

    def has_permission(  # pylint: disable=function-redefined
        self,
        permission: t.Union[GlobalPermission, CoursePermission],
        course_id: t.Union['Course', int, None] = None
    ) -> bool:
        """Check whether this user has the specified global or course
        :class:`Permission`.

        To check a course permission the course_id has to be set.

        :param permission: The permission or permission name
        :param course_id: The course or course id
        :returns: Whether the role has the permission or not

        :raises KeyError: If the permission parameter is a string and no
                         permission with this name exists.
        """
        if not self.active or self.virtual:
            return False

        if course_id is None:
            assert isinstance(permission, GlobalPermission)
            return self.role.has_permission(permission)
        else:
            assert isinstance(permission, CoursePermission)

            if isinstance(course_id, Course):
                course_id = course_id.id

            if course_id in self.courses:
                return self.courses[course_id].has_permission(permission)
            return False

    def get_permissions_in_courses(
        self,
        wanted_perms: t.Sequence[CoursePermission],
    ) -> t.Mapping[int, t.Mapping[CoursePermission, bool]]:
        """Check for specific :class:`Permission`s in all courses
        (:class:`Course`) the user is enrolled in.

        Please note that passing an empty ``perms`` object is
        supported. However the resulting mapping will be empty.

        >>> User().get_permissions_in_courses([])
        {}

        :param wanted_perms: The permissions names to check for.
        :returns: A mapping where the first keys indicate the course id,
            the values at this are a mapping between the given permission names
            and a boolean indicating if the current user has this permission
            for the course with this course id.
        """
        assert not self.virtual

        if not wanted_perms:
            return {}

        perms: t.Sequence[Permission[CoursePermission]]
        perms = Permission.get_all_permissions_from_list(wanted_perms)

        course_roles = db.session.query(
            user_course.c.course_id
        ).join(User, User.id == user_course.c.user_id).filter(
            User.id == self.id
        ).subquery('course_roles')

        crp = db.session.query(
            course_permissions.c.course_role_id,
            t.cast(DbColumn[int], Permission.id),
        ).join(
            Permission,
            course_permissions.c.permission_id == Permission.id,
        ).filter(
            t.cast(DbColumn[int], Permission.id).in_(p.id for p in perms)
        ).subquery('crp')

        res: t.Sequence[t.Tuple[int, int]]
        res = db.session.query(course_roles.c.course_id, crp.c.id).join(
            crp,
            course_roles.c.course_id == crp.c.course_role_id,
            isouter=False,
        ).all()

        lookup: t.Mapping[int, t.Set[int]] = defaultdict(set)
        for course_role_id, permission_id in res:
            lookup[permission_id].add(course_role_id)

        out: t.MutableMapping[int, t.Mapping[CoursePermission, bool]] = {}
        for course_id, course_role in self.courses.items():
            out[course_id] = {
                p.value: (course_role.id in lookup[p.id]) != p.default_value
                for p in perms
            }

        return out

    @property
    def can_see_hidden(self) -> bool:
        """Can the user see hidden assignments.
        """
        return self.has_course_permission_once(
            CoursePermission.can_see_hidden_assignments
        )

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'id':    int, # The id of this user.
                'name':  str, # The full name of this user.
                'email': str, # The email of this user.
                'username': str, # The username of this user.
            }

        :returns: An object as described above.
        """
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'username': self.username,
        }

    def __extended_to_json__(self) -> t.Mapping[str, t.Any]:
        """Create a extended JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'hidden': bool, # indicating if this user can once
                                # see hidden assignments.
                **self.__to_json__()
            }

        :returns: A object as described above.
        """
        return {
            "hidden": self.can_see_hidden,
            **self.__to_json__(),
        }

    def has_course_permission_once(self, perm: CoursePermission) -> bool:
        """Check whether this user has the specified course :class:`Permission`
        in at least one enrolled :class:`Course`.

        :param perm: The permission or permission name
        :returns: True if the user has the permission once
        """
        assert not self.virtual

        permission = Permission.get_permission(perm)
        assert permission.course_permission

        course_roles = db.session.query(
            user_course.c.course_id
        ).join(User, User.id == user_course.c.user_id).filter(
            User.id == self.id
        ).subquery('course_roles')
        crp = db.session.query(course_permissions.c.course_role_id).join(
            Permission, course_permissions.c.permission_id == Permission.id
        ).filter(Permission.id == permission.id).subquery('crp')
        res = db.session.query(
            course_roles.c.course_id
        ).join(crp, course_roles.c.course_id == crp.c.course_role_id)
        link: bool = db.session.query(res.exists()).scalar()

        return (not link) if permission.default_value else link

    @t.overload
    def get_all_permissions(self) -> t.Mapping[GlobalPermission, bool]:  # pylint: disable=function-redefined,missing-docstring,no-self-use
        ...  # pylint: disable=pointless-statement

    @t.overload
    def get_all_permissions(  # pylint: disable=function-redefined,missing-docstring,no-self-use,unused-argument
        self,
        course_id: t.Union['Course', int],
    ) -> t.Mapping[CoursePermission, bool]:
        ...  # pylint: disable=pointless-statement

    def get_all_permissions(  # pylint: disable=function-redefined
        self, course_id: t.Union['Course', int, None] = None
    ) -> t.Union[t.Mapping[CoursePermission, bool], t.
                 Mapping[GlobalPermission, bool]]:
        """Get all global permissions (:class:`Permission`) of this user or all
        course permissions of the user in a specific :class:`Course`.

        :param course_id: The course or course id

        :returns: A name boolean mapping where the name is the name of the
                  permission and the value indicates if this user has this
                  permission.
        """
        assert not self.virtual

        if isinstance(course_id, Course):
            course_id = course_id.id

        if course_id is None:
            return self.role.get_all_permissions()
        elif course_id in self.courses:
            return self.courses[course_id].get_all_permissions()
        else:
            perms = Permission.get_all_permissions(CoursePermission)
            return {perm.value: False for perm in perms}

    def get_reset_token(self) -> str:
        """Get a token which a user can use to reset his password.

        :returns: A token that can be used in :py:meth:`User.reset_password` to
            reset the password of a user.
        """
        timed_serializer = URLSafeTimedSerializer(
            current_app.config['SECRET_KEY']
        )
        self.reset_token = str(uuid.uuid4())
        return str(
            timed_serializer.dumps(self.username, salt=self.reset_token)
        )

    def reset_password(self, token: str, new_password: str) -> None:
        """Reset a users password by using a token.

        .. note:: Don't forget to commit the database.

        :param token: A token as generated by :py:meth:`User.get_reset_token`.
        :param new_password: The new password to set.
        :returns: Nothing.

        :raises PermissionException: If something was wrong with the
            given token.
        """
        assert not self.virtual

        timed_serializer = URLSafeTimedSerializer(
            current_app.config['SECRET_KEY']
        )
        try:
            username = timed_serializer.loads(
                token,
                max_age=current_app.config['RESET_TOKEN_TIME'],
                salt=self.reset_token
            )
        except BadSignature:
            logger.warning(
                'Invalid password reset token encountered',
                token=token,
                exc_info=True,
            )
            raise PermissionException(
                'The given token is not valid',
                f'The given token {token} is not valid.',
                APICodes.INVALID_CREDENTIALS, 403
            )

        # This should never happen but better safe than sorry.
        if (
            username != self.username or self.reset_token is None
        ):  # pragma: no cover
            raise PermissionException(
                'The given token is not valid for this user',
                f'The given token {token} is not valid for user "{self.id}".',
                APICodes.INVALID_CREDENTIALS, 403
            )

        self.password = new_password
        self.reset_token = None

    @property
    def is_active(self) -> bool:
        """Is the current user an active user.

        .. todo::

            Remove this property

        :returns: If the user is active.
        """
        return self.active


class Course(Base):
    """This class describes a course.

    A course can hold a collection of :class:`Assignment` objects.

    :param name: The name of the course
    :param lti_course_id: The id of the course in LTI
    :param lti_provider: The LTI provider
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['Course']]
    __tablename__ = "Course"
    id: int = db.Column('id', db.Integer, primary_key=True)
    name: str = db.Column('name', db.Unicode)

    created_at: datetime.datetime = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )

    # All stuff for LTI
    lti_course_id: str = db.Column(db.Unicode, unique=True)

    lti_provider_id: str = db.Column(
        db.String(UUID_LENGTH), db.ForeignKey('LTIProvider.id')
    )
    lti_provider: LTIProvider = db.relationship("LTIProvider")

    virtual: bool = db.Column(
        'virtual', db.Boolean, default=False, nullable=False
    )

    assignments = db.relationship(
        "Assignment", back_populates="course", cascade='all,delete'
    )  # type: t.MutableSequence[Assignment]

    def __init__(
        self,
        name: str = None,
        lti_course_id: str = None,
        lti_provider: LTIProvider = None,
        virtual: bool = False,
    ) -> None:
        super().__init__(
            name=name,
            lti_course_id=lti_course_id,
            lti_provider=lti_provider,
            virtual=virtual,
        )
        if virtual:
            return
        for role_name, perms in CourseRole.get_default_course_roles().items():
            CourseRole(name=role_name, course=self, _permissions=perms)

    __hash__ = object.__hash__

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Course) and self.id == other.id

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'name': str, # The name of the course,
                'id': int, # The id of this course.
                'created_at': str, # ISO UTC date.
                'is_lti': bool, # Is the this course a LTI course,
                'virtual': bool, # Is this a virtual course,
            }

        :returns: A object as described above.
        """
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'is_lti': self.lti_course_id is not None,
            'virtual': self.virtual,
        }

    def get_all_visible_assignments(self) -> t.Sequence['Assignment']:
        """Get all visible assignments for the current user for this course.

        :returns: A list of assignments the currently logged in user may see.
        """
        if psef.current_user.has_permission(
            CoursePermission.can_see_hidden_assignments, self.id
        ):
            return sorted(self.assignments, key=lambda item: item.deadline)
        else:
            return sorted(
                (a for a in self.assignments if not a.is_hidden),
                key=lambda item: item.deadline
            )

    def get_all_users_in_course(self) -> '_MyQuery[t.Tuple[User, CourseRole]]':
        """Get a query that returns all users in the current course and their
            role.

        :returns: A query that contains all users in the current course and
            their role.
        """
        return db.session.query(User, CourseRole).join(
            user_course,
            user_course.c.user_id == User.id,
        ).join(
            CourseRole,
            CourseRole.id == user_course.c.course_id,
        ).filter(
            CourseRole.course_id == self.id,
            t.cast(DbColumn[bool], User.virtual).isnot(True)
        )

    @classmethod
    def create_virtual_course(
        cls: t.Type['Course'], tree: 'psef.files.ExtractFileTree'
    ) -> 'Course':
        """Create a virtual course.

        The course will contain a single assignment. The tree should be a
        single directory with multiple directories under it. For each directory
        a user will be created and a submission will be created using the files
        of this directory.

        :param tree: The tree to use to create the submissions.
        :returns: A virtual course with a random name.
        """
        self = cls(name=f'VIRTUAL_COURSE__{uuid.uuid4()}', virtual=True)
        assig = Assignment(
            name=f'Virtual assignment - {tree.name}', course=self
        )
        self.assignments.append(assig)
        for child in tree.values:
            # This is done before we wrap single files to get better author
            # names.
            user = User.create_virtual_user(child.name)
            work = Work(assignment=assig, user=user)

            subdir: psef.files.ExtractFileTreeBase
            if isinstance(child, psef.files.ExtractFileTreeFile):
                subdir = psef.files.ExtractFileTreeDirectory(
                    name='top', values=[child]
                )
            else:
                assert isinstance(child, psef.files.ExtractFileTreeDirectory)
                subdir = child
            work.add_file_tree(subdir)
        return self


class GradeHistory(Base):
    """This object is a item in a grade history of a :class:`Work`.

    :ivar changed_at: When was this grade added.
    :ivar is_rubric: Was this grade added as a result of a rubric.
    :ivar passed_back: Was this grade passed back to the LMS through LTI.
    :ivar work: What work does this grade belong to.
    :ivar user: What user added this grade.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['GradeHistory']]
    __tablename__ = "GradeHistory"
    id: int = db.Column('id', db.Integer, primary_key=True)
    changed_at: datetime.datetime = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )
    is_rubric: bool = db.Column('is_rubric', db.Boolean)
    grade: float = db.Column('grade', db.Float)
    passed_back: bool = db.Column('passed_back', db.Boolean, default=False)

    work_id: int = db.Column(
        'Work_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
    )
    user_id: int = db.Column(
        'User_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
    )

    work = db.relationship(
        'Work',
        foreign_keys=work_id,
        backref=db.backref('grade_histories', lazy='select')
    )  # type: 'Work'
    user = db.relationship('User', foreign_keys=user_id)  # type: User

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Converts a rubric of a work to a object that is JSON serializable.

        The resulting object will look like this:

        .. code:: python

            {
                'changed_at': str, # The date the history was added.
                'is_rubric': bool, # Was this history items added by a rubric
                                   # grade.
                'grade': float, # The new grade, -1 if the grade was deleted.
                'passed_back': bool, # Is this grade given back to LTI.
                'user': User, # The user that added this grade.
            }

        :returns: A object as described above.
        """
        return {
            'changed_at': self.changed_at.isoformat(),
            'is_rubric': self.is_rubric,
            'grade': self.grade,
            'passed_back': self.passed_back,
            'user': self.user,
        }


class Work(Base):
    """This object describes a single work or submission of a :class:`User` for
    an :class:`Assignment`.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['Work']]
    __tablename__ = "Work"  # type: str
    id = db.Column('id', db.Integer, primary_key=True)  # type: int
    assignment_id: int = db.Column(
        'Assignment_id', db.Integer, db.ForeignKey('Assignment.id')
    )
    user_id: int = db.Column(
        'User_id', db.Integer, db.ForeignKey('User.id', ondelete='CASCADE')
    )
    _grade: t.Optional[float] = db.Column('grade', db.Float, default=None)
    comment: str = orm.deferred(db.Column('comment', db.Unicode, default=None))
    comment_author_id: t.Optional[int] = db.Column(
        'comment_author_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='SET NULL'),
        nullable=True,
    )

    orm.deferred(db.Column('comment', db.Unicode, default=None))
    created_at: datetime.datetime = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )
    assigned_to: t.Optional[int] = db.Column(
        'assigned_to', db.Integer, db.ForeignKey('User.id')
    )
    selected_items = db.relationship(
        'RubricItem', secondary=work_rubric_item
    )  # type: t.MutableSequence['RubricItem']

    assignment = db.relationship(
        'Assignment',
        foreign_keys=assignment_id,
        lazy='joined',
        backref=db.backref('submissions', lazy='select', uselist=True)
    )  # type: 'Assignment'
    comment_author = db.relationship(
        'User', foreign_keys=comment_author_id, lazy='select'
    )  # type: t.Optional[User]
    user = db.relationship(
        'User', foreign_keys=user_id, lazy='joined'
    )  # type: User
    assignee = db.relationship(
        'User', foreign_keys=assigned_to, lazy='joined'
    )  # type: t.Optional[User]

    grade_histories: t.List['GradeHistory']

    # This variable is generated from the backref from all files
    files: 't.List["File"]'

    def divide_new_work(self) -> None:
        """Divide a freshly created work.

        First we check if an old work of the same author exists, that case the
        same grader is assigned. Otherwise we take the grader that misses the
        most of work.

        :returns: Nothing
        """
        self.assigned_to = self.assignment.get_from_latest_submissions(
            Work.assigned_to
        ).filter(Work.user_id == self.user_id).limit(1).scalar()

        if self.assigned_to is None:
            missing, _ = self.assignment.get_divided_amount_missing()
            if missing:
                self.assigned_to = max(missing.keys(), key=missing.get)
                self.assignment.set_graders_to_not_done(
                    [self.assigned_to],
                    send_mail=True,
                    ignore_errors=True,
                )

    def run_linter(self) -> None:
        """Run all linters for the assignment on this work.

        All linters that have been used on the assignment will also run on this
        work.

        If the linters feature is disabled this function will simply return and
        not do anything.

        :returns: Nothing
        """
        if not psef.helpers.has_feature('LINTERS'):
            return

        for linter in self.assignment.linters:
            instance = LinterInstance(work=self, tester=linter)

            linter_cls = psef.linters.get_linter_by_name(linter.name)
            if not linter_cls.RUN_LINTER:
                instance.state = LinterState.done

            db.session.add(instance)
            db.session.commit()

            if not linter_cls.RUN_LINTER:
                return

            psef.tasks.lint_instances(
                linter.name,
                linter.config,
                [instance.id],
            )

    @property
    def grade(self) -> t.Optional[float]:
        """Get the actual current grade for this work.

        This is done by not only checking the ``grade`` field but also checking
        if rubric could be found.

        :returns: The current grade for this work.
        """
        if self._grade is None:
            if not self.selected_items:
                return None

            max_rubric_points = self.assignment.max_rubric_points
            assert max_rubric_points is not None

            selected = sum(item.points for item in self.selected_items)
            return psef.helpers.between(
                self.assignment.min_grade,
                selected / max_rubric_points * 10,
                self.assignment.max_grade,
            )
        return self._grade

    def set_grade(
        self,
        new_grade: t.Optional[float],
        user: User,
        never_passback: bool = False,
    ) -> GradeHistory:
        """Set the grade to the new grade.

        .. note:: This also passes back the grade to LTI if this is necessary
            (see :py:func:`passback_grade`).

        :param new_grade: The new grade to set
        :param user: The user setting the new grade.
        :param never_passback: Never passback the new grade.
        :returns: Nothing
        """
        self._grade = new_grade
        passback = self.assignment.should_passback
        grade = self.grade
        history = GradeHistory(
            is_rubric=self._grade is None and grade is not None,
            grade=-1 if grade is None else grade,
            passed_back=False,
            work=self,
            user=user
        )
        self.grade_histories.append(history)

        if not never_passback and passback:
            psef.helpers.callback_after_this_request(
                lambda: psef.tasks.passback_grades([self.id])
            )

        return history

    @property
    def selected_rubric_points(self) -> float:
        """The amount of points that are currently selected in the rubric for
        this work.
        """
        return sum(item.points for item in self.selected_items)

    def passback_grade(self, initial: bool = False) -> None:
        """Initiates a passback of the grade to the LTI consumer via the
        :class:`LTIProvider`.

        :param initial: Should we do a initial LTI grade passback with no
            result so that the real grade won't show as too late.
        :returns: Nothing
        """
        if not self.assignment.is_lti:
            return

        lti_provider = self.assignment.course.lti_provider

        lti_provider.passback_grade(self, initial)

        newest_grade_history_id = db.session.query(
            t.cast(DbColumn[int], GradeHistory.id)
        ).filter_by(work_id=self.id).order_by(
            t.cast(DbColumn[datetime.datetime],
                   GradeHistory.changed_at).desc(),
        ).limit(1).with_for_update()

        db.session.query(GradeHistory).filter(
            GradeHistory.id == newest_grade_history_id.as_scalar(),
        ).update({
            'passed_back': True
        }, synchronize_session='fetch')

    def select_rubric_items(
        self, items: t.List['RubricItem'], user: User, override: bool = False
    ) -> None:
        """ Selects the given :class:`RubricItem`.

        .. note:: This also passes back the grade to LTI if this is necessary.

        .. note:: This also sets the actual grade field to `None`.

        :param item: The item to add.
        :param user: The user selecting the item.
        :returns: Nothing
        """
        if override:
            self.selected_items = []

        for item in items:
            self.selected_items.append(item)

        self.set_grade(None, user)

    def __to_json__(self) -> t.MutableMapping[str, t.Any]:
        """Returns the JSON serializable representation of this work.

        The representation is based on the permissions (:class:`Permission`) of
        the logged in :class:`User`. Namely the assignee, feedback, and grade
        attributes are only included if the current user can see them,
        otherwise they are set to `None`.

        The resulting object will look like this:

        .. code:: python

            {
                'id': int # Submission id.
                'user': User # User that submitted this work.
                'created_at': str # Submission date in ISO-8601 datetime
                                  # format.
                'grade': t.Optional[float] # Grade for this submission, or
                                              # None if the submission hasn't
                                              # been graded yet or if the
                                              # logged in user doesn't have
                                              # permission to see the grade.
                'assignee': t.Optional[User] # User assigned to grade this
                                                # submission, or None if the
                                                # logged in user doesn't have
                                                # permission to see the
                                                # assignee.
            }

        :returns: A dict containing JSON serializable representations of the
                  attributes of this work.
        """
        item = {
            'id': self.id,
            'user': self.user,
            'created_at': self.created_at.isoformat(),
        }

        try:
            psef.auth.ensure_permission(
                CoursePermission.can_see_assignee, self.assignment.course_id
            )
            item['assignee'] = self.assignee
        except PermissionException:
            item['assignee'] = None

        try:
            psef.auth.ensure_can_see_grade(self)
        except PermissionException:
            item['grade'] = None
        else:
            item['grade'] = self.grade
        return item

    def __extended_to_json__(self) -> t.Mapping[str, t.Any]:
        """Create a extended JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'comment': t.Optional[str] # General feedback comment for
                                           # this submission, or None in
                                           # the same cases as the grade.
                'comment_author': t.Optional[User] # The author of the comment
                                                   # field submission, or None
                                                   # if the logged in user
                                                   # doesn't have permission to
                                                   # see the assignee.
                **self.__to_json__()
            }

        :returns: A object as described above.
        """
        res: t.Dict[str, object] = {
            'comment': None,
            'comment_author': None,
            **self.__to_json__()
        }

        try:
            psef.auth.ensure_can_see_grade(self)
        except PermissionException:
            pass
        else:
            res['comment'] = self.comment
            if psef.current_user.has_permission(
                CoursePermission.can_see_assignee, self.assignment.course_id
            ):
                res['comment_author'] = self.comment_author

        return res

    def __rubric_to_json__(self) -> t.Mapping[str, t.Any]:
        """Converts a rubric of a work to a object that is JSON serializable.

        The resulting object will look like this:

        .. code:: python

            {
                'rubrics': t.List[RubricRow] # A list of all the rubrics for
                                             # this work.
                'selected': t.List[RubricItem] # A list of all the selected
                                               # rubric items for this work,
                                               # or an empty list if the logged
                                               # in user doesn't have
                                               # permission to see the rubric.
                'points': {
                    'max': t.Optional[float] # The maximal amount of points
                                                # for this rubric, or `None` if
                                                # logged in user doesn't have
                                                # permission to see the rubric.
                    'selected': t.Optional[float] # The amount of point that
                                                     # is selected for this
                                                     # work, or `None` if the
                                                     # logged in user doesn't
                                                     # have permission to see
                                                     # the rubric.
                }
            }

        :returns: A object as described above.

        .. todo:: Remove the points object.
        """
        try:
            psef.auth.ensure_can_see_grade(self)

            return {
                'rubrics': self.assignment.rubric_rows,
                'selected': self.selected_items,
                'points':
                    {
                        'max': self.assignment.max_rubric_points,
                        'selected': self.selected_rubric_points,
                    },
            }
        except PermissionException:
            return {
                'rubrics': self.assignment.rubric_rows,
                'selected': [],
                'points': {
                    'max': None,
                    'selected': None,
                },
            }

    def add_file_tree(
        self, tree: 'psef.files.ExtractFileTreeDirectory'
    ) -> None:
        """Add the given tree to as only files to the current work.

        .. warning:: All previous files will be unlinked from this assignment.

        :param tree: The file tree as described by
            :py:func:`psef.files.rename_directory_structure`
        :returns: Nothing
        """
        self._add_file_tree(tree, None)

    def _add_file_tree(
        self,
        tree: 'psef.files.ExtractFileTreeDirectory',
        top: t.Optional['File'],
    ) -> 'File':
        """Add the given tree to the session with top as parent.

        :param tree: The file tree as described by
                          :py:func:`psef.files.rename_directory_structure`
        :param top: The parent file
        :returns: Nothing
        """
        new_top = File(
            work=self, is_directory=True, name=tree.name, parent=top
        )

        for child in tree.values:
            if isinstance(child, psef.files.ExtractFileTreeDirectory):
                self._add_file_tree(child, new_top)
            elif isinstance(child, psef.files.ExtractFileTreeFile):
                File(
                    work=self,
                    name=child.name,
                    filename=child.disk_name,
                    is_directory=False,
                    parent=new_top
                )
            else:
                # The above checks are exhaustive, so this cannot happen
                assert False
        return new_top

    def get_all_feedback(self) -> t.Tuple[t.Iterable[str], t.Iterable[str], ]:
        """Get all feedback for this work.

        :returns: A tuple of two iterators both producing human readable
            representations of the given feedback. The first iterator produces
            the feedback given by a person and the second the feedback given by
            the linters.
        """

        def __get_user_feedback() -> t.Iterable[str]:
            comments = Comment.query.filter(
                t.cast(DbColumn[File], Comment.file).has(work=self),
            ).order_by(
                t.cast(DbColumn[int], Comment.file_id).asc(),
                t.cast(DbColumn[int], Comment.line).asc(),
            )
            for com in comments:
                yield f'{com.file.name}:{com.line}:0: {com.comment}'

        def __get_linter_feedback() -> t.Iterable[str]:
            linter_comments = LinterComment.query.filter(
                LinterComment.file.has(work=self)  # type: ignore
            ).order_by(
                LinterComment.file_id.asc(),  # type: ignore
                LinterComment.line.asc(),  # type: ignore
            )
            for line_comm in linter_comments:
                yield (
                    f'{line_comm.file.name}:{line_comm.line}:0: '
                    f'({line_comm.linter.tester.name}'
                    f' {line_comm.linter_code}) {line_comm.comment}'
                )

        return __get_user_feedback(), __get_linter_feedback()

    def remove_selected_rubric_item(self, row_id: int) -> None:
        """Deselect selected :class:`RubricItem` on row.

        Deselects the selected rubric item on the given row with _row_id_  (if
        there are any selected).

        :param row_id: The id of the RubricRow from which to deselect
                           rubric items
        :returns: Nothing
        """
        rubricitem = db.session.query(RubricItem).join(
            work_rubric_item, RubricItem.id == work_rubric_item.c.rubricitem_id
        ).filter(
            work_rubric_item.c.work_id == self.id,
            RubricItem.rubricrow_id == row_id
        ).first()
        if rubricitem is not None:
            self.selected_items.remove(rubricitem)

    def search_file_filters(
        self,
        pathname: str,
        exclude: 'FileOwner',
    ) -> t.List[t.Any]:
        """Get the filters needed to search for a file in the this directory
        with a given name.

        :param pathname: The path of the file to search for, this may contain
            leading and trailing slashes which do not have any meaning.
        :param exclude: The fileowner to exclude from search, like described in
            :func:`get_zip`.
        :returns: The criteria needed to find the file with the given pathname.
        """
        patharr, is_dir = psef.files.split_path(pathname)

        parent: t.Optional[t.Any] = None
        for idx, pathpart in enumerate(patharr[:-1]):
            if parent is not None:
                parent = parent.c.id

            parent = db.session.query(t.cast(DbColumn[int], File.id)).filter(
                File.name == pathpart,
                File.parent_id == parent,
                File.work_id == self.id,
                File.is_directory,
            ).subquery(f'parent_{idx}')

        if parent is not None:
            parent = parent.c.id

        return [
            File.work_id == self.id,
            File.name == patharr[-1],
            File.parent_id == parent,
            File.fileowner != exclude,
            File.is_directory == is_dir,
        ]

    def search_file(
        self,
        pathname: str,
        exclude: 'FileOwner',
    ) -> 'File':
        """Search for a file in the this directory with the given name.

        :param pathname: The path of the file to search for, this may contain
            leading and trailing slashes which do not have any meaning.
        :param exclude: The fileowner to exclude from search, like described in
            :func:`get_zip`.
        :returns: The found file.
        """

        return psef.helpers.filter_single_or_404(
            File,
            *self.search_file_filters(pathname, exclude),
        )


@enum.unique
class FileOwner(enum.IntEnum):
    """Describes to which version of a submission (student's submission or
    teacher's revision) a file belongs. When a student adds or changes a file
    after the deadline for the assignment has passed, the original file's owner
    is set `teacher` and the new file's to `student`.

    :param student: The file is in the student's submission, but changed in the
        teacher's revision.
    :param teacher: The inverse of `student`. The file is added or changed in
        the teacher's revision.
    :param both: The file is not changed in the teacher's revision and belongs
        to both versions.
    """

    student: int = 1
    teacher: int = 2
    both: int = 3


class File(Base):
    """
    This object describes a file or directory that stored is stored on the
    server.

    Files are always connected to :class:`Work` objects. A directory file does
    not physically exist but is stored only in the database to preserve the
    submitted work structure. Each submission should have a single top level
    file. Each other file in a submission should be directly or indirectly
    connected to this file via the parent attribute.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['File']]
    __tablename__ = "File"
    id: int = db.Column('id', db.Integer, primary_key=True)
    work_id: int = db.Column(
        'Work_id', db.Integer, db.ForeignKey('Work.id', ondelete='CASCADE')
    )
    # The given name of the file.
    name: str = db.Column('name', db.Unicode, nullable=False)

    # This is the filename for the actual file on the disk. This is probably a
    # randomly generated uuid.
    filename: t.Optional[str]
    filename = db.Column('filename', db.Unicode, nullable=True)
    modification_date = db.Column(
        'modification_date', db.DateTime, default=datetime.datetime.utcnow
    )

    fileowner: FileOwner = db.Column(
        'fileowner',
        db.Enum(FileOwner),
        default=FileOwner.both,
        nullable=False
    )

    is_directory: bool = db.Column('is_directory', db.Boolean)
    parent_id = db.Column('parent_id', db.Integer, db.ForeignKey('File.id'))

    # This variable is generated from the backref from the parent
    children: '_MyQuery["File"]'

    parent = db.relationship(
        'File',
        remote_side=[id],
        backref=db.backref('children', lazy='dynamic')
    )  # type: 'File'

    work = db.relationship(
        'Work',
        foreign_keys=work_id,
        backref=db.backref(
            'files', lazy='select', uselist=True, cascade='all,delete'
        )
    )  # type: 'Work'

    @staticmethod
    def get_exclude_owner(owner: t.Optional[str], course_id: int) -> FileOwner:
        """Get the :class:`FileOwner` the current user does not want to see
        files for.

        The result will be decided like this, if the given str is not
        `student`, `teacher` or `auto` the result will be `FileOwner.teacher`.
        If the str is `student`, the result will be `FileOwner.teacher`, vica
        versa for `teacher` as input. If the input is auto `student` will be
        returned if the currently logged in user is a teacher, otherwise it
        will be `student`.

        :param owner: The owner that was given in the `GET` paramater.
        :param course_id: The course for which the files are requested.
        :returns: The object determined as described above.
        """
        psef.auth.ensure_logged_in()

        teacher, student = FileOwner.teacher, FileOwner.student
        if owner == 'student':
            return teacher
        elif owner == 'teacher':
            return student
        elif owner == 'auto':
            if psef.current_user.has_permission(
                CoursePermission.can_edit_others_work, course_id
            ):
                return student
            else:
                return teacher
        else:
            return teacher

    def get_diskname(self) -> str:
        """Get the absolute path on the disk for this file.

        :returns: The absolute path.
        """
        assert not self.is_directory
        return os.path.join(
            current_app.config['UPLOAD_DIR'], t.cast(str, self.filename)
        )

    def delete_from_disk(self) -> None:
        """Delete the file from disk if it is not a directory.

        :returns: Nothing.
        """
        if not self.is_directory:
            os.remove(self.get_diskname())

    def list_contents(self, exclude: FileOwner) -> 'psef.files.FileTree':
        """List the basic file info and the info of its children.

        If the file is a directory it will return a tree like this:

        .. code:: python

            {
                'name': 'dir_1',
                'id': 1,
                'entries': [
                    {
                        'name': 'file_1',
                        'id': 2
                    },
                    {
                        'name': 'file_2',
                        'id': 3
                    },
                    {
                        'name': 'dir_2',
                        'id': 4,
                        'entries': []
                    }
                ]
            }

        Otherwise it will formatted like one of the file children of the above
        tree.

        :param exclude: The file owner to exclude from the tree.

        :returns: A tree as described above.
        """
        if not self.is_directory:
            return {"name": self.name, "id": self.id}
        else:
            children = [
                child.list_contents(exclude)
                for child in self.get_sorted_children(exclude)
            ]
            return {
                "name": self.name,
                "id": self.id,
                "entries": children,
            }

    def get_sorted_children(self, exclude: FileOwner) -> t.List['File']:
        return sorted(
            self.children.filter(File.fileowner != exclude),
            key=lambda el: el.name.lower(),
        )

    def rename_code(
        self,
        new_name: str,
        new_parent: 'File',
        exclude_owner: FileOwner,
    ) -> None:
        """Rename the this file to the given new name.

        :param new_name: The new name to be given to the given file.
        :param new_parent: The new parent of this file.
        :param exclude_owner: The owner to exclude while searching for
            collisions.
        :returns: Nothing.

        :raises APIException: If renaming would result in a naming collision
            (INVALID_STATE).
        """
        if new_parent.children.filter_by(name=new_name).filter(
            File.fileowner != exclude_owner,
        ).first() is not None:
            raise APIException(
                'This file already exists within this directory',
                f'The file "{new_parent.id}" has '
                f'a child with the name "{new_name}"', APICodes.INVALID_STATE,
                400
            )

        self.name = new_name

    def __to_json__(self) -> t.Mapping[str, t.Union[str, bool, int]]:
        """Creates a JSON serializable representation of this object.


        This object will look like this:

        .. code:: python

            {
                'name': str, # The name of the file or directory.
                'id': int, # The id of this file.
                'is_directory': bool, # Is this file a directory.
            }

        :returns: A object as described above.
        """
        return {
            'name': self.name,
            'is_directory': self.is_directory,
            'id': self.id,
        }


class LinterComment(Base):
    """Describes a comment created by a :class:`LinterInstance`.

    Like a :class:`Comment` it is attached to a specific line in a
    :class:`File`.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['LinterComment']]
    __tablename__ = "LinterComment"  # type: str
    id: int = db.Column('id', db.Integer, primary_key=True)
    file_id: int = db.Column(
        'File_id',
        db.Integer,
        db.ForeignKey('File.id', ondelete='CASCADE'),
        index=True
    )
    linter_id = db.Column(
        'linter_id', db.Unicode, db.ForeignKey('LinterInstance.id')
    )

    line: int = db.Column('line', db.Integer)
    linter_code: str = db.Column('linter_code', db.Unicode)
    comment: str = db.Column('comment', db.Unicode)

    linter = db.relationship(
        "LinterInstance", back_populates="comments"
    )  # type: 'LinterInstance'
    file: File = db.relationship('File', foreign_keys=file_id)

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'code': self.linter_code,
            'line': self.line,
            'msg': self.comment,
        }


class Comment(Base):
    """Describes a comment placed in a :class:`File` by a :class:`User` with
    the ability to grade.

    A comment is always linked to a specific line in a file.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['Comment']]
    __tablename__ = "Comment"
    file_id: int = db.Column(
        'File_id', db.Integer, db.ForeignKey('File.id', ondelete='CASCADE')
    )
    user_id: int = db.Column(
        'User_id', db.Integer, db.ForeignKey('User.id', ondelete='CASCADE')
    )
    line: int = db.Column('line', db.Integer)
    comment: str = db.Column('comment', db.Unicode)
    __table_args__ = (db.PrimaryKeyConstraint(file_id, line), )

    file: File = db.relationship('File', foreign_keys=file_id)
    user: User = db.relationship('User', foreign_keys=user_id)

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.


        This object will look like this:

        .. code:: python

            {
                'line': int, # The line of this comment.
                'msg': str,  # The message of this comment.
                'author': t.Optional[User], # The author of this comment. This
                                            # is ``None`` if the user does not
                                            # have permission to see it.
            }

        :returns: A object as described above.
        """
        res = {
            'line': self.line,
            'msg': self.comment,
        }

        if psef.current_user.has_permission(
            CoursePermission.can_see_assignee,
            self.file.work.assignment.course_id
        ):
            res['author'] = self.user

        return res


@enum.unique
class LinterState(enum.IntEnum):
    """Describes in what state a :class:`LinterInstance` is.

    :param running: The linter is currently running.
    :param done: The linter has finished without crashing.
    :param crashed: The linter has crashed in some way.
    """
    running: int = 1
    done: int = 2
    crashed: int = 3


@enum.unique
class PlagiarismState(enum.IntEnum):
    """Describes in what state a :class:`PlagiarismRun` is.

    :param running: The provider is currently running.
    :param done: The provider has finished without crashing.
    :param crashed: The provider has crashed in some way.
    """
    running: int = 1
    done: int = 2
    crashed: int = 3


class AssignmentLinter(Base):
    """The class is used when a linter (see :py:mod:`psef.linters`) is used on
    a :class:`Assignment`.

    Every :class:`Work` that is tested is attached by a
    :class:`LinterInstance`.

    The name identifies which :class:`.linters.Linter` is used.

    :ivar name: The name of the linter which is the `__name__` of a subclass of
        :py:class:`linters.Linter`.
    :ivar tests: All the linter instances for this linter, this are the
        recordings of the running of the actual linter (so in the case of the
        :py:class:`linters.Flake8` metadata about the `flake8` program).
    :ivar config: The config that was passed to the linter.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['AssignmentLinter']]
    __tablename__ = 'AssignmentLinter'  # type: str
    # This has to be a String object as the id has to be a non guessable uuid.
    id: str = db.Column(
        'id', db.String(UUID_LENGTH), nullable=False, primary_key=True
    )
    name: str = db.Column('name', db.Unicode)
    tests = db.relationship(
        "LinterInstance",
        back_populates="tester",
        cascade='all,delete',
        order_by='LinterInstance.work_id'
    )  # type: t.Sequence[LinterInstance]
    config: str = db.Column(
        'config',
        db.Unicode,
        nullable=False,
    )
    assignment_id = db.Column(
        'Assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id'),
    )  # type: int

    assignment = db.relationship(
        'Assignment',
        foreign_keys=assignment_id,
        backref=db.backref('linters', uselist=True),
    )  # type: 'Assignment'

    @property
    def linters_crashed(self) -> int:
        """The amount of linters that have crashed.
        """
        return self._amount_linters_in_state(LinterState.crashed)

    @property
    def linters_done(self) -> int:
        """The amount of linters that are done.
        """
        return self._amount_linters_in_state(LinterState.done)

    @property
    def linters_running(self) -> int:
        """The amount of linters that are running.
        """
        return self._amount_linters_in_state(LinterState.running)

    def _amount_linters_in_state(self, state: LinterState) -> int:
        return LinterInstance.query.filter_by(
            tester_id=self.id, state=state
        ).count()

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Returns the JSON serializable representation of this class.

        This representation also returns a count of the :class:`LinterState` of
        the attached :class:`LinterInstance` objects.

        :returns: A dict containing JSON serializable representations of the
                  attributes and the test state counts of this
                  AssignmentLinter.
        """
        return {
            'done': self.linters_done,
            'working': self.linters_running,
            'crashed': self.linters_crashed,
            'id': self.id,
            'name': self.name,
        }

    @classmethod
    def create_linter(
        cls: t.Type['AssignmentLinter'],
        assignment_id: int,
        name: str,
        config: str,
    ) -> 'AssignmentLinter':
        """Create a new instance of this class for a given :class:`Assignment`
        with a given :py:class:`.linters.Linter`

        :param assignment_id: The id of the assignment
        :param name: Name of the linter
        :returns: The created AssignmentLinter
        """
        new_id = str(uuid.uuid4())

        # Find a unique id.
        while db.session.query(
            AssignmentLinter.query.filter(cls.id == new_id).exists()
        ).scalar():  # pragma: no cover
            new_id = str(uuid.uuid4())

        self = cls(id=new_id, assignment_id=assignment_id, name=name)
        self.config = config

        self.tests = []
        assig = Assignment.query.get(assignment_id)

        if assig is not None:
            for work in assig.get_all_latest_submissions():
                self.tests.append(LinterInstance(work, self))

        return self


class LinterInstance(Base):
    """Describes the connection between a :class:`AssignmentLinter` and a
    :class:`Work`.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['LinterInstance']]
    __tablename__ = 'LinterInstance'
    id: str = db.Column(
        'id', db.String(UUID_LENGTH), nullable=False, primary_key=True
    )
    state: LinterState = db.Column(
        'state',
        db.Enum(LinterState),
        default=LinterState.running,
        nullable=False
    )
    work_id: int = db.Column(
        'Work_id', db.Integer, db.ForeignKey('Work.id', ondelete='CASCADE')
    )
    tester_id: str = db.Column(
        'tester_id', db.Unicode, db.ForeignKey('AssignmentLinter.id')
    )

    tester: AssignmentLinter = db.relationship(
        "AssignmentLinter", back_populates="tests"
    )
    work: Work = db.relationship('Work', foreign_keys=work_id)

    comments: LinterComment = db.relationship(
        "LinterComment", back_populates="linter", cascade='all,delete'
    )

    def __init__(self, work: Work, tester: AssignmentLinter) -> None:
        super().__init__(work=work, tester=tester)

        # Find a unique id
        new_id = str(uuid.uuid4())
        while db.session.query(
            LinterInstance.query.filter(LinterInstance.id == new_id).exists()
        ).scalar():  # pragma: no cover
            new_id = str(uuid.uuid4())

        self.id = new_id

    def add_comments(
        self,
        feedbacks: t.Mapping[int, t.Mapping[int, t.Sequence[t.
                                                            Tuple[str, str]]]],
    ) -> t.Iterable[LinterComment]:
        """Add comments written by this instance.

        :param feedbacks: The feedback to add, it should be in form as
            described below.
        :returns: A iterable with comments that have not been added or commited
            to the database yet.

        .. code:: python

            {
                file_id: {
                    line_number: [(linter_code, msg), ...]
                }
            }
        """
        for file_id, feedback in feedbacks.items():
            for line_number, msgs in feedback.items():
                for linter_code, msg in msgs:
                    yield LinterComment(
                        file_id=file_id,
                        line=line_number,
                        linter_code=linter_code,
                        linter_id=self.id,
                        comment=msg,
                    )


@enum.unique
class _AssignmentStateEnum(enum.IntEnum):
    """Describes in what state an :class:`Assignment` is.
    """
    hidden = 0
    open = 1
    done = 2


@enum.unique
class AssignmentDoneType(enum.IntEnum):
    """Describes what type of reminder should be sent.

    :param none: Nobody should be e-mailed.
    :param assigned_only: Only graders that are assigned will be notified.
    :param all_graders: All users that have the permission to grade.
    """
    assigned_only: int = 1
    all_graders: int = 2


class Assignment(Base):
    """This class describes a :class:`Course` specific assignment.

    :ivar name: The name of the assignment.
    :ivar cgignore: The .cgignore file of this assignment.
    :ivar state: The current state the assignment is in.
    :ivar description: UNUSED
    :ivar course: The course this assignment belongs to.
    :ivar created_at: The date this assignment was added.
    :ivar deadline: The deadline of this assignment.
    :ivar _mail_task_id: This is the id of the current task that will email all
        the TA's to hurry up with grading.
    :ivar reminder_email_time: The time the reminder email should be sent. To
        see if we should actually send these reminders look at `done_type`
    :ivar done_email: The email address we should sent a email if the grading
        is done. The function :py:func:`email.utils.getaddresses` should be
        able to parse this string.
    :ivar done_type: The type of reminder that should be sent.
    :ivar assigned_graders: All graders that are assigned to grade mapped by
        user_id to `AssignmentAssignedGrader` object.
    :ivar rubric_rows: The rubric rows that make up the rubric for this
        assignment.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type:  t.ClassVar[_MyQuery['Assignment']]
    __tablename__ = "Assignment"
    id: int = db.Column('id', db.Integer, primary_key=True)
    name: str = db.Column('name', db.Unicode)
    cgignore: t.Optional[str] = db.Column('cgignore', db.Unicode)
    state: _AssignmentStateEnum = db.Column(
        'state',
        db.Enum(_AssignmentStateEnum),
        default=_AssignmentStateEnum.hidden,
        nullable=False
    )
    description: str = db.Column('description', db.Unicode, default='')
    course_id: int = db.Column(
        'Course_id', db.Integer, db.ForeignKey('Course.id')
    )
    created_at: datetime.datetime = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )
    deadline: t.Optional[datetime.datetime
                         ] = db.Column('deadline', db.DateTime)

    _mail_task_id: t.Optional[str] = db.Column(
        'mail_task_id',
        db.Unicode,
        nullable=True,
        default=None,
    )
    reminder_email_time: t.Optional[datetime.datetime] = db.Column(
        'reminder_email_time',
        db.DateTime,
        default=None,
        nullable=True,
    )
    done_email: t.Optional[str] = db.Column(
        'done_email',
        db.Unicode,
        default=None,
        nullable=True,
    )
    done_type: t.Optional[AssignmentDoneType] = db.Column(
        'done_type',
        db.Enum(AssignmentDoneType),
        nullable=True,
        default=None,
    )
    _max_grade: t.Optional[float] = db.Column(
        'max_grade', db.Float, nullable=True, default=None
    )
    lti_points_possible: t.Optional[float] = db.Column(
        'lti_points_possible',
        db.Float,
        nullable=True,
        default=None,
    )

    # All stuff for LTI
    lti_assignment_id: str = db.Column(db.Unicode, unique=True)
    lti_outcome_service_url: str = db.Column(db.Unicode)

    assigned_graders: t.MutableMapping[
        int, AssignmentAssignedGrader] = db.relationship(
            'AssignmentAssignedGrader',
            cascade='delete-orphan, delete',
            collection_class=attribute_mapped_collection('user_id'),
            backref=db.backref('assignment', lazy='select')
        )

    finished_graders = db.relationship(
        'AssignmentGraderDone',
        backref=db.backref('assignment'),
        cascade='delete-orphan, delete',
    )  # type: t.MutableSequence['AssignmentGraderDone']

    assignment_results: t.MutableMapping[
        int, AssignmentResult] = db.relationship(
            'AssignmentResult',
            collection_class=attribute_mapped_collection('user_id'),
            backref=db.backref('assignment', lazy='select')
        )

    course: Course = db.relationship(
        'Course',
        foreign_keys=course_id,
        back_populates='assignments',
        lazy='joined'
    )

    fixed_max_rubric_points: t.Optional[float] = db.Column(
        'fixed_max_rubric_points',
        db.Float,
        nullable=True,
    )
    rubric_rows = db.relationship(
        'RubricRow',
        backref=db.backref('assignment'),
        cascade='delete-orphan, delete, save-update',
        order_by="RubricRow.created_at"
    )  # type: t.MutableSequence['RubricRow']

    # This variable is available through a backref
    linters: t.Iterable['AssignmentLinter']

    # This variable is available through a backref
    submissions: t.Iterable['Work']

    @property
    def max_grade(self) -> float:
        """Get the maximum grade possible for this assignment.

        :returns: The maximum a grade for a submission.
        """
        return 10 if self._max_grade is None else self._max_grade

    # We don't use property.setter because in that case `new_val` could only be
    # a `float` because of https://github.com/python/mypy/issues/220
    def set_max_grade(self, new_val: t.Union[None, float, int]) -> None:
        """Set or unset the maximum grade for this assignment.

        :param new_val: The new value for ``_max_grade``.
        :return: Nothing.
        """
        self._max_grade = new_val

    min_grade = 0
    """The minimum grade for a submission in this assignment."""

    def _submit_grades(self) -> None:
        subs = t.cast(
            t.List[t.Tuple[int]],
            self.get_from_latest_submissions(Work.id).all()
        )
        for i in range(0, len(subs), 10):
            psef.tasks.passback_grades([s[0] for s in subs[i:i + 10]])

    def change_notifications(
        self,
        done_type: t.Optional[AssignmentDoneType],
        grader_date: t.Optional[datetime.datetime],
        done_email: t.Optional[str],
    ) -> None:
        """Change the notifications for the current assignment.

        :param done_type: How to determine when the assignment is done. Set
            this value to ``None`` to disable the reminder for this assignment.
        :param grader_date: The datetime when to send graders that are causing
            the assignment to be not done a reminder email.
        :param done_email: The email to send a notification when grading for
            this assignment is done.
        """
        if self._mail_task_id is not None:
            psef.tasks.celery.control.revoke(self._mail_task_id)

        self.done_type = done_type

        # Make sure _reminder_email_time is ``None`` if ``done_type`` is
        # ``none``
        self.reminder_email_time = None if done_type is None else grader_date
        self.done_email = None if done_type is None else done_email

        if self.reminder_email_time is None:
            # Make sure id is reset so we don't revoke it multiple times
            self._mail_task_id = None
        else:
            res = psef.tasks.send_reminder_mails((self.id, ), eta=grader_date)
            self._mail_task_id = res.id

    def graders_are_done(self) -> bool:
        """Check if the graders of this assignment are done.

        :returns: A boolean indicating if the graders of this assignment are
            done.
        """
        if self.done_type is None:
            # We are never done as we have no condition to be done
            return False
        elif self.done_type == AssignmentDoneType.assigned_only:
            assigned = set(self.get_assigned_grader_ids())
            finished = set(fg.user_id for fg in self.finished_graders)
            # Check if every assigned grader is done.
            return assigned.issubset(finished)
        elif self.done_type == AssignmentDoneType.all_graders:
            # All graders should be done. As finished_graders all have unique
            # user ids we simply need to check if the lengths are the same
            return len(self.finished_graders) == self.get_all_graders().count()

        # This is needed because of https://github.com/python/mypy/issues/4223
        # and to please pylint
        raise ValueError(
            f'The assignment has a invalid `done_type`: {self.done_type}'
        )  # pragma: no cover

    def get_assigned_grader_ids(self) -> t.Iterable[int]:
        """Get the ids of all the graders that have submissions assigned.

        .. note::

            This only gets graders with latest submissions assigned to them.

        :returns: The ids of the all the graders that have work assigned within
            this assignnment.
        """
        return map(
            itemgetter(0),
            self.get_from_latest_submissions(
                Work.assigned_to,
            ).distinct(),
        )

    def set_graders_to_not_done(
        self,
        user_ids: t.Sequence[int],
        send_mail: bool = False,
        ignore_errors: bool = False,
    ) -> None:
        """Set the status of the given graders to 'not done'.

        :param user_ids: The ids of the users that should be set to 'not done'
        :param send_mail: If ``True`` the users who are reset to 'not done'
            will get an email notifying them of this.
        :param ignore_errors: Do not raise an error if a user in ``user_ids``
            was not yet done.
        :raise ValueError: If a user in ``user_ids`` was not yet done. This can
            happen because the user has not indicated this yet, because this
            user does not exist or because of any reason.
        """
        if not user_ids:
            return

        graders = AssignmentGraderDone.query.filter(
            AssignmentGraderDone.assignment_id == self.id,
            t.cast(t.Any, AssignmentGraderDone.user_id).in_(user_ids),
        ).all()

        if not ignore_errors and len(graders) != len(user_ids):
            raise ValueError('Not all graders were found')

        for grader in graders:
            if send_mail:
                psef.tasks.send_grader_status_mail(self.id, grader.user_id)
            db.session.delete(grader)

    def has_non_graded_submissions(self, user_id: int) -> bool:
        """Check if the user with the given ``user_id`` has submissions
        assigned without a grade.

        :param user_id: The id of the user to check for
        :returns: A boolean indicating if user has work assigned that does not
            have grade or a selected rubric item
        """
        latest = self.get_from_latest_submissions(Work.id)
        sql = latest.filter(
            Work.assigned_to == user_id,
        ).join(
            work_rubric_item,
            work_rubric_item.c.work_id == Work.id,
            isouter=True
        ).having(
            and_(
                func.count(work_rubric_item.c.rubricitem_id) == 0,
                # We access _grade here directly as we need it to do this query
                t.cast(DbColumn[t.Optional[int]], Work._grade).is_(None)  # pylint: disable=protected-access
            )
        ).group_by(Work.id)

        return db.session.query(sql.exists()).scalar()

    @property
    def is_lti(self) -> bool:
        """Is this assignment a LTI assignment.

        :returns: A boolean indicating if this is the case.
        """
        return self.lti_outcome_service_url is not None

    @property
    def max_rubric_points(self) -> t.Optional[float]:
        """Get the maximum amount of points possible for the rubric

        .. note::

          This is always higher than zero (so also not zero).


        :returns: The maximum amount of points.
        """
        if self.fixed_max_rubric_points is not None:
            return self.fixed_max_rubric_points
        else:
            return self._dynamic_max_points

    @cached_property
    def _dynamic_max_points(self) -> t.Optional[float]:
        sub = db.session.query(
            func.max(RubricItem.points).label('max_val')
        ).join(RubricRow, RubricRow.id == RubricItem.rubricrow_id).filter(
            RubricRow.assignment_id == self.id
        ).group_by(RubricRow.id).subquery('sub')
        return db.session.query(func.sum(sub.c.max_val)).scalar()

    @property
    def is_open(self) -> bool:
        """Is the current assignment open, which means the assignment is in the
        state students submit work.
        """
        return bool(
            self.deadline is not None and
            self.state == _AssignmentStateEnum.open and
            self.deadline >= psef.helpers.get_request_start_time()
        )

    @property
    def is_hidden(self) -> bool:
        """Is the assignment hidden.
        """
        return self.state == _AssignmentStateEnum.hidden

    @property
    def is_done(self) -> bool:
        """Is the assignment done, which means that grades are open.
        """
        return self.state == _AssignmentStateEnum.done

    @property
    def should_passback(self) -> bool:
        """Should we passback the current grade.
        """
        return self.is_done

    @property
    def state_name(self) -> str:
        """The current name of the grade.

        .. warning:: This is not the same as ``str(self.state)``.

        :returns: The correct name of the current state.
        """
        if self.state == _AssignmentStateEnum.open:
            return 'submitting' if self.is_open else 'grading'
        return _AssignmentStateEnum(self.state).name

    @property
    def whitespace_linter_exists(self) -> bool:
        """Does this assignment have a whitespace linter.
        """
        # pylint: disable=attribute-defined-outside-init
        # _whitespace_linter_exists is a cache property, so this is why it is
        # defined outside of the init.
        if not hasattr(self, '_whitespace_linter_exists'):
            self._whitespace_linter_exists = db.session.query(
                AssignmentLinter.query.filter(
                    AssignmentLinter.assignment_id == self.id,
                    AssignmentLinter.name == 'MixedWhitespace'
                ).exists()
            ).scalar()

        return self._whitespace_linter_exists

    @whitespace_linter_exists.setter
    def whitespace_linter_exists(self, exists: bool) -> None:
        """Preset the cache for ``whitespace_linter_exists`` reducing the
        amount of queries needed.
        """
        # pylint: disable=attribute-defined-outside-init
        # _whitespace_linter_exists is a cache property, so this is why it is
        # defined outside of the init.
        self._whitespace_linter_exists = exists

    @property
    def whitespace_linter(self) -> bool:
        """Check if this assignment has an associated MixedWhitespace linter.

        .. note::

            If the assignment is not yet done we check if the ``current_user``
            has the permission ``can_see_grade_before_open``.

        :returns: True if there is an :py:class:`.AssignmentLinter` with name
            ``MixedWhitespace`` and ``assignment_id``.
        """
        try:
            if not self.is_done:
                psef.auth.ensure_permission(
                    CoursePermission.can_see_grade_before_open, self.course_id
                )
        except PermissionException:
            return False
        else:
            return self.whitespace_linter_exists

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this assignment.

        This object will look like this:

        .. code:: python

            {
                'id': int, # The id of this assignment.
                'state': str, # Current state of this assignment.
                'description': str, # Description of this assignment.
                'created_at': str, # ISO UTC date.
                'deadline': str, # ISO UTC date.
                'name': str, # Assignment name.
                'is_lti': bool, # Is this an LTI assignment.
                'course': models.Course, # Course of this assignment.
                'cgignore': str, # The cginore of this assignment.
                'whitespace_linter': bool, # Has the whitespace linter
                                           # run on this assignment.
                'done_type': str, # The kind of reminder that will be sent.
                                  # If you don't have the permission to see
                                  # this it will always be `null`. If this is
                                  # not set it will also be `null`.
                'reminder_time': str, # ISO UTC date. This will be `null` if
                                      # you don't have the permission to see
                                      # this or if it is unset.
                'fixed_max_rubric_points': float, # The fixed value for the
                                                  # maximum that can be
                                                  # achieved in a rubric. This
                                                  # can be higher and lower
                                                  # than the actual max. Will
                                                  # be `null` if unset.
                'max_grade': float, # The maximum grade you can get for this
                                    # assignment. This is based around the idea
                                    # that a 10 is a 'perfect' score. So if
                                    # this value is 12 a user can score 2
                                    # additional bonus points. If this value is
                                    # `null` it is unset and regarded as a 10.
            }

        :returns: An object as described above.

        .. todo:: Remove 'description' field from Assignment model.
        """
        res = {
            'id': self.id,
            'state': self.state_name,
            'description': self.description,
            'created_at': self.created_at and self.created_at.isoformat(),
            'deadline': self.deadline and self.deadline.isoformat(),
            'name': self.name,
            'is_lti': self.is_lti,
            'course': self.course,
            'cgignore': self.cgignore,
            'whitespace_linter': self.whitespace_linter,
            'done_type': None,
            'done_email': None,
            'reminder_time': None,
            'fixed_max_rubric_points': self.fixed_max_rubric_points,
            'max_grade': self._max_grade,
        }

        try:
            psef.auth.ensure_permission(
                CoursePermission.can_grade_work,
                self.course_id,
            )
            if self.done_email is not None:
                res['done_email'] = self.done_email
            if self.done_type is not None:
                res['done_type'] = self.done_type.name
            if self.reminder_email_time is not None:
                res['reminder_time'] = self.reminder_email_time.isoformat()
        except PermissionException:
            pass

        return res

    def set_state(self, state: str) -> None:
        """Update the current state (class:`_AssignmentStateEnum`).

        You can update the state to hidden, done or open. A assignment can not
        be updated to 'submitting' or 'grading' as this is an assignment with
        state of 'open' and, respectively, a deadline before or after the
        current time.

        :param state: The new state, can be 'hidden', 'done' or 'open'
        :returns: Nothing
        """
        if state == 'open':
            self.state = _AssignmentStateEnum.open
        elif state == 'hidden':
            self.state = _AssignmentStateEnum.hidden
        elif state == 'done':
            self.state = _AssignmentStateEnum.done
            if self.lti_outcome_service_url is not None:
                self._submit_grades()
        else:
            raise InvalidAssignmentState(f'{state} is not a valid state')

    def get_from_latest_submissions(self, *to_query: T) -> '_MyQuery[T]':
        """Get the given fields from all last submitted submissions.

        :param to_query: The field to get from the last submitted submissions.
        :returns: A query object with the given fields selected from the last
            submissions.
        """
        sub = db.session.query(
            Work.user_id.label('user_id'),  # type: ignore
            func.max(Work.created_at).label('max_date')
        ).filter_by(assignment_id=self.id).group_by(Work.user_id
                                                    ).subquery('sub')
        return db.session.query(*to_query).select_from(Work).join(  # type: ignore
            sub,
            and_(
                sub.c.user_id == Work.user_id,
                sub.c.max_date == Work.created_at
            )
        ).filter(Work.assignment_id == self.id)

    def get_all_latest_submissions(self) -> '_MyQuery[Work]':
        """Get a list of all the latest submissions (:class:`Work`) by each
        :class:`User` who has submitted at least one work for this assignment.

        :returns: The latest submissions.
        """
        # get_from_latest_submissions uses SQLAlchemy magic that MyPy cannot
        # encode.
        return self.get_from_latest_submissions(t.cast(Work, Work))

    def get_divided_amount_missing(
        self
    ) -> t.Tuple[t.Mapping[int, float], t.Callable[[int], t.
                                                   Mapping[int, float]]]:
        """Get a mapping between user and the amount of submissions that they
        should be assigned but are not.

        For example if we have two graders, John and Dorian that respectively
        have the weights 1 and 1 assigned. Lets say we have three submissions
        divided in such a way that John has to grade 2 and Dorian has to grade
        one, then our function we return that John is missing -0.5 submissions
        and Dorian is missing 0.5.

        .. note::

            If ``self.assigned_graders`` is empty this function and its
            recalculate will always return an empty directory.

        :returns: A mapping between user int and the amount missing as
            described above. Furthermore it returns a function that can be used
            to recalculate this mapping by given it the user id of the user
            that was assigned a submission.
        """
        if not self.assigned_graders:
            return {}, lambda _: {}

        total_weight = sum(w.weight for w in self.assigned_graders.values())

        amount_subs: int
        amount_subs = self.get_from_latest_submissions(  # type: ignore
            func.count(),
        ).scalar()

        divided_amount: t.MutableMapping[int, float] = defaultdict(float)
        for u_id, amount in self.get_from_latest_submissions(  # type: ignore
            Work.assigned_to, func.count()
        ).group_by(Work.assigned_to):
            divided_amount[u_id] = amount

        missing = {}
        for user_id, assigned in self.assigned_graders.items():
            missing[user_id] = (assigned.weight / total_weight *
                                amount_subs) - divided_amount[user_id]

        def __recalculate(user_id: int) -> t.MutableMapping[int, float]:
            nonlocal amount_subs

            amount_subs += 1
            divided_amount[user_id] += 1
            missing = {}

            for assigned_user_id, assigned in self.assigned_graders.items():
                missing[assigned_user_id] = (
                    assigned.weight / total_weight * amount_subs
                ) - divided_amount[assigned_user_id]

            return missing

        return missing, __recalculate

    def _weights_changed(self, user_weights: t.Sequence[t.Tuple[User, float]]
                         ) -> bool:
        """Check if the given users and their weights have changed since the
        last division.

        :param user_weights: A list of tuples that map users and the weights.
            The weights are used to determine how many submissions should be
            assigned to a single user.
        :returns: If the weights have changed.
        """
        if len(user_weights) == len(self.assigned_graders):
            for user, weight in user_weights:
                if (
                    user.id not in self.assigned_graders or
                    self.assigned_graders[user.id].weight != weight
                ):
                    break
            else:
                return False

        return True

    def divide_submissions(
        self, user_weights: t.Sequence[t.Tuple[User, float]]
    ) -> None:
        """Divide all newest submissions for this assignment between the given
        users.

        This methods prefers to keep submissions assigned to the same grader as
        much as possible. To get completely new and random assignments first
        clear all old assignments.

        :param user_weights: A list of tuples that map users and the weights.
            The weights are used to determine how many submissions should be
            assigned to a single user.
        :returns: Nothing.
        """
        # First check if there were changes in the weights
        if not self._weights_changed(user_weights):
            return

        submissions = self.get_all_latest_submissions().all()
        shuffle(submissions)

        counts: t.MutableMapping[int, int] = defaultdict(int)
        user_submissions: t.MutableMapping[t.Optional[int], t.List[Work]]
        user_submissions = defaultdict(list)

        # Remove all users not in user_weights
        new_users = set(u.id for u, _ in user_weights)
        for submission in submissions:
            if submission.assigned_to not in new_users:
                submission.assigned_to = None
            else:
                counts[submission.assigned_to] += 1
            user_submissions[submission.assigned_to].append(submission)

        new_total_weight = sum(weight for _, weight in user_weights)

        negative_weights, positive_weights = {}, {}
        for user, new_weight in user_weights:
            percentage = (new_weight / new_total_weight)
            new = percentage * len(submissions)

            if new < counts[user.id]:
                negative_weights[user.id] = counts[user.id] - new
            elif new > counts[user.id]:
                positive_weights[user.id] = new - counts[user.id]

        for user_id, delete_amount in negative_weights.items():
            for sub in user_submissions[user_id][:round(delete_amount)]:
                user_submissions[None].append(sub)

        to_assign: t.List[int] = []
        if positive_weights:
            ratio = math.ceil(1 / min(1, max(positive_weights.values())))
            for user_id, new_amount in positive_weights.items():
                to_assign += [user_id] * round(new_amount * ratio)

        shuffle(to_assign)
        newly_assigned: t.Set[int] = set()
        for sub, user_id in zip(user_submissions[None], cycle(to_assign)):
            sub.assigned_to = user_id
            newly_assigned.add(user_id)

        self.set_graders_to_not_done(
            list(newly_assigned),
            send_mail=True,
            ignore_errors=True,
        )

        self.assigned_graders = {}
        for user, weight in user_weights:
            db.session.add(
                AssignmentAssignedGrader(
                    weight=weight, user_id=user.id, assignment=self
                )
            )

    def get_all_graders(
        self, sort: bool = True
    ) -> '_MyQuery[t.Tuple[str, int, bool]]':
        """Get all graders for this assignment.

        The graders are retrieved from the database using a single query. The
        return value is a query with three items selected: the first is the
        name of the grader, the second is the database id of the user object
        of grader and the third and last is a boolean indicating if this grader
        is done grading. You can use this query as an iterator.

        :param sort: Should the graders be sorted by name.
        :returns: A query with items selected as described above.
        """
        done_graders = db.session.query(
            t.cast(DbColumn[str], User.name).label("name"),
            t.cast(DbColumn[int], User.id).label("id"),
            t.cast(
                DbColumn[bool],
                ~t.cast(DbColumn[int], AssignmentGraderDone.user_id).is_(None)
            ).label("done"),
            t.cast(DbColumn[int], user_course.c.course_id).label("course_id"),
        ).join(
            AssignmentGraderDone,
            and_(
                User.id == AssignmentGraderDone.user_id,
                AssignmentGraderDone.assignment_id == self.id,
            ),
            isouter=True
        ).join(
            user_course,
            User.id == user_course.c.user_id,
        ).subquery('done_graders')

        graders = db.session.query(course_permissions.c.course_role_id).join(
            CourseRole,
            CourseRole.id == course_permissions.c.course_role_id,
        ).join(
            Permission,
            course_permissions.c.permission_id == Permission.id,
        ).filter(
            CourseRole.course_id == self.course_id,
            Permission.value == CoursePermission.can_grade_work,
        ).subquery('graders')

        res = db.session.query(
            t.cast(str, done_graders.c.name),
            t.cast(int, done_graders.c.id),
            t.cast(bool, done_graders.c.done),
        ).join(graders, done_graders.c.course_id == graders.c.course_role_id)

        if sort:
            res = res.order_by(func.lower(done_graders.c.name))

        return res


class Snippet(Base):
    """Describes a :class:`User` specified mapping from a keyword to some
    string.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['Snippet']]
    __tablename__ = 'Snippet'
    id: int = db.Column('id', db.Integer, primary_key=True)
    key: str = db.Column('key', db.Unicode, nullable=False)
    value: str = db.Column('value', db.Unicode, nullable=False)
    user_id: int = db.Column('User_id', db.Integer, db.ForeignKey('User.id'))

    user: User = db.relationship('User', foreign_keys=user_id)

    @classmethod
    def get_all_snippets(cls: t.Type['Snippet'],
                         user: User) -> t.Sequence['Snippet']:
        """Return all snippets of the given :class:`User`.

        :param user: The user to get the snippets for.
        :returns: List of all snippets of the user.
        """
        return cls.query.filter_by(user_id=user.id).order_by('id').all()

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'key': self.key,
            'value': self.value,
            'id': self.id,
        }


class RubricItem(Base):
    """This class holds the information about a single option/item in a
    :class:`RubricRow`.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['RubricItem']]

    __tablename__ = 'RubricItem'

    id: int = db.Column('id', db.Integer, primary_key=True)
    rubricrow_id: int = db.Column(
        'Rubricrow_id', db.Integer,
        db.ForeignKey('RubricRow.id', ondelete='CASCADE')
    )
    header: str = db.Column('header', db.Unicode, default='')
    description: str = db.Column('description', db.Unicode, default='')
    points: float = db.Column('points', db.Float)

    # This variable is generated from the backref from RubricRow
    rubricrow: 'RubricRow'

    class JSONBaseSerialization(TypedDict, total=True):
        """The base serialization of a rubric item.
        """
        description: str
        header: str
        points: numbers.Real

    class JSONSerialization(JSONBaseSerialization, total=True):
        id: int

    def __to_json__(self) -> 'RubricItem.JSONSerialization':
        """Creates a JSON serializable representation of this object.
        """
        return {
            'id': self.id,
            'description': self.description,
            'header': self.header,
            # A float is a ``Real``, mypy issue:
            # https://github.com/python/mypy/issues/2636
            'points': t.cast(numbers.Real, self.points),
        }


class RubricRow(Base):
    """Describes a row of some rubric.

    This class forms the link between :class:`Assignment` and
    :class:`RubricItem` and holds information about the row.

    :ivar ~.RubricRow.assignment_id: The assignment id of the assignment that
        belows to this rubric row.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['RubricRow']]
    __tablename__ = 'RubricRow'
    id: int = db.Column('id', db.Integer, primary_key=True)
    assignment_id: int = db.Column(
        'Assignment_id', db.Integer, db.ForeignKey('Assignment.id')
    )
    header: str = db.Column('header', db.Unicode)
    description: str = db.Column('description', db.Unicode, default='')
    created_at = db.Column(
        'created_at', db.DateTime, default=datetime.datetime.utcnow
    )
    items = db.relationship(
        "RubricItem",
        backref="rubricrow",
        cascade='delete-orphan, delete, save-update',
        order_by='asc(RubricItem.points)',
    )  # type: t.MutableSequence[RubricItem]

    # This is for the type checker and is available because of a backref.
    assignment: Assignment

    @property
    def is_valid(self) -> bool:
        """Check if the current row is valid.

        :returns: ``False`` if the row has no items or if the max points of the
            items is not > 0.
        """
        if not self.items:
            return False
        return max(it.points for it in self.items) >= 0

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'id': self.id,
            'header': self.header,
            'description': self.description,
            'items': self.items,
        }

    def _get_item(self, item_id: int) -> t.Optional['RubricItem']:
        """Get a rubric item from this row by id.

        :param item_id: The id of the item to get.
        :returns: The item found or ``None`` if the row didn't contain any item
            with the given id.
        """
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def update_items_from_json(
        self, items: t.List[RubricItem.JSONBaseSerialization]
    ) -> None:
        """Update the items of this row in place.

        .. warning::

            All items not present in the given ``items`` list will be deleted
            from the rubric row.

        :param items: The items (:class:`.RubricItem`) that should be added or
            updated. If ``id`` is in an item it should be an ``int`` and the
            rubric item with the corresponding ``id`` will be updated instead
            of added.
        :returns: Nothing.
        """
        # We store all new items in this list and not `self.items` as we need
        # to search for items in `self.items` if a rubric item needs to be
        # updated (instead of added).
        new_items: t.List[RubricItem] = []

        for item in items:
            item_description: str = item['description']
            item_header: str = item['header']
            points: numbers.Real = item['points']

            if 'id' in item:
                psef.helpers.ensure_keys_in_dict(item, [('id', int)])
                item_id = t.cast(int, item['id'])  # type: ignore
                rubric_item = self._get_item(item_id)
                if rubric_item is None:
                    raise psef.errors.APIException(
                        "The requested rubric item is not present in this row",
                        f'The row "{self.id}" doesn\'t contain "{item_id}"',
                        psef.errors.APICodes.OBJECT_NOT_FOUND, 404
                    )

                rubric_item.header = item_header
                rubric_item.description = item_description
                rubric_item.points = float(points)
            else:
                rubric_item = RubricItem(
                    rubricrow=self,
                    description=item_description,
                    header=item_header,
                    points=points
                )

            new_items.append(rubric_item)

        self.items = new_items

    def update_from_json(
        self, header: str, description: str,
        items: t.List[RubricItem.JSONBaseSerialization]
    ) -> None:
        """Update this rubric in place.

        .. warning::

            All items not present in the given ``items`` list will be deleted
            from the rubric row.

        :param header: The new header of the row.
        :param description: The new description of the row.
        :param items: The items that should be in this row (see warning). The
            format is the same as the items passed to
            :meth:`.RubricRow.update_items_from_json`.
        :returns: Nothing.
        """
        self.header = header
        self.description = description
        self.update_items_from_json(items)

    @classmethod
    def create_from_json(
        cls: t.Type['RubricRow'], assig: Assignment, header: str,
        description: str, items: t.List[RubricItem.JSONBaseSerialization]
    ) -> 'RubricRow':
        """Create a new rubric row for an assignment.

        :param assig: The assignment to add the rubric row to
        :param header: The name of the new rubric row.
        :param description: The description of the new rubric row.
        :param items: The items that should be added to this row. The format is
            the same as the items passed to
            :meth:`.RubricRow.update_items_from_json`.
        :returns: The newly created row.
        """
        self = cls(assignment=assig, header=header, description=description)
        self.update_items_from_json(items)

        return self


class PlagiarismRun(Base):
    """Describes a run for a plagiarism provider.

    :ivar ~.PlagiarismRun.state: The state this run is in.
    :ivar ~.PlagiarismRun.log: The log on ``stdout`` and ``stderr`` we got from
        running the plagiarism provider. This is only available if the
        ``state`` is ``done`` or ``crashed``.
    :ivar ~.PlagiarismRun.json_config: The config used for this run saved in a
        sorted association list.
    :ivar ~.PlagiarismRun.assignment_id: The id of the assignment this
        belongs to.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['PlagiarismRun']]
    __tablename__ = 'PlagiarismRun'

    id = db.Column('id', db.Integer, primary_key=True)
    state: PlagiarismState = db.Column(
        'state',
        db.Enum(PlagiarismState),
        default=PlagiarismState.running,
        nullable=False
    )
    log: t.Optional[str] = orm.deferred(
        db.Column('log', db.Unicode, nullable=True)
    )
    json_config = db.Column('json_config', db.Unicode, nullable=False)
    assignment_id: int = db.Column(
        'assignment_id', db.Integer, db.ForeignKey('Assignment.id')
    )
    created_at: datetime.datetime = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )

    assignment = db.relationship(
        'Assignment', foreign_keys=assignment_id, lazy='joined'
    )  # type: 'Assignment'

    cases: t.List['PlagiarismCase'] = db.relationship(
        "PlagiarismCase",
        backref=db.backref('plagiarism_run'),
        order_by='desc(PlagiarismCase.match_avg)'
    )

    @property
    def provider_name(self) -> str:
        """
        :returns: The provider name of this plagiarism run.
        """
        for key, val in json.loads(self.json_config):
            if key == 'provider':
                return val
        # This can never happen
        raise KeyError  # pragma: no cover

    def __to_json__(self) -> t.Mapping[str, object]:
        """Creates a JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'id': int, # The id of this run.
                'state': str, # The name of the current state this run is in.
                'provider_name': str, # The name of the provider used in this
                                      # run.
                'config': t.List[t.List[str]], # A sorted association list with
                                               # the config used for this run.
                'created_at': str, # ISO UTC date.
                'assignment': Assignment, # The assignment this run belongs to.
            }

        :returns: A object as described above.
        """
        return {
            'id': self.id,
            'state': self.state.name,
            'provider_name': self.provider_name,
            'config': json.loads(self.json_config),
            'created_at': self.created_at.isoformat(),
            'assignment': self.assignment,
        }

    def __extended_to_json__(self) -> t.Mapping[str, object]:
        """Create a extended JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'cases': t.List[PlagiarismCase], # The cases of possible
                                                 # plagiarism found during this
                                                 # run.
                'log': str, # The log on stderr and stdout of this run.
                **self.__to_json__(),
            }

        :returns: A object as described above.
        """
        return {
            'cases': self.cases,
            'log': self.log,
            **self.__to_json__(),
        }


class PlagiarismCase(Base):
    """Describe a case of possible plagiarism.

    :ivar ~.PlagiarismCase.work1_id: The id of the first work to be associated
        with this possible case of plagiarism.
    :ivar ~.PlagiarismCase.work2_id: The id of the second work to be associated
        with this possible case of plagiarism.
    :ivar ~.PlagiarismCase.created_at: When was this case created.
    :ivar ~.PlagiarismCase.plagiarism_run_id: The :class:`.PlagiarismRun` in
        which this case was discovered.
    :ivar ~.PlagiarismCase.match_avg: The average similarity between the two
        matches. What the value exactly means differs per provider.
    :ivar ~.PlagiarismCase.match_max: The maximum similarity between the two
        matches. What the value exactly means differs per provider.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['PlagiarismCase']]

    __tablename__ = 'PlagiarismCase'
    id = db.Column('id', db.Integer, primary_key=True)

    work1_id: int = db.Column(
        'work1_id', db.Integer, db.ForeignKey('Work.id', ondelete='CASCADE')
    )
    work2_id: int = db.Column(
        'work2_id', db.Integer, db.ForeignKey('Work.id', ondelete='CASCADE')
    )
    created_at: datetime.datetime = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )
    plagiarism_run_id = db.Column(
        'plagiarism_run_id', db.Integer,
        db.ForeignKey('PlagiarismRun.id', ondelete='CASCADE')
    )

    match_avg = db.Column('match_avg', db.Float, nullable=False)
    match_max = db.Column('match_max', db.Float, nullable=False)

    work1 = db.relationship(
        'Work', foreign_keys=work1_id, lazy='joined'
    )  # type: Work
    work2 = db.relationship(
        'Work', foreign_keys=work2_id, lazy='joined'
    )  # type: Work

    plagiarism_run: PlagiarismRun

    matches = db.relationship(
        "PlagiarismMatch",
        back_populates="plagiarism_case",
        cascade='all,delete',
        order_by='PlagiarismMatch.file1_id'
    )  # type: t.List['PlagiarismMatch']

    def __to_json__(self) -> t.Mapping[str, object]:
        """Creates a JSON serializable representation of this object.


        This object will look like this:

        The ``submissions`` field may be ``None`` and the assignments field may
        contain only partial information because of permissions issues.

        .. code:: python

            {
                'id': int, # The id of this case.
                'users': t.List[User], # The users of this plagiarism case.
                'match_avg': float, # The average similarity of this case.
                'match_max': float, # The maximum similarity of this case.
                'assignments': t.List[Assignment], # The two assignments of
                                                   # this case. These can
                                                   # differ!
                'submissions': t.List[Work], # The two submissions of this
                                             # case.
            }

        :returns: A object as described above.
        """
        data: t.MutableMapping[str, t.Any] = {
            'id': self.id,
            'users': [self.work1.user, self.work2.user],
            'match_avg': self.match_avg,
            'match_max': self.match_max,
            'assignments': [self.work1.assignment, self.work2.assignment],
            'submissions': [self.work1, self.work2],
        }
        try:
            psef.auth.ensure_can_see_plagiarims_case(
                self, assignments=True, submissions=False
            )
        except PermissionException:
            other_work_index = (
                1 if
                self.work1.assignment_id == self.plagiarism_run.assignment_id
                else 0
            )
            assig = data['assignments'][other_work_index]
            data['assignments'][other_work_index] = {
                'name': assig.name,
                'course': {
                    'name': assig.course.name
                }
            }

        # Make sure we may actually see this file.
        try:
            psef.auth.ensure_can_see_plagiarims_case(
                self, assignments=False, submissions=True
            )
        except PermissionException:
            data['submissions'] = None

        return data

    def __extended_to_json__(self) -> t.Mapping[str, object]:
        """Create a extended JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'matches': t.List[PlagiarismMatch], # The list of matches that
                                                    # are part of this case.
                **self.__to_json__(),
            }

        :returns: A object as described above.
        """
        return {
            'matches': self.matches,
            **self.__to_json__(),
        }


class PlagiarismMatch(Base):
    """Describes a possible plagiarism match between two files.

    :ivar ~.PlagiarismMatch.file1_id: The id of the first file associated with
        this match.
    :ivar ~.PlagiarismMatch.file1_start: The start position of the first file
        associated with this match. This position can be (and probably is) a
        line but it could also be a byte offset.
    :ivar ~.PlagiarismMatch.file1_end: The end position of the first file
        associated with this match. This position can be (and probably is) a
        line but it could also be a byte offset.
    :ivar ~.PlagiarismMatch.file2_id: Same as ``file1_id`` but of the second
        file.
    :ivar ~.PlagiarismMatch.file2_start: Same as ``file1_start`` but for the
        second file.
    :ivar ~.PlagiarismMatch.file2_end: Same as ``file1_end`` but for the second
        file.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['PlagiarismMatch']]

    __tablename__ = 'PlagiarismMatch'
    id = db.Column('id', db.Integer, primary_key=True)  # type: int

    file1_id = db.Column(
        'file1_id', db.Integer, db.ForeignKey('File.id', ondelete='CASCADE')
    )
    file2_id = db.Column(
        'file2_id', db.Integer, db.ForeignKey('File.id', ondelete='CASCADE')
    )

    file1_start = db.Column('file1_start', db.Integer, nullable=False)
    file1_end = db.Column('file1_end', db.Integer, nullable=False)
    file2_start = db.Column('file2_start', db.Integer, nullable=False)
    file2_end = db.Column('file2_end', db.Integer, nullable=False)

    plagiarism_case_id = db.Column(
        'plagiarism_case_id',
        db.Integer,
        db.ForeignKey('PlagiarismCase.id', ondelete='CASCADE'),
    )

    plagiarism_case: PlagiarismCase = db.relationship(
        "PlagiarismCase", back_populates="matches"
    )

    file1 = db.relationship(
        'File', foreign_keys=file1_id, lazy='joined'
    )  # type: File
    file2 = db.relationship(
        'File', foreign_keys=file2_id, lazy='joined'
    )  # type: File

    def __to_json__(self) -> t.Mapping[str, object]:
        """Creates a JSON serializable representation of this object.


        This object will look like this:

        .. code:: python

            {
                'id': int, # The id of this match.
                'files': t.List[File], # The files of this match
                'lines': t.List[t.Tuple[int]], # The tuple of ``(start, end)``
                                               # for both files that are
                                               # present this match.
            }

        :returns: A object as described above.
        """
        return {
            'id':
                self.id,
            'files': [self.file1, self.file2],
            'lines':
                [
                    (self.file1_start, self.file1_end),
                    (self.file2_start, self.file2_end)
                ],
        }

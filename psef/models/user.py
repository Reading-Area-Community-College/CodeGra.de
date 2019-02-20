"""This module defines a User.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import typing as t
from collections import defaultdict

import structlog
from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy_utils import PasswordType
from sqlalchemy.sql.expression import false
from sqlalchemy.orm.collections import attribute_mapped_collection

import psef

from . import UUID_LENGTH, Base, DbColumn, db, course, _MyQuery
from .role import Role, CourseRole
from .permission import Permission
from ..exceptions import APICodes, PermissionException
from .link_tables import user_course, course_permissions
from ..permissions import CoursePermission, GlobalPermission

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    # pylint: disable=unused-import,invalid-name
    from . import group as group_models
    from .assignment import AssignmentResult, AssignmentAssignedGrader
    hybrid_property = property
else:
    from sqlalchemy.ext.hybrid import hybrid_property  # type: ignore

logger = structlog.get_logger()


class User(Base):
    """This class describes a user of the system.

    :ivar ~.User.lti_user_id: The id of this user in a LTI consumer.
    :ivar ~.User.name: The name of this user.
    :ivar ~.User.role_id: The id of the role this user has.
    :ivar ~.User.courses: A mapping between course_id and course-role for all
        courses this user is currently enrolled.
    :ivar ~.User.email: The e-mail of this user.
    :ivar ~.User.virtual: Is this user an actual user of the site, or is it a
        virtual user.
    :ivar ~.User.password: The password of this user, it is automatically
        hashed.
    :ivar ~.User.assignment_results: The way this user can do LTI grade
        passback.
    :ivar ~.User.assignments_assigned: A mapping between assignment_ids and
        :py:class:`.AssignmentAssignedGrader` objects.
    :ivar reset_email_on_lti: Determines if the email should be reset on the
        next LTI launch.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['User']] = Base.query

    __tablename__ = "User"

    _id: int = db.Column('id', db.Integer, primary_key=True)

    @hybrid_property
    def id(self) -> int:
        """The id of the user
        """
        return self._id

    @id.setter
    def id(self, n_id: int) -> None:
        assert not hasattr(self, '_id') or self._id is None
        self._id = n_id

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
    _username: str = db.Column(
        'username',
        db.Unicode,
        unique=True,
        nullable=False,
        index=True,
    )

    @hybrid_property
    def username(self) -> str:
        """The username of the user
        """
        return self._username

    @username.setter
    def username(self, username: str) -> None:
        assert not hasattr(self, '_username') or self._username is None
        self._username = username

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
        int, 'AssignmentAssignedGrader'] = db.relationship(
            'AssignmentAssignedGrader',
            collection_class=attribute_mapped_collection('assignment_id'),
            backref=db.backref('user', lazy='select')
        )

    assignment_results: t.MutableMapping[
        int, 'AssignmentResult'] = db.relationship(
            'AssignmentResult',
            collection_class=attribute_mapped_collection('assignment_id'),
            backref=db.backref('user', lazy='select')
        )

    group = db.relationship(
        'Group',
        back_populates='virtual_user',
        lazy='selectin',
        uselist=False,
    )  # type: group_models.Group

    role: Role = db.relationship('Role', foreign_keys=role_id, lazy='select')

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __ne__(self, other: object) -> bool:  # pragma: no cover
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
        self, permission: CoursePermission, course_id: t.Union[int, 'course.Course']
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
        course_id: t.Union['course.Course', int, None] = None
    ) -> bool:
        """Check whether this user has the specified global or course
        :class:`.Permission`.

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

            if isinstance(course_id, course.Course):
                course_id = course_id.id

            if course_id in self.courses:
                return self.courses[course_id].has_permission(permission)
            return False

    def get_all_permissions_in_courses(
        self,
    ) -> t.Mapping[int, t.Mapping[CoursePermission, bool]]:
        """Get all permissions for all courses the current user is enrolled in

        :returns: A mapping from course id to a mapping from
            :py:class:`.CoursePermission` to a boolean indicating if the
            current user has this permission.
        """
        permission_links = db.session.query(
            user_course.c.course_id, Permission.get_name_column()
        ).join(User, User.id == user_course.c.user_id).filter(
            user_course.c.user_id == self.id
        ).join(
            course_permissions,
            course_permissions.c.course_role_id == user_course.c.course_id
        ).join(
            Permission,
            course_permissions.c.permission_id == Permission.id,
            isouter=True
        )
        lookup: t.Mapping[int, t.Set[int]] = defaultdict(set)
        for course_role_id, perm_name in permission_links:
            lookup[course_role_id].add(perm_name)

        out: t.MutableMapping[int, t.Mapping[CoursePermission, bool]] = {}
        for course_id, course_role in self.courses.items():
            perms = lookup[course_role.id]
            out[course_id] = {
                p: (p.name in perms) ^ p.value.default_value
                for p in CoursePermission
            }
        return out

    def get_permissions_in_courses(
        self,
        wanted_perms: t.Sequence[CoursePermission],
    ) -> t.Mapping[int, t.Mapping[CoursePermission, bool]]:
        """Check for specific :class:`.Permission`s in all courses
        (:class:`.course.Course`) the user is enrolled in.

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
                'username': str, # The username of this user.
                'group': t.Optional[Group], # The group that this user
                                            # represents.
            }

        :returns: An object as described above.
        """
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'group': self.group,
        }

    def __extended_to_json__(self) -> t.Mapping[str, t.Any]:
        """Create a extended JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'email': str, # The email of this user.
                'hidden': bool, # indicating if this user can once
                                # see hidden assignments.
                **self.__to_json__()
            }

        :returns: A object as described above.
        """
        is_self = psef.current_user and psef.current_user.id == self.id
        return {
            'email': self.email if is_self else '<REDACTED>',
            "hidden": self.can_see_hidden,
            **self.__to_json__(),
        }

    def has_course_permission_once(self, perm: CoursePermission) -> bool:
        """Check whether this user has the specified course
        :class:`.Permission` in at least one enrolled :class:`.course.Course`.

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
        course_id: t.Union['course.Course', int],
    ) -> t.Mapping[CoursePermission, bool]:
        ...  # pylint: disable=pointless-statement

    def get_all_permissions(  # pylint: disable=function-redefined
        self, course_id: t.Union['course.Course', int, None] = None
    ) -> t.Union[t.Mapping[CoursePermission, bool], t.
                 Mapping[GlobalPermission, bool]]:
        """Get all global permissions (:class:`.Permission`) of this user or
        all course permissions of the user in a specific
        :class:`.course.Course`.

        :param course_id: The course or course id

        :returns: A name boolean mapping where the name is the name of the
                  permission and the value indicates if this user has this
                  permission.
        """
        assert not self.virtual

        if isinstance(course_id, course.Course):
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

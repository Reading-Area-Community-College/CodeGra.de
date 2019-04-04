"""This module defines a Course.

SPDX-License-Identifier: AGPL-3.0-only
"""
import copy
import uuid
import typing as t
import datetime

import psef

from . import UUID_LENGTH, Base, DbColumn, db, _MyQuery
from .role import CourseRole
from .user import User
from .work import Work
from .assignment import Assignment
from .link_tables import user_course
from ..permissions import CoursePermission

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import,cyclic-import
    from .lti_provider import LTIProvider
    from .group import GroupSet


class CourseSnippet(Base):
    """Describes a mapping from a keyword to a replacement text that is shared
    amongst the teachers and TAs of the course.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['CourseSnippet']] = Base.query
    __tablename__ = 'CourseSnippet'
    id: int = db.Column('id', db.Integer, primary_key=True)
    key: str = db.Column('key', db.Unicode, nullable=False)
    value: str = db.Column('value', db.Unicode, nullable=False)
    course_id: int = db.Column(
        'course_id', db.Integer, db.ForeignKey('Course.id'), nullable=False
    )
    created_at: datetime.datetime = db.Column(
        'created_at',
        db.DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    course: 'Course' = db.relationship(
        'Course',
        foreign_keys=course_id,
        back_populates='snippets',
        innerjoin=True,
    )

    __table_args__ = (db.UniqueConstraint(course_id, key), )

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'key': self.key,
            'value': self.value,
            'id': self.id,
        }


class Course(Base):
    """This class describes a course.

    A course can hold a collection of :class:`.Assignment` objects.

    :param name: The name of the course
    :param lti_course_id: The id of the course in LTI
    :param lti_provider: The LTI provider
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['Course']] = Base.query
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
    lti_provider: 'LTIProvider' = db.relationship("LTIProvider")

    virtual: bool = db.Column(
        'virtual', db.Boolean, default=False, nullable=False
    )

    group_sets: t.MutableSequence['GroupSet'] = db.relationship(
        "GroupSet",
        back_populates="course",
        cascade='all,delete',
        uselist=True,
        order_by='GroupSet.created_at'
    )

    snippets: t.MutableSequence['CourseSnippet'] = db.relationship(
        'CourseSnippet',
        back_populates='course',
        cascade='all,delete',
        uselist=True,
        lazy='select',
        order_by='CourseSnippet.created_at',
    )

    assignments = db.relationship(
        "Assignment", back_populates="course", cascade='all,delete'
    )  # type: t.MutableSequence[Assignment]

    def __init__(
        self,
        name: str = None,
        lti_course_id: str = None,
        lti_provider: 'LTIProvider' = None,
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
        assigs: t.Iterable[Assignment] = self.assignments
        if not psef.current_user.has_permission(
            CoursePermission.can_see_hidden_assignments, self.id
        ):
            assigs = (a for a in assigs if not a.is_hidden)
        return sorted(
            assigs, key=lambda item: item.deadline or datetime.datetime.max
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
        for child in copy.copy(tree.values):
            # This is done before we wrap single files to get better author
            # names.
            work = Work(
                assignment=assig, user=User.create_virtual_user(child.name)
            )

            subdir: psef.files.ExtractFileTreeBase
            if isinstance(child, psef.files.ExtractFileTreeFile):
                subdir = psef.files.ExtractFileTreeDirectory(
                    name='top', values=[child], parent=None
                )
                tree.forget_child(child)
                subdir.add_child(child)
            else:
                assert isinstance(child, psef.files.ExtractFileTreeDirectory)
                subdir = child
            work.add_file_tree(subdir)
        return self

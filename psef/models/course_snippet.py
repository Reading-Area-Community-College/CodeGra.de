"""This module defines a CourseSnippet.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t

from . import Base, db, _MyQuery
from .course import Course


class CourseSnippet(Base):
    """Describes a :class:`.User` specified mapping from a keyword to some
    string.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['CourseSnippet']] = Base.query
    __tablename__ = 'CourseSnippet'
    id: int = db.Column('id', db.Integer, primary_key=True)
    key: str = db.Column('key', db.Unicode, nullable=False)
    value: str = db.Column('value', db.Unicode, nullable=False)
    course_id: int = db.Column(
        'Course_id', db.Integer, db.ForeignKey('Course.id')
    )

    course: Course = db.relationship('Course', foreign_keys=course_id)

    @classmethod
    def get_course_snippets(cls: t.Type['CourseSnippet'],
                            course: Course) -> t.Sequence['CourseSnippet']:
        """Return all snippets of the given :class:`.Course`.

        :param user: The user to get the snippets for.
        :returns: List of all snippets of the user.
        """
        return cls.query.filter_by(course_id=course.id).order_by('id').all()

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'key': self.key,
            'value': self.value,
            'id': self.id,
        }

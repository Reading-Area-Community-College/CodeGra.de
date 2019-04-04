"""This module defines all models needed for an assignment.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import json
import math
import uuid
import typing as t
import datetime
from random import shuffle
from operator import itemgetter
from itertools import cycle
from collections import Counter, defaultdict

from sqlalchemy.orm import validates
from mypy_extensions import DefaultArg
from sqlalchemy.sql.expression import and_, func
from sqlalchemy.orm.collections import attribute_mapped_collection

import psef

from . import UUID_LENGTH, Base, DbColumn, db
from . import user as user_models
from . import work as work_models
from . import group as group_models
from . import linter as linter_models
from . import _MyQuery
from .. import auth, ignore, helpers
from .role import CourseRole
from .rubric import RubricRow, RubricItem
from .permission import Permission
from ..exceptions import PermissionException, InvalidAssignmentState
from .link_tables import user_course, work_rubric_item, course_permissions
from ..permissions import CoursePermission as CPerm

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import
    from . import course as course_models
    cached_property = property  # pylint: disable=invalid-name
else:
    from werkzeug.utils import cached_property

T = t.TypeVar('T')


@enum.unique
class _AssignmentStateEnum(enum.IntEnum):
    """Describes in what state an :class:`.Assignment` is.
    """
    hidden = 0
    open = 1
    done = 2


class AssignmentAssignedGrader(Base):
    """The class creates the link between an :class:`.user_models.User` and an
    :class:`.Assignment`.

    The user linked to the assignment is an assigned grader. In this link the
    weight is the weight this user was given when assigning.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['AssignmentAssignedGrader']]
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
    """This class creates the link between an :class:`.user_models.User` and an
    :class:`.Assignment` that exists only when the grader is done.

    If a user is linked to the assignment this indicates that this user is done
    with grading.

    :ivar ~.AssignmentGraderDone.user_id: The id of the user that is linked.
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


class AssignmentDoneType(enum.IntEnum):
    """Describes what type of reminder should be sent.

    :param none: Nobody should be e-mailed.
    :param assigned_only: Only graders that are assigned will be notified.
    :param all_graders: All users that have the permission to grade.
    """
    assigned_only: int = 1
    all_graders: int = 2


class AssignmentLinter(Base):
    """The class is used when a linter (see :py:mod:`psef.linters`) is used on
    a :class:`.Assignment`.

    Every :class:`.work_models.Work` that is tested is attached by a
    :class:`.linter_models.LinterInstance`.

    The name identifies which :class:`.linter_models.Linter` is used.

    :ivar ~.AssignmentLinter.name: The name of the linter which is the
        `__name__` of a subclass of :py:class:`.linter_models.Linter`.
    :ivar tests: All the linter instances for this linter, this are the
        recordings of the running of the actual linter (so in the case of the
        :py:class:`.Flake8` metadata about the `flake8` program).
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
    )  # type: t.Sequence[linter_models.LinterInstance]
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
        return self._amount_linters_in_state(linter_models.LinterState.crashed)

    @property
    def linters_done(self) -> int:
        """The amount of linters that are done.
        """
        return self._amount_linters_in_state(linter_models.LinterState.done)

    @property
    def linters_running(self) -> int:
        """The amount of linters that are running.
        """
        return self._amount_linters_in_state(linter_models.LinterState.running)

    def _amount_linters_in_state(
        self, state: 'linter_models.LinterState'
    ) -> int:
        return linter_models.LinterInstance.query.filter_by(
            tester_id=self.id, state=state
        ).count()

    def __extended_to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates an extended JSON serializable representation of this
        assignment linter.

        This object will look like this:

        .. code:: python

            {
                'tests': t.List[LinterInstance], # The tests done by this
                                                 # assignment linter.
                'id': str, # The id of this assignment linter.
                'name': str, # The name.
            }

        :returns: An object as described above.
        """
        return {
            'tests': self.tests,
            'id': self.id,
            'name': self.name,
        }

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Returns the JSON serializable representation of this class.

        This representation also returns a count of the
        :class:`.linter_models.LinterState` of the attached
        :class:`.linter_models.LinterInstance` objects.

        :returns: A dict containing JSON serializable representations of the
            attributes and the test state counts of this AssignmentLinter.
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
        """Create a new instance of this class for a given :class:`.Assignment`
        with a given :py:class:`.linter_models.Linter`

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
                self.tests.append(linter_models.LinterInstance(work, self))

        return self


class AssignmentResult(Base):
    """The class creates the link between an :class:`.user_models.User` and an
    :class:`.Assignment` in the database and the external users LIS sourcedid.

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


class Assignment(Base):  # pylint: disable=too-many-public-methods
    """This class describes a :class:`.course_models.Course` specific assignment.

    :ivar ~.Assignment.name: The name of the assignment.
    :ivar ~.Assignment.cgignore: The .cgignore file of this assignment.
    :ivar ~.Assignment.state: The current state the assignment is in.
    :ivar ~.Assignment.description: UNUSED
    :ivar ~.Assignment.course: The course this assignment belongs to.
    :ivar ~.Assignment.created_at: The date this assignment was added.
    :ivar ~.Assignment.deadline: The deadline of this assignment.
    :ivar ~.Assignment._mail_task_id: This is the id of the current task that
        will email all the TA's to hurry up with grading.
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
    _cgignore: t.Optional[str] = db.Column('cgignore', db.Unicode)
    _cgignore_version: t.Optional[str] = db.Column(
        'cgignore_version', db.Unicode
    )
    state: _AssignmentStateEnum = db.Column(
        'state',
        db.Enum(_AssignmentStateEnum),
        default=_AssignmentStateEnum.hidden,
        nullable=False
    )
    description: str = db.Column('description', db.Unicode, default='')
    course_id: int = db.Column(
        'Course_id', db.Integer, db.ForeignKey('Course.id'), nullable=False
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
            cascade='delete-orphan, delete, save-update',
            collection_class=attribute_mapped_collection('user_id'),
            backref=db.backref('assignment', lazy='select')
        )
    division_parent_id: t.Optional[int] = db.Column(
        'division_parent_id',
        db.Integer,
        db.ForeignKey('Assignment.id'),
        nullable=True,
    )
    division_parent = db.relationship(
        'Assignment',
        back_populates='division_children',
        foreign_keys=division_parent_id,
        remote_side=[id],
        lazy='select',
    )  # type: t.Optional[Assignment]
    division_children = db.relationship(
        "Assignment",
        back_populates="division_parent",
        uselist=True,
        lazy='select',
    )  # type: t.MutableSequence[Assignment]

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

    course: 'course_models.Course' = db.relationship(
        'Course',
        foreign_keys=course_id,
        back_populates='assignments',
        lazy='joined',
        innerjoin=True,
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

    group_set_id: int = db.Column(
        'group_set_id',
        db.Integer,
        db.ForeignKey('GroupSet.id'),
        nullable=True,
    )

    group_set = db.relationship(
        'GroupSet',
        back_populates='assignments',
        cascade='all',
    )  # type: t.Optional['group_models.GroupSet']

    # This variable is available through a backref
    linters: t.Iterable['AssignmentLinter']

    # This variable is available through a backref
    submissions: t.Iterable['work_models.Work']

    @validates('group_set')
    def validate_group_set(
        self, _: str, group_set: t.Optional['group_models.GroupSet']
    ) -> t.Optional['group_models.GroupSet']:
        """Make sure the course id of the group set is the same as the course
        id of the assignment.
        """
        if group_set is not None:
            assert self.course_id == group_set.course_id
        return group_set

    @property
    def max_grade(self) -> float:
        """Get the maximum grade possible for this assignment.

        :returns: The maximum a grade for a submission.
        """
        return 10 if self._max_grade is None else self._max_grade

    @property
    def cgignore(self) -> t.Optional[ignore.SubmissionFilter]:
        """The submission filter of this assignment.
        """
        if self._cgignore is None:
            return None
        elif self._cgignore_version is None:  # pragma: no cover
            # This branch is needed for backwards compatibility, but it is not
            # possible to test as it is not possible to insert this old data
            # using the api.
            return ignore.IgnoreFilterManager.parse(self._cgignore)
        else:
            filter_type = ignore.filter_handlers[self._cgignore_version]
            return filter_type.parse(json.loads(self._cgignore))

    @cgignore.setter
    def cgignore(self, val: ignore.SubmissionFilter) -> None:
        self._cgignore_version = ignore.filter_handlers.find(type(val), None)
        self._cgignore = json.dumps(val.export())

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
            self.get_from_latest_submissions(work_models.Work.id).all()
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
                work_models.Work.assigned_to,
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
        latest = self.get_from_latest_submissions(work_models.Work.id)
        sql = latest.filter(
            work_models.Work.assigned_to == user_id,
        ).join(
            work_rubric_item,
            work_rubric_item.c.work_id == work_models.Work.id,
            isouter=True
        ).having(
            and_(
                func.count(work_rubric_item.c.rubricitem_id) == 0,
                # We access _grade here directly as we need it to do this query
                t.cast(DbColumn[t.Optional[int]],
                       work_models.Work._grade).is_(None)  # pylint: disable=protected-access
            )
        ).group_by(work_models.Work.id)

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
            self.deadline >= helpers.get_request_start_time()
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
                auth.ensure_permission(
                    CPerm.can_see_grade_before_open, self.course_id
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
                'lms_name': t.Optional[str], # The LMS providing this LTI
                                             # assignment.
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
        # This property getter is quite expensive, and we evaluate it at most 3
        # times so caching it in a local variable is a good idea.
        cgignore = self.cgignore

        res = {
            'id': self.id,
            'state': self.state_name,
            'description': self.description,
            'created_at': self.created_at and self.created_at.isoformat(),
            'deadline': self.deadline and self.deadline.isoformat(),
            'name': self.name,
            'is_lti': self.is_lti,
            'course': self.course,
            'cgignore': None if cgignore is None else cgignore.export(),
            'cgignore_version': self._cgignore_version,
            'whitespace_linter': self.whitespace_linter,
            'done_type': None,
            'done_email': None,
            'reminder_time': None,
            'fixed_max_rubric_points': self.fixed_max_rubric_points,
            'max_grade': self._max_grade,
            'group_set': self.group_set,
            'division_parent_id': None,
        }

        if self.course.lti_provider is not None:
            res['lms_name'] = self.course.lti_provider.lms_name
        else:
            res['lms_name'] = None

        if psef.current_user.has_permission(
            CPerm.can_grade_work,
            self.course_id,
        ):
            if self.done_email is not None:
                res['done_email'] = self.done_email
            if self.done_type is not None:
                res['done_type'] = self.done_type.name
            if self.reminder_email_time is not None:
                res['reminder_time'] = self.reminder_email_time.isoformat()
        if psef.current_user.has_permission(
            CPerm.can_see_assignee, self.course_id
        ):
            res['division_parent_id'] = self.division_parent_id

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
            work_models.Work.user_id.label('user_id'),  # type: ignore
            func.max(work_models.Work.created_at).label('max_date')
        ).filter_by(assignment_id=self.id).group_by(work_models.Work.user_id
                                                    ).subquery('sub')
        return db.session.query(*to_query).select_from(work_models.Work).join(  # type: ignore
            sub,
            and_(
                sub.c.user_id == work_models.Work.user_id,
                sub.c.max_date == work_models.Work.created_at
            )
        ).filter(work_models.Work.assignment_id == self.id)

    def get_all_latest_submissions(self) -> '_MyQuery[work_models.Work]':
        """Get a list of all the latest submissions (:class:`.work_models.Work`) by each
        :class:`.user_models.User` who has submitted at least one work for this
        assignment.

        :returns: The latest submissions.
        """
        # get_from_latest_submissions uses SQLAlchemy magic that MyPy cannot
        # encode.
        return self.get_from_latest_submissions(
            t.cast(work_models.Work, work_models.Work)
        )

    def get_divided_amount_missing(
        self
    ) -> t.Tuple[t.Mapping[int, float], t.Callable[[int, DefaultArg(bool)], t.
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
            return {}, lambda _, __=False: {}

        total_weight = sum(w.weight for w in self.assigned_graders.values())

        amount_subs: int
        amount_subs = self.get_from_latest_submissions(  # type: ignore
            func.count(),
        ).scalar()

        divided_amount: t.MutableMapping[int, float] = defaultdict(float)
        for u_id, amount in self.get_from_latest_submissions(  # type: ignore
            work_models.Work.assigned_to, func.count()
        ).group_by(work_models.Work.assigned_to):
            divided_amount[u_id] = amount

        missing = {}
        for user_id, assigned in self.assigned_graders.items():
            missing[user_id] = (assigned.weight / total_weight *
                                amount_subs) - divided_amount[user_id]

        def __recalculate(user_id: int, increment_sub_amount: bool = True
                          ) -> t.MutableMapping[int, float]:
            nonlocal amount_subs

            if increment_sub_amount:
                amount_subs += 1
            divided_amount[user_id] += 1
            missing = {}

            for assigned_user_id, assigned in self.assigned_graders.items():
                missing[assigned_user_id] = (
                    assigned.weight / total_weight * amount_subs
                ) - divided_amount[assigned_user_id]

            return missing

        return missing, __recalculate

    def _weights_changed(
        self, user_weights: t.Sequence[t.Tuple['user_models.User', float]]
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
        self, user_weights: t.Sequence[t.Tuple['user_models.User', float]]
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
        # If the weights are not changed we should not divide anything as that
        # would mean that pressing the button again on accident might change
        # the (custom) division.
        if not self._weights_changed(user_weights):
            return

        submissions = self.get_all_latest_submissions().all()
        shuffle(submissions)

        counts: t.MutableMapping[int, int] = defaultdict(int)
        user_submissions: t.MutableMapping[t.Optional[int], t.List[work_models.
                                                                   Work]]
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

    def get_assignee_from_division_children(self, student_id: int
                                            ) -> t.Optional[int]:
        """Get id of the most common grader for a student in the division
        children of this assignment.

        If this is tied a user is chosen arbitrarily from the most common
        graders. If the student is not present in the children ``None`` is
        returned.

        :param student_id: The id of the student you want to get the assignee
            for.
        :returns: The id of the assignee, or ``None`` if there is none.
        """
        assert self.division_children
        assert not self.division_parent_id

        shuffled_children = list(self.division_children)
        shuffle(shuffled_children)
        latest = Counter(
            child.get_from_latest_submissions(work_models.Work.assigned_to).
            filter(work_models.Work.user_id == student_id).limit(1).scalar()
            for child in shuffled_children
        )
        del latest[None]
        if latest:
            return latest.most_common(1)[0][0]
        return None

    def get_assignee_for_submission(
        self, sub: 'work_models.Work', *, from_divided: bool = True
    ) -> t.Optional[int]:
        """Get the id of the default assignee for a given submission.

        This checks if a user has handed in a submission to this assignment
        before. In that is the case the same assignee is returned. Otherwise,
        if the assignment has a division parent it checks for an assignee
        there, and uses the value if it is not ``None``.

        If the assignment doesn't have a submission by the same user and is a
        parent it will search through the children. There the most common
        assignee for the submitting user is found. If such an assignee exists
        this value is returned.

        Finally if ``from_divided`` is enabled it finds a assignee among the
        divided graders. If no assignee is found ``None`` is returned.

        :param sub: The submission you want to get the assignee for.
        :param from_divided: Get a grader from the divided graders if all other
            methods fail.
        :returns: The id of the assignee or ``None`` if no assignee was found.
        """
        user = self.get_from_latest_submissions(
            work_models.Work.assigned_to
        ).filter(work_models.Work.user_id == sub.user_id).limit(1).scalar()
        if user is not None:
            return user

        if self.division_parent is not None:
            user = self.division_parent.get_assignee_for_submission(
                sub, from_divided=False
            )
            if user is not None:
                return user
        elif self.division_children:
            most_common = self.get_assignee_from_division_children(sub.user_id)
            if most_common is not None:
                return most_common

        if from_divided:
            missing, _ = self.get_divided_amount_missing()
            if missing:
                return max(missing.keys(), key=missing.get)
        return None

    def connect_division(self, parent: t.Optional['Assignment']
                         ) -> t.List['work_models.Work']:
        """Set the division parent of this assignment.

        :param parent: The assignment that should be the new division parent of
            this assignment. Set this to ``None`` to remove the division parent
            of this assignment.
        :returns: A list of submissions that couldn't be assigned and are left
            unassigned.
        """
        # If we unset the division parent we don't touch the divisions at all.
        if parent is None:
            self.division_parent = None
            return []

        assert parent.division_parent is None
        assert parent.course_id == self.course_id
        if self.division_parent_id == parent.id:
            return []

        # We first empty this value. This is needed as
        # `AssignmentAssignedGrader` objects have a primary key constraint on
        # the tuple `(assignment_id, user_id)`. If a assignee only changes
        # weight sqlalchemy gets confused as this tuple doesn't change. This is
        # a bit slower (as the flush does a db roundtrip) but fixes that issue.
        # TODO: Investigate if this is possible without the db.session.flush()
        self.assigned_graders = {}
        db.session.flush()
        self.assigned_graders = {
            key: AssignmentAssignedGrader(
                weight=value.weight,
                user_id=value.user_id,
                assignment_id=self.id
            )
            for key, value in parent.assigned_graders.items()
        }
        self.division_parent = parent
        user_sub = {s.user_id: s for s in self.get_all_latest_submissions()}
        todo = {}
        for sub in user_sub.values():
            sub.assigned_to = None
            todo[sub.id] = sub

        for user_id, assigned_to in parent.get_from_latest_submissions(  # type: ignore
            work_models.Work.user_id,
            work_models.Work.assigned_to,
        ):
            if user_id in user_sub:
                user_sub[user_id].assigned_to = assigned_to
                if user_sub[user_id].assigned_to:
                    del todo[user_sub[user_id].id]

        db.session.flush()
        missing, recalc = self.get_divided_amount_missing()
        for sub in list(todo.values()):
            other = parent.get_assignee_from_division_children(sub.user_id)
            if other is None and missing:
                other = max(missing.keys(), key=missing.get)
            sub.assigned_to = other
            if sub.assigned_to is not None:
                recalc(sub.assigned_to, False)
                del todo[sub.id]
        return list(todo.values())

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
            t.cast(DbColumn[str], user_models.User.name).label("name"),
            t.cast(DbColumn[int], user_models.User.id).label("id"),
            t.cast(
                DbColumn[bool],
                ~t.cast(DbColumn[int], AssignmentGraderDone.user_id).is_(None)
            ).label("done"),
            t.cast(DbColumn[int], user_course.c.course_id).label("course_id"),
        ).join(
            AssignmentGraderDone,
            and_(
                user_models.User.id == AssignmentGraderDone.user_id,
                AssignmentGraderDone.assignment_id == self.id,
            ),
            isouter=True
        ).join(
            user_course,
            user_models.User.id == user_course.c.user_id,
        ).subquery('done_graders')

        graders = db.session.query(course_permissions.c.course_role_id).join(
            CourseRole,
            CourseRole.id == course_permissions.c.course_role_id,
        ).join(
            Permission,
            course_permissions.c.permission_id == Permission.id,
        ).filter(
            CourseRole.course_id == self.course_id,
            Permission[CPerm].value == CPerm.can_grade_work,  # type: ignore
        ).subquery('graders')

        res = db.session.query(
            t.cast(str, done_graders.c.name),
            t.cast(int, done_graders.c.id),
            t.cast(bool, done_graders.c.done),
        ).join(graders, done_graders.c.course_id == graders.c.course_role_id)

        if sort:
            res = res.order_by(func.lower(done_graders.c.name))

        return res

    def has_group_submissions(self) -> bool:
        """Check if the assignment has submissions by a group.

        :returns: ``True`` if the assignment has a submission by a group.
        """
        return db.session.query(
            db.session.query(
                work_models.Work
            ).filter_by(assignment_id=self.id).join(
                user_models.User,
                user_models.User.id == work_models.Work.user_id
            ).join(group_models.Group).exists()
        ).scalar()

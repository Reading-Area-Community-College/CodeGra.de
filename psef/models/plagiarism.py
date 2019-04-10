"""This module defines a PlagiarismCase.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import json
import typing as t
import datetime

import psef

from . import Base, db, _MyQuery
from .. import auth
from .assignment import Assignment
from ..exceptions import PermissionException

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import
    from . import work as work_models
    from .file import File


@enum.unique
class PlagiarismState(enum.IntEnum):
    """Describes in what state a :class:`.PlagiarismRun` is.

    :param running: The provider is currently running.
    :param done: The provider has finished without crashing.
    :param crashed: The provider has crashed in some way.
    """
    starting: int = 1
    done: int = 2
    crashed: int = 3
    started: int = 4
    parsing: int = 5
    running: int = 6
    finalizing: int = 7
    comparing: int = 8


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
        query: t.ClassVar[_MyQuery['PlagiarismRun']] = Base.query
    __tablename__ = 'PlagiarismRun'

    id = db.Column('id', db.Integer, primary_key=True)
    state: PlagiarismState = db.Column(
        'state',
        db.Enum(PlagiarismState),
        default=PlagiarismState.starting,
        nullable=False
    )
    submissions_total: int = db.Column(
        'submissions_total', db.Integer, default=0, nullable=True
    )
    submissions_done: int = db.Column(
        'submissions_done', db.Integer, default=0, nullable=True
    )
    log: t.Optional[str] = db.Column('log', db.Unicode, nullable=True)
    json_config = db.Column('json_config', db.Unicode, nullable=False)
    assignment_id: int = db.Column(
        'assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id'),
        nullable=False,
    )
    created_at: datetime.datetime = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )

    assignment: Assignment = db.relationship(
        'Assignment',
        foreign_keys=assignment_id,
        lazy='joined',
        innerjoin=True,
    )

    cases: t.List['PlagiarismCase'] = db.relationship(
        "PlagiarismCase",
        backref=db.backref('plagiarism_run', innerjoin=True),
        order_by='desc(PlagiarismCase.match_avg)',
        cascade='all,delete',
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

    @property
    def plagiarism_cls(self) -> t.Type['psef.plagiarism.PlagiarismProvider']:
        """Get the class of the plagiarism provider of this run.

        :returns: The class of this plagiarism provider run.
        """
        return psef.helpers.get_class_by_name(
            psef.plagiarism.PlagiarismProvider,
            self.provider_name,
        )

    def __to_json__(self) -> t.Mapping[str, object]:
        """Creates a JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'id': int, # The id of this run.
                'state': str, # The name of the current state this run is in.
                'provider_name': str, # The name of the provider used in this
                                      # run.
                'submissions_done': int, # The amount of submissions that have
                                         # completed the current state.
                'submissions_total': int, # The total amount of submissions
                                          # that have to complete the current
                                          # state.
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
            'submissions_done': self.submissions_done,
            'submissions_total': self.submissions_total,
            'provider_name': self.provider_name,
            'config': json.loads(self.json_config),
            'created_at': self.created_at.isoformat(),
            'assignment': self.assignment,
            'log': self.log,
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
        'work1_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
    )
    work2_id: int = db.Column(
        'work2_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
    )
    created_at: datetime.datetime = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )
    plagiarism_run_id = db.Column(
        'plagiarism_run_id',
        db.Integer,
        db.ForeignKey('PlagiarismRun.id', ondelete='CASCADE'),
        nullable=False,
    )

    match_avg = db.Column('match_avg', db.Float, nullable=False)
    match_max = db.Column('match_max', db.Float, nullable=False)

    work1 = db.relationship(
        'Work',
        foreign_keys=work1_id,
        lazy='joined',
        innerjoin=True,
        backref=db.backref(
            '_plagiarism_cases1',
            lazy='select',
            uselist=True,
            cascade='all,delete'
        ),
    )  # type: work_models.Work
    work2 = db.relationship(
        'Work',
        foreign_keys=work2_id,
        lazy='joined',
        innerjoin=True,
        backref=db.backref(
            '_plagiarism_cases2',
            lazy='select',
            uselist=True,
            cascade='all,delete'
        ),
    )  # type: work_models.Work

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
                'submissions': t.List[work_models.Work], # The two submissions
                                                         # of this case.
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
            auth.ensure_can_see_plagiarims_case(
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
            auth.ensure_can_see_plagiarims_case(
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
        'file1_id',
        db.Integer,
        db.ForeignKey('File.id', ondelete='CASCADE'),
        nullable=False,
    )
    file2_id = db.Column(
        'file2_id',
        db.Integer,
        db.ForeignKey('File.id', ondelete='CASCADE'),
        nullable=False,
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
        'File', foreign_keys=file1_id, lazy='joined', innerjoin=True
    )  # type: File
    file2 = db.relationship(
        'File', foreign_keys=file2_id, lazy='joined', innerjoin=True
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

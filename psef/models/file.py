"""This module defines a File.

SPDX-License-Identifier: AGPL-3.0-only
"""

import os
import enum
import typing as t
import datetime

from flask import current_app

import psef

from . import Base, db, _MyQuery
from .. import auth
from ..exceptions import APICodes, APIException
from ..permissions import CoursePermission

if t.TYPE_CHECKING:  # pragma: no cover
    from . import work as work_models  # pylint: disable=unused-import


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

    Files are always connected to :class:`.work_models.Work` objects. A
    directory file does not physically exist but is stored only in the database
    to preserve the submitted work structure. Each submission should have a
    single top level file. Each other file in a submission should be directly
    or indirectly connected to this file via the parent attribute.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['File']]
    __tablename__ = "File"
    id: int = db.Column('id', db.Integer, primary_key=True)
    work_id: int = db.Column(
        'Work_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
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
    )  # type: 'work_models.Work'

    @staticmethod
    def get_exclude_owner(owner: t.Optional[str], course_id: int) -> FileOwner:
        """Get the :class:`.FileOwner` the current user does not want to see
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
        auth.ensure_logged_in()

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
        assert self.filename is not None
        res = os.path.realpath(
            os.path.join(current_app.config['UPLOAD_DIR'], self.filename)
        )
        assert res.startswith(current_app.config['UPLOAD_DIR'])
        return res

    def delete_from_disk(self) -> None:
        """Delete the file from disk if it is not a directory.

        :returns: Nothing.
        """
        if not self.is_directory:
            os.remove(self.get_diskname())

    def list_contents(
        self,
        exclude: FileOwner,
    ) -> 'psef.files.FileTree':
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
        cache = self.work.get_file_children_mapping(exclude)
        return self._list_contents(exclude, cache)

    def _list_contents(
        self,
        exclude: FileOwner,
        cache: t.Mapping[int, t.Sequence['File']],
    ) -> 'psef.files.FileTree':
        if not self.is_directory:
            return {"name": self.name, "id": self.id}
        else:
            children = [
                c._list_contents(exclude, cache)  # pylint: disable=protected-access
                for c in cache[self.id]
            ]
            return {
                "name": self.name,
                "id": self.id,
                "entries": children,
            }

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

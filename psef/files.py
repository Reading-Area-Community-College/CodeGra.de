"""
This module is used for file IO and handling and provides functions for
extracting and abstracting the structures of directories and archives.

SPDX-License-Identifier: AGPL-3.0-only
"""
import io
import os
import re
import copy
import uuid
import shutil
import typing as t
import tarfile
import zipfile
import tempfile

import structlog
import mypy_extensions
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

import psef.models as models

from . import app, archive, helpers, blackboard
from .ignore import (
    DeletionType, FileDeletion, IgnoreHandling, SubmissionFilter,
    EmptySubmissionFilter
)
from .exceptions import APICodes, APIWarnings, APIException
from .extract_tree import (
    ExtractFileTree, ExtractFileTreeBase, ExtractFileTreeFile,
    ExtractFileTreeDirectory
)

logger = structlog.get_logger()

# Gestolen van Erik Kooistra
_BB_TXT_FORMAT = re.compile(
    r"(?P<assignment_name>.+)_(?P<student_id>.+?)_attempt_"
    r"(?P<datetime>\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}).txt"
)
FileTreeBase = mypy_extensions.TypedDict(  # pylint: disable=invalid-name
    'FileTreeBase',
    {
        'name': str,
        'id': int,
    }
)

SPECIAL_FILES = {
    '.cg-grade',
    '.cg-rubric.md',
    '.cg-feedback',
    '.cg-submission-id',
    '.cg-edit-rubric.md',
    '.cg-edit-rubric.help',
    '.cg-assignment-settings.ini',
    '.cg-assignment-id',
    '.api-socket',
    '.cg-mode',
    '.cg-members',
    '.cg-test-output',
    '.cg-assignee',
    '.cg-linter-feedback',
    '.cg-line-feedback',
    '.cg-overview.csv',
    '.cg-plagiarism',
    '.cg-diff',
    '.cg-student-diff',
    '.cg-teacher-diff',
    '.cg-grade-history',
    '.cg-review',
    '.cg-peer-review',
    '.cg-allesreiniger',
}

SPECIAL_FILENAMES = {
    '..',
    '.',
    *SPECIAL_FILES,
}


def init_app(_: t.Any) -> None:
    pass


def get_file_size(f: str) -> archive.FileSize:
    return archive.FileSize(max(1, os.path.getsize(f)))


def escape_logical_filename(name: str) -> str:
    """Escape a logical filename

    If the name is a special file or the literal string '.' or '..' the string
    '-USER_PROVIDED' is appended to the name.

    .. note::

        A logical filename is the filename as stored in the database and
        displayed to the users, called ``name`` in the database. This is
        different from physical filenames which are the names of the files as
        stored on disk, called ``filename`` in the database.

    >>> logger.warning = lambda *_, **__: True
    >>> helpers.add_warning = lambda *_, **__: True
    >>> escape_logical_filename('.')
    '.-USER_PROVIDED'
    >>> escape_logical_filename('.cg-grade')
    '.cg-grade-USER_PROVIDED'
    >>> escape_logical_filename('.cg-grade-USER_PROVIDED')
    '.cg-grade-USER_PROVIDED-USER_PROVIDED'
    >>> escape_logical_filename('normal file')
    'normal file'
    >>> escape_logical_filename('.bashrc')
    '.bashrc'

    :param name: The original logical filename.
    :returns: An escaped logical filename.
    """
    # Use `startswith` to make sure no collisions can occur.
    if name.startswith(tuple(SPECIAL_FILES)) or name in SPECIAL_FILENAMES:
        new_name = name + '-USER_PROVIDED'
        logger.warning('Invalid filename found', original_filename=name)
        helpers.add_warning(
            f'Invalid filename "{name}" was renamed to "{new_name}"',
            APIWarnings.INVALID_FILENAME
        )
        name = new_name

    if '/' in name:
        name = split_path(name)[0][-1]

    return name


# This is valid, see https://github.com/PyCQA/pylint/issues/1927
class FileTree(  # pylint: disable=inherit-non-class,missing-docstring
    FileTreeBase,
    total=False,
):
    """A file tree with.

    This file tree has structure like this:

    .. code-block:: python

        {
            "id": 1,
            "name": "rootdir",
            "entries": [
                {
                    "id": 2,
                    "name": "file1.txt"
                },
                {
                    "id": 3,
                    "name": "subdir",
                    "entries": [
                        {
                            "id": 4,
                            "name": "file2.txt"
                        },
                        {
                            "id": 5,
                            "name": "file3.txt"
                        }
                    ],
                },
            ],
        }
    """
    entries: t.MutableSequence[t.Any]


class IgnoredFilesException(APIException):
    """The exception used when a permission check fails.
    """

    def __init__(
        self,
        invalid_files: t.List[FileDeletion],
        filter_version: int,
        original_tree: ExtractFileTree,
        missing_files: t.List[t.Mapping[str, str]],
    ) -> None:
        self.invalid_files: t.List[FileDeletion] = invalid_files
        message = 'The archive contains files that are ignored'
        if missing_files:
            message += ' and it misses required files'
        super().__init__(
            message=f'{message}.',
            description='Some files in the archive matched the ignore file',
            api_code=APICodes.INVALID_FILE_IN_ARCHIVE,
            status_code=400,
            invalid_files=[
                [d.deleted_file.get_full_name(), d.reason]
                for d in self.invalid_files
                if d.deletion_type != DeletionType.leading_directory
            ],
            removed_files=self.invalid_files,
            original_tree=original_tree,
            filter_version=filter_version,
            missing_files=missing_files,
        )


def get_stat_information(file: models.File) -> t.Mapping[str, t.Any]:
    """Get stat information for a given :class:`.models.File`

    The resulting object will look like this:

    .. code:: python

        {
            'is_directory': bool, # Is the given file a directory
            'modification_date':  int, # When was the file last modified, as
                                       # unix timestamp in utc time.
            'size': int, # The size on disk of the file or 0 if the file is a
                         # directory.
            'id': int, # The id of the given file.
        }

    :param file: The file to get the stat information for.
    :returns: The information as described above.
    """
    mod_date = file.modification_date

    if file.is_directory:
        size = 0
    else:
        filename = file.get_diskname()
        size = os.stat(filename).st_size

    return {
        'is_directory': file.is_directory,
        'modification_date': round(mod_date.timestamp()),
        'size': size,
        'id': file.id,
    }


def get_file_contents(code: models.File) -> bytes:
    """Get the contents of the given :class:`.models.File`.

    :param code: The file object to read.
    :returns: The contents of the file with newlines.
    """
    if code.is_directory:
        raise APIException(
            'Cannot display this file as it is a directory.',
            f'The selected file with id {code.id} is a directory.',
            APICodes.OBJECT_WRONG_TYPE, 400
        )

    filename = code.get_diskname()
    if os.path.islink(filename):  # pragma: no cover
        # This should not be possible as we replace symlinks with regular
        # files on submission.
        logger.error(
            'Symlink found in uploads directory',
            filename=filename,
        )
        raise APIException(
            f'This file is a symlink to `{os.readlink(filename)}`.',
            'The file {} is a symlink'.format(code.id), APICodes.INVALID_STATE,
            410
        )
    with open(filename, 'rb') as codefile:
        return codefile.read()


def search_path_in_filetree(filetree: FileTree, path: str) -> int:
    """Search for a path in a filetree.

    >>> filetree = {
    ...    "id": 1,
    ...    "name": "rootdir",
    ...    "entries": [
    ...        {
    ...            "id": 2,
    ...            "name": "file1.txt"
    ...        },
    ...        {
    ...            "id": 3,
    ...            "name": "subdir",
    ...            "entries": [
    ...                {
    ...                    "id": 4,
    ...                    "name": "file2.txt"
    ...                },
    ...                {
    ...                    "id": 5,
    ...                    "name": "file3.txt"
    ...                }
    ...            ],
    ...        },
    ...    ],
    ... }
    ...
    >>> search_path_in_filetree(filetree, "file1.txt")
    2
    >>> search_path_in_filetree(filetree, "/subdir/")
    3
    >>> search_path_in_filetree(filetree, "/subdir//file2.txt")
    4
    >>> search_path_in_filetree(filetree, "Non existing/path")
    Traceback (most recent call last):
    ...
    KeyError: 'Path (Non existing/path) not in tree'

    :param filetree: The filetree to search.
    :param path: The path the search for.
    :returns: The id of the file associated with the path in the filetree.
    """
    cur = filetree
    for part in path.split('/'):
        if not part:
            continue
        for entry in cur['entries']:
            if entry['name'] == part:
                cur = entry
                break
        else:
            raise KeyError(f'Path ({path}) not in tree')
    return cur['id']


def restore_directory_structure(
    work: models.Work,
    parent: str,
    exclude: models.FileOwner = models.FileOwner.teacher
) -> FileTree:
    """Restores the directory structure recursively for a submission
    (a :class:`.models.Work`).

    The directory structure is returned like this:

    .. code:: python

       {
           "id": 1,
           "name": "rootdir"
           "entries": [
               {
                   "id": 2,
                   "name": "file1.txt"
               },
               {
                   "id": 3,
                   "name": "subdir"
                   "entries": [
                       {
                           "id": 4,
                           "name": "file2.txt."
                       },
                       {
                           "id": 5,
                           "name": "file3.txt"
                       }
                   ],
               },
           ],
       }

    :param work: A submissions.
    :param parent: Path to parent directory.
    :param exclude: The file owner to exclude.
    :returns: A tree as described.
    """
    code = helpers.filter_single_or_404(
        models.File,
        models.File.work_id == work.id,
        t.cast(models.DbColumn[int], models.File.parent_id).is_(None),
        models.File.fileowner != exclude,
    )
    cache = work.get_file_children_mapping(exclude)
    return _restore_directory_structure(code, parent, cache)


def _restore_directory_structure(
    code: models.File,
    parent: str,
    cache: t.Mapping[int, t.Sequence[models.File]],
) -> FileTree:
    """Worker function for :py:func:`.restore_directory_structure`

    :param code: A file
    :param parent: Path to parent directory
    :param cache: The cache to use to get file children.
    :returns: A tree as described in :py:func:`.restore_directory_structure`
    """
    out = os.path.join(parent, code.name)
    if code.is_directory:
        os.mkdir(out)
        subtree: t.List[FileTree] = [
            _restore_directory_structure(child, out, cache)
            for child in cache[code.id]
        ]
        return {
            "name": code.name,
            "id": code.id,
            "entries": subtree,
        }
    else:  # this is a file
        shutil.copyfile(code.get_diskname(), out, follow_symlinks=False)
        return {"name": code.name, "id": code.id}


def rename_directory_structure(rootdir: str) -> ExtractFileTreeDirectory:
    """Creates a nested dictionary that represents the folder structure of
    rootdir.

    A tree like:

    - dir1
        - dir 2
            - file 1
            - file 2
        - file 3

    will be moved to files given by :py:func:`random_file_path` and the object
    returned will represent the file structure, which will be something like
    this:

    .. code:: python

      {
          'dir1': {
              [
                  'dir 2':{
                      [
                          ('file 1', 'new_name'),
                          ('file 2', 'new_name2')
                      ]
                  },
                  ('file 3', 'new_name3')
              ]
          }
      }

    :param str rootdir: The root directory to rename, files will not be removed
    :returns: The tree as described above
    """
    directory: t.MutableMapping[str, t.Any] = {}

    rootdir = rootdir.rstrip(os.sep)
    start = rootdir.rfind(os.sep) + 1

    for path, _, files in os.walk(rootdir):
        folders = path[start:].split(os.sep)
        subdir = dict.fromkeys(files)

        parent: t.MutableMapping[str, t.Any] = directory
        for folder in folders[:-1]:
            parent = parent[folder]
        parent[folders[-1]] = subdir

    def __to_lists(
        name: str,
        dirs: t.Mapping[str, t.Any],
    ) -> t.List[ExtractFileTreeBase]:
        res: t.List[ExtractFileTreeBase] = []

        for key, value in dirs.items():
            if value is None:
                new_name, filename = random_file_path()
                shutil.move(os.path.join(name, key), new_name)
                res.append(
                    ExtractFileTreeFile(
                        name=key,
                        disk_name=filename,
                        parent=None,
                        size=get_file_size(new_name),
                    )
                )
            else:
                new_dir = ExtractFileTreeDirectory(
                    name=key, values=[], parent=None
                )
                for child in __to_lists(os.path.join(name, key), value):
                    new_dir.add_child(child)
                res.append(new_dir)
        return res

    result_lists = __to_lists(rootdir[:start], directory)
    assert len(result_lists) == 1
    assert isinstance(result_lists[0], ExtractFileTreeDirectory)
    return result_lists[0]


def extract_to_temp(
    file: FileStorage,
    max_size: archive.FileSize,
    archive_name: str = 'archive',
    parent_result_dir: t.Optional[str] = None,
) -> t.Tuple[str, archive.FileSize]:
    """Extracts the contents of file into a temporary directory.

    :param file: The archive to extract.
    :param max_size: The maximum size the extracted archive may be.
    :param archive_name: The name used for the archive in error messages.
    :param parent_result_dir: The location the resulting directory should be
        placed in.
    :returns: The pathname of the new temporary directory.
    """
    tmpfd, tmparchive = tempfile.mkstemp()
    size: archive.FileSize

    try:
        os.remove(tmparchive)
        tmparchive += '_archive_{}'.format(
            os.path.basename(secure_filename(file.filename))
        )
        tmpdir = tempfile.mkdtemp(dir=parent_result_dir)
        file.save(tmparchive)

        with archive.Archive.create_from_file(tmparchive) as arch:
            size = arch.extract(to_path=tmpdir, max_size=max_size)
    except (
        tarfile.ReadError, zipfile.BadZipFile,
        archive.UnrecognizedArchiveFormat
    ):
        raise APIException(
            f'The given {archive_name} could not be extracted',
            "The given archive doesn't seem to be an archive",
            APICodes.INVALID_ARCHIVE,
            400,
        )
    except (archive.ArchiveTooLarge, archive.FileTooLarge) as e:
        helpers.raise_file_too_big_exception(
            max_size, single_file=isinstance(e, archive.FileTooLarge)
        )
    except archive.UnsafeArchive as e:
        logger.warning('Unsafe archive submitted', exc_info=True)
        raise APIException(
            f'The given {archive_name} contains invalid or too many files',
            str(e),
            APICodes.INVALID_FILE_IN_ARCHIVE,
            400,
        )
    finally:
        os.close(tmpfd)
        os.remove(tmparchive)

    return tmpdir, size


def extract(
    file: FileStorage,
    max_size: archive.FileSize,
) -> ExtractFileTree:
    """Extracts all files in archive with random name to uploads folder.

    .. warning::

        The returned ExtractFileTree may be empty, i.e. contain only
        directories and no files.

    :param file: The file to extract.
    :param max_size: The maximum size of the extracted archive.
    :returns: A file tree as generated by
        :py:func:`rename_directory_structure`.
    """
    tmpdir, _ = extract_to_temp(
        file=file,
        max_size=max_size,
    )

    try:
        res = rename_directory_structure(tmpdir).values
        for val in res:
            val.forget_parent()

        new_parent = ExtractFileTree(
            name=file.filename,
            values=[],
            parent=None,
        )
        for val in res:
            new_parent.add_child(val)
        return new_parent
    finally:
        shutil.rmtree(tmpdir)


def random_file_path(use_mirror_dir: bool = False) -> t.Tuple[str, str]:
    """Generates a new random file path in the upload directory.

    :param use_mirror_dir: Use the mirror directory as the basedir of the
        random file path.
    :returns: The name of the new file and a path to that file
    """
    if use_mirror_dir:
        root = app.config['MIRROR_UPLOAD_DIR']
    else:
        root = app.config['UPLOAD_DIR']

    while True:
        name = str(uuid.uuid4())
        candidate = os.path.join(root, name)
        if os.path.exists(candidate):  # pragma: no cover
            continue
        else:
            break
    return candidate, name


def process_files(
    files: t.MutableSequence[FileStorage],
    max_size: archive.FileSize,
    force_txt: bool = False,
    ignore_filter: t.Optional[SubmissionFilter] = None,
    handle_ignore: IgnoreHandling = IgnoreHandling.keep,
) -> ExtractFileTree:
    """Process the given files by extracting, moving and saving their tree
    structure.

    :param files: The files to move and extract
    :param max_size: The maximum combined size of all extracted files.
    :param force_txt: Do not extract archive and force all files to be
        considered to be plain text.
    :param ignore_filter: The files and directories that should be ignored.
    :param handle_ignore: Determines how ignored files should be handled.
    :returns: The tree of the files as is described by
        :py:func:`rename_directory_structure`
    """
    if ignore_filter is None:
        ignore_filter = EmptySubmissionFilter()

    if (
        handle_ignore == IgnoreHandling.keep and
        not ignore_filter.can_override_ignore_filter
    ):
        raise APIException(
            'Overriding the ignore filter is not possible for this assignment',
            'The filter disallows overriding it', APICodes.INVALID_PARAM, 400
        )

    def consider_archive(f: FileStorage) -> bool:
        return not force_txt and archive.Archive.is_archive(f.filename)

    if len(files) > 1 or not consider_archive(files[0]):
        tree = ExtractFileTree(name='top', values=[], parent=None)
        for file in files:
            if consider_archive(file):
                tree.add_child(extract(
                    file,
                    max_size=max_size,
                ))
            else:
                new_file_name, filename = random_file_path()
                file.save(new_file_name)
                tree.add_child(
                    ExtractFileTreeFile(
                        name=file.filename,
                        disk_name=filename,
                        parent=None,
                        size=get_file_size(new_file_name),
                    )
                )
                if tree.get_size() > app.max_single_file_size:
                    helpers.raise_file_too_big_exception(
                        app.max_single_file_size, single_file=True
                    )

    else:
        tree = extract(
            files[0],
            max_size=max_size,
        )

    if not tree.contains_file:
        raise APIException(
            'No files found in archive',
            'No files were in the given archive.',
            APICodes.NO_FILES_SUBMITTED,
            400,
        )

    tree.fix_duplicate_filenames()
    original_tree = copy.deepcopy(tree)
    tree, total_changes, missing_files = ignore_filter.process_submission(
        tree, handle_ignore
    )
    actual_file_changes = any(
        c.deletion_type != DeletionType.leading_directory
        for c in total_changes
    )
    if missing_files or (
        handle_ignore == IgnoreHandling.error and actual_file_changes
    ):
        raise IgnoredFilesException(
            total_changes,
            ignore_filter.CGIGNORE_VERSION,
            original_tree=original_tree,
            missing_files=missing_files,
        )

    logger.info('Removing files', removed_files=total_changes)

    if actual_file_changes:
        # We need to do this again as moving files might have caused duplicate
        # filenames
        tree.fix_duplicate_filenames()

    # It did contain files before deleting, so the deletion caused the tree to
    # be empty.
    if not tree.contains_file:
        raise APIException(
            (
                "All files are ignored by a rule in the assignment's"
                ' ignore file'
            ),
            'No files were in the given archive after filtering.',
            APICodes.NO_FILES_SUBMITTED,
            400,
        )

    tree_size = tree.get_size()
    logger.info('Total size', total_size=tree_size, size=max_size)
    if tree_size > max_size:
        tree.delete(app.config['UPLOAD_DIR'])
        helpers.raise_file_too_big_exception(max_size, single_file=False)

    return tree


def process_blackboard_zip(
    blackboard_zip: FileStorage,
    max_size: archive.FileSize,
) -> t.MutableSequence[t.Tuple[blackboard.SubmissionInfo, ExtractFileTree]]:
    """Process the given :py:mod:`.blackboard` zip file.

    This is done by extracting, moving and saving the tree structure of each
    submission.

    :param file: The blackboard gradebook to import
    :returns: List of tuples (BBInfo, tree)
    """

    def __get_files(info: blackboard.SubmissionInfo) -> t.List[FileStorage]:
        files = []
        for blackboard_file in info.files:
            if isinstance(blackboard_file, blackboard.FileInfo):
                name = blackboard_file.original_name
                stream = open(
                    os.path.join(tmpdir, blackboard_file.name), mode='rb'
                )
            else:
                name = blackboard_file[0]
                stream = io.BytesIO(blackboard_file[1])

            if name == '__WARNING__':
                name = '__WARNING__ (User)'

            files.append(FileStorage(stream=stream, filename=name))
        return files

    tmpdir, _ = extract_to_temp(
        blackboard_zip,
        max_size=max_size,
    )
    try:
        info_files = filter(
            None, (_BB_TXT_FORMAT.match(f) for f in os.listdir(tmpdir))
        )
        submissions = []
        for info_file in info_files:
            info = blackboard.parse_info_file(
                os.path.join(tmpdir, info_file.string)
            )

            try:
                tree = process_files(
                    files=__get_files(info), max_size=max_size
                )
            # TODO: We catch all exceptions, this should probably be narrowed
            # down, however finding all exception types is difficult.
            except Exception:  # pylint: disable=broad-except
                files = __get_files(info)
                files.append(
                    FileStorage(
                        stream=io.BytesIO(
                            b'Some files could not be extracted!',
                        ),
                        filename='__WARNING__'
                    )
                )
                tree = process_files(
                    files=files, max_size=max_size, force_txt=True
                )

            submissions.append((info, tree))
        if not submissions:
            raise ValueError
    finally:
        shutil.rmtree(tmpdir)
    return submissions


def split_path(path: str) -> t.Tuple[t.Sequence[str], bool]:
    """Split a path into an array of parts of a path.

    This functions splits a forward slash separated path into an sequence of
    the directories of this path. If the given path ends with a '/' it returns
    that the given path ends with an directory, otherwise the last part is a
    file, this information is returned as the last part of the returned tuple.

    The given path may contain multiple consecutive forward slashes, these are
    interpreted as a single slash. A leading forward slash is also optional.

    :param path: The forward slash separated path to split.
    :returns: A tuple where the first item is the splitted path and the second
        item is a boolean indicating if the last item of the given path was a
        directory.
    """
    is_dir = path[-1] == '/'

    patharr = [item for item in path.split('/') if item]

    return patharr, is_dir


def check_dir(path: str) -> bool:
    '''Check if the path is a directory that is readable, writable, and
    executable for the current user.

    :param path: Path to check.
    :returns: ``True`` if path has the properties described above, ``False``
        otherwise.
    '''
    mode = os.R_OK | os.W_OK | os.X_OK
    return os.access(path, mode) and os.path.isdir(path)

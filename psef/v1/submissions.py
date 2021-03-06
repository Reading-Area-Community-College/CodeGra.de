"""
This module defines all API routes with the main directory "submissions". The
APIs allow the retrieving, and patching of :class: Work objects. Furthermore
functions are defined to get related objects and information.

SPDX-License-Identifier: AGPL-3.0-only
"""

import os
import typing as t
import numbers
import zipfile
import tempfile
from collections import Counter, defaultdict

import structlog
from flask import request
from sqlalchemy.orm import selectinload
from mypy_extensions import TypedDict

import psef.files
from psef import app, current_user

from . import api
from .. import auth, models, helpers, features
from ..errors import APICodes, APIException
from ..models import DbColumn, FileOwner, db
from ..helpers import (
    JSONResponse, EmptyResponse, ExtendedJSONResponse, jsonify,
    ensure_json_dict, extended_jsonify, ensure_keys_in_dict,
    make_empty_response
)
from ..permissions import CoursePermission as CPerm

logger = structlog.get_logger()

Feedback = TypedDict(  # pylint: disable=invalid-name
    'Feedback', {
        'user': t.MutableMapping[int, t.MutableMapping[int, str]],
        'linter': t.MutableMapping[
            int,
            t.MutableMapping[int, t.List[t.Tuple[str, models.LinterComment]]],
        ],
        'general': str,
        'authors': t.Optional[t.MutableMapping[
            int,
            t.MutableMapping[int, models.User]
        ]],
    }
)


@api.route("/submissions/<int:submission_id>", methods=['GET'])
@auth.login_required
def get_submission(
    submission_id: int
) -> ExtendedJSONResponse[t.Union[models.Work, t.Mapping[str, str]]]:
    """Get the given submission (:class:`.models.Work`).

    .. :quickref: Submission; Get a single submission.

    This API has some options based on the 'type' argument in the request

    - If ``type == 'zip'`` see :py:func:`.get_zip`
    - If ``type == 'feedback'`` see :py:func:`.submissions.get_feedback`

    :param int submission_id: The id of the submission
    :returns: A response with the JSON serialized submission as content unless
              specified otherwise
    :rtype: flask.Response

    :query str owner: The type of files to list, if set to `teacher` only
        teacher files will be listed, otherwise only student files will be
        listed.

    :raises APIException: If the submission with given id does not exist.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the submission does not belong to the
                                 current user and the user can not see others
                                 work in the attached course.
                                 (INCORRECT_PERMISSION)
    """
    work = helpers.get_or_404(models.Work, submission_id)

    if not work.has_as_author(current_user):
        auth.ensure_permission(
            CPerm.can_see_others_work, work.assignment.course_id
        )

    if request.args.get('type') == 'zip':
        exclude_owner = models.File.get_exclude_owner(
            request.args.get('owner'),
            work.assignment.course_id,
        )
        return extended_jsonify(get_zip(work, exclude_owner))
    elif request.args.get('type') == 'feedback':
        auth.ensure_can_see_grade(work)
        return extended_jsonify(get_feedback(work))
    return extended_jsonify(work, use_extended=models.Work)


def get_feedback(work: models.Work) -> t.Mapping[str, str]:
    """Get the feedback of :class:`.models.Work` as a plain text file.

    :param work: The submission with the required feedback.
    :returns: A object with two keys: ``name`` where the value is the name
        which can be given to ``GET - /api/v1/files/<name>`` and
        ``output_name`` which is the resulting file should be named.
    """
    comments, linter_comments = work.get_all_feedback()

    filename = f'{work.assignment.name}-{work.user.name}-feedback.txt'

    path, name = psef.files.random_file_path(True)

    with open(path, 'w') as f:
        f.write(
            'Assignment: {}\n'
            'Grade: {}\n'
            'General feedback:\n{}\n\n'
            'Comments:\n'.format(
                work.assignment.name, work.grade or '', work.comment or ''
            )
        )
        for comment in comments:
            f.write(f'{comment}\n')

        if features.has_feature(features.Feature.LINTERS):
            f.write('\nLinter comments:\n')
            for lcomment in linter_comments:
                f.write(f'{lcomment}\n')

    return {'name': name, 'output_name': filename}


def get_zip(work: models.Work,
            exclude_owner: FileOwner) -> t.Mapping[str, str]:
    """Return a :class:`.models.Work` as a zip file.

    :param work: The submission which should be returns as zip file.
    :param exclude_owner: The owner to exclude from the files in the zip. So if
        this is `teacher` only files owned by `student` and `both` will be in
        the zip.
    :returns: A object with two keys: ``name`` where the value is the name
        which can be given to ``GET - /api/v1/files/<name>`` and
        ``output_name`` which is the resulting file should be named.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If submission does not belong to the current
                                 user and the user can not view files in the
                                 attached course. (INCORRECT_PERMISSION)
    """
    auth.ensure_can_view_files(work, exclude_owner == FileOwner.student)

    path, name = psef.files.random_file_path(True)

    with open(
        path,
        'w+b',
    ) as f, tempfile.TemporaryDirectory(
        suffix='dir',
    ) as tmpdir, zipfile.ZipFile(
        f,
        'w',
        compression=zipfile.ZIP_DEFLATED,
    ) as zipf:
        # Restore the files to tmpdir
        tree_root = psef.files.restore_directory_structure(
            work, tmpdir, exclude_owner
        )

        zipf.write(tmpdir, tree_root['name'])

        for root, _dirs, files in os.walk(tmpdir):
            for file in files:
                path = os.path.join(root, file)
                zipf.write(path, path[len(tmpdir):])

    return {
        'name': name,
        'output_name': f'{work.assignment.name}-{work.user.name}-archive.zip'
    }


@api.route('/submissions/<int:submission_id>', methods=['DELETE'])
def delete_submission(submission_id: int) -> EmptyResponse:
    """Delete a submission and all its files.

    .. :quickref: Submission; Delete a submission and all its files.

    .. warning::

        This is irreversible, so make sure the user really wants this!

    :param submission_id: The submission to delete.
    :returns: Nothing
    """
    submission = helpers.get_or_404(models.Work, submission_id)

    auth.ensure_permission(
        CPerm.can_delete_submission, submission.assignment.course_id
    )

    for sub_file in db.session.query(models.File).filter_by(
        work_id=submission_id, is_directory=False
    ).all():
        try:
            sub_file.delete_from_disk()
        except FileNotFoundError:  # pragma: no cover
            pass

    db.session.delete(submission)
    db.session.commit()

    return make_empty_response()


@api.route('/submissions/<int:submission_id>/feedbacks/', methods=['GET'])
@auth.login_required
def get_feedback_from_submission(submission_id: int) -> JSONResponse[Feedback]:
    """Get all feedback for a submission

    .. :quickref: Submission; Get all (linter, user and general) feedback.

    :>json general: The general feedback given on this submission.
    :>json user: A mapping between file id and a mapping that is between line
        and feedback. So for example: ``{5: {0: 'Nice job!'}}`` means that file
        with ``id`` 5 has feedback on line 0.
    :>json linter: A mapping that is almost the same the user feedback mapping,
        only the final key is not a string but a list of tuples where the first
        item is the linter code and the second item is a
        :class:`.models.LinterComment`.
    :>json authors: The authors of the user feedback. In the example above the
        author of the feedback 'Nice job!' would be at ``{5: {0: $USER}}``.
    """
    work = helpers.get_or_404(models.Work, submission_id)
    auth.ensure_can_see_grade(work)
    can_view_author = current_user.has_permission(
        CPerm.can_see_assignee, work.assignment.course_id
    )

    # The authors dict gets filled if `can_view_authors` is set to `True`. This
    # value is used so that `mypy` wont complain about indexing null values.
    authors: t.MutableMapping[int, t.MutableMapping[int, models.
                                                    User]] = defaultdict(dict)
    res: Feedback = {
        'general': work.comment or '',
        'user': defaultdict(dict),
        'linter': defaultdict(lambda: defaultdict(list)),
        'authors': authors if can_view_author else None,
    }

    comments = models.Comment.query.filter(
        t.cast(DbColumn[models.File], models.Comment.file).has(work=work),
    ).order_by(
        t.cast(DbColumn[int], models.Comment.file_id).asc(),
        t.cast(DbColumn[int], models.Comment.line).asc(),
    )

    for comment in comments:
        res['user'][comment.file_id][comment.line] = comment.comment
        if can_view_author:
            authors[comment.file_id][comment.line] = comment.user

    linter_comments = models.LinterComment.query.filter(
        t.cast(DbColumn[models.File],
               models.LinterComment.file).has(work=work)
    ).order_by(
        t.cast(DbColumn[int], models.LinterComment.file_id).asc(),
        t.cast(DbColumn[int], models.LinterComment.line).asc(),
    )
    if features.has_feature(features.Feature.LINTERS):
        for lcomment in linter_comments:
            res['linter'][lcomment.file_id][lcomment.line].append(
                (lcomment.linter_code, lcomment)
            )

    return jsonify(res)


@api.route("/submissions/<int:submission_id>/rubrics/", methods=['GET'])
@features.feature_required(features.Feature.RUBRICS)
def get_rubric(submission_id: int) -> JSONResponse[t.Mapping[str, t.Any]]:
    """Return full rubric of the :class:`.models.Assignment` of the given
    submission (:class:`.models.Work`).

    .. :quickref: Submission; Get a rubric and its selected items.

    :param int submission_id: The id of the submission
    :returns: A response containing the JSON serialized rubric as described in
        :py:meth:`.Work.__rubric_to_json__`.

    :raises APIException: If the submission with the given id does not exist.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not see the assignment of the
                                 given submission. (INCORRECT_PERMISSION)
    """
    work = helpers.get_or_404(
        models.Work,
        submission_id,
        options=[
            selectinload(
                models.Work.assignment,
            ).selectinload(
                models.Assignment.rubric_rows,
            ).selectinload(
                models.RubricRow.items,
            ),
            selectinload(models.Work.selected_items),
        ]
    )
    auth.ensure_permission(
        CPerm.can_see_assignments, work.assignment.course_id
    )
    return jsonify(work.__rubric_to_json__())


@api.route('/submissions/<int:submission_id>/rubricitems/', methods=['PATCH'])
@features.feature_required(features.Feature.RUBRICS)
def select_rubric_items(submission_id: int, ) -> EmptyResponse:
    """Select the given rubric items for the given submission.

    .. :quickref: Submission; Select multiple rubric items.

    :param submission_id: The submission to unselect the item for.

    :>json array items: The ids of the rubric items you want to select.

    :returns: Nothing.

    :raises APIException: If the assignment of a given item does not belong to
        the assignment of the given submission. of the submission
        (INVALID_PARAM).
    :raises PermissionException: If the current user cannot grace work
        (INCORRECT_PERMISSION).
    """
    submission = helpers.get_or_404(models.Work, submission_id)

    auth.ensure_permission(
        CPerm.can_grade_work, submission.assignment.course_id
    )

    content = ensure_json_dict(request.get_json())
    ensure_keys_in_dict(content, [('items', list)])
    item_ids = t.cast(list, content['items'])

    items = helpers.get_in_or_error(
        models.RubricItem, t.cast(models.DbColumn[int], models.RubricItem.id),
        item_ids
    )

    if any(
        item.rubricrow.assignment_id != submission.assignment_id
        for item in items
    ):
        raise APIException(
            'Selected rubric item is not coupled to the given submission',
            f'A given item of "{", ".join(str(i) for i in item_ids)}"'
            f' does not belong to assignment "{submission.assignment_id}"',
            APICodes.INVALID_PARAM, 400
        )

    row_ids = [item.rubricrow_id for item in items]
    if len(row_ids) != len(set(row_ids)):
        duplicates = [k for k, v in Counter(row_ids).items() if v > 1]
        raise APIException(
            'Duplicate rows in selected items',
            'The rows "{}" had duplicate items'.format(
                ','.join(map(str, duplicates))
            ), APICodes.INVALID_PARAM, 400
        )

    submission.select_rubric_items(items, current_user, True)
    db.session.commit()

    return make_empty_response()


@api.route(
    '/submissions/<int:submission_id>/rubricitems/<int:rubric_item_id>',
    methods=['DELETE']
)
@features.feature_required(features.Feature.RUBRICS)
@features.feature_required(features.Feature.INCREMENTAL_RUBRIC_SUBMISSION)
def unselect_rubric_item(
    submission_id: int, rubric_item_id: int
) -> EmptyResponse:
    """Unselect the given rubric item for the given submission.

    .. :quickref: Submission; Unselect the given rubric item.

    :param submission_id: The submission to unselect the item for.
    :param rubric_item_id: The rubric items id to unselect.
    :returns: Nothing.
    """
    submission = helpers.get_or_404(models.Work, submission_id)

    auth.ensure_permission(
        CPerm.can_grade_work, submission.assignment.course_id
    )

    new_items = [
        item for item in submission.selected_items if item.id != rubric_item_id
    ]
    if len(new_items) == len(submission.selected_items):
        raise APIException(
            'Selected rubric item was not selected for this submission',
            f'The item {rubric_item_id} is not selected for {submission_id}',
            APICodes.INVALID_PARAM, 400
        )

    submission.selected_items = new_items
    db.session.commit()

    return make_empty_response()


@api.route(
    "/submissions/<int:submission_id>/rubricitems/<int:rubricitem_id>",
    methods=['PATCH']
)
@features.feature_required(features.Feature.RUBRICS)
@features.feature_required(features.Feature.INCREMENTAL_RUBRIC_SUBMISSION)
def select_rubric_item(
    submission_id: int, rubricitem_id: int
) -> EmptyResponse:
    """Select a rubric item of the given submission (:class:`.models.Work`).

    .. :quickref: Submission; Select a rubric item.

    :param int submission_id: The id of the submission
    :param int rubricitem_id: The id of the rubric item
    :returns: Nothing.

    :raises APIException: If either the submission or rubric item with the
                          given ids does not exist. (OBJECT_ID_NOT_FOUND)
    :raises APIException: If the assignment of the rubric is not the assignment
                          of the submission. (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not grade the given submission
                                 (INCORRECT_PERMISSION)
    """
    work = helpers.get_or_404(models.Work, submission_id)
    rubric_item = helpers.get_or_404(models.RubricItem, rubricitem_id)

    auth.ensure_permission(CPerm.can_grade_work, work.assignment.course_id)
    if rubric_item.rubricrow.assignment_id != work.assignment_id:
        raise APIException(
            'Rubric item selected does not match assignment',
            'The rubric item with id {} does not match the assignment'.
            format(rubricitem_id), APICodes.INVALID_PARAM, 400
        )

    work.remove_selected_rubric_item(rubric_item.rubricrow_id)
    work.select_rubric_items([rubric_item], current_user, False)
    db.session.commit()

    return make_empty_response()


@api.route("/submissions/<int:submission_id>", methods=['PATCH'])
def patch_submission(submission_id: int) -> JSONResponse[models.Work]:
    """Update the given submission (:class:`.models.Work`) if it already
    exists.

    .. :quickref: Submission; Update a submissions grade and feedback.

    :param int submission_id: The id of the submission
    :returns: Empty response with return code 204

    :>json float grade: The new grade, this can be null or float where null
        resets the grade or clears it. This field is optional
    :>json str feedback: The feedback for the student. This field is optional.

    :raise APIException: If the submission with the given id does not exist
        (OBJECT_ID_NOT_FOUND)
    :raise APIException: If the value of the "grade" parameter is not a float
        (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If user can not grade the submission with the
        given id (INCORRECT_PERMISSION)
    """
    work = helpers.get_or_404(models.Work, submission_id)
    content = ensure_json_dict(request.get_json())

    auth.ensure_permission(CPerm.can_grade_work, work.assignment.course_id)

    if 'feedback' in content:
        ensure_keys_in_dict(content, [('feedback', str)])
        feedback = t.cast(str, content['feedback'])

        work.comment = feedback
        work.comment_author = current_user

    if 'grade' in content:
        ensure_keys_in_dict(content, [('grade', (numbers.Real, type(None)))])
        grade = t.cast(t.Optional[float], content['grade'])
        assig = work.assignment

        if not (
            grade is None or
            (assig.min_grade <= float(grade) <= assig.max_grade)
        ):
            raise APIException(
                (
                    f'Grade submitted not between {assig.min_grade} and'
                    f' {assig.max_grade}'
                ), (
                    f'Grade for work with id {submission_id} '
                    f'is {content["grade"]} which is not between '
                    f'{assig.min_grade} and {assig.max_grade}'
                ), APICodes.INVALID_PARAM, 400
            )

        work.set_grade(grade, current_user)

    db.session.commit()
    return jsonify(work)


@api.route("/submissions/<int:submission_id>/grader", methods=['PATCH'])
def update_submission_grader(submission_id: int) -> EmptyResponse:
    """Change the assigned grader of the given submission.

    .. :quickref: Submission; Update grader for the submission.

    :returns: Empty response and a 204 status.

    :>json int user_id: Id of the new grader. This is a required parameter.

    :raises PermissionException: If the logged in user cannot manage the
        course of the submission. (INCORRECT_PERMISSION)
    :raises APIException: If the new grader does not have the correct
        permission to grade this submission. (INCORRECT_PERMISSION)
    """
    work = helpers.get_or_404(models.Work, submission_id)
    content = ensure_json_dict(request.get_json())
    ensure_keys_in_dict(content, [('user_id', int)])
    user_id = t.cast(int, content['user_id'])

    auth.ensure_permission(CPerm.can_assign_graders, work.assignment.course_id)

    grader = helpers.get_or_404(models.User, user_id)
    if not grader.has_permission(
        CPerm.can_grade_work, work.assignment.course_id
    ):
        raise APIException(
            f'User "{grader.name}" doesn\'t have the required permission',
            f'User "{grader.name}" doesn\'t have permission "can_grade_work"',
            APICodes.INCORRECT_PERMISSION, 400
        )

    work.assignee = grader
    work.assignment.set_graders_to_not_done(
        [grader.id],
        send_mail=grader.id != current_user.id,
        ignore_errors=True,
    )
    db.session.commit()

    return make_empty_response()


@api.route("/submissions/<int:submission_id>/grader", methods=['DELETE'])
def delete_submission_grader(submission_id: int) -> EmptyResponse:
    """Change the assigned grader of the given submission.

    .. :quickref: Submission; Delete grader for the submission.

    :returns: Empty response and a 204 status.

    :raises PermissionException: If the logged in user cannot manage the
        course of the submission. (INCORRECT_PERMISSION)
    """
    work = helpers.get_or_404(models.Work, submission_id)

    auth.ensure_permission(CPerm.can_assign_graders, work.assignment.course_id)

    work.assignee = None
    db.session.commit()

    return make_empty_response()


@api.route('/submissions/<int:submission_id>/grade_history/', methods=['GET'])
def get_grade_history(submission_id: int
                      ) -> JSONResponse[t.Sequence[models.GradeHistory]]:
    """Get the grade history for the given submission.

    .. :quickref: Submission; Get the grade history for the given submission.

    :returns: A list of :class:`.models.GradeHistory` object serialized to
        json for the given assignment.
    :raises PermissionException: If the current user has no permission to see
        the grade history. (INCORRECT_PERMISSION)
    """
    work = helpers.get_or_404(models.Work, submission_id)

    auth.ensure_permission(
        CPerm.can_see_grade_history, work.assignment.course_id
    )

    hist: t.MutableSequence[models.GradeHistory]
    hist = db.session.query(
        models.GradeHistory
    ).filter_by(work_id=work.id).order_by(
        models.GradeHistory.changed_at.desc(),  # type: ignore
    ).all()

    return jsonify(hist)


@api.route("/submissions/<int:submission_id>/files/", methods=['POST'])
def create_new_file(submission_id: int) -> JSONResponse[t.Mapping[str, t.Any]]:
    """Create a new file or directory for the given submission.

    .. :quickref: Submission; Create a new file or directory for a submission.

    :param str path: The path of the new file to create. If the path ends in
        a forward slash a new directory is created and the body of the request
        is ignored, otherwise a regular file is created.

    :returns: Stat information about the new file, see
        :py:func:`.files.get_stat_information`

    :raises APIException: If the request is bigger than the maximum upload
        size. (REQUEST_TOO_LARGE)
    """
    work = helpers.get_or_404(models.Work, submission_id)
    exclude_owner = models.File.get_exclude_owner(
        'auto', work.assignment.course_id
    )

    auth.ensure_can_edit_work(work)
    if exclude_owner == FileOwner.teacher:  # we are a student
        assig = work.assignment
        new_owner = FileOwner.both if assig.is_open else FileOwner.student
    else:
        new_owner = FileOwner.teacher

    ensure_keys_in_dict(request.args, [('path', str)])

    pathname: str = request.args.get('path', '')
    # `create_dir` means that the last file should be a dir or not.
    patharr, create_dir = psef.files.split_path(pathname)

    if (
        not create_dir and request.content_length and
        request.content_length > app.max_single_file_size
    ):
        helpers.raise_file_too_big_exception(
            app.max_single_file_size, single_file=True
        )

    if len(patharr) < 2:
        raise APIException(
            'Path should contain at least a two parts',
            f'"{pathname}" only contains {len(patharr)} parts',
            APICodes.INVALID_PARAM, 400
        )

    parent = helpers.filter_single_or_404(
        models.File,
        models.File.work_id == submission_id,
        models.File.fileowner != exclude_owner,
        models.File.name == patharr[0],
        t.cast(DbColumn[int], models.File.parent_id).is_(None),
    )

    code = None
    end_idx = 0
    for idx, part in enumerate(patharr[1:]):
        code = models.File.query.filter(
            models.File.fileowner != exclude_owner,
            models.File.name == part,
            models.File.parent == parent,
        ).first()
        end_idx = idx + 1
        if code is None:
            break
        parent = code
    else:
        end_idx += 1

    def _is_last(idx: int) -> bool:
        return end_idx + idx + 1 == len(patharr)

    if _is_last(-1) or not parent.is_directory:
        raise APIException(
            'All part did already exist',
            f'The path "{pathname}" did already exist',
            APICodes.INVALID_STATE,
            400,
        )

    filename: t.Optional[str]
    parts = patharr[end_idx:]

    if set(parts) & psef.files.SPECIAL_FILENAMES:
        logger.warning('Invalid filename uploaded using API', filenames=parts)

        raise APIException(
            'Invalid filenames',
            f'Some requested names are reserved',
            APICodes.INVALID_PARAM,
            400,
        )

    for idx, part in enumerate(parts):
        if _is_last(idx) and not create_dir:
            is_dir = False
            d_filename, filename = psef.files.random_file_path()
            with open(d_filename, 'wb') as f:
                f.write(request.get_data(as_text=False))
        else:
            is_dir, filename = True, None
        code = models.File(
            work_id=submission_id,
            name=part,
            filename=filename,
            is_directory=is_dir,
            parent=parent,
            fileowner=new_owner,
        )
        db.session.add(code)
        parent = code
    db.session.commit()

    assert code is not None
    return jsonify(psef.files.get_stat_information(code))


@api.route("/submissions/<int:submission_id>/files/", methods=['GET'])
@auth.login_required
def get_dir_contents(
    submission_id: int
) -> t.Union[JSONResponse[psef.files.FileTree], JSONResponse[t.Mapping[str, t.
                                                                       Any]]]:
    """Return the file directory info of a file of the given submission
    (:class:`.models.Work`).

    .. :quickref: Submission; Get the directory contents for a submission.

    The default file is the root of the submission, but a specific file can be
    specified with the file_id argument in the request.

    :param int submission_id: The id of the submission
    :returns: A response with the JSON serialized directory structure as
        content and return code 200. For the exact structure see
        :py:meth:`.File.list_contents`. If path is given the return value will
        be stat datastructure, see :py:func:`.files.get_stat_information`.

    :query int file_id: The file id of the directory to get. If this is not
        given the parent directory for the specified submission is used.
    :query str path: The path that should be searched. The ``file_id`` query
        parameter is used if both ``file_id`` and ``path`` are present.
    :query str owner: The type of files to list, if set to `teacher` only
        teacher files will be listed, otherwise only student files will be
        listed.

    :raise APIException: If the submission with the given id does not exist or
                         when a file id was specified no file with this id
                         exists. (OBJECT_ID_NOT_FOUND)
    :raises APIException: wWhen a file id is specified and the submission id
                          does not match the submission id of the file.
                          (INVALID_URL)
    :raises APIException: When a file id is specified and the file with that id
                          is not a directory. (OBJECT_WRONG_TYPE)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If submission does not belong to the current
                                 user and the user can not view files in the
                                 attached course. (INCORRECT_PERMISSION)
    """
    work = helpers.get_or_404(models.Work, submission_id)

    file_id: str = request.args.get('file_id', '')
    path: str = request.args.get('path', '')

    exclude_owner = models.File.get_exclude_owner(
        request.args.get('owner', None),
        work.assignment.course_id,
    )

    auth.ensure_can_view_files(work, exclude_owner == FileOwner.student)

    if file_id:
        file = helpers.filter_single_or_404(
            models.File,
            models.File.id == file_id,
            models.File.work_id == work.id,
        )
    elif path:
        found_file = work.search_file(path, exclude_owner)
        return jsonify(psef.files.get_stat_information(found_file))
    else:
        file = helpers.filter_single_or_404(
            models.File, models.File.work_id == submission_id,
            t.cast(DbColumn[int], models.File.parent_id).is_(None),
            models.File.fileowner != exclude_owner
        )

    if not file.is_directory:
        raise APIException(
            'File is not a directory',
            f'The file with code {file.id} is not a directory',
            APICodes.OBJECT_WRONG_TYPE, 400
        )

    return jsonify(file.list_contents(exclude_owner))

"""
This module defines all API routes with the main directory "assignments". Thus
the APIs in this module are mostly used to manipulate
:class:`.models.Assignment` objects and their relations.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import json
import shutil
import typing as t
import datetime
from collections import defaultdict

import werkzeug
import structlog
import sqlalchemy.sql as sql
from flask import request
from sqlalchemy.orm import undefer, joinedload, selectinload

import psef
import psef.files
from psef import app as current_app
from psef import current_user
from psef.models import db
from psef.helpers import (
    JSONType, JSONResponse, EmptyResponse, ExtendedJSONResponse, jsonify,
    add_warning, ensure_json_dict, extended_jsonify, ensure_keys_in_dict,
    make_empty_response
)
from psef.exceptions import (
    APICodes, APIWarnings, APIException, InvalidAssignmentState
)

from . import api
from .. import (
    auth, tasks, ignore, models, archive, helpers, linters, parsers, features,
    plagiarism
)
from ..permissions import CoursePermission as CPerm

logger = structlog.get_logger()


@api.route('/assignments/', methods=['GET'])
@auth.login_required
def get_all_assignments() -> JSONResponse[t.Sequence[models.Assignment]]:
    """Get all the :class:`.models.Assignment` objects that the current user
    can see.

    .. :quickref: Assignment; Get all assignments.

    :returns: An array of :py:class:`.models.Assignment` items encoded in JSON.
    :query only_with_rubric: When this parameter is given only assignments that
        have a rubric will be loaded.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    courses = []

    for course_role in current_user.courses.values():
        if course_role.has_permission(CPerm.can_see_assignments):
            courses.append(course_role.course_id)

    res = []

    query = db.session.query(
        models.Assignment,
        t.cast(models.DbColumn[str], models.AssignmentLinter.id).isnot(None)
    ).filter(
        t.cast(
            models.DbColumn[int],
            models.Assignment.course_id,
        ).in_(courses)
    ).join(
        models.AssignmentLinter,
        sql.expression.and_(
            models.Assignment.id == models.AssignmentLinter.assignment_id,
            models.AssignmentLinter.name == 'MixedWhitespace'
        ),
        isouter=True
    ).order_by(
        t.cast(models.DbColumn[object], models.Assignment.created_at).desc()
    )
    if request.args.get('only_with_rubric',
                        'false').lower() in {'', 't', 'true'}:
        query = query.filter(
            t.cast(models.DbColumn[object],
                   models.Assignment.rubric_rows).any()
        )

    if courses:
        for assignment, has_linter in query.all():
            has_perm = current_user.has_permission(
                CPerm.can_see_hidden_assignments, assignment.course_id
            )
            assignment.whitespace_linter_exists = has_linter
            if ((not assignment.is_hidden) or has_perm):
                res.append(assignment)

    return jsonify(res)


@api.route("/assignments/<int:assignment_id>", methods=['GET'])
@auth.login_required
def get_assignment(assignment_id: int) -> JSONResponse[models.Assignment]:
    """Return the given :class:`.models.Assignment`.

    .. :quickref: Assignment; Get a single assignment by id.

    :param int assignment_id: The id of the assignment
    :returns: A response containing the JSON serialized assignment

    :raises APIException: If no assignment with given id exists.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user is not allowed to view this
                                 assignment. (INCORRECT_PERMISSION)
    """
    assignment = helpers.get_or_404(models.Assignment, assignment_id)

    auth.ensure_can_see_assignment(assignment)

    return jsonify(assignment)


@api.route("/assignments/<int:assignment_id>/feedbacks/", methods=['GET'])
@auth.login_required
def get_assignments_feedback(assignment_id: int) -> JSONResponse[
    t.Mapping[str, t.Mapping[str, t.Union[t.Sequence[str], str]]]]:
    """Get all feedbacks for all latest submissions for a given assignment.

    .. :quickref: Assignment; Get feedback for all submissions in a assignment.

    :param int assignment_id: The assignment to query for.
    :returns: A mapping between the id of the submission and a object contain
        three keys: ``general`` for general feedback as a string, ``user`` for
        user feedback as a list of strings and ``linter`` for linter feedback
        as a list of strings. If a user cannot see others work only submissions
        by the current users are returned.
    """
    assignment = helpers.get_or_404(models.Assignment, assignment_id)

    auth.ensure_enrolled(assignment.course_id)

    latest_subs = assignment.get_all_latest_submissions()
    try:
        auth.ensure_permission(CPerm.can_see_others_work, assignment.course_id)
    except auth.PermissionException:
        latest_subs = models.Work.limit_to_user_submissions(
            latest_subs, current_user
        )

    res = {}
    for sub in latest_subs:
        try:
            # This call should be cached in auth.py
            auth.ensure_can_see_grade(sub)

            user_feedback, linter_feedback = sub.get_all_feedback()
            item = {
                'general': sub.comment or '',
                'user': list(user_feedback),
                'linter': list(linter_feedback),
            }
        except auth.PermissionException:
            item = {'user': [], 'linter': [], 'general': ''}

        res[str(sub.id)] = item

    return jsonify(res)


def set_reminder(
    assig: models.Assignment,
    content: t.Dict[str, helpers.JSONType],
) -> None:
    """Set the reminder of an assignment from a JSON dict.

    :param assig: The assignment to set the reminder for.
    :param content: The json input.
    :returns: A warning if it should be returned to the user.
    """
    ensure_keys_in_dict(content, [
        ('done_type', (type(None), str)),
        ('done_email', (type(None), str)),
        ('reminder_time', (type(None), str)),
    ])  # yapf: disable

    done_type = parsers.parse_enum(
        content.get('done_type', None),
        models.AssignmentDoneType,
        allow_none=True,
        option_name='done type'
    )
    reminder_time = parsers.parse_datetime(
        content.get('reminder_time', None),
        allow_none=True,
    )
    done_email = parsers.try_parse_email_list(
        content.get('done_email', None),
        allow_none=True,
    )

    if reminder_time and (reminder_time -
                          datetime.datetime.utcnow()).total_seconds() < 60:
        raise APIException(
            (
                'The given date is not far enough from the current time, '
                'it should be at least 60 seconds in the future.'
            ), f'{reminder_time} is not atleast 60 seconds in the future',
            APICodes.INVALID_PARAM, 400
        )

    assig.change_notifications(done_type, reminder_time, done_email)
    if done_email is not None and assig.graders_are_done():
        add_warning(
            'Grading is already done, no email will be sent!',
            APIWarnings.CONDITION_ALREADY_MET
        )


@api.route('/assignments/<int:assignment_id>', methods=['PATCH'])
@auth.login_required
def update_assignment(assignment_id: int) -> JSONResponse[models.Assignment]:
    # pylint: disable=too-many-branches,too-many-statements
    """Update the given :class:`.models.Assignment` with new values.

    .. :quickref: Assignment; Update assignment information.

    :<json str state: The new state of the assignment, can be `hidden`, `open`
        or `done`. (OPTIONAL)
    :<json str name: The new name of the assignment, this string should not be
        empty. (OPTIONAL)
    :<json str deadline: The new deadline of the assignment. This should be a
        ISO 8061 date without timezone information. (OPTIONAL)
    :<json str done_type: The type to determine if a assignment is done. This
        can be any value of :class:`.models.AssignmentDoneType` or
        ``null``. (OPTIONAL)
    :<json str done_email: The emails to send an email to if the assignment is
        done. Can be ``null`` to disable these emails. (OPTIONAL)
    :<json str reminder_time: The time on which graders which are causing the
        grading to be not should be reminded they have to grade. Can be
        ``null`` to disable these emails. (OPTIONAL)
    :<json float max_grade: The maximum possible grade for this assignment. You
        can reset this by passing ``null`` as value. This value has to be >
        0. (OPTIONAL)
    :<json int group_set_id: The group set id for this assignment. Set
        to ``null`` to make this assignment not a group assignment.

    If any of ``done_type``, ``done_email`` or ``reminder_time`` is given all
    the other values should be given too.

    :param int assignment_id: The id of the assignment
    :returns: An empty response with return code 204.
    :raises APIException: If an invalid value is submitted. (INVALID_PARAM)
    """
    assig = helpers.get_or_404(models.Assignment, assignment_id)
    content = ensure_json_dict(request.get_json())

    lti_class: t.Optional[t.Type[psef.lti.LTI]]
    lms_name: t.Optional[str]

    if assig.is_lti:
        lti_class = assig.course.lti_provider.lti_class
        lms_name = assig.course.lti_provider.lms_name
    else:
        lti_class = None
        lms_name = None

    if 'state' in content:
        auth.ensure_permission(CPerm.can_edit_assignment_info, assig.course_id)
        ensure_keys_in_dict(content, [('state', str)])
        state = t.cast(str, content['state'])

        try:
            assig.set_state(state)
        except InvalidAssignmentState:
            raise APIException(
                'The selected state is not valid',
                'The state {} is not a valid state'.format(state),
                APICodes.INVALID_PARAM, 400
            )

    if 'name' in content:
        if assig.is_lti:
            raise APIException(
                (
                    'The name of this assignment should be changed in '
                    f'{lms_name}.'
                ), f'{assig.name} is an LTI assignment', APICodes.UNSUPPORTED,
                400
            )

        auth.ensure_permission(CPerm.can_edit_assignment_info, assig.course_id)
        ensure_keys_in_dict(content, [('name', str)])
        name = t.cast(str, content['name'])

        if not name:
            raise APIException(
                'The name of an assignment should be at least 1 char',
                'len({}) == 0'.format(content['name']),
                APICodes.INVALID_PARAM,
                400,
            )

        assig.name = name

    if 'deadline' in content:
        if lti_class is not None and lti_class.supports_deadline():
            raise APIException(
                (
                    'The deadline of this assignment should be set in '
                    f'{lms_name}.'
                ), f'{assig.name} is an LTI assignment', APICodes.UNSUPPORTED,
                400
            )

        auth.ensure_permission(CPerm.can_edit_assignment_info, assig.course_id)
        ensure_keys_in_dict(content, [('deadline', str)])
        deadline = t.cast(str, content['deadline'])
        assig.deadline = parsers.parse_datetime(deadline)

    if 'ignore' in content:
        auth.ensure_permission(CPerm.can_edit_cgignore, assig.course_id)
        ignore_version = helpers.get_key_from_dict(
            content, 'ignore_version', 'IgnoreFilterManager'
        )
        filter_type = ignore.filter_handlers.get(ignore_version)
        if filter_type is None:
            raise APIException(
                'The given ignore version was not found.', (
                    'The known values are:'
                    f' {", ".join(ignore.filter_handlers.keys())}'
                ), APICodes.OBJECT_NOT_FOUND, 404
            )
        assig.cgignore = filter_type.parse(t.cast(JSONType, content['ignore']))

    if 'max_grade' in content:
        if lti_class is not None and not lti_class.supports_max_points():
            raise APIException(
                f'{lms_name} does not support setting the maximum grade',
                f'{lms_name} does not support setting the maximum grade',
                APICodes.UNSUPPORTED, 400
            )

        auth.ensure_permission(CPerm.can_edit_maximum_grade, assig.course_id)
        ensure_keys_in_dict(content, [('max_grade', (float, int, type(None)))])
        max_grade = t.cast(t.Union[float, int, None], content['max_grade'])
        if not (max_grade is None or max_grade > 0):
            raise APIException(
                'The maximum grade must be higher than 0',
                f'The value "{max_grade}" is too low as a maximum grade',
                APICodes.INVALID_PARAM, 400
            )
        assig.set_max_grade(max_grade)

    if any(t in content for t in ['done_type', 'reminder_time', 'done_email']):
        auth.ensure_permission(
            CPerm.can_update_course_notifications,
            assig.course_id,
        )
        set_reminder(assig, content)

    if 'group_set_id' in content:
        auth.ensure_permission(
            CPerm.can_edit_group_assignment, assig.course_id
        )
        ensure_keys_in_dict(content, [('group_set_id', (int, type(None)))])
        group_set_id = t.cast(t.Optional[int], content['group_set_id'])
        if group_set_id is None:
            group_set = None
        else:
            group_set = helpers.get_or_404(models.GroupSet, group_set_id)

        if assig.group_set != group_set and assig.has_group_submissions():
            raise APIException(
                (
                    'This assignment has submissions by a group, delete'
                    ' these first'
                ), (
                    "You can't disconnect this group set as there are"
                    " still submissions by groups"
                ), APICodes.INVALID_STATE, 400
            )

        assig.group_set = group_set

    db.session.commit()

    return jsonify(assig)


@api.route('/assignments/<int:assignment_id>/rubrics/', methods=['GET'])
@features.feature_required(features.Feature.RUBRICS)
def get_assignment_rubric(assignment_id: int
                          ) -> JSONResponse[t.Sequence[models.RubricRow]]:
    """Return the rubric corresponding to the given ``assignment_id``.

    .. :quickref: Assignment; Get the rubric of an assignment.

    :param int assignment_id: The id of the assignment
    :returns: A list of JSON of :class:`.models.RubricRows` items.

    :raises APIException: If no assignment with given id exists.
        (OBJECT_ID_NOT_FOUND)
    :raises APIException: If the assignment has no rubric.
        (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    assig = helpers.get_or_404(
        models.Assignment,
        assignment_id,
        options=[
            selectinload(
                models.Assignment.rubric_rows,
            ).selectinload(
                models.RubricRow.items,
            )
        ]
    )

    auth.ensure_permission(CPerm.can_see_assignments, assig.course_id)
    if assig.is_hidden:
        auth.ensure_permission(
            CPerm.can_see_hidden_assignments, assig.course_id
        )
    if not assig.rubric_rows:
        raise APIException(
            'Assignment has no rubric',
            'The assignment with id "{}" has no rubric'.format(assignment_id),
            APICodes.OBJECT_ID_NOT_FOUND, 404
        )

    return jsonify(assig.rubric_rows)


@api.route('/assignments/<int:assignment_id>/rubrics/', methods=['DELETE'])
@features.feature_required(features.Feature.RUBRICS)
def delete_rubric(assignment_id: int) -> EmptyResponse:
    """Delete the rubric for the given assignment.

    .. :quickref: Assignment; Delete the rubric of an assignment.

    :param assignment_id: The id of the :class:`.models.Assignment` whose
        rubric should be deleted.
    :returns: Nothing.

    :raises PermissionException: If the user does not have the
        ``manage_rubrics`` permission (INCORRECT_PERMISSION).
    :raises APIException: If the assignment has no rubric.
        (OBJECT_ID_NOT_FOUND)
    """
    assig = helpers.get_or_404(models.Assignment, assignment_id)
    auth.ensure_permission(CPerm.manage_rubrics, assig.course_id)

    if not assig.rubric_rows:
        raise APIException(
            'Assignment has no rubric',
            'The assignment with id "{}" has no rubric'.format(assignment_id),
            APICodes.OBJECT_ID_NOT_FOUND, 404
        )

    assig.rubric_rows = []

    db.session.commit()

    return make_empty_response()


@api.route('/assignments/<int:assignment_id>/rubric', methods=['POST'])
@features.feature_required(features.Feature.RUBRICS)
def import_assignment_rubric(assignment_id: int
                             ) -> JSONResponse[t.Sequence[models.RubricRow]]:
    """Import a rubric from a different assignment.

    .. :quickref: Assignment; Import a rubric from a different assignment.

    :param assignment_id: The id of the assignment in which you want to import
        the rubric. This assignment shouldn't have a rubric.
    :>json old_assignment_id: The id of the assignment from which the rubric
        should be imported. This assignment should have a rubric.

    :returns: The rubric rows of the assignment in which the rubric was
        imported, so the assignment with id ``assignment_id`` and not
        ``old_assignment_id``.
    """
    assig = helpers.get_or_404(models.Assignment, assignment_id)
    auth.ensure_permission(CPerm.manage_rubrics, assig.course_id)

    content = ensure_json_dict(request.get_json())
    ensure_keys_in_dict(content, [('old_assignment_id', int)])
    old_assig = helpers.get_or_404(
        models.Assignment, content['old_assignment_id']
    )

    auth.ensure_permission(CPerm.can_see_assignments, old_assig.course_id)
    if old_assig.is_hidden:
        auth.ensure_permission(
            CPerm.can_see_hidden_assignments, old_assig.course_id
        )

    if assig.rubric_rows:
        raise APIException(
            'The given assignment already has a rubric',
            'You cannot import a rubric into an assignment which has a rubric',
            APICodes.OBJECT_ALREADY_EXISTS, 400
        )
    if not old_assig.rubric_rows:
        raise APIException(
            "The given old assignment doesn't have a rubric", (
                "You cannot import a rubric from an assignment which doesn't"
                " have a rubric"
            ), APICodes.OBJECT_NOT_FOUND, 404
        )

    assig.rubric_rows = [row.copy() for row in old_assig.rubric_rows]
    db.session.commit()
    return jsonify(assig.rubric_rows)


@api.route('/assignments/<int:assignment_id>/rubrics/', methods=['PUT'])
@features.feature_required(features.Feature.RUBRICS)
def add_assignment_rubric(assignment_id: int
                          ) -> JSONResponse[t.Sequence[models.RubricRow]]:
    """Add or update rubric of an assignment.

    .. :quickref: Assignment; Add a rubric to an assignment.

    :>json array rows: An array of rows. Each row should be an object that
        should contain a ``header`` mapping to a string, a ``description`` key
        mapping to a string, an ``items`` key mapping to an array and it may
        contain an ``id`` key mapping to the current id of this row. The items
        array should contain objects with a ``description`` (string),
        ``header`` (string) and ``points`` (number) and optionally an ``id`` if
        you are modifying an existing item in an existing row.
    :>json number max_points: Optionally override the maximum amount of points
        you can get for this rubric. By passing ``null`` you reset this value,
        by not passing it you keep its current value. (OPTIONAL)

    :param int assignment_id: The id of the assignment
    :returns: An empty response with return code 204

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user is not allowed to manage rubrics.
                                (INCORRECT_PERMISSION)
    """
    assig = helpers.get_or_404(models.Assignment, assignment_id)

    auth.ensure_permission(CPerm.manage_rubrics, assig.course_id)
    content = ensure_json_dict(request.get_json())

    if 'max_points' in content:
        helpers.ensure_keys_in_dict(
            content, [('max_points', (type(None), int, float))]
        )
        max_points = t.cast(t.Optional[float], content['max_points'])
        if max_points is not None and max_points <= 0:
            raise APIException(
                'The max amount of points you can '
                'score should be higher than 0',
                f'The max amount of points was {max_points} which is <= 0',
                APICodes.INVALID_STATE, 400
            )
        assig.fixed_max_rubric_points = max_points

    if 'rows' in content:
        with db.session.begin_nested():
            helpers.ensure_keys_in_dict(content, [('rows', list)])
            rows = t.cast(t.List[JSONType], content['rows'])
            new_rubric_rows = [process_rubric_row(r) for r in rows]

            if any(not row.is_valid for row in new_rubric_rows):
                wrong_rows = [r for r in new_rubric_rows if not r.is_valid]
                single = len(wrong_rows) == 1
                raise APIException(
                    (
                        'The row{s} {rows} do{es} not contain at least one'
                        ' item with 0 or higher as points.'
                    ).format(
                        rows=', and '.join(r.header for r in wrong_rows),
                        s='' if single else 's',
                        es='es' if single else '',
                    ), 'Not all rows contain at least one '
                    'item after updating the rubric.', APICodes.INVALID_STATE,
                    400
                )

            assig.rubric_rows = new_rubric_rows
            db.session.flush()
            max_points = assig.max_rubric_points

            if max_points is None or max_points <= 0:
                raise APIException(
                    'The max amount of points you can '
                    'score should be higher than 0',
                    f'The max amount of points was {max_points} which is <= 0',
                    APICodes.INVALID_STATE, 400
                )

    db.session.commit()
    return jsonify(assig.rubric_rows)


def process_rubric_row(row: JSONType) -> models.RubricRow:
    """Process a single rubric row updating or creating it.

    This function works on the input json data. It makes sure that the input
    has the correct format and dispatches it to the necessary functions.

    :param row: The row to process.
    :returns: The updated or created row.
    """
    row = ensure_json_dict(row)
    ensure_keys_in_dict(
        row, [('description', str), ('header', str), ('items', list)]
    )
    header = t.cast(str, row['header'])
    desc = t.cast(str, row['description'])
    items: t.Sequence[models.RubricItem.JSONBaseSerialization]
    items = [
        # This is a mypy bug that is why we need this cast:
        # https://github.com/python/mypy/issues/5723
        t.cast(
            models.RubricItem.JSONBaseSerialization,
            helpers.coerce_json_value_to_typeddict(
                it, models.RubricItem.JSONBaseSerialization
            )
        ) for it in t.cast(list, row['items'])
    ]

    if header == '':
        raise APIException(
            "A row can't have an empty header",
            f'The row "{row}" has an empty header', APICodes.INVALID_PARAM, 400
        )

    if 'id' in row:
        ensure_keys_in_dict(row, [('id', int)])
        row_id = t.cast(int, row['id'])
        rubric_row = helpers.get_or_404(models.RubricRow, row_id)
        rubric_row.update_from_json(header, desc, items)
        return rubric_row
    else:
        return models.RubricRow.create_from_json(header, desc, items)


@api.route('/assignments/<int:assignment_id>/submission', methods=['POST'])
def upload_work(assignment_id: int) -> ExtendedJSONResponse[models.Work]:
    """Upload one or more files as :class:`.models.Work` to the given
    :class:`.models.Assignment`.

    .. :quickref: Assignment; Create work by uploading a file.

    :query ignored_files: How to handle ignored files. The options are:
        ``ignore``: this the default, sipmly do nothing about ignored files,
        ``delete``: delete the ignored files, ``error``: raise an
        :py:class:`.APIException` when there are ignored files in the archive.
    :query author: The username of the user that should be the author of this
        new submission. Simply don't give this if you want to be the author.

    :param int assignment_id: The id of the assignment
    :returns: A JSON serialized work and with the status code 201.

    :raises APIException: If the request is bigger than the maximum upload
        size. (REQUEST_TOO_LARGE)
    :raises APIException: If there was no file in the request.
        (MISSING_REQUIRED_PARAM)
    :raises APIException: If some file was under the wrong key or some filename
        is empty. (INVALID_PARAM)
    """
    files = helpers.get_files_from_request(
        max_size=current_app.max_file_size, keys=['file'], only_start=True
    )
    assig = helpers.get_or_404(models.Assignment, assignment_id)
    given_author = request.args.get('author', None)

    if assig.deadline is None:
        raise APIException(
            (
                'The deadline for this assignment has not yet been set. '
                'Please ask your teacher to set a deadline before you can '
                'submit your work.'
            ),
            f'The deadline for assignment {assig.name} is unset.',
            APICodes.ASSIGNMENT_DEADLINE_UNSET,
            400,
        )

    if given_author is None:
        author = current_user
    else:
        author = helpers.filter_single_or_404(
            models.User,
            models.User.username == given_author,
        )

    auth.ensure_can_submit_work(assig, author)

    group = None
    if assig.group_set:
        group = assig.group_set.get_valid_group_for_user(author)
    if group is not None:
        author = group.virtual_user
        if assig.is_lti and any(
            assig.id not in member.assignment_results
            for member in group.members
        ):
            lms = assig.course.lti_provider.lms_name
            raise APIException(
                f"Some authors haven't opened the assignment in {lms} yet",
                'No assignment_results found for some authors in the group',
                APICodes.ASSIGNMENT_RESULT_GROUP_NOT_READY,
                400,
                group=group,
            )

    work = models.Work(assignment=assig, user_id=author.id)
    work.divide_new_work()

    try:
        raise_or_delete = psef.ignore.IgnoreHandling[request.args.get(
            'ignored_files',
            'keep',
        )]
    except KeyError:  # The enum value does not exist
        raise APIException(
            'The given value for "ignored_files" is invalid',
            (
                f'The value "{request.args.get("ignored_files")}" is'
                ' not in the `IgnoreHandling` enum'
            ),
            APICodes.INVALID_PARAM,
            400,
        )

    tree = psef.files.process_files(
        files,
        max_size=current_app.max_file_size,
        force_txt=False,
        ignore_filter=assig.cgignore,
        handle_ignore=raise_or_delete,
    )
    work.add_file_tree(tree)
    db.session.add(work)
    db.session.flush()

    if work.assignment.is_lti:
        # TODO: Doing this for a LMS other than Canvas is probably not a good
        # idea as it will result in a wrong submission date.
        helpers.callback_after_this_request(
            lambda: tasks.passback_grades([work.id], initial=True)
        )
    db.session.commit()

    work.run_linter()

    return extended_jsonify(work, status_code=201, use_extended=models.Work)


@api.route(
    '/assignments/<int:assignment_id>/division_parent', methods=['PATCH']
)
def change_division_parent(assignment_id: int) -> EmptyResponse:
    """Change the division parent of an assignment.

    Set the division parent of this assignment. See the documentation about
    dividing submissions for more information about division parents.

    .. :quickref: Assignment; Change the division parent of an assignment.

    :param assignment_id: The id of the assignment you want to change.
    :<json parent_assignment_id: The id of the assignment that should be the
        division parent of the given assignment. If this is set to ``null`` the
        division parent of this assignment will be cleared.
    :returns: An empty response with status code code 204.
    """
    assignment = helpers.get_or_404(
        models.Assignment,
        assignment_id,
        options=[joinedload(models.Assignment.division_children)],
    )

    auth.ensure_permission(CPerm.can_assign_graders, assignment.course_id)

    content = ensure_json_dict(request.get_json())

    ensure_keys_in_dict(content, [('parent_id', (int, type(None)))])
    parent_id = t.cast(t.Union[int, None], content['parent_id'])

    if parent_id is None:
        parent_assig = None
    else:
        parent_assig = helpers.filter_single_or_404(
            models.Assignment,
            models.Assignment.id == parent_id,
            models.Assignment.course_id == assignment.course_id,
        )
    if (
        parent_assig is not None and
        parent_assig.division_parent_id is not None
    ):
        # The id is not None so the object itself can't None
        assert parent_assig.division_parent is not None
        raise APIException(
            (
                f'The division of {parent_assig.name} is already'
                f' determined by {parent_assig.division_parent.name},'
                f' so you cannot connect to this assignment.'
            ), 'The division parent of {parent_assig.id} is already set',
            APICodes.INVALID_STATE, 400
        )
    missed_work = assignment.connect_division(parent_assig)
    db.session.commit()

    if missed_work and parent_assig is not None:
        helpers.add_warning(
            (
                f"Some submissions were not divided as they weren't"
                f' assigned in {parent_assig.name}. Make sure you divide'
                ' those manually.'
            ), APIWarnings.UNASSIGNED_ASSIGNMENTS
        )

    return make_empty_response()


@api.route('/assignments/<int:assignment_id>/divide', methods=['PATCH'])
def divide_assignments(assignment_id: int) -> EmptyResponse:
    """Assign graders to all the latest :class:`.models.Work` objects of
    the given :class:`.models.Assignment`.

    .. :quickref: Assignment; Divide a submission among given TA's.

    The redivide tries to minimize shuffles. This means that calling it twice
    with the same data is effectively a noop. If the relative weight (so the
    percentage of work) of a user doesn't change it will not lose or gain any
    submissions.

    .. warning::

        If a user was marked as done grading and gets assigned new submissions
        this user is marked as not done and gets a notification email!

    :<json dict graders: A mapping that maps user ids (strings) and the new
        weight they should get (numbers).
    :param int assignment_id: The id of the assignment
    :returns: An empty response with return code 204

    :raises APIException: If no assignment with given id exists or the
        assignment has no submissions. (OBJECT_ID_NOT_FOUND)
    :raises APIException: If there was no grader in the request.
        (MISSING_REQUIRED_PARAM)
    :raises APIException: If some grader id is invalid or some grader does not
        have the permission to grade the assignment.  (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user is not allowed to divide
        submissions for this assignment.  (INCORRECT_PERMISSION)
    """
    assignment = helpers.get_or_404(
        models.Assignment,
        assignment_id,
        options=[joinedload(models.Assignment.division_children)],
    )

    auth.ensure_permission(CPerm.can_assign_graders, assignment.course_id)

    content = ensure_json_dict(request.get_json())

    if (
        assignment.division_parent_id is not None or
        assignment.division_children
    ):
        raise APIException(
            'You cannot change the division of a connected assignment.', (
                f'The assignment {assignment.id} is connect or a parent so you'
                ' cannot change the grader weights'
            ), APICodes.INVALID_STATE, 400
        )

    ensure_keys_in_dict(content, [('graders', dict)])
    graders = {}

    for user_id, weight in t.cast(dict, content['graders']).items():
        if not (isinstance(user_id, str) and isinstance(weight, (float, int))):
            raise APIException(
                'Given graders weight or id is invalid',
                'Both key and value in graders object should be integers',
                APICodes.INVALID_PARAM, 400
            )
        graders[int(user_id)] = weight

    if graders:
        negative_weights = ', '.join(str(g) for g, w in graders.items() if w < 0)
        if negative_weights:
            raise APIException(
                'Weights must be positive.',
                (
                    f'The graders {negative_weights} have been assigned a'
                    ' negative weight'
                ),
                APICodes.INVALID_PARAM, 400
            )
        users = helpers.filter_all_or_404(
            models.User,
            models.User.id.in_(graders.keys())  # type: ignore
        )
    else:
        models.Work.query.filter_by(assignment_id=assignment.id).update(
            {'assigned_to': None}
        )
        assignment.assigned_graders = {}
        db.session.commit()
        return make_empty_response()

    if len(users) != len(graders):
        raise APIException(
            'Invalid grader id given', 'Invalid grader (=user) id given',
            APICodes.INVALID_PARAM, 400
        )

    for user in users:
        if not user.has_permission(CPerm.can_grade_work, assignment.course_id):
            raise APIException(
                'Selected grader has no permission to grade',
                f'The grader {user.id} has no permission to grade',
                APICodes.INVALID_PARAM, 400
            )

    assignment.divide_submissions([(user, graders[user.id]) for user in users])
    db.session.commit()

    return make_empty_response()


@api.route('/assignments/<int:assignment_id>/graders/', methods=['GET'])
def get_all_graders(
    assignment_id: int
) -> JSONResponse[t.Sequence[t.Mapping[str, t.Union[float, str, bool]]]]:
    """Gets a list of all :class:`.models.User` objects who can grade the given
    :class:`.models.Assignment`.

    .. :quickref: Assignment; Get all graders for an assignment.

    :param int assignment_id: The id of the assignment
    :returns: A response containing the JSON serialized graders.

    :>jsonarr string name: The name of the grader.
    :>jsonarr int id: The user id of this grader.
    :>jsonarr bool divided: Is this user assigned to any submission for this
        assignment.
    :>jsonarr bool done: Is this user done grading?

    :raises APIException: If no assignment with given id exists.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user is not allowed to view graders of
                                 this assignment. (INCORRECT_PERMISSION)
    """
    assignment = helpers.get_or_404(models.Assignment, assignment_id)
    auth.ensure_permission(CPerm.can_see_assignee, assignment.course_id)

    result = assignment.get_all_graders(sort=True)

    divided: t.MutableMapping[int, float] = defaultdict(int)
    for assigned_grader in models.AssignmentAssignedGrader.query.filter_by(
        assignment_id=assignment_id
    ):
        divided[assigned_grader.user_id] = assigned_grader.weight

    return jsonify(
        [
            {
                'id': res[1],
                'name': res[0],
                'weight': float(divided[res[1]]),
                'done': res[2],
            } for res in result
        ]
    )


@api.route(
    '/assignments/<int:assignment_id>/graders/<int:grader_id>/done',
    methods=['DELETE']
)
@auth.login_required
def set_grader_to_not_done(
    assignment_id: int, grader_id: int
) -> EmptyResponse:
    """Indicate that the given grader is not yet done grading the given
    `:class:.models.Assignment`.

    .. :quickref: Assignment; Set the grader status to 'not done'.

    :param assignment_id: The id of the assignment the grader is not yet done
        grading.
    :param grader_id: The id of the `:class:.models.User` that is not yet done
        grading.
    :returns: An empty response with return code 204

    :raises APIException: If the given grader was not indicated as done before
        calling this endpoint. (INVALID_STATE)
    :raises PermissionException: If the current user wants to change a status
        of somebody else but the user does not have the
        `can_update_grader_status` permission. (INCORRECT_PERMISSION)
    :raises PermissionException: If the current user wants to change its own
        status but does not have the `can_update_grader_status` or the
        `can_grade_work` permission. (INCORRECT_PERMISSION)
    """
    assig = helpers.get_or_404(models.Assignment, assignment_id)

    if current_user.id == grader_id:
        auth.ensure_permission(CPerm.can_grade_work, assig.course_id)
    else:
        auth.ensure_permission(CPerm.can_update_grader_status, assig.course_id)

    try:
        send_mail = grader_id != current_user.id
        assig.set_graders_to_not_done([grader_id], send_mail=send_mail)
        db.session.commit()
    except ValueError:
        raise APIException(
            'The grader is not finished!',
            f'The grader {grader_id} is not done.',
            APICodes.INVALID_STATE,
            400,
        )
    else:
        return make_empty_response()


@api.route(
    '/assignments/<int:assignment_id>/graders/<int:grader_id>/done',
    methods=['POST']
)
@auth.login_required
def set_grader_to_done(assignment_id: int, grader_id: int) -> EmptyResponse:
    """Indicate that the given grader is done grading the given
    `:class:.models.Assignment`.

    .. :quickref: Assignment; Set the grader status to 'done'.

    :param assignment_id: The id of the assignment the grader is done grading.
    :param grader_id: The id of the `:class:.models.User` that is done grading.
    :returns: An empty response with return code 204

    :raises APIException: If the given grader was indicated as done before
        calling this endpoint. (INVALID_STATE)
    :raises PermissionException: If the current user wants to change a status
        of somebody else but the user does not have the
        `can_update_grader_status` permission. (INCORRECT_PERMISSION)
    :raises PermissionException: If the current user wants to change its own
        status but does not have the `can_update_grader_status` or the
        `can_grade_work` permission. (INCORRECT_PERMISSION)
    """
    assig = helpers.get_or_404(
        models.Assignment,
        assignment_id,
        options=[joinedload(models.Assignment.finished_graders)],
    )

    if current_user.id == grader_id:
        auth.ensure_permission(CPerm.can_grade_work, assig.course_id)
    else:
        auth.ensure_permission(CPerm.can_update_grader_status, assig.course_id)

    grader = helpers.get_or_404(models.User, grader_id)
    if not grader.has_permission(CPerm.can_grade_work, assig.course_id):
        raise APIException(
            'The given user is not a grader in this course',
            (
                f'The user with id "{grader_id}" is not a grader '
                f'in the course "{assig.course_id}"'
            ),
            APICodes.INVALID_PARAM,
            400,
        )

    if any(g.user_id == grader_id for g in assig.finished_graders):
        raise APIException(
            'The grader is already finished!',
            f'The grader {grader_id} is already done.',
            APICodes.INVALID_STATE,
            400,
        )
    done_before = assig.graders_are_done()

    grader_done = models.AssignmentGraderDone(
        user_id=grader_id,
        assignment=assig,
    )
    db.session.add(grader_done)
    db.session.commit()

    if not done_before and assig.graders_are_done():
        psef.tasks.send_done_mail(assig.id)

    if assig.has_non_graded_submissions(grader_id):
        add_warning(
            'You have non graded work!',
            APIWarnings.GRADER_NOT_DONE,
        )

    return make_empty_response()


WorkList = t.Sequence[models.Work]  # pylint: disable=invalid-name


@api.route('/assignments/<int:assignment_id>/submissions/', methods=['GET'])
def get_all_works_for_assignment(
    assignment_id: int
) -> t.Union[JSONResponse[WorkList], ExtendedJSONResponse[WorkList]]:
    """Return all :class:`.models.Work` objects for the given
    :class:`.models.Assignment`.

    .. :quickref: Assignment; Get all works for an assignment.

    :qparam boolean extended: Whether to get extended or normal
        :class:`.models.Work` objects. The default value is ``false``, you can
        enable extended by passing ``true``, ``1`` or an empty string.

    :param int assignment_id: The id of the assignment
    :returns: A response containing the JSON serialized submissions.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the assignment is hidden and the user is
                                 not allowed to view it. (INCORRECT_PERMISSION)
    """
    assignment = helpers.get_or_404(models.Assignment, assignment_id)

    auth.ensure_permission(CPerm.can_see_assignments, assignment.course_id)

    if assignment.is_hidden:
        auth.ensure_permission(
            CPerm.can_see_hidden_assignments, assignment.course_id
        )

    obj = models.Work.query.filter_by(
        assignment_id=assignment_id,
    ).options(
        joinedload(
            models.Work.selected_items,
        ),
        # We want to load all users directly. We do this by loading the user,
        # which might be a group. For such groups we also load all users.
        # The users in this group will never be a group, so the last
        # `selectinload` here might be seen as strange. However, during the
        # serialization of a group we access `User.group`, which checks if a
        # user is really not a group. To prevent these last queries the last
        # `selectinload` is needed here.
        selectinload(
            models.Work.user,
        ).selectinload(
            models.User.group,
        ).selectinload(
            models.Group.members,
        ).selectinload(
            models.User.group,
        )
    ).order_by(t.cast(t.Any, models.Work.created_at).desc())

    if not current_user.has_permission(
        CPerm.can_see_others_work, course_id=assignment.course_id
    ):
        obj = models.Work.limit_to_user_submissions(obj, current_user)

    if helpers.extended_requested():
        obj = obj.options(undefer(models.Work.comment))
        return extended_jsonify(
            obj.all(),
            use_extended=models.Work,
        )
    else:
        return jsonify(obj.all())


@api.route("/assignments/<int:assignment_id>/submissions/", methods=['POST'])
@features.feature_required(features.Feature.BLACKBOARD_ZIP_UPLOAD)
def post_submissions(assignment_id: int) -> EmptyResponse:
    """Add submissions to the  given:class:`.models.Assignment` from a
    blackboard zip file as :class:`.models.Work` objects.

    .. :quickref: Assignment; Create works from a blackboard zip.

    You should upload a file as multiform post request. The key should start
    with 'file'. Multiple blackboard zips are not supported and result in one
    zip being chosen at (psuedo) random.

    :param int assignment_id: The id of the assignment
    :returns: An empty response with return code 204

    :raises APIException: If no assignment with given id exists.
        (OBJECT_ID_NOT_FOUND)
    :raises APIException: If there was no file in the request.
        (MISSING_REQUIRED_PARAM)
    :raises APIException: If the file parameter name is incorrect or if the
        given file does not contain any valid submissions. (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user is not allowed to manage the
        course attached to the assignment. (INCORRECT_PERMISSION)
    """
    assignment = helpers.get_or_404(models.Assignment, assignment_id)
    auth.ensure_permission(CPerm.can_upload_bb_zip, assignment.course_id)
    files = helpers.get_files_from_request(
        max_size=current_app.max_large_file_size, keys=['file']
    )

    try:
        submissions = psef.files.process_blackboard_zip(
            files[0], max_size=current_app.max_large_file_size
        )
    except Exception:  # pylint: disable=broad-except
        # TODO: Narrow this exception down.
        logger.info(
            'Exception encountered when processing blackboard zip',
            assignment_id=assignment.id,
            exc_info=True,
        )
        submissions = []

    if not submissions:
        raise APIException(
            "The blackboard zip could not imported or it was empty.",
            'The blackboard zip could not'
            ' be parsed or it did not contain any valid submissions.',
            APICodes.INVALID_PARAM, 400
        )

    missing, recalc_missing = assignment.get_divided_amount_missing()
    sub_lookup = {}
    for sub in assignment.get_all_latest_submissions():
        sub_lookup[sub.user_id] = sub

    student_course_role = models.CourseRole.query.filter_by(
        name='Student', course_id=assignment.course_id
    ).first()
    assert student_course_role is not None
    global_role = models.Role.query.filter_by(name='Student').first()

    subs = []

    found_users = {
        u.username: u
        for u in models.User.query.filter(
            t.cast(
                models.DbColumn[str],
                models.User.username,
            ).in_([si.student_id for si, _ in submissions])
        ).options(joinedload(models.User.courses))
    }

    newly_assigned: t.Set[int] = set()

    missing_users: t.List[models.User] = []
    for submission_info, _ in submissions:
        if found_users.get(submission_info.student_id, None) is None:
            # TODO: Check if this role still exists
            user = models.User(
                name=submission_info.student_name,
                username=submission_info.student_id,
                courses={assignment.course_id: student_course_role},
                email='',
                password=None,
                role=global_role,
            )
            found_users[user.username] = user
            missing_users.append(user)
    db.session.add_all(missing_users)

    for submission_info, submission_tree in submissions:
        user = found_users[submission_info.student_id]
        user.courses[assignment.course_id] = student_course_role

        work = models.Work(
            assignment=assignment,
            user=user,
            created_at=submission_info.created_at,
        )
        subs.append(work)

        if user.id is not None and user.id in sub_lookup:
            work.assigned_to = sub_lookup[user.id].assigned_to

        if work.assigned_to is None:
            if missing:
                work.assigned_to = max(missing.keys(), key=missing.get)
                missing = recalc_missing(work.assigned_to)
                sub_lookup[user.id] = work

        work.set_grade(submission_info.grade, current_user)
        work.add_file_tree(submission_tree)
        if work.assigned_to is not None:
            newly_assigned.add(work.assigned_to)

    assignment.set_graders_to_not_done(
        list(newly_assigned),
        send_mail=True,
        ignore_errors=True,
    )

    db.session.add_all(subs)
    db.session.commit()

    return make_empty_response()


@api.route('/assignments/<int:assignment_id>/linters/', methods=['GET'])
@features.feature_required(features.Feature.LINTERS)
def get_linters(assignment_id: int
                ) -> JSONResponse[t.Sequence[t.Mapping[str, t.Any]]]:
    """Get all linters for the given :class:`.models.Assignment`.

    .. :quickref: Assignment; Get all linters for a assignment.

    :param int assignment_id: The id of the assignment
    :returns: A response containing the JSON serialized linters which is sorted
        by the name of the linter.

    :>jsonarr str state: The state of the linter, which can be ``new``, or any
        state from :py:class:`.models.LinterState`.
    :>jsonarr str name: The name of this linter.
    :>jsonarr str id: The id of the linter, this will only be present when
        ``state`` is not ``new``.
    :>jsonarr ``*rest``: All items as described in
        :py:func:`.linters.get_all_linters`

    :raises APIException: If no assignment with given id exists.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not user linters in this
                                 course. (INCORRECT_PERMISSION)
    """
    assignment = helpers.get_or_404(models.Assignment, assignment_id)

    auth.ensure_permission(CPerm.can_use_linter, assignment.course_id)

    res = []
    for name, opts in linters.get_all_linters().items():
        linter = models.AssignmentLinter.query.filter_by(
            assignment_id=assignment_id, name=name
        ).first()

        if linter:
            running = db.session.query(
                models.LinterInstance.query.filter(
                    models.LinterInstance.tester_id == linter.id,
                    models.LinterInstance.state == models.LinterState.running
                ).exists()
            ).scalar()
            crashed = db.session.query(
                models.LinterInstance.query.filter(
                    models.LinterInstance.tester_id == linter.id,
                    models.LinterInstance.state == models.LinterState.crashed
                ).exists()
            ).scalar()
            if running:
                state = models.LinterState.running.name
            elif crashed:
                state = models.LinterState.crashed.name
            else:
                state = models.LinterState.done.name
            opts['id'] = linter.id
        else:
            state = 'new'

        opts['state'] = state
        opts['name'] = name

        res.append(opts)

    return jsonify(sorted(res, key=lambda item: item['name']))


@api.route('/assignments/<int:assignment_id>/linter', methods=['POST'])
@features.feature_required(features.Feature.LINTERS)
def start_linting(assignment_id: int) -> JSONResponse[models.AssignmentLinter]:
    """Starts running a specific linter on all the latest submissions
    (:class:`.models.Work`) of the given :class:`.models.Assignment`.

    .. :quickref: Assignment; Start linting an assignment with a given linter.

    :param int assignment_id: The id of the assignment
    :returns: A response containing the serialized linter that is started by
              the request

    :raises APIException: If a required parameter is missing.
                          (MISSING_REQUIRED_PARAM)
    :raises APIException: If a linter of the same name is already running on
                          the assignment. (INVALID_STATE)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not user linters in this
                                 course. (INCORRECT_PERMISSION)
    """
    content = ensure_json_dict(request.get_json())

    assig = helpers.get_or_404(models.Assignment, assignment_id)
    auth.ensure_permission(CPerm.can_use_linter, assig.course_id)

    ensure_keys_in_dict(content, [('cfg', str), ('name', str)])
    cfg = t.cast(str, content['cfg'])
    name = t.cast(str, content['name'])

    if db.session.query(
        models.LinterInstance.query.filter(
            models.AssignmentLinter.assignment_id == assignment_id,
            models.AssignmentLinter.name == content['name']
        ).exists()
    ).scalar():
        raise APIException(
            'There is still a linter instance running',
            'There is a linter named "{}" running for assignment {}'.format(
                content['name'], assignment_id
            ), APICodes.INVALID_STATE, 409
        )

    res = models.AssignmentLinter.create_linter(assignment_id, name, cfg)
    db.session.add(res)

    try:
        linter_cls = linters.get_linter_by_name(name)
    except KeyError:
        raise APIException(
            f'No linter named "{name}" was found',
            (
                f'There is no subclass of the "Linter"'
                f'class with the name "{name}"'
            ),
            APICodes.OBJECT_NOT_FOUND,
            404,
        )
    linter_cls.validate_config(cfg)

    if linter_cls.RUN_LINTER:

        def start_running_linter() -> None:
            for i in range(0, len(res.tests), 10):
                tasks.lint_instances(
                    name,
                    cfg,
                    [t.id for t in res.tests[i:i + 10]],
                )

        helpers.callback_after_this_request(start_running_linter)
    else:
        for linter_inst in res.tests:
            linter_inst.state = models.LinterState.done
    db.session.commit()

    return jsonify(res)


@api.route('/assignments/<int:assignment_id>/plagiarism/', methods=['GET'])
def get_plagiarism_runs(
    assignment_id: int,
) -> JSONResponse[t.Iterable[models.PlagiarismRun]]:
    """Get all plagiarism runs for the given :class:`.models.Assignment`.

    .. :quickref: Assignment; Get all plagiarism runs for an assignment.

    :param int assignment_id: The id of the assignment
    :returns: A response containing the JSON serialized list of plagiarism
        runs.

    :raises PermissionException: If the user can not view plagiarism runs or
        cases for this course. (INCORRECT_PERMISSION)
    """
    assig = helpers.get_or_404(models.Assignment, assignment_id)
    try:
        auth.ensure_permission(CPerm.can_view_plagiarism, assig.course_id)
    except auth.PermissionException:
        auth.ensure_permission(CPerm.can_manage_plagiarism, assig.course_id)

    return jsonify(
        models.PlagiarismRun.query.filter_by(assignment=assig).order_by(
            models.PlagiarismRun.created_at
        ).all()
    )


@api.route('/assignments/<int:assignment_id>/plagiarism', methods=['POST'])
@auth.login_required
def start_plagiarism_check(
    assignment_id: int,
) -> JSONResponse[models.PlagiarismRun]:
    """Run a plagiarism checker for the given :class:`.models.Assignment`.

    .. :quickref: Assignment; Run a plagiarism checker for an assignment.

    :param int assignment_id: The id of the assignment
    :returns: The json serialization newly created
        :class:`.models.PlagiarismRun`.

    .. note::

        This route is weird in one very important way. You can provide your
        json input in two different ways. One is the 'normal' way, the body of
        the request is the json data and the content-type is set
        appropriately. However as this route allows you to upload files, this
        approach will not always work. Therefore for this route it is also
        possible to provide json by uploading it as a file under the ``json``
        key.

    :<json str provider: The name of the plagiarism checker to use.
    :<json list old_assignments: The id of the assignments that need to be used
        as old assignments.
    :<json has_base_code: Does this request contain base code that should be
        used by the plagiarism checker.
    :<json has_old_submissions: Does this request contain old submissions that
        should be used by the plagiarism checker.
    :<json ``**rest``: The other options used by the provider, as indicated by
        ``/api/v1/plagiarism/``. Each key should be a possible option and its
        value is the value that should be used.

    :raises PermissionException: If the user can not manage plagiarism runs or
        cases for this course. (INCORRECT_PERMISSION)
    """
    assig = helpers.get_or_404(models.Assignment, assignment_id)
    auth.ensure_permission(CPerm.can_manage_plagiarism, assig.course_id)

    content = ensure_json_dict(
        ('json' in request.files and json.loads(request.files['json'].read()))
        or request.get_json()
    )

    ensure_keys_in_dict(
        content, [
            ('provider', str), ('old_assignments', list),
            ('has_base_code', bool), ('has_old_submissions', bool)
        ]
    )
    provider_name = t.cast(str, content['provider'])
    old_assig_ids = t.cast(t.List[object], content['old_assignments'])
    has_old_submissions = t.cast(bool, content['has_old_submissions'])
    has_base_code = t.cast(bool, content['has_base_code'])

    json_config = json.dumps(sorted(content.items()))
    if db.session.query(
        models.PlagiarismRun.query.filter_by(
            assignment_id=assignment_id, json_config=json_config
        ).exists()
    ).scalar():
        raise APIException(
            'This run has already been done!',
            'This assignment already has a run with the exact same config',
            APICodes.OBJECT_ALREADY_EXISTS, 400
        )

    try:
        provider_cls = helpers.get_class_by_name(
            plagiarism.PlagiarismProvider, provider_name
        )
    except ValueError:
        raise APIException(
            'The given provider does not exist',
            f'The provider "{provider_name}" does not exist',
            APICodes.OBJECT_NOT_FOUND, 404
        )

    if any(not isinstance(item, int) for item in old_assig_ids):
        raise APIException(
            'All assignment ids should be integers',
            'Some ids were not integers', APICodes.INVALID_PARAM, 400
        )
    old_assigs = helpers.get_in_or_error(
        models.Assignment,
        t.cast(models.DbColumn[int], models.Assignment.id),
        t.cast(t.List[int], old_assig_ids),
    )

    for old_course_id in set(a.course_id for a in old_assigs):
        auth.ensure_permission(CPerm.can_view_plagiarism, old_course_id)

    if has_old_submissions:
        max_size = current_app.max_file_size
        old_subs = helpers.get_files_from_request(
            max_size=max_size, keys=['old_submissions']
        )
        tree = psef.files.process_files(old_subs, max_size=max_size)
        for i, child in enumerate(tree.values):
            if isinstance(
                child,
                psef.files.ExtractFileTreeFile,
            ) and archive.Archive.is_archive(child.name):
                child_path = os.path.join(
                    current_app.config['UPLOAD_DIR'], child.disk_name
                )
                with open(child_path, 'rb') as f:
                    tree.values[i] = psef.files.process_files(
                        [
                            werkzeug.datastructures.FileStorage(
                                stream=f,
                                filename=child.name,
                            )
                        ],
                        max_size=max_size,
                    )
                    # This is to create a name for the author that resembles
                    # the name of the archive.
                    tree.values[i].name = child.name.split('.')[0]
                os.unlink(child_path)

        virtual_course = models.Course.create_virtual_course(tree)
        db.session.add(virtual_course)
        old_assigs.append(virtual_course.assignments[0])

    # provider_cls is a subclass of PlagiarismProvider and that can be
    # instantiated
    provider: plagiarism.PlagiarismProvider = t.cast(t.Any, provider_cls)()
    provider.set_options(content)

    # If base code was provided check this now. We do this after all checking
    # as the task is responsible for cleaning the created directory, so any
    # exception after this point would mean that the directory won't be cleaned
    # up.
    base_code_dir = None
    if has_base_code:
        # We do not have any provider yet that doesn't support this, so we
        # don't check the coverage.
        if not provider.supports_base_code():  # pragma: no cover
            raise APIException(
                'This provider does not support base code',
                f'The provider "{provider_name}" does not support base code',
                APICodes.INVALID_PARAM, 400
            )

        base_code = helpers.get_files_from_request(
            max_size=current_app.max_large_file_size, keys=['base_code']
        )[0]
        base_code_dir, _ = psef.files.extract_to_temp(
            base_code,
            max_size=current_app.max_large_file_size,
            archive_name='base_code_archive',
            parent_result_dir=current_app.config['SHARED_TEMP_DIR'],
        )

    try:
        run = models.PlagiarismRun(json_config=json_config, assignment=assig)
        db.session.add(run)
        db.session.commit()

        # Start after this request because the created run needs to be commited
        # into the database
        helpers.callback_after_this_request(
            lambda: psef.tasks.run_plagiarism_control(
                plagiarism_run_id=run.id,
                main_assignment_id=assig.id,
                old_assignment_ids=[a.id for a in old_assigs],
                call_args=provider.get_program_call(),
                base_code_dir=base_code_dir,
                csv_location=provider.matches_output,
            )
        )
    except:  # pylint: disable=broad-except; #pragma: no cover
        # Delete base_code_dir if anything goes wrong
        if base_code_dir:
            shutil.rmtree(base_code_dir)
        raise

    return jsonify(run)


@api.route(
    '/assignments/<int:assignment_id>/groups/<int:group_id>/member_states/',
    methods=['GET']
)
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def get_group_member_states(assignment_id: int, group_id: int
                            ) -> JSONResponse[t.Mapping[int, bool]]:
    """Get the LTI states for the members of a group for the given assignment.

    .. :quickref: Assignment; Get LTI states for members of a group.

    :param assignment_id: The assignment for which the LTI states should be
        given.
    :param group_id: The group for which the states should be returned.
    :returns: A mapping between user id and a boolean indicating if we can
        already passback grades for this user. If the assignment is any LTI
        assignment and any of the values in this mapping is ``False`` trying to
        submit anyway will result in a failure.
    """
    assig = helpers.get_or_404(models.Assignment, assignment_id)
    group = helpers.filter_single_or_404(
        models.Group, models.Group.id == group_id,
        models.Group.group_set_id == assig.group_set_id
    )
    auth.ensure_can_view_group(group)

    return jsonify(group.get_member_lti_states(assig))

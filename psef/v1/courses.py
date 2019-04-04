"""
This module defines all API routes with the main directory "courses". The APIs
are used to create courses and return information about courses.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t

from flask import request
from sqlalchemy.orm import selectinload
from mypy_extensions import TypedDict

import psef.auth as auth
import psef.models as models
import psef.helpers as helpers
from psef import limiter, current_user
from psef.errors import APICodes, APIException
from psef.models import db
from psef.helpers import (
    JSONResponse, EmptyResponse, jsonify, ensure_keys_in_dict,
    make_empty_response, get_json_dict_from_request
)

from . import api
from .. import features
from ..lti import LTI_COURSEROLE_LOOKUPS
from ..permissions import CoursePermMap
from ..permissions import CoursePermission as CPerm
from ..permissions import GlobalPermission as GPerm

_UserCourse = TypedDict(  # pylint: disable=invalid-name
    '_UserCourse', {
        'User': models.User,
        'CourseRole': models.CourseRole
    }
)


@api.route('/courses/<int:course_id>/roles/<int:role_id>', methods=['DELETE'])
def delete_role(course_id: int, role_id: int) -> EmptyResponse:
    """Remove a :class:`.models.CourseRole` from the given
    :class:`.models.Course`.

    .. :quickref: Course; Delete a course role from a course.

    :param int course_id: The id of the course
    :returns: An empty response with return code 204

    :raises APIException: If the role with the given ids does not exist.
        (OBJECT_NOT_FOUND)
    :raises APIException: If there are still users with this role.
        (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
        given id. (INCORRECT_PERMISSION)
    """
    auth.ensure_permission(CPerm.can_edit_course_roles, course_id)

    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )
    role = helpers.filter_single_or_404(
        models.CourseRole, models.CourseRole.course_id == course_id,
        models.CourseRole.id == role_id
    )

    if course.lti_provider is not None:
        if any(r == role.name for r in LTI_COURSEROLE_LOOKUPS.values()):
            lms = course.lti_provider.lms_name
            raise APIException(
                f'You cannot delete default {lms} roles', (
                    'The course "{}" is an LTI course so it is impossible to '
                    'delete role {}'
                ).format(course.id, role.id), APICodes.INCORRECT_PERMISSION,
                403
            )

    sql = db.session.query(
        models.user_course
    ).filter(models.user_course.c.course_id == role_id).exists()
    if db.session.query(sql).scalar():
        raise APIException(
            'There are still users with this role',
            'There are still users with role {}'.format(role_id),
            APICodes.INVALID_PARAM, 400
        )

    db.session.delete(role)
    db.session.commit()

    return make_empty_response()


@api.route('/courses/<int:course_id>/roles/', methods=['POST'])
def add_role(course_id: int) -> EmptyResponse:
    """Add a new :class:`.models.CourseRole` to the given
    :class:`.models.Course`.

    .. :quickref: Course; Add a new course role to a course.

    :param int course_id: The id of the course
    :returns: An empty response with return code 204.

    :<json str name: The name of the new course role.

    :raises APIException: If the name parameter was not in the request.
                          (MISSING_REQUIRED_PARAM)
    :raises APIException: If the course with the given id was not found.
                          (OBJECT_NOT_FOUND)
    :raises APIException: If the course already has a role with the submitted
                          name. (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
                                 given id. (INCORRECT_PERMISSION)
    """
    auth.ensure_permission(CPerm.can_edit_course_roles, course_id)

    content = get_json_dict_from_request()

    ensure_keys_in_dict(content, [('name', str)])
    name = t.cast(str, content['name'])

    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )

    if models.CourseRole.query.filter_by(
        name=name, course_id=course_id
    ).first() is not None:
        raise APIException(
            'This course already has a role with this name',
            'The course "{}" already has a role named "{}"'.format(
                course_id, name
            ), APICodes.INVALID_PARAM, 400
        )

    role = models.CourseRole(name=name, course=course)
    db.session.add(role)
    db.session.commit()

    return make_empty_response()


@api.route('/courses/<int:course_id>/roles/<int:role_id>', methods=['PATCH'])
def update_role(course_id: int, role_id: int) -> EmptyResponse:
    """Update the :class:`.models.Permission` of a given
    :class:`.models.CourseRole` in the given :class:`.models.Course`.

    .. :quickref: Course; Update a permission for a certain role.

    :param int course_id: The id of the course.
    :param int role_id: The id of the course role.
    :returns: An empty response with return code 204.

    :<json str permission: The name of the permission to change.
    :<json bool value: The value to set the permission to (``True`` means the
        specified role has the specified permission).

    :raises APIException: If the value or permission parameter are not in the
                          request. (MISSING_REQUIRED_PARAM)
    :raises APIException: If the role with the given id does not exist or the
                          permission with the given name does not exist.
                          (OBJECT_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
                                 given id. (INCORRECT_PERMISSION)
    """
    content = get_json_dict_from_request()

    auth.ensure_permission(CPerm.can_edit_course_roles, course_id)

    ensure_keys_in_dict(content, [('value', bool), ('permission', str)])
    value = t.cast(bool, content['value'])
    permission_name = t.cast(str, content['permission'])
    permission = CPerm.get_by_name(permission_name)

    role = helpers.filter_single_or_404(
        models.CourseRole,
        models.CourseRole.course_id == course_id,
        models.CourseRole.id == role_id,
    )

    if (
        current_user.courses[course_id].id == role.id and
        permission == CPerm.can_edit_course_roles
    ):
        raise APIException(
            'You cannot remove this permission from your own role', (
                'The current user is in role {} which'
                ' cannot remove "can_edit_course_roles"'
            ).format(role.id), APICodes.INCORRECT_PERMISSION, 403
        )

    role.set_permission(permission, value)

    db.session.commit()

    return make_empty_response()


@api.route('/courses/<int:course_id>/roles/', methods=['GET'])
def get_all_course_roles(
    course_id: int
) -> JSONResponse[t.Union[t.Sequence[models.CourseRole], t.Sequence[
    t.MutableMapping[str, t.Union[t.Mapping[str, bool], bool]]]]]:
    """Get a list of all :class:`.models.CourseRole` objects of a given
    :class:`.models.Course`.

    .. :quickref: Course; Get all course roles for a single course.

    :param int course_id: The id of the course to get the roles for.
    :returns: An array of all course roles for the given course.

    :>jsonarr perms: All permissions this role has as returned
        by :py:meth:`.models.CourseRole.get_all_permissions`.
    :>jsonarrtype perms: :py:class:`t.Mapping[str, bool]`
    :>jsonarr bool own: True if the current course role is the current users
        course role.
    :>jsonarr ``**rest``: The course role as returned by
        :py:meth:`.models.CourseRole.__to_json__`

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
                                 given id. (INCORRECT_PERMISSION)
    """
    auth.ensure_permission(CPerm.can_edit_course_roles, course_id)

    course_roles: t.Sequence[models.CourseRole]
    course_roles = models.CourseRole.query.filter_by(course_id=course_id
                                                     ).order_by(
                                                         models.CourseRole.name
                                                     ).all()

    if request.args.get('with_roles') == 'true':
        res = []
        for course_role in course_roles:
            json_course = course_role.__to_json__()
            json_course['perms'] = CPerm.create_map(
                course_role.get_all_permissions()
            )
            json_course['own'] = current_user.courses[course_role.course_id
                                                      ] == course_role
            res.append(json_course)
        return jsonify(res)
    return jsonify(course_roles)


@api.route('/courses/<int:course_id>/users/', methods=['PUT'])
def set_course_permission_user(
    course_id: int
) -> t.Union[EmptyResponse, JSONResponse[_UserCourse]]:
    """Set the :class:`.models.CourseRole` of a :class:`.models.User` in the
    given :class:`.models.Course`.

    .. :quickref: Course; Change the course role for a user.

    :param int course_id: The id of the course
    :returns: If the user_id parameter is set in the request the response will
              be empty with return code 204. Otherwise the response will
              contain the JSON serialized user and course role with return code
              201

    :raises APIException: If the parameter role_id or not at least one of
                          user_id and user_email are in the request.
                          (MISSING_REQUIRED_PARAM)
    :raises APIException: If no role with the given role_id or no user
                          with the supplied parameters exists.
                          (OBJECT_ID_NOT_FOUND)
    :raises APIException: If the user was selected by email and the user is
                          already in the course. (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not manage the course with the
                                 given id. (INCORRECT_PERMISSION)

    .. todo::
        This function should probability be splitted.
    """
    auth.ensure_permission(CPerm.can_edit_course_users, course_id)

    content = get_json_dict_from_request()
    ensure_keys_in_dict(content, [('role_id', int)])
    role_id = t.cast(int, content['role_id'])

    role = helpers.filter_single_or_404(
        models.CourseRole, models.CourseRole.id == role_id,
        models.CourseRole.course_id == course_id
    )

    res: t.Union[EmptyResponse, JSONResponse[_UserCourse]]

    if 'user_id' in content:
        ensure_keys_in_dict(content, [('user_id', int)])
        user_id = t.cast(int, content['user_id'])

        user = helpers.get_or_404(models.User, user_id)

        if user.id == current_user.id:
            raise APIException(
                'You cannot change your own role',
                'The user requested and the current user are the same',
                APICodes.INCORRECT_PERMISSION, 403
            )

        res = make_empty_response()
    elif 'username' in content:
        ensure_keys_in_dict(content, [('username', str)])

        user = helpers.filter_single_or_404(
            models.User, models.User.username == content['username']
        )

        if course_id in user.courses:
            raise APIException(
                'The specified user is already in this course',
                'The user {} is in course {}'.format(user.id, course_id),
                APICodes.INVALID_PARAM, 400
            )

        res = jsonify({
            'User': user,
            'CourseRole': role,
        }, status_code=201)
    else:
        raise APIException(
            'None of the keys "user_id" or "role_id" were found', (
                'The given content ({})'
                ' does  not contain "user_id" or "user_email"'
            ).format(content), APICodes.MISSING_REQUIRED_PARAM, 400
        )

    user.courses[role.course_id] = role
    db.session.commit()
    return res


@api.route('/courses/<int:course_id>/users/', methods=['GET'])
@auth.login_required
def get_all_course_users(
    course_id: int
) -> JSONResponse[t.Union[t.List[_UserCourse], t.List[models.User]]]:
    """Return a list of all :class:`.models.User` objects and their
    :class:`.models.CourseRole` in the given :class:`.models.Course`.

    .. :quickref: Course; Get all users for a single course.

    :param int course_id: The id of the course

    :query string q: Search for users matching this query string. This will
        change the output to a list of users.

    :returns: A response containing the JSON serialized users and course roles

    :>jsonarr User:  A member of the given course.
    :>jsonarrtype User: :py:class:`~.models.User`
    :>jsonarr CourseRole: The role that this user has.
    :>jsonarrtype CourseRole: :py:class:`~.models.CourseRole`
    """
    auth.ensure_permission(CPerm.can_list_course_users, course_id)
    course = helpers.get_or_404(models.Course, course_id)

    if 'q' in request.args:

        @limiter.limit('1 per second', key_func=lambda: str(current_user.id))
        def get_users_in_course() -> t.List[models.User]:
            query: str = request.args.get('q', '')
            base = course.get_all_users_in_course().from_self(models.User)
            return helpers.filter_users_by_name(query, base).all()

        return jsonify(get_users_in_course())

    users = course.get_all_users_in_course()

    user_course: t.List[_UserCourse]
    user_course = [
        {
            'User': user,
            'CourseRole': crole
        } for user, crole in users
    ]
    return jsonify(sorted(user_course, key=lambda item: item['User'].name))


@api.route('/courses/<int:course_id>/assignments/', methods=['GET'])
def get_all_course_assignments(
    course_id: int
) -> JSONResponse[t.Sequence[models.Assignment]]:
    """Get all :class:`.models.Assignment` objects of the given
    :class:`.models.Course`.

    .. :quickref: Course; Get all assignments for single course.

    The returned assignments are sorted by deadline.

    :param int course_id: The id of the course
    :returns: A response containing the JSON serialized assignments sorted by
        deadline of the assignment. See
        :py:func:`.models.Assignment.__to_json__` for the way assignments are
        given.

    :raises APIException: If there is no course with the given id.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not see assignments in the
                                 given course. (INCORRECT_PERMISSION)
    """
    auth.ensure_permission(CPerm.can_see_assignments, course_id)

    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )

    return jsonify(course.get_all_visible_assignments())


@api.route('/courses/<int:course_id>/assignments/', methods=['POST'])
def create_new_assignment(course_id: int) -> JSONResponse[models.Assignment]:
    """Create a new course for the given assignment.

    .. :quickref: Course; Create a new assignment in a course.

    :param int course_id: The course to create an assignment in.

    :<json str name: The name of the new assignment.

    :returns: The newly created assignment.

    :raises PermissionException: If the current user does not have the
        ``can_create_assignment`` permission (INCORRECT_PERMISSION).
    """
    auth.ensure_permission(CPerm.can_create_assignment, course_id)

    content = get_json_dict_from_request()
    ensure_keys_in_dict(content, [('name', str)])
    name = t.cast(str, content['name'])

    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )

    if course.lti_course_id is not None:
        lms = course.lti_provider.lms_name
        raise APIException(
            f'You cannot add assignments to a {lms} course',
            f'The course "{course_id}" is a LTI course',
            APICodes.INVALID_STATE, 400
        )

    assig = models.Assignment(
        name=name,
        course=course,
    )
    db.session.add(assig)
    db.session.commit()

    return jsonify(assig)


@api.route('/courses/', methods=['POST'])
@auth.permission_required(GPerm.can_create_courses)
def add_course() -> JSONResponse[models.Course]:
    """Add a new :class:`.models.Course`.

    .. :quickref: Course; Add a new course.

    :returns: A response containing the JSON serialization of the new course

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not create courses.
                                 (INCORRECT_PERMISSION)
    :raises APIException: If the parameter "name" is not in the request.
        (MISSING_REQUIRED_PARAM)
    """
    content = get_json_dict_from_request()
    ensure_keys_in_dict(content, [('name', str)])
    name = t.cast(str, content['name'])

    new_course = models.Course(name)
    db.session.add(new_course)
    db.session.commit()

    role = models.CourseRole.get_initial_course_role(new_course)
    current_user.courses[new_course.id] = role
    db.session.commit()

    return jsonify(new_course)


@api.route('/courses/', methods=['GET'])
@auth.login_required
def get_courses() -> JSONResponse[t.Sequence[t.Mapping[str, t.Any]]]:
    """Return all :class:`.models.Course` objects the current user is a member
    of.

    .. :quickref: Course; Get all courses the current user is enrolled in.

    :returns: A response containing the JSON serialized courses

    :param str extended: If set to ``true``, ``1`` or the empty string all the
        assignments and group sets for each course are also included under the
        key ``assignments`` and ``group_sets`` respectively.

    :>jsonarr str role: The name of the role the current user has in this
        course.
    :>jsonarr ``**rest``: JSON serialization of :py:class:`psef.models.Course`.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """

    def _get_rest(course: models.Course) -> t.Mapping[str, t.Any]:
        if helpers.extended_requested():
            snippets: t.Sequence[models.CourseSnippet] = []
            if current_user.has_permission(
                CPerm.can_view_course_snippets, course_id=course.id
            ):
                snippets = course.snippets

            return {
                'assignments': course.get_all_visible_assignments(),
                'group_sets': course.group_sets,
                'snippets': snippets,
                **course.__to_json__(),
            }
        return course.__to_json__()

    extra_loads = [
        selectinload(
            models.User.courses,
        ).selectinload(
            models.CourseRole.course,
        )
    ]
    if helpers.extended_requested():
        extra_loads = [
            extra_loads[0].selectinload(
                models.Course.assignments,
            ),
            selectinload(
                models.User.courses,
            ).selectinload(
                models.CourseRole._permissions,  # pylint: disable=protected-access
            )
        ]

    user = helpers.get_or_404(
        models.User,
        current_user.id,
        options=extra_loads,
    )

    return jsonify(
        [
            {
                'role': c.name,
                **_get_rest(c.course),
            } for c in user.courses.values()
        ]
    )


@api.route('/courses/<int:course_id>', methods=['GET'])
@auth.login_required
def get_course_data(course_id: int) -> JSONResponse[t.Mapping[str, t.Any]]:
    """Return course data for a given :class:`.models.Course`.

    .. :quickref: Course; Get data for a given course.

    :param int course_id: The id of the course

    :returns: A response containing the JSON serialized course

    :>json str role: The name of the role the current user has in this
        course.
    :>json ``**rest``: JSON serialization of :py:class:`psef.models.Course`.

    :raises APIException: If there is no course with the given id.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    # TODO: Optimize this loop to a single query
    for course_role in current_user.courses.values():
        if course_role.course_id == course_id:
            return jsonify(
                {
                    'role': course_role.name,
                    **course_role.course.__to_json__(),
                }
            )

    raise APIException(
        'Course not found',
        'The course with id {} was not found'.format(course_id),
        APICodes.OBJECT_ID_NOT_FOUND, 404
    )


@api.route('/courses/<int:course_id>/permissions/', methods=['GET'])
@auth.login_required
def get_permissions_for_course(
    course_id: int,
) -> JSONResponse[CoursePermMap]:
    """Get all the course :class:`.models.Permission` of the currently logged
    in :class:`.models.User`

    .. :quickref: Course; Get all the course permissions for the current user.

    :param int course_id: The id of the course of which the permissions should
        be retrieved.
    :returns: A mapping between the permission name and a boolean indicating if
        the currently logged in user has this permission.
    """
    course = helpers.get_or_404(
        models.Course,
        course_id,
        also_error=lambda c: c.virtual,
    )
    return jsonify(CPerm.create_map(current_user.get_all_permissions(course)))


@api.route('/courses/<int:course_id>/group_sets/', methods=['GET'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def get_group_sets(course_id: int
                   ) -> JSONResponse[t.Sequence[models.GroupSet]]:
    """Get the all the :class:`.models.GroupSet` objects in the given course.

    .. :quickref: Course; Get all group sets in the course.

    :param int course_id: The id of the course of which the group sets should
        be retrieved.
    :returns: A list of group sets.
    """
    course = helpers.get_or_404(models.Course, course_id)
    auth.ensure_enrolled(course.id)
    return jsonify(course.group_sets)


@api.route('/courses/<int:course_id>/group_sets/', methods=['PUT'])
@features.feature_required(features.Feature.GROUPS)
@auth.login_required
def create_group_set(course_id: int) -> JSONResponse[models.GroupSet]:
    """Create or update a :class:`.models.GroupSet` in the given course id.

    .. :quickref: Course; Create a new group set in the course.

    :>json int minimum_size: The minimum size attribute that the group set
        should have.
    :>json int maximum_size: The maximum size attribute that the group set
        should have.
    :>json int id: The id of the group to update.
    :param course_id: The id of the course in which the group set should be
        created or updated. The course id of a group set cannot change.
    :returns: The created or updated group.
    """
    auth.ensure_permission(CPerm.can_edit_group_set, course_id)
    course = helpers.get_or_404(models.Course, course_id)

    content = get_json_dict_from_request()
    ensure_keys_in_dict(
        content, [
            ('minimum_size', int),
            ('maximum_size', int),
        ]
    )
    min_size = t.cast(int, content['minimum_size'])
    max_size = t.cast(int, content['maximum_size'])

    if 'id' in content:
        ensure_keys_in_dict(content, [('id', int)])
        group_set_id = t.cast(int, content['id'])
        group_set = helpers.get_or_404(
            models.GroupSet,
            group_set_id,
        )
        if group_set.course_id != course.id:
            raise APIException(
                'You cannot change the course id of a group set', (
                    f'The group set {group_set.id} is '
                    f'not connected to course {course.id}'
                ), APICodes.INVALID_PARAM, 400
            )
    else:
        group_set = models.GroupSet(course_id=course.id)
        models.db.session.add(group_set)

    if min_size <= 0:
        raise APIException(
            'Minimum size should be larger than 0',
            f'Minimum size "{min_size}" is <= than 0', APICodes.INVALID_PARAM,
            400
        )
    elif max_size < min_size:
        raise APIException(
            'Maximum size is smaller than minimum size', (
                f'Maximum size "{max_size}" is smaller '
                f'than minimum size "{min_size}"'
            ), APICodes.INVALID_PARAM, 400
        )
    elif group_set.largest_group_size > max_size:
        raise APIException(
            'There are groups larger than the new maximum size',
            f'Some groups have more than {max_size} members',
            APICodes.INVALID_PARAM, 400
        )
    elif group_set.smallest_group_size < min_size:
        raise APIException(
            'There are groups smaller than the new minimum size',
            f'Some groups have less than {min_size} members',
            APICodes.INVALID_PARAM, 400
        )
    group_set.minimum_size = min_size
    group_set.maximum_size = max_size

    models.db.session.commit()

    return jsonify(group_set)


@api.route('/courses/<int:course_id>/snippets/', methods=['GET'])
@auth.permission_required(GPerm.can_use_snippets)
@auth.login_required
def get_course_snippets(course_id: int
                        ) -> JSONResponse[t.Sequence[models.CourseSnippet]]:
    """Get all snippets (:class:`.models.CourseSnippet`) of the given
    :class:`.models.Course`.

    .. :quickref: CourseSnippet; Get all snippets for the given course.

    :returns: An array containing all snippets for the given course.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use snippets.
        (INCORRECT_PERMISSION)
    :raises PermissionException: If the user can not manage snippets for this
        course. (INCORRECT_PERMISSION)
    """
    auth.ensure_any_of_permissions(
        [CPerm.can_view_course_snippets, CPerm.can_manage_course_snippets],
        course_id,
    )

    course = helpers.get_or_404(models.Course, course_id)
    return jsonify(course.snippets)


@api.route('/courses/<int:course_id>/snippet', methods=['PUT'])
@auth.permission_required(GPerm.can_use_snippets)
@auth.login_required
def create_course_snippet(course_id: int
                          ) -> JSONResponse[models.CourseSnippet]:
    """Add or modify a :class:`.models.CourseSnippet` by key.

    .. :quickref: CourseSnippet; Add or modify a course snippet.

    :returns: A response containing the JSON serialized snippet and return
              code 201.
    :<json str value: The new value of the snippet.
    :<json str key: The key of the new or existing snippet.

    :raises APIException: If the parameters "key", "value", and/or "course_id"
        were not in the request. (MISSING_REQUIRED_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use snippets
        (INCORRECT_PERMISSION)
    """
    auth.ensure_permission(CPerm.can_manage_course_snippets, course_id)
    content = get_json_dict_from_request()
    ensure_keys_in_dict(content, [('value', str), ('key', str)])
    key = t.cast(str, content['key'])
    value = t.cast(str, content['value'])

    snippet = models.CourseSnippet.query.filter_by(
        course_id=course_id,
        key=key,
    ).first()

    if snippet is None:
        snippet = models.CourseSnippet(
            course_id=course_id,
            key=key,
            value=value,
        )
        db.session.add(snippet)
    else:
        snippet.value = value

    db.session.commit()

    return jsonify(snippet, status_code=201)


@api.route(
    '/courses/<int:course_id>/snippets/<int:snippet_id>', methods=['PATCH']
)
@auth.permission_required(GPerm.can_use_snippets)
@auth.login_required
def patch_course_snippet(course_id: int, snippet_id: int) -> EmptyResponse:
    """Modify the :class:`.models.CourseSnippet` with the given id.

    .. :quickref: CourseSnippet; Change a snippets key and value.

    :param int snippet_id: The id of the snippet to change.
    :returns: An empty response with return code 204.

    :<json str key: The new key of the snippet.
    :<json str value: The new value of the snippet.

    :raises APIException: If the parameters "key" and/or "value" were not in
        the request. (MISSING_REQUIRED_PARAM)
    :raises APIException: If the snippet does not belong to the current user.
        (INCORRECT_PERMISSION)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use snippets.
        (INCORRECT_PERMISSION)
    """
    auth.ensure_permission(CPerm.can_manage_course_snippets, course_id)
    content = get_json_dict_from_request()

    ensure_keys_in_dict(content, [('key', str), ('value', str)])
    key = t.cast(str, content['key'])
    value = t.cast(str, content['value'])

    snip = helpers.get_or_404(models.CourseSnippet, snippet_id)

    if snip.course_id != course_id:
        raise APIException(
            'The given snippet does not belong to the given course',
            'The snippet "{}" does not belong to course "{}"'.format(
                snip.id, course_id
            ), APICodes.INCORRECT_PERMISSION, 403
        )

    snip.key = key
    snip.value = value
    db.session.commit()

    return make_empty_response()


@api.route(
    '/courses/<int:course_id>/snippets/<int:snippet_id>', methods=['DELETE']
)
@auth.permission_required(GPerm.can_use_snippets)
@auth.login_required
def delete_course_snippets(course_id: int, snippet_id: int) -> EmptyResponse:
    """Delete the :class:`.models.CourseSnippet` with the given id.

    .. :quickref: CourseSnippet; Delete a course snippet.

    :param int snippet_id: The id of the snippet
    :returns: An empty response with return code 204

    :raises APIException: If the snippet with the given id does not exist.
        (OBJECT_ID_NOT_FOUND)
    :raises APIException: If the snippet does not belong the current user.
        (INCORRECT_PERMISSION)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not use snippets.
        (INCORRECT_PERMISSION)
    """
    auth.ensure_permission(CPerm.can_manage_course_snippets, course_id)

    snip: t.Optional[models.CourseSnippet]
    snip = helpers.get_or_404(models.CourseSnippet, snippet_id)
    snip = models.CourseSnippet.query.get(snippet_id)
    assert snip is not None

    if snip.course_id != course_id:
        raise APIException(
            'The given snippet does not belong to the given course',
            'The snippet "{}" does not belong to course "{}"'.format(
                snip.id, course_id
            ), APICodes.INCORRECT_PERMISSION, 403
        )
    else:
        db.session.delete(snip)
        db.session.commit()
        return make_empty_response()

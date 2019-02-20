"""
This module defines all API routes with the main directory "permissions". These
APIs are used communicate the permissions users.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t

from flask import request

import psef.auth as auth
from psef import current_user
from psef.errors import APICodes, APIException
from psef.helpers import (
    JSONResponse, jsonify, ensure_keys_in_dict, add_deprecate_warning
)

from . import api
from ..permissions import CoursePermMap, GlobalPermMap
from ..permissions import CoursePermission as CPerm
from ..permissions import GlobalPermission as GPerm


@api.route('/permissions/', methods=['GET'])
@auth.login_required
def get_course_or_global_permissions(
) -> JSONResponse[t.Union[GlobalPermMap, t.Mapping[int, CoursePermMap]]]:
    """Get all the global :class:`.psef.models.Permission` or the value of a
    permission in all courses of the currently logged in
    :class:`.psef.models.User`

    .. :quickref: Permission; Get global permissions or all the course
        permissions for the current user.

    :qparam str type: The type of permissions to get. This can be ``global`` or
        ``course``.
    :qparam str permission: The permissions to get when getting course
        permissions. You can pass this parameter multiple times to get multiple
        permissions. DEPRECATED: This option is deprecated, as it is preferred
        that you simply get all permissions for a course.

    :returns: The returning object depends on the given ``type``. If it was
        ``global`` a mapping between permissions name and a boolean indicating
        if the currently logged in user has this permissions is returned.

        If it was ``course`` such a mapping is returned for every course the
        user is enrolled in. So it is a mapping between course ids and
        permission mapping. The permissions given as ``permission`` query
        parameter are the only ones that are present in the permission
        map. When no ``permission`` query is given all course permissions are
        returned.
    """
    ensure_keys_in_dict(request.args, [('type', str)])
    permission_type = t.cast(str, request.args['type']).lower()

    if permission_type == 'global':
        return jsonify(GPerm.create_map(current_user.get_all_permissions()))
    elif permission_type == 'course' and 'permission' in request.args:
        add_deprecate_warning(
            'Requesting a subset of course permissions is deprecated'
        )
        # Make sure at least one permission is present
        ensure_keys_in_dict(request.args, [('permission', str)])
        perm_names = t.cast(t.List[str], request.args.getlist('permission'))
        return jsonify(
            {
                course_id: CPerm.create_map(v)
                for course_id, v in current_user.get_permissions_in_courses(
                    [CPerm.get_by_name(p) for p in perm_names]
                ).items()
            }
        )
    elif permission_type == 'course':
        return jsonify(
            {
                course_id: CPerm.create_map(v)
                for course_id, v in current_user.
                get_all_permissions_in_courses().items()
            }
        )
    else:
        raise APIException(
            'Invalid permission type given',
            f'The given type "{permission_type}" is not "global" or "course"',
            APICodes.INVALID_PARAM,
            400,
        )

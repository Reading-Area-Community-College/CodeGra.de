"""This module implements all authorization functions used by :py:mod:`psef`.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
from functools import wraps

import oauth2
import flask_jwt_extended as flask_jwt
from flask import _app_ctx_stack  # type: ignore
from werkzeug.local import LocalProxy
from mypy_extensions import NoReturn

import psef
from psef.exceptions import APICodes, APIException, PermissionException

from .permissions import CoursePermission as CPerm
from .permissions import GlobalPermission as GPerm

jwt = flask_jwt.JWTManager()  # pylint: disable=invalid-name

T = t.TypeVar('T', bound=t.Callable)


def init_app(app: t.Any) -> None:
    """Initialize the app by initializing our jwt manager.

    :param app: The flask app to initialize.
    """
    jwt.init_app(app)


def _get_login_exception(
    desc: str = 'No user was logged in.'
) -> PermissionException:
    return PermissionException(
        'You need to be logged in to do this.', desc, APICodes.NOT_LOGGED_IN,
        401
    )


def _raise_login_exception(desc: str = 'No user was logged in.') -> NoReturn:
    raise _get_login_exception(desc)


@jwt.revoked_token_loader
@jwt.expired_token_loader
@jwt.invalid_token_loader
@jwt.needs_fresh_token_loader
def _handle_jwt_errors(
    reason: str = 'No user was logged in.',
) -> 'psef.helpers.JSONResponse[PermissionException]':
    return psef.helpers.jsonify(
        PermissionException(
            'You need to be logged in to do this.',
            reason,
            APICodes.NOT_LOGGED_IN,
            401,
        ),
        status_code=401
    )


jwt.user_loader_error_loader(
    lambda id: _handle_jwt_errors(f'No user with id "{id}" was found.')
)


@jwt.user_loader_callback_loader
def _load_user(user_id: int) -> t.Optional['psef.models.User']:
    return psef.models.User.query.get(int(user_id))


def _user_active(user: t.Optional['psef.models.User']) -> bool:
    """Check if the given user is active.

    :returns: True if the given user is not ``None`` and active.
    """
    try:
        return user is not None and user.is_active
    except AttributeError:
        return False


def login_required(fun: T) -> T:
    """Make sure a valid user is logged in at this moment.

    :raises PermissionException: If no user was logged in.
    """

    @wraps(fun)
    def __wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        ensure_logged_in()
        return fun(*args, **kwargs)

    return t.cast(T, __wrapper)


def ensure_logged_in() -> None:
    """Make sure a user is currently logged in.

    :returns: Nothing.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    if not _user_active(psef.current_user):
        _raise_login_exception()


@login_required
def ensure_enrolled(
    course_id: int, user: t.Optional['psef.models.User'] = None
) -> None:
    """Ensure that the given user is enrolled in the given course.

    :param course_id: The id of the course to check for.
    :param user: The user to check for. This defaults to the current user.

    :returns: Nothing.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user is not enrolled.
        (INCORRECT_PERMISSION)
    """
    if user is None:
        label = 'You are'
        user = psef.current_user
    else:
        label = f'The user "{user.name}" is'

    if user.virtual or course_id not in user.courses:
        raise PermissionException(
            f'{label} not enrolled in this course.',
            f'The user "{user.id}" is not enrolled in course "{course_id}"',
            APICodes.INCORRECT_PERMISSION, 403
        )


def set_current_user(user: 'psef.models.User') -> None:
    """Set the current user for this request.

    You probably never should use this method, it is only useful after logging
    in a user.

    :param user: The user that should become the current user.
    :returns: Nothing
    """
    # This prevents infinite recursion if the `user` is a `LocalProxy` by
    # making sure we always assign an actual User object.
    if isinstance(user, LocalProxy):
        # pylint: disable=protected-access
        user = psef.current_user._get_current_object()  # type: ignore
    # This sets the current user for flask jwt. See
    # https://github.com/vimalloc/flask-jwt-extended/issues/206 to make this
    # easier.
    _app_ctx_stack.top.jwt_user = user


@login_required
def ensure_can_submit_work(
    assig: 'psef.models.Assignment',
    author: 'psef.models.User',
) -> None:
    """Check if the current user can submit for the given assignment as the given
    author.

    .. note::

        This function also checks if the assignment is a LTI assignment. If
        this is the case it makes sure the ``author`` can do grade passback.

    :param assig: The assignment that should be submitted to.
    :param author: The author of the submission.

    :raises PermissionException: If there the current user cannot submit for
        the given author.
    :raises APIException: If the author is not enrolled in course of the given
        assignment or if the LTI state was wrong.
    """
    submit_self = psef.current_user.id == author.id

    if assig.course_id not in author.courses:
        raise APIException(
            'The given user is not enrolled in this course',
            (
                f'The user "{author.id}" is not enrolled '
                f'in course "{assig.course_id}"'
            ),
            APICodes.INVALID_STATE,
            400,
        )

    if submit_self:
        ensure_permission(CPerm.can_submit_own_work, assig.course_id)
    else:
        ensure_permission(CPerm.can_submit_others_work, assig.course_id)

    if not assig.is_open:
        ensure_permission(CPerm.can_upload_after_deadline, assig.course_id)

    if assig.is_lti and assig.id not in author.assignment_results:
        lms_name = assig.course.lti_provider.lms_name
        raise APIException(
            (
                f'This is a {lms_name} assignment and it seems we do not have '
                'the possibility to pass back the grade. Please {}visit the '
                f'assignment again on {lms_name}. If this issue persists, '
                'please contact your system administrator.'
            ).format('ask the given author to ' if submit_self else ''),
            (
                f'The assignment {assig.id} is not present in the '
                f'user {author.id} `assignment_results`'
            ),
            APICodes.INVALID_STATE,
            400,
        )


@login_required
def ensure_can_see_grade(work: 'psef.models.Work') -> None:
    """Ensure the current user can see the grade of the given work.

    :param work: The work to check for.

    :returns: Nothing

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not see the grade.
        (INCORRECT_PERMISSION)
    """
    if not work.has_as_author(psef.current_user):
        ensure_permission(CPerm.can_see_others_work, work.assignment.course_id)

    if not work.assignment.is_done:
        ensure_permission(
            CPerm.can_see_grade_before_open, work.assignment.course_id
        )


@login_required
def ensure_can_edit_work(work: 'psef.models.Work') -> None:
    """Make sure the current user can edit files in the given work.

    :param work: The work the given user should be able to see edit files in.
    :returns: Nothing.
    :raises PermissionException: If the user should not be able te edit these
        files.
    """
    if work.user_id == psef.current_user.id:
        if work.assignment.is_open:
            ensure_permission(
                CPerm.can_submit_own_work, work.assignment.course_id
            )
        else:
            ensure_permission(
                CPerm.can_upload_after_deadline, work.assignment.course_id
            )
    else:
        if work.assignment.is_open:
            raise APIException(
                (
                    'You cannot edit work as teacher'
                    ' if the assignment is stil open!'
                ),
                f'The assignment "{work.assignment.id}" is still open.',
                APICodes.INCORRECT_PERMISSION,
                403,
            )
        ensure_permission(
            CPerm.can_edit_others_work, work.assignment.course_id
        )


@login_required
def ensure_can_see_plagiarims_case(
    case: 'psef.models.PlagiarismCase',
    assignments: bool = True,
    submissions: bool = True,
) -> None:
    """Make sure the current user can see the given plagiarism case.

    :param assignments: Make sure the user can see the assignments of these
        cases.
    :param submissions: Make sure the user can see the submissions of these
        cases.
    :returns: Nothing
    """
    ensure_permission(
        CPerm.can_view_plagiarism, case.plagiarism_run.assignment.course_id
    )

    if case.work1.assignment_id == case.work2.assignment_id:
        return

    other_work_index = (
        1
        if case.work1.assignment_id == case.plagiarism_run.assignment_id else 0
    )
    other_work = case.work1 if other_work_index == 0 else case.work2
    other_assignment = other_work.assignment
    other_course_id = other_work.assignment.course_id

    # You can see virtual data of virtual assignments
    if other_work.assignment.course.virtual:
        return

    # Different assignment but same course, so no troubles here.
    if other_course_id == case.plagiarism_run.assignment.course_id:
        return

    # If we have this permission in the external course we may also see al
    # the other information
    if psef.current_user.has_permission(
        CPerm.can_view_plagiarism, other_course_id
    ):
        return

    # We probably don't have permission, however we could have the necessary
    # permissions for this information on the external course.
    if assignments:
        ensure_can_see_assignment(other_assignment)

    if submissions and not other_work.has_as_author(psef.current_user):
        ensure_permission(CPerm.can_see_others_work, other_course_id)


@login_required
def ensure_can_see_assignment(assignment: 'psef.models.Assignment') -> None:
    """Make sure the current user can see the given assignment.

    :param assignment: The assignment to check for.
    :returns: Nothing.
    """
    ensure_permission(CPerm.can_see_assignments, assignment.course_id)

    if assignment.is_hidden:
        ensure_permission(
            CPerm.can_see_hidden_assignments, assignment.course_id
        )


@login_required
def ensure_can_view_files(
    work: 'psef.models.Work', teacher_files: bool
) -> None:
    """Make sure the current user can see files in the given work.

    :param work: The work the given user should be able to see files in.
    :param teacher_files: Should the user be able to see teacher files.
    :returns: Nothing.
    :raises PermissionException: If the user should not be able te see these
        files.
    """
    try:
        if not work.has_as_author(psef.current_user):
            try:
                ensure_permission(
                    CPerm.can_see_others_work, work.assignment.course_id
                )
            except PermissionException:
                ensure_permission(
                    CPerm.can_view_plagiarism, work.assignment.course_id
                )

        if teacher_files:
            if (
                work.user_id == psef.current_user.id and
                work.assignment.is_done
            ):
                ensure_permission(
                    CPerm.can_view_own_teacher_files, work.assignment.course_id
                )
            else:
                # If the assignment is not done you can only view teacher files
                # if you can edit somebodies work.
                ensure_permission(
                    CPerm.can_edit_others_work, work.assignment.course_id
                )
    except PermissionException:
        # A user can also view a file if there is a plagiarism case between
        # submission {A, B} where submission A is from a virtual course and the
        # user has the `can_view_plagiarism` permission on the course of
        # submission B.
        if not work.assignment.course.virtual:
            raise

        for case in psef.models.PlagiarismCase.query.filter(
            (psef.models.PlagiarismCase.work1_id == work.id)
            | (psef.models.PlagiarismCase.work2_id == work.id)
        ):
            other_work = case.work1 if case.work2_id == work.id else case.work2
            if psef.current_user.has_permission(
                CPerm.can_view_plagiarism,
                course_id=other_work.assignment.course_id,
            ):
                return
        raise


@login_required
def ensure_can_view_group(group: 'psef.models.Group') -> None:
    """Make sure that the current user can view the given group.

    :param group: The group to check for.
    :returns: Nothing.
    :raises PermissionException: If the current user cannot view the given
        group.
    """
    if group.members and psef.current_user.id not in (
        m.id for m in group.members
    ):
        ensure_permission(
            CPerm.can_view_others_groups,
            group.group_set.course_id,
        )


@login_required
def ensure_can_edit_members_of_group(
    group: 'psef.models.Group', members: t.List['psef.models.User']
) -> None:
    """Make sure that the current user can edit the given group.

    :param group: The group to check for.
    :param members: The members you want to add to the group.
    :returns: Nothing.
    :raises PermissionException: If the current user cannot edit the given
        group.
    """
    perms = []
    if all(member.id == psef.current_user.id for member in members):
        perms.append(CPerm.can_edit_own_groups)
    perms.append(CPerm.can_edit_others_groups)
    ensure_any_of_permissions(
        perms,
        group.group_set.course_id,
    )

    for member in members:
        ensure_enrolled(group.group_set.course_id, member)

    if group.has_a_submission:
        ensure_permission(
            CPerm.can_edit_groups_after_submission,
            group.group_set.course_id,
            extra_message=(
                # The leading space is needed as the message of the default
                # exception ends with a .
                " This is because you don't have the permission to"
                " change the users of a group after the group handed in a"
                " submission."
            )
        )


@login_required
def ensure_any_of_permissions(
    permissions: t.List[CPerm], course_id: int
) -> None:
    """Make sure that the current user has at least one of the given
        permissions.

    :param permissions: The permissions to check for.
    :param course_id: The course id of the course that should be used to check
        for the given permissions.
    :returns: Nothing.
    :raises PermissionException: If the current user has none of the given
        permissions. This will always happen if the list of given permissions
        is empty.
    """
    for perm in permissions:
        try:
            ensure_permission(perm, course_id)
        except PermissionException:
            continue
        else:
            return
    # All checks raised a PermissionException
    raise PermissionException(
        'You do not have permission to do this.',
        'None of the permissions "{}" are not enabled for user "{}"'.format(
            ', '.join(p.name for p in permissions), psef.current_user.id
        ), APICodes.INCORRECT_PERMISSION, 403
    )


@t.overload
# pylint: disable=function-redefined,missing-docstring,unused-argument
def ensure_permission(
    permission: CPerm,
    course_id: int,
    *,
    user: t.Optional['psef.models.User'] = None,
    extra_message: str = '',
) -> None:
    ...  # pylint: disable=pointless-statement


@t.overload
# pylint: disable=function-redefined,missing-docstring,unused-argument
def ensure_permission(
    permission: GPerm,
    *,
    user: t.Optional['psef.models.User'] = None,
    extra_message: str = ''
) -> None:
    ...  # pylint: disable=pointless-statement


def ensure_permission(  # pylint: disable=function-redefined
    permission: t.Union[CPerm, GPerm], course_id: t.Optional[int] = None
        , *, user: t.Optional['psef.models.User'] = None,
        extra_message: str = '',
) -> None:
    """Ensure that the current user is logged and has the given permission.

    :param permission_name: The name of the permission to check for.
    :param course_id: The course id of the course that should be used for the
        course permission, if it is None a role permission is implied. If a
        course_id is supplied but the given permission is not a course
        permission (but a role permission) this function will **NEVER** grant
        the permission.
    :param user: The user to check for, defaults to current user when not
        provided.
    :param extra_message: Text that should be appended to the message provided
        in the raised :class:`.PermissionException` when the permission check
        fails.

    :returns: Nothing

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the permission is not enabled for the
                                 current user. (INCORRECT_PERMISSION)
    """
    user = psef.current_user if user is None else user

    if _user_active(user):
        if isinstance(permission,
                      CPerm) and course_id is not None and user.has_permission(
                          permission, course_id=course_id
                      ):
            return
        elif isinstance(
            permission, GPerm
        ) and course_id is None and user.has_permission(permission):
            return
        else:
            you_do = (
                'You do'
                if user.id == psef.current_user.id else f'{user.name} does'
            )
            msg = (
                '{you_do} not have the permission'
                ' to do this.{extra_msg}'
            ).format(
                you_do=you_do,
                extra_msg=extra_message,
            )
            raise PermissionException(
                msg,
                'The permission "{}" is not enabled for user "{}"'.format(
                    permission.name,
                    user.id,
                ),
                APICodes.INCORRECT_PERMISSION,
                403,
            )
    else:
        _raise_login_exception(
            (
                'The user was not logged in, ' +
                'so it did not have the permission "{}"'
            ).format(permission.name)
        )


def permission_required(permission: GPerm) -> t.Callable[[T], T]:
    """A decorator used to make sure the function decorated is only called with
    certain permissions.

    :param permission: The global permission to check for.

    :returns: The value of the decorated function if the current user has the
        required permission.

    :raises PermissionException: If the current user does not have the required
        permission, this is done in the same way as
        :py:func:`ensure_permission` does this.
    """

    def __decorator(f: T) -> T:
        @wraps(f)
        def __decorated_function(*args: t.Any, **kwargs: t.Any) -> t.Any:
            assert isinstance(permission, GPerm)
            ensure_permission(permission)
            return f(*args, **kwargs)

        return t.cast(T, __decorated_function)

    return __decorator


class RequestValidatorMixin:
    '''
    A 'mixin' for OAuth request validation.
    '''

    def __init__(self, key: str, secret: str) -> None:
        super(RequestValidatorMixin, self).__init__()
        self.consumer_key = key
        self.consumer_secret = secret

        self.oauth_server = oauth2.Server()
        signature_method = oauth2.SignatureMethod_HMAC_SHA1()
        self.oauth_server.add_signature_method(signature_method)
        self.oauth_consumer = oauth2.Consumer(
            self.consumer_key, self.consumer_secret
        )

    def is_valid_request(
        self,
        request: t.Any,
        parameters: t.Optional[t.MutableMapping[str, str]] = None,
        fake_method: t.Any = None,
        handle_error: bool = True
    ) -> bool:
        '''
        Validates an OAuth request using the python-oauth2 library:
            https://github.com/simplegeo/python-oauth2
        '''

        def __handle(err: oauth2.Error) -> bool:
            if handle_error:
                return False
            else:
                raise err
            # This is needed to please pylint
            raise RuntimeError()

        try:
            method, url, headers, parameters = self.parse_request(
                request, parameters, fake_method
            )

            oauth_request = oauth2.Request.from_request(
                method,
                url,
                headers=headers,
                parameters=parameters,
            )

            self.oauth_server.verify_request(
                oauth_request, self.oauth_consumer, {}
            )

        except (oauth2.Error, ValueError) as err:
            return __handle(err)
        # Signature was valid
        return True

    def parse_request(
        self,
        req: t.Any,
        parameters: t.Optional[t.MutableMapping[str, str]] = None,
        fake_method: t.Optional[t.Any] = None,
    ) -> t.Tuple[str, str, t.MutableMapping[str, str], t.
                 MutableMapping[str, str]]:  # pragma: no cover
        '''
        This must be implemented for the framework you're using
        Returns a tuple: (method, url, headers, parameters)
        method is the HTTP method: (GET, POST)
        url is the full absolute URL of the request
        headers is a dictionary of any headers sent in the request
        parameters are the parameters sent from the LMS

        :param object request: The request to be parsed.
        :param dict parameters: Extra parameters for the given request.
        :param object fake_method: The fake method to be used.
        :rtype: tuple[str, str, dict[str, str], dict[str, str]]
        :returns: A tuple of, respectively, the requets method, url, headers
            and form, where the last two are a key value mapping.
        '''
        raise NotImplementedError()


class _FlaskOAuthValidator(RequestValidatorMixin):
    def parse_request(
        self,
        req: 'flask.Request',
        parameters: t.MutableMapping[str, str] = None,
        fake_method: t.Any = None,
    ) -> t.Tuple[str, str, t.MutableMapping[str, str], t.
                 MutableMapping[str, str]]:
        '''
        Parse Flask request
        '''
        # base_url is used because of:
        # https://github.com/instructure/canvas-lms/issues/600
        return (req.method, req.base_url, dict(req.headers), req.form.copy())


def ensure_valid_oauth(
    key: str,
    secret: str,
    request: t.Any,
    parser_cls: t.Type = _FlaskOAuthValidator
) -> None:
    """Make sure the given oauth key and secret is valid for the given request.

    :param str key: The oauth key to be used for validating.
    :param str secret: The oauth secret to be used for validating.
    :param object request: The request that should be validated.
    :param RequestValidatorMixin parser_cls: The class used to parse the given
        ``request`` it should subclass :py:class:`RequestValidatorMixin` and
        should at least override the
        :func:`RequestValidatorMixin.parse_request` method.
    :returns: Nothing
    """
    validator = parser_cls(key, secret)
    if not validator.is_valid_request(request):
        raise PermissionException(
            'No valid oauth request could be found.',
            'The given request is not a valid oauth request.',
            APICodes.INVALID_OAUTH_REQUEST, 400
        )


if t.TYPE_CHECKING:  # pragma: no cover
    import flask  # pylint: disable=unused-import

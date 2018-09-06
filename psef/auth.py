"""This module implements all authorization functions used by :py:mod:`psef`.

:license: AGPLv3, see LICENSE for details.
"""
import typing as t
from functools import wraps

import oauth2
import flask_jwt_extended as flask_jwt
from mypy_extensions import NoReturn

import psef
from psef.errors import APICodes, APIException

jwt = flask_jwt.JWTManager()  # pylint: disable=invalid-name


def init_app(app: t.Any) -> None:
    """Initialize the app by initializing our jwt manager.

    :param app: The flask app to initialize.
    """
    jwt.init_app(app)


class PermissionException(APIException):
    """The exception used when a permission check fails.
    """
    pass


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


def _user_active() -> bool:
    """Check if there is a current user who is authenticated and active.

    :returns: True if there is an active logged in user
    """
    # pylint: disable=protected-access
    user = psef.current_user._get_current_object()  # type: ignore
    return user is not None and user.is_active


def login_required(fun: t.Callable) -> t.Callable:
    """Make sure a valid user is logged in at this moment.

    :raises PermissionException: If no user was logged in.
    """

    @wraps(fun)
    def __wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        ensure_logged_in()
        return fun(*args, **kwargs)

    return __wrapper


def ensure_logged_in() -> None:
    """Make sure a user is currently logged in.

    :returns: Nothing.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    if not _user_active():
        _raise_login_exception()


@login_required
def ensure_enrolled(course_id: int) -> None:
    """Ensure that the current user is enrolled in the given course.

    :param course_id: The id of the course to check for.

    :returns: Nothing.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user is not enrolled.
        (INCORRECT_PERMISSION)
    """
    if course_id not in psef.current_user.courses:
        raise PermissionException(
            'You are not enrolled in this course.',
            'The user "{}" is not enrolled in course "{}"'.format(
                psef.current_user.id, course_id
            ), APICodes.INCORRECT_PERMISSION, 403
        )


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
        ensure_permission('can_submit_own_work', assig.course_id)
    else:
        ensure_permission('can_submit_others_work', assig.course_id)

    if not assig.is_open:
        ensure_permission('can_upload_after_deadline', assig.course_id)

    if assig.is_lti and assig.id not in author.assignment_results:
        raise APIException(
            (
                "This assignment is a LTI assignment and it seems we "
                "don't have the possibility to passback the grade to the "
                "LMS. Please {}visit the assignment on the LMS again, if "
                "this issue persist please contact your administrator."
            ).format('let the given author ' if submit_self else ''),
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
    if work.user_id != psef.current_user.id:
        ensure_permission('can_see_others_work', work.assignment.course_id)

    if not work.assignment.is_done:
        ensure_permission(
            'can_see_grade_before_open', work.assignment.course_id
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
            ensure_permission('can_submit_own_work', work.assignment.course_id)
        else:
            ensure_permission(
                'can_upload_after_deadline', work.assignment.course_id
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
        ensure_permission('can_edit_others_work', work.assignment.course_id)


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
    if work.user_id != psef.current_user.id:
        ensure_permission('can_see_others_work', work.assignment.course_id)

    if teacher_files:
        if work.user_id == psef.current_user.id and work.assignment.is_done:
            ensure_permission(
                'can_view_own_teacher_files', work.assignment.course_id
            )
        else:
            # If the assignment is not done you can only view teacher files if
            # you can edit somebodies work.
            ensure_permission(
                'can_edit_others_work', work.assignment.course_id
            )


def ensure_permission(permission_name: str, course_id: int = None) -> None:
    """Ensure that the current user is logged and has the given permission.

    :param permission_name: The name of the permission to check for.
    :param course_id: The course id of the course that should be used for the
        course permission, if it is None a role permission is implied. If a
        course_id is supplied but the given permission is not a course
        permission (but a role permission) this function will **NEVER** grant
        the permission.

    :returns: Nothing

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the permission is not enabled for the
                                 current user. (INCORRECT_PERMISSION)
    """
    if _user_active():
        if psef.current_user.has_permission(
            permission_name, course_id=course_id
        ):
            return
        else:
            raise PermissionException(
                'You do not have permission to do this.',
                'The permission "{}" is not enabled for user "{}"'.format(
                    permission_name, psef.current_user.id
                ), APICodes.INCORRECT_PERMISSION, 403
            )
    else:
        _raise_login_exception(
            (
                'The user was not logged in, ' +
                'so it did not have the permission "{}"'
            ).format(permission_name)
        )


def permission_required(
    permission_name: str, course_id: int = None
) -> t.Callable:
    """A decorator used to make sure the function decorated is only called with
    certain permissions.

    :param permission_name: The name of the permission to check for.
    :param course_id: The id of the course if the permission is a course
        permission.

    :returns: The value of the decorated function if the current user has the
        required permission.

    :raises PermissionException: If the current user does not have the required
        permission, this is done in the same way as
        :py:func:`ensure_permission` does this.
    """

    def __decorator(f: t.Callable) -> t.Callable:
        @wraps(f)
        def __decorated_function(*args: t.Any, **kwargs: t.Any) -> t.Any:
            ensure_permission(permission_name, course_id=course_id)
            return f(*args, **kwargs)

        return __decorated_function

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
                method, url, headers=headers, parameters=parameters
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
    ) -> t.Tuple[str, str, t.MutableMapping[str, str],
                 t.MutableMapping[str, str]]:  # pragma: no cover
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
    ) -> t.Tuple[str, str, t.MutableMapping[str, str], t.MutableMapping[str,
                                                                        str]]:
        '''
        Parse Flask request
        '''
        return (req.method, req.url, dict(req.headers), req.form.copy())


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

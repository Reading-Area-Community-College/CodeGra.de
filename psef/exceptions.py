"""This module defines all exceptions used within CodeGrade and their error
codes.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
from enum import IntEnum, unique


@unique
class APIWarnings(IntEnum):
    """API codes used to signal warnings to the client.
    """
    DEPRECATED = 0
    GRADER_NOT_DONE = 1
    CONDITION_ALREADY_MET = 2
    SYMLINK_IN_ARCHIVE = 3
    INVALID_FILENAME = 4
    WEAK_PASSWORD = 5
    UNASSIGNED_ASSIGNMENTS = 6


@unique
class APICodes(IntEnum):
    """Internal API codes that are used by :class:`APIException` objects.
    """
    INCORRECT_PERMISSION = 0
    NOT_LOGGED_IN = 1
    OBJECT_ID_NOT_FOUND = 2
    OBJECT_WRONG_TYPE = 3
    MISSING_REQUIRED_PARAM = 4
    INVALID_PARAM = 5
    REQUEST_TOO_LARGE = 6
    LOGIN_FAILURE = 7
    INACTIVE_USER = 8
    INVALID_URL = 9
    OBJECT_NOT_FOUND = 10
    BLOCKED_ASSIGNMENT = 11
    INVALID_CREDENTIALS = 12
    INVALID_STATE = 13
    INVALID_OAUTH_REQUEST = 14
    DISABLED_FEATURE = 15
    UNKOWN_ERROR = 16
    INVALID_FILE_IN_ARCHIVE = 17
    NO_FILES_SUBMITTED = 18
    RATE_LIMIT_EXCEEDED = 19
    OBJECT_ALREADY_EXISTS = 20
    INVALID_ARCHIVE = 21
    ROUTE_NOT_FOUND = 22
    WEAK_PASSWORD = 23
    INSUFFICIENT_GROUP_SIZE = 24
    ASSIGNMENT_RESULT_GROUP_NOT_READY = 25
    ASSIGNMENT_GROUP_FULL = 26
    UNSUPPORTED = 27
    ASSIGNMENT_DEADLINE_UNSET = 28
    PARSING_FAILED = 29


class InvalidAssignmentState(TypeError):
    """Exception used to signal the assignment state is invalid.
    """


class APIException(Exception):
    """The exception to use if an API call failed.

    :param message: The user friendly message to display.
    :param description: The description used for debugging.
    :param api_code: The error code in the API, should be a constant
                            from this class.
    :param status_code: The Http status code to use, should not be 2xx.
    :param rest: All the other fields to return in the JSON object.
    """

    def __init__(
        self, message: str, description: str, api_code: APICodes,
        status_code: int, **rest: t.Any
    ) -> None:
        super(APIException, self).__init__()
        self.status_code = status_code
        self.api_code = api_code
        self.description = description
        self.message = message
        self.rest = rest

    def __to_json__(self) -> t.Mapping[t.Any, t.Any]:
        """Creates a JSON serializable representation of this object.

        :returns: This APIException instance as a dictionary.
        """
        ret = dict(self.rest)  # type: t.MutableMapping[t.Any, t.Any]
        ret['message'] = self.message
        ret['description'] = self.description
        ret['code'] = self.api_code.name
        return ret


class PermissionException(APIException):
    """The exception used when a permission check fails.
    """


class ValidationException(APIException):
    """Thrown when some kind of validation fails.
    """

    def __init__(
        self,
        message: str,
        description: str,
        code: APICodes = APICodes.INVALID_PARAM,
        **rest: t.Any,
    ) -> None:
        super().__init__(message, description, code, 400, **rest)


class WeakPasswordException(ValidationException):
    """Thrown when a password is too weak.
    """

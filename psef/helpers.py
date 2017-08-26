#!/usr/bin/env python3
"""
This module implements generic helpers and convenience functions.

:license: AGPLv3, see LICENSE for details.
"""
import typing as t
import datetime
from functools import wraps, reduce

import flask  # type: ignore
import werkzeug

import psef
import psef.errors
import psef.models

#: Any thingy
T = t.TypeVar('T')


def get_all_subclasses(cls: t.Type[T]) -> t.Iterable[t.Type['T']]:
    """Returns all subclasses of the given class.

    Stolen from:
    https://stackoverflow.com/questions/3862310/how-can-i-find-all-subclasses-of-a-class-given-its-name

    :param cls: The parent class
    :returns: A list of all subclasses
    """
    all_subclasses = []

    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))

    return all_subclasses


def get_request_start_time() -> datetime.datetime:
    """Return the start time of the current request.

    :returns: The time as returned by the python time module.
    :rtype: float
    """
    return flask.g.request_start_time


_JSONValue = t.Union[str, int, float, bool, None, t.Dict[str, t.Any],
                     t.List[t.Any]]
JSONType = t.Union[t.Dict[str, _JSONValue], t.List[_JSONValue], _JSONValue]


class JSONResponse(t.Generic[T]):
    """A datatype for a JSON response.

    This is a subtype of :py:class:`werkzeug.wrappers.Response` where the body
    is a valid JSON object and ``content-type`` is ``application/json``.

    .. warning::

        This class is only used for type hinting and is never actually used! It
        does not contain any valid data!
    """

    def __init__(self) -> None:  # pragma: no cover
        raise NotImplementedError("Do not use this class as actual data")


class EmptyResponse:
    """An empty response.

    This is a subtype of :py:class:`werkzeug.wrappers.Response` where the body
    is empty and the status code is always 204.

    .. warning::

        This class is only used for type hinting and is never actually used! It
        does not contain any valid data!
    """

    def __init__(self) -> None:  # pragma: no cover
        raise NotImplementedError("Do not use this class as actual data")


Y = t.TypeVar('Y', bound='psef.models.Base')


def _filter_or_404(model: t.Type[Y], get_all: bool,
                   criteria: t.Tuple) -> t.Union[Y, t.Sequence[Y]]:
    """Get the specified object by filtering or raise an exception.

    :param get_all: Get all objects if ``True`` else get a single one.
    :param model: The object to get.
    :param criteria: The criteria to filter with.
    :returns: The requested object.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    query = model.query.filter(*criteria)  # type: ignore
    obj = query.all() if get_all else query.one_or_none()
    if not obj:
        raise psef.errors.APIException(
            f'The requested {model.__name__.lower()} was not found',
            f'There is no "{model.__name__}" when filtering with {criteria}',
            psef.errors.APICodes.OBJECT_ID_NOT_FOUND, 404
        )
    return obj


def filter_all_or_404(model: t.Type[Y], *criteria: t.Any) -> t.Sequence[Y]:
    """Get all objects of the specified model filtered by the specified
    criteria.

    .. note::
        ``Y`` is bound to :py:class:`psef.models.Base`, so it should be a
        SQLAlchemy model.

    :param model: The object to get.
    :param criteria: The criteria to filter with.
    :returns: The requested objects.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    return t.cast(t.Sequence[Y], _filter_or_404(model, True, criteria))


def filter_single_or_404(model: t.Type[Y], *criteria: t.Any) -> Y:
    """Get a single object of the specified model by filtering or raise an
    exception.

    .. note::
        ``Y`` is bound to :py:class:`psef.models.Base`, so it should be a
        SQLAlchemy model.

    :param model: The object to get.
    :param criteria: The criteria to filter with.
    :returns: The requested object.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    return t.cast(Y, _filter_or_404(model, False, criteria))


def get_or_404(model: t.Type[Y], object_id: t.Any) -> Y:
    """Get the specified object by primary key or raise an exception.

    .. note::
        ``Y`` is bound to :py:class:`psef.models.Base`, so it should be a
        SQLAlchemy model.

    :param model: The object to get.
    :param object_id: The primary key identifier for the given object.
    :returns: The requested object.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    obj: t.Optional[Y] = model.query.get(object_id)
    if obj is None:
        raise psef.errors.APIException(
            f'The requested "{model.__name__}" was not found',
            f'There is no "{model.__name__}" with primary key {object_id}',
            psef.errors.APICodes.OBJECT_ID_NOT_FOUND, 404
        )
    return obj


def ensure_keys_in_dict(
    mapping: t.Mapping[T, t.Any], keys: t.Sequence[t.Tuple[T, t.Type]]
) -> None:
    """Ensure that the given keys are in the given mapping.

    :param mapping: The mapping to check.
    :param keys: The keys that should be in the mapping. If key is a tuple it
        is of the form (key, type) where ``mappping[key]`` has to be of type
        ``type``.
    :return: Nothing.

    :raises psef.errors.APIException: If a key from ``keys`` is missing in
        ``mapping`` (MISSING_REQUIRED_PARAM)
    """
    missing: t.List[t.Union[T, str]] = []
    type_wrong = False
    for key, check_type in keys:
        if key not in mapping:
            missing.append(key)
        elif (not isinstance(mapping[key], check_type)
              ) or (check_type == int and isinstance(mapping[key], bool)):
            missing.append(
                f'{str(key)} was of wrong type'
                f' (should be a "{check_type.__name__}"'
                f', was a "{type(mapping[key]).__name__}")'
            )
            type_wrong = True
    if missing:
        msg = 'The given object does not contain all required keys'
        key_type = ', '.join(f"\'{k[0]}\': {k[1].__name__}" for k in keys)
        raise psef.errors.APIException(
            msg + (' or the type was wrong' if type_wrong else ''),
            '"{}" is missing required keys "{}" of all required keys "{}{}{}"'.
            format(
                mapping, ', '.join(str(m) for m in missing), '{', key_type, '}'
            ), psef.errors.APICodes.MISSING_REQUIRED_PARAM, 400
        )


def ensure_json_dict(json: JSONType) -> t.Dict[str, JSONType]:
    """Make sure that the given json is a JSON dictionary

    :param json: The input json that should be checked.
    :returns: Exactly the same JSON if it is in fact a dictionary.

    :raises psef.errors.APIException: If the given JSON is not a dictionary.
        (INVALID_PARAM)
    """
    if isinstance(json, t.Dict):
        return json
    raise psef.errors.APIException(
        'The given JSON is not a object as is required',
        f'"{json}" is not a object', psef.errors.APICodes.INVALID_PARAM, 400
    )


def jsonify(obj: T, status_code: int=200) -> JSONResponse[T]:
    response = flask.make_response(flask.jsonify(obj))
    response.status_code = status_code
    return response


def make_empty_response() -> EmptyResponse:
    """Create an empty response.
    """
    response = flask.make_response('')
    response.status_code = 204
    return response


def feature_required(feature_name: str) -> t.Callable:
    """ A decorator used to make sure the function decorated is only called
    with a certain feature enabled.

    :param feature_name: The name of the feature to check for.

    :returns: The value of the decorated function if the given feature is
        enabled.

    :raises APIException: If the feature is not enabled. (DISABLED_FEATURE)
    """

    def decorator(f: t.Callable) -> t.Callable:
        @wraps(f)
        def decorated_function(*args: t.Any, **kwargs: t.Any) -> t.Any:
            enabled = psef.app.config['FEATURES'][feature_name]
            if enabled:
                return f(*args, **kwargs)
            else:
                raise psef.errors.APIException(
                    'This feature is not enabled for this instance.',
                    f'The feature "{feature_name}" is not enabled.',
                    psef.errors.APICodes.DISABLED_FEATURE, 400
                )

        return decorated_function

    return decorator

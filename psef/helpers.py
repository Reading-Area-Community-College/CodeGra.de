"""
This module implements generic helpers and convenience functions.

SPDX-License-Identifier: AGPL-3.0-only
"""
import re
import abc
import typing as t
import datetime
import contextlib
import subprocess
from functools import wraps

import flask
import structlog
import mypy_extensions
from typing_extensions import Protocol
from werkzeug.datastructures import FileStorage
from sqlalchemy.sql.expression import or_

import psef
import psef.models
import psef.json_encoders as json

from . import errors, models

if t.TYPE_CHECKING:  # pragma: no cover
    from psef import model_types  # pylint: disable=unused-import
    import werkzeug  # pylint: disable=unused-import

logger = structlog.get_logger()

#: Type vars
T = t.TypeVar('T')
Z = t.TypeVar('Z', bound='Comparable')
Y = t.TypeVar('Y', bound='model_types.Base')
T_Type = t.TypeVar('T_Type', bound=t.Type)  # pylint: disable=invalid-name
T_TypedDict = t.TypeVar(  # pylint: disable=invalid-name
    'T_TypedDict',
    bound=t.Mapping,
)

IsInstanceType = t.Union[t.Type, t.Tuple[t.Type, ...]]  # pylint: disable=invalid-name


def init_app(_: t.Any) -> None:
    pass


class Comparable(Protocol):  # pragma: no cover
    """A protocol that for comparable variables.

    To satisfy this protocol a object should implement the ``__eq__``,
    ``__lt__``, ``__gt__``, ``__le__`` and``__ge__`` magic functions.
    """

    @abc.abstractmethod
    def __eq__(self, other: t.Any) -> bool:
        ...  # pylint: disable=W0104

    @abc.abstractmethod
    def __lt__(self: Z, other: Z) -> bool:
        ...  # pylint: disable=W0104

    def __gt__(self: Z, other: Z) -> bool:
        return (not self < other) and self != other

    def __le__(self: Z, other: Z) -> bool:
        return self < other or self == other

    def __ge__(self: Z, other: Z) -> bool:
        return not (self < other)  # pylint: disable=superfluous-parens


def get_all_subclasses(cls: T_Type) -> t.Iterable[T_Type]:
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


def escape_like(unescaped_like: str) -> str:
    r"""Escape a string used for the LIKE clause by escaping all wildcards.

    .. note::

      The escape characters are "%", "_" and "\". They are escaped by placing a
      "\" before them.

    >>> escape_like('hello')
    'hello'
    >>> escape_like('This is % a _ string\%')
    'This is \\% a \\_ string\\\\\\%'
    >>> escape_like('%')
    '\\%'

    :param unescaped_like: The string to escape
    :returns: The same string but escaped
    """
    return re.sub(r'(%|_|\\)', r'\\\1', unescaped_like)


def between(min_bound: Z, item: Z, max_bound: Z) -> Z:
    """Make sure ``item`` is between two bounds.

    >>> between(0, 5, 10)
    5
    >>> between(0, -1, 10)
    0
    >>> between(0, 11, 10)
    10
    >>> between(10, 5, 0)
    Traceback (most recent call last):
    ...
    ValueError: `min_bound` cannot be higher than `max_bound`

    .. note::

        ``min_bound`` cannot be larger than ``max_bound``. They can be equal.

    :param min_bound: The minimum this function should return
    :param max_bound: The maximum this function should return
    :param item: The item to check
    :returns: ``item`` if it is between ``min_bound`` and ``max_bound``,
        otherwise the bound is returned that is closest to the item.
    """
    if min_bound > max_bound:
        raise ValueError('`min_bound` cannot be higher than `max_bound`')

    if item <= min_bound:
        return min_bound
    elif item >= max_bound:
        return max_bound

    return item


def get_request_start_time() -> datetime.datetime:
    """Return the start time of the current request.

    :returns: The time as returned by the python time module.
    :rtype: float
    """
    return flask.g.request_start_time


_JSONValue = t.Union[str, int, float, bool, None, t.Dict[str, t.Any],  # pylint: disable=invalid-name
                     t.List[t.Any]]
JSONType = t.Union[t.Dict[str, _JSONValue], t.List[_JSONValue], _JSONValue]  # pylint: disable=invalid-name


class ExtendedJSONResponse(t.Generic[T]):
    """A datatype for a JSON response created by using the
    ``__extended_to_json__`` if available.

    This is a subtype of :py:class:`werkzeug.wrappers.Response` where the body
    is a valid JSON object and ``content-type`` is ``application/json``.

    .. warning::

        This class is only used for type hinting and is never actually used! It
        does not contain any valid data!
    """

    def __init__(self) -> None:  # pragma: no cover
        raise NotImplementedError("Do not use this class as actual data")


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


def get_in_or_error(
    model: t.Type[Y], in_column: psef.models.DbColumn[T], in_values: t.List[T]
) -> t.List[Y]:
    """Get object by doing an ``IN`` query.

    This method protects against empty ``in_values``, and will return an empty
    list in that case. If not all items from the ``in_values`` this function
    will raise an exception.

    :param model: The objects to get.
    :param in_column: The column of the object to perform the in on.
    :param in_values: The values used for the ``IN`` clause.
    :returns: A list of objects with the same length as ``in_values``.

    :raises APIException: If on of the items in ``in_values`` was not found.
    """
    if not in_values:
        return []

    res = models.db.session.query(model).filter(in_column.in_(in_values)).all()
    if len(res) != len(in_values):
        raise psef.errors.APIException(
            f'Not all requested {model.__name__.lower()} could be found', (
                f'Out of the {len(in_values)} requested only {len(res)} were'
                ' found'
            ), psef.errors.APICodes.OBJECT_ID_NOT_FOUND, 404
        )
    return res


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
    crit_str = ' AND '.join(str(crit) for crit in criteria)
    query = model.query.filter(*criteria)  # type: ignore
    obj = query.all() if get_all else query.one_or_none()
    if not obj:
        raise psef.errors.APIException(
            f'The requested {model.__name__.lower()} was not found',
            f'There is no "{model.__name__}" when filtering with {crit_str}',
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


def get_or_404(
    model: t.Type[Y],
    object_id: t.Any,
    options: t.Optional[t.List[t.Any]] = None,
    also_error: t.Optional[t.Callable[[Y], bool]] = None,
) -> Y:
    """Get the specified object by primary key or raise an exception.

    .. note::
        ``Y`` is bound to :py:class:`psef.models.Base`, so it should be a
        SQLAlchemy model.

    :param model: The object to get.
    :param object_id: The primary key identifier for the given object.
    :param options: A list of options to give to the executed query. This can
        be used to undefer or eagerly load some columns or relations.
    :param also_error: If this function when called with the found object
        returns ``True`` generate the 404 error even though the object was
        found.
    :returns: The requested object.

    :raises APIException: If no object with the given id could be found.
        (OBJECT_ID_NOT_FOUND)
    """
    query = psef.models.db.session.query(model)
    if options is not None:
        query = query.options(*options)
    obj: t.Optional[Y] = query.get(object_id)

    if obj is None or (also_error is not None and also_error(obj)):
        raise psef.errors.APIException(
            f'The requested "{model.__name__}" was not found',
            f'There is no "{model.__name__}" with primary key {object_id}',
            psef.errors.APICodes.OBJECT_ID_NOT_FOUND, 404
        )
    return obj


def filter_users_by_name(
    query: str, base: 'psef.models._MyQuery[psef.models.User]'
) -> 'psef.models._MyQuery[psef.models.User]':
    """Find users from the given base query using the given query string.

    :param query: The string to filter usernames and names of users with.
    :param base: The query to filter.
    :returns: A new query with the users filtered.
    """
    if len(query) < 3:
        raise psef.errors.APIException(
            'The search string should be at least 3 chars',
            f'The search string "{query}" is not 3 chars or longer.',
            psef.errors.APICodes.INVALID_PARAM, 400
        )

    likes = [
        t.cast(t.Any, col).ilike(
            '%{}%'.format(
                escape_like(query).replace(' ', '%'),
            )
        ) for col in [psef.models.User.name, psef.models.User.username]
    ]

    return base.filter(or_(*likes)).order_by(
        t.cast(psef.models.DbColumn[str], psef.models.User.name)
    )


def coerce_json_value_to_typeddict(
    obj: JSONType, typeddict: t.Type[T_TypedDict]
) -> T_TypedDict:
    """Coerce a json object to a typed dict.

    .. warning::

        All types of the typed dict must be types that can be used with
        :func:`isinstance`.

    .. note::

        The original object is returned, this only checks if all values are
        valid.

    :param obj: The object to coerce:
    :param typeddict: The typeddict type that ``obj`` should be coerced to.
    :returns: The given value ``obj``.
    """
    mapping = ensure_json_dict(obj)
    annots = list(typeddict.__annotations__.items())
    assert all(isinstance(t, type) for _, t in annots
               ), "This function only supports checking for basic types"
    ensure_keys_in_dict(mapping, annots)
    return t.cast(T_TypedDict, mapping)


def ensure_keys_in_dict(
    mapping: t.Mapping[T, object], keys: t.Sequence[t.Tuple[T, IsInstanceType]]
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

    def __get_type_name(typ: t.Union[t.Type, t.Tuple[t.Type, ...]]) -> str:
        if isinstance(typ, tuple):
            return ', '.join(ty.__name__ for ty in typ)
        else:
            return typ.__name__

    missing: t.List[t.Union[T, str]] = []
    type_wrong = False
    for key, check_type in keys:
        if key not in mapping:
            missing.append(key)
        elif (not isinstance(mapping[key], check_type)
              ) or (check_type == int and isinstance(mapping[key], bool)):
            missing.append(
                f'{str(key)} was of wrong type'
                f' (should be a "{__get_type_name(check_type)}"'
                f', was a "{type(mapping[key]).__name__}")'
            )
            type_wrong = True
    if missing:
        msg = 'The given object does not contain all required keys'
        key_type = ', '.join(
            f"\'{k[0]}\': {__get_type_name(k[1])}" for k in keys
        )
        raise psef.errors.APIException(
            msg + (' or the type was wrong' if type_wrong else ''),
            '"{}" is missing required keys "{}" of all required keys "{}{}{}"'.
            format(
                mapping, ', '.join(str(m) for m in missing), '{', key_type, '}'
            ), psef.errors.APICodes.MISSING_REQUIRED_PARAM, 400
        )


def ensure_json_dict(
    json_value: JSONType,
    replace_log: t.Optional[t.Callable[[str, object], object]] = None
) -> t.Dict[str, JSONType]:
    """Make sure that the given json is a JSON dictionary

    :param json_value: The input json that should be checked.
    :returns: Exactly the same JSON if it is in fact a dictionary.

    :raises psef.errors.APIException: If the given JSON is not a dictionary.
        (INVALID_PARAM)
    """
    if isinstance(json_value, t.Dict):
        to_log = json_value
        if replace_log is not None:
            to_log = {k: replace_log(k, v) for k, v in json_value.items()}
        logger.info('JSON request processed', request_data=to_log)

        return json_value
    raise psef.errors.APIException(
        'The given JSON is not a object as is required',
        f'"{json_value}" is not a object',
        psef.errors.APICodes.INVALID_PARAM,
        400,
    )


def _maybe_add_warning(
    response: flask.Response,
    warning: t.Optional[psef.errors.HttpWarning],
) -> None:
    if warning is not None:
        logger.info('Added warning to response', warning=warning)
        response.headers['Warning'] = warning


def extended_jsonify(
    obj: T,
    status_code: int = 200,
    warning: t.Optional[psef.errors.HttpWarning] = None,
    use_extended: t.Union[t.Callable[[object], bool],
                          type,
                          t.Tuple[type, ...],
                          ] = object,
) -> ExtendedJSONResponse[T]:
    """Create a response with the given object ``obj`` as json payload.

    This function differs from :py:func:`jsonify` by that it used the
    ``__extended_to_json__`` magic function if it is available.

    :param obj: The object that will be jsonified using
        :py:class:`~.psef.json.CustomExtendedJSONEncoder`
    :param statuscode: The status code of the response
    :param warning: The warning that should be added to the response
    :param use_extended: The ``__extended_to_json__`` method is only used if
        this function returns something that equals to ``True``. This method is
        called with object that is currently being encoded. You can also pass a
        class or tuple as this parameter which is converted to
        ``lambda o: isinstance(o, passed_value)``.
    :returns: The response with the jsonified object as payload
    """

    try:
        if isinstance(use_extended, (tuple, type)):
            class_only = use_extended  # needed to please mypy
            use_extended = lambda o: isinstance(o, class_only)
        psef.app.json_encoder = json.get_extended_encoder_class(use_extended)
        response = flask.make_response(flask.jsonify(obj))
    finally:
        psef.app.json_encoder = json.CustomJSONEncoder
    response.status_code = status_code

    if not isinstance(obj, psef.errors.APIException):
        if getattr(psef.current_app, 'debug', False) and not getattr(
            psef.current_app, 'testing', False
        ):  # pragma: no cover
            to_log = response.get_json()
        else:
            to_log = response.response
        logger.info(
            'Created extended json return response',
            reponse_type=str(type(obj)),
            response=to_log,
        )

    _maybe_add_warning(response, warning)

    return response


def jsonify(
    obj: T,
    status_code: int = 200,
    warning: t.Optional[psef.errors.HttpWarning] = None,
) -> JSONResponse[T]:
    """Create a response with the given object ``obj`` as json payload.

    :param obj: The object that will be jsonified using
        :py:class:`~.psef.json.CustomJSONEncoder`
    :param statuscode: The status code of the response
    :param warning: The warning that should be added to the response
    :returns: The response with the jsonified object as payload
    """
    response = flask.jsonify(obj)
    if not isinstance(obj, psef.errors.APIException):
        if getattr(psef.current_app, 'debug', False) and not getattr(
            psef.current_app, 'testing', False
        ):  # pragma: no cover
            to_log = response.get_json()
        else:
            to_log = response.response
        logger.info(
            'Created json return response',
            reponse_type=str(type(obj)),
            response=to_log,
        )
    response.status_code = status_code

    _maybe_add_warning(response, warning)

    return response


def make_empty_response(
    warning: t.Optional[psef.errors.HttpWarning] = None,
) -> EmptyResponse:
    """Create an empty response.

    :param warning: The warning that should be added to the response
    :returns: A empty response with status code 204
    """
    response = flask.make_response('')
    response.status_code = 204

    _maybe_add_warning(response, warning)

    return response


def has_feature(feature_name: str) -> bool:
    """Check if a certain feature is enabled.

    :param feature_name: The name of te feature to check for.
    :returns: A boolean indicating if the given feature is enabled
    """
    return bool(psef.app.config['FEATURES'][feature_name])


def ensure_feature(feature_name: str) -> None:
    """Check if a certain feature is enabled.

    :param feature_name: The name of te feature to check for.
    :returns: Nothing.

    :raises APIException: If the feature is not enabled. (DISABLED_FEATURE)
    """
    if not has_feature(feature_name):
        logger.warning('Tried to use disabled feature', feature=feature_name)
        raise psef.errors.APIException(
            'This feature is not enabled for this instance.',
            f'The feature "{feature_name}" is not enabled.',
            psef.errors.APICodes.DISABLED_FEATURE, 400
        )


def feature_required(feature_name: str) -> t.Callable:
    """ A decorator used to make sure the function decorated is only called
    with a certain feature enabled.

    :param feature_name: The name of the feature to check for.

    :returns: The value of the decorated function if the given feature is
        enabled.

    :raises APIException: If the feature is not enabled. (DISABLED_FEATURE)
    """

    def __decorator(f: t.Callable) -> t.Callable:
        @wraps(f)
        def __decorated_function(*args: t.Any, **kwargs: t.Any) -> t.Any:
            ensure_feature(feature_name)
            return f(*args, **kwargs)

        return __decorated_function

    return __decorator


def raise_file_too_big_exception() -> mypy_extensions.NoReturn:
    """Get an exception that should be thrown when uploade file is too big.

    :returns: A exception that should be thrown when file is too big.
    """
    raise psef.errors.APIException(
        'Uploaded files are too big.', 'Request is bigger than maximum '
        f'upload size of {psef.current_app.config["MAX_UPLOAD_SIZE"]}.',
        psef.errors.APICodes.REQUEST_TOO_LARGE, 400
    )


def callback_after_this_request(
    fun: t.Callable[[], object],
) -> t.Callable[[T], T]:
    """Execute a callback after this request without changing the response.

    :param fun: The callback to execute after the current request.
    :returns: The function that will execute after this request that does that
        the response as argument, so this function wraps your given callback.
    """

    @flask.after_this_request
    def after(res: T) -> T:
        """The entire callback that is executed at the end of the request.
        """
        fun()
        return res

    return after


def get_class_by_name(superclass: T_Type, name: str) -> T_Type:
    """Get a class with given name

    :param superclass: A superclass of the class found
    :param name: The name of the class wanted.
    :returns: The class with the attribute `__name__` equal to `name`. If
        there are multiple classes with the name `name` the result can be any
        one of these classes.
    :raises ValueError: If the class with the specified name is not found.
    """
    for subcls in get_all_subclasses(superclass):
        if subcls.__name__ == name:
            return subcls
    raise ValueError('No class with name {} found.'.format(name))


def extended_requested() -> bool:
    """Check if a extended JSON serialization was requested.

    :returns: ``True`` if and only iff the ``extended`` get parameter was
        present and it value equals (case insensitive) ``'true'``, ``'1'``, or
        ``''`` (empty string).
    """
    return flask.request.args.get('extended',
                                  'false').lower() in {'true', '1', ''}


@contextlib.contextmanager
def defer(function: t.Callable[[], object]) -> t.Generator[None, None, None]:
    """Defer a function call to the end of the context manager.

    :param: The function to call.
    :returns: A context manager that can be used to execute the given function
        at the end of the block.
    """
    try:
        yield
    finally:
        function()


def call_external(call_args: t.List[str]) -> t.Tuple[bool, str, str]:
    """Safely call an external program without any exceptions.

    .. note:: This function should not be used when you don't want to handle
        errors as it will silently fail.

    :param call_args: The call passed to :py:func:`~subprocess.check_output`
        with ``shell`` set to ``False``.
    :returns: A tuple with the first argument if the process crashed, the
        second item is the ``stdout`` and the third and final item is the
        ``stderr``.
    """
    stdout = ''
    stderr = ''
    ok = True

    try:
        stdout = subprocess.check_output(
            call_args, stderr=subprocess.STDOUT, shell=False
        )
    except subprocess.CalledProcessError as err:
        logger.warning(
            'External program crashed.', call_args=call_args, exc_info=True
        )
        stdout = (err.stdout or b'').decode('utf-8').replace('\0', '')
        stderr = (err.stderr or b'').decode('utf-8').replace('\0', '')
        ok = False
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            'External program crashed.', call_args=call_args, exc_info=True
        )
        stderr = 'Unknown crash!'
        ok = False
    else:
        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8').replace('\0', '')

    return (ok, stdout, stderr)


def get_files_from_request(
    *,
    check_size: bool,
    keys: t.Sequence[str],
    only_start: bool = False,
) -> t.MutableSequence[FileStorage]:
    """Get all the submitted files in the current request.

    This function also checks if the files are in the correct format and are
    lot too large if you provide check_size. This is done for the entire
    request, not only the processed files.

    :param check_size: Should the size of the request be checked.
    :param keys: The keys the files should match in the request.
    :param only_start: If set to false the key of the request should only match
        the start of one of the keys in ``keys``.
    :returns: The files in the current request. The length of this list is
        always at least one and if ``only_start`` is false is never larger than
        the length of ``keys``.
    :raises APIException: When a given file is not correct.
    """
    res = []

    if (
        check_size and flask.request.content_length and (
            flask.request.content_length >
            psef.current_app.config['MAX_UPLOAD_SIZE']
        )
    ):
        raise_file_too_big_exception()

    if not flask.request.files:
        raise errors.APIException(
            "No file in HTTP request.",
            "There was no file in the HTTP request.",
            errors.APICodes.MISSING_REQUIRED_PARAM, 400
        )

    if only_start:
        for key, file in flask.request.files.items():
            if any(key.startswith(cur_key) for cur_key in keys):
                res.append(file)
    else:
        for key in keys:
            if key in flask.request.files:
                res.append(flask.request.files[key])

        # Make sure we never return more files than requested.
        assert len(keys) >= len(res)

    if not res:
        raise errors.APIException(
            'Request did not contain any valid files', (
                'The request did not contain any files {} the parameter'
                ' name{} with "{}"'
            ).format(
                'where' if only_start else 'with',
                ' started' if only_start else '',
                ','.join(keys),
            ), errors.APICodes.MISSING_REQUIRED_PARAM, 400
        )

    # Werkzeug >= 0.14.0 should check this, however the documentation is not
    # completely clear and it is better to blow up here than somewhere else.
    assert all(f.filename for f in res)

    return res

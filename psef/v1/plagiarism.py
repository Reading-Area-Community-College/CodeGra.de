"""
This module defines all API routes with the main directory "assignments". Thus
the APIs in this module are mostly used to manipulate
:class:`.models.Assignment` objects and their relations.

:license: AGPLv3, see LICENSE for details.
"""
import typing as t

from . import api
from .. import auth, models, helpers, plagiarism
from ..helpers import (
    JSONResponse, EmptyResponse, ExtendedJSONResponse, jsonify,
    extended_jsonify, make_empty_response
)


@api.route('/plagiarism/<int:plagiarism_id>', methods=['DELETE'])
def delete_plagiarism_run(plagiarism_id: int, ) -> EmptyResponse:
    """Delete a given plagiarism run and all its cases.

    .. :quickref: Plagiarism; Delete a plagiarism run and all its cases.

    .. warning::

        This is irreversible, so make sure the user really wants this!

    :param int plagiarism_id: The id of the run to delete.
    :returns: Nothing.

    :raises PermissionException: If the user can not manage plagiarism runs or
        cases for the course associated with the run. (INCORRECT_PERMISSION)
    """
    run = helpers.get_or_404(models.PlagiarismRun, plagiarism_id)
    auth.ensure_permission('can_manage_plagiarism', run.assignment.course_id)
    models.db.session.delete(run)
    models.db.session.commit()
    return make_empty_response()


@api.route('/plagiarism/<int:plagiarism_id>', methods=['GET'])
def get_plagiarism_run(
    plagiarism_id: int,
) -> t.Union[JSONResponse[models.PlagiarismRun], ExtendedJSONResponse[
    models.PlagiarismRun]]:
    """Get a :class:`.models.PlagiarismRun`.

    .. :quickref: Plagiarism; Get a single plagiarism run.

    :qparam boolean extended: Whether to get an extended or normal
        :class:`.models.PlagiarismRun` object. The default value is ``false``,
        you can enable extended by passing ``true``, ``1`` or an empty string.

    :param int plagiarism_id: The of the plagiarism run.
    :returns: An single plagiarism run.

    :raises PermissionException: If the user can not view plagiarism runs or
        cases for the course associated with the run. (INCORRECT_PERMISSION)
    """
    run = helpers.get_or_404(models.PlagiarismRun, plagiarism_id)
    auth.ensure_permission('can_view_plagiarism', run.assignment.course_id)

    if helpers.extended_requested():
        return extended_jsonify(run, use_extended=models.PlagiarismRun)
    return jsonify(run)


@api.route('/plagiarism/<int:plagiarism_id>/cases/', methods=['GET'])
def get_plagiarism_run_cases(
    plagiarism_id: int,
) -> JSONResponse[t.Iterable[models.PlagiarismCase]]:
    """Get all the :class:`.models.PlagiarismCase`s for the given
    :class:`.models.PlagiarismRun`.

    .. :quickref: Plagiarism; Get the cases for a plagiarism run.

    :param int plagiarism_id: The of the plagiarism run.
    :returns: An array of JSON serialized plagiarism cases.

    :raises PermissionException: If the user can not view plagiarism runs or
        cases for the course associated with the run. (INCORRECT_PERMISSION)
    """
    run = helpers.get_or_404(models.PlagiarismRun, plagiarism_id)
    auth.ensure_permission('can_view_plagiarism', run.assignment.course_id)
    return jsonify(run.cases)


@api.route(
    '/plagiarism/<int:plagiarism_id>/cases/<int:case_id>',
    methods=['GET'],
)
def get_plagiarism_case(
    plagiarism_id: int,
    case_id: int,
) -> ExtendedJSONResponse[models.PlagiarismCase]:
    """Get the extended view of a single :class:`.models.PlagiarismCase` object.

    .. :quickref: Plagiarism; Get a single plagiarism case.

    :param int plagiarism_id: The id of the run the case should belong to.
    :param int case_id: The id of the case requested.
    :returns: The extended JSON serialization of the plagiarism case requested.

    :raises PermissionException: If the user can not view plagiarism runs or
        cases for the course associated with the run. (INCORRECT_PERMISSION)
    """
    # We use the `plagiarism_id` and the `case_id` so we can later make the
    # `case_id` only unique within a single run.
    case = helpers.filter_single_or_404(
        models.PlagiarismCase, models.PlagiarismCase.id == case_id,
        models.PlagiarismCase.plagiarism_run_id == plagiarism_id
    )
    auth.ensure_can_see_plagiarims_case(case)

    return extended_jsonify(
        case,
        use_extended=models.PlagiarismCase,
    )


@api.route('/plagiarism/', methods=['GET'])
def get_plag_opts() -> JSONResponse[t.List[t.Dict[str, object]]]:
    """Get all plagiarism providers for this instance.

    :returns: An array of plagiarism providers.
    :>jsonarr str name: The name of the plagiarism provider.
    :>jsonarr array options: The extra possible options for this provider, this
        is an array of JSON serialized :class:`.plagiarism.Option` classes.
    """
    return jsonify(
        [
            {
                'name': cls.__name__,
                'options': cls.get_options()
            } for cls in sorted(
                helpers.get_all_subclasses(plagiarism.PlagiarismProvider),
                key=lambda o: o.__name__
            )
        ]
    )

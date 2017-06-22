from flask import jsonify

import psef.auth as auth
import psef.models as models
from psef.errors import APICodes, APIException

from . import api


@api.route('/courses/<int:course_id>/assignments/', methods=['GET'])
def get_all_course_assignments(course_id):
    auth.ensure_permission('can_see_assignments', course_id)

    course = models.Course.query.get(course_id)
    if course is None:
        return APIException('Specified course not found',
                            'The course {} was not found'.format(course_id),
                            APICodes.OBJECT_ID_NOT_FOUND, 404)

    res = [assig.to_dict() for assig in course.assignments]
    res.sort(key=lambda item: item['deadline'])
    return jsonify(res)
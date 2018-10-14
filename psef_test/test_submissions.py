# SPDX-License-Identifier: AGPL-3.0-only
import io
import os
import zipfile
import datetime

import pytest
from pytest import approx

import psef.models as m
from helpers import create_marker

http_error = create_marker(pytest.mark.http_error)
perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)
list_error = create_marker(pytest.mark.list_error)


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize('grade', [
    4.5,
])
@pytest.mark.parametrize('feedback', [
    'Goed gedaan!',
])
def test_get_grade_history(
    assignment_real_works, ta_user, test_client, logged_in, request, grade,
    feedback, error_template, teacher_user
):
    assignment, work = assignment_real_works
    work_id = work['id']

    data = {}
    data['grade'] = grade
    data['feedback'] = feedback

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/grade_history/',
            200,
            result=[]
        )

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data=data,
            result=dict,
        )
        data['grade'] = grade + 1
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data=data,
            result=dict,
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/grade_history/',
            403,
            result=error_template
        )

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/grade_history/',
            200,
            result=[
                {
                    'changed_at': str,
                    'is_rubric': False,
                    'grade': grade + 1,
                    'passed_back': False,
                    'user': dict,
                },
                {
                    'changed_at': str,
                    'is_rubric': False,
                    'grade': grade,
                    'passed_back': False,
                    'user': dict,
                }
            ]
        )

        res = test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': None},
            result=dict
        )

        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/grade_history/',
            200,
            result=[
                {
                    'changed_at': str,
                    'is_rubric': False,
                    'grade': -1,
                    'passed_back': False,
                    'user': dict,
                },
                {
                    'changed_at': str,
                    'is_rubric': False,
                    'grade': grade + 1,
                    'passed_back': False,
                    'user': dict,
                },
                {
                    'changed_at': str,
                    'is_rubric': False,
                    'grade': grade,
                    'passed_back': False,
                    'user': dict,
                }
            ]
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403)('Student1'),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'grade', [
        data_error(-1),
        data_error(11),
        data_error('err'),
        None,
        4,
        4.5,
    ]
)
@pytest.mark.parametrize(
    'feedback', [
        data_error(1),
        None,
        '',
        'Goed gedaan!',
    ]
)
def test_patch_submission(
    assignment_real_works, named_user, test_client, logged_in, request, grade,
    feedback, ta_user, error_template
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    if perm_err:
        error = perm_err.kwargs['error']
    elif data_err:
        error = 400
    else:
        error = False

    data = {}
    if grade is not None:
        data['grade'] = grade
    if feedback is not None:
        data['feedback'] = feedback

    with logged_in(named_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            error or 200,
            data=data,
            result=error_template if error else dict,
        )

    with logged_in(ta_user):
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200,
            result={
                'id':
                    work_id,
                'assignee':
                    None,
                'user':
                    dict,
                'created_at':
                    str,
                'grade':
                    None if error else grade,
                'comment':
                    None if error else feedback,
                'comment_author':
                    (None if error or 'feedback' not in data else dict),
            }
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_delete_grade_submission(
    ta_user, test_client, logged_in, assignment_real_works
):
    assignment, work = assignment_real_works
    work_id = work['id']

    with logged_in(ta_user):
        res = test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={
                'grade': 5,
                'feedback': ''
            },
            result=dict
        )
        assert res['grade'] == 5
        res = test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={
                'grade': None,
                'feedback': 'ww'
            },
            result=dict
        )
        assert res['grade'] is None
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200,
            result={
                'id': work_id,
                'assignee': None,
                'user': dict,
                'created_at': str,
                'grade': None,
                'comment': 'ww',
                'comment_author': dict,
            }
        )
        assert res['comment_author']['id'] == ta_user.id


def test_patch_non_existing_submission(
    ta_user, test_client, logged_in, error_template
):
    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/0',
            404,
            data={
                'grade': 4,
                'feedback': 'wow!'
            },
            result=error_template
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_negative_points(
    request, test_client, logged_in, error_template, teacher_user, ta_user,
    assignment_real_works, session
):
    assignment, work = assignment_real_works
    work_id = work['id']

    rubric = {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
            'items': [{
                'description': '5points',
                'header': 'bladie',
                'points': 5
            }, {
                'description': '10points',
                'header': 'bladie',
                'points': 10,
            }]
        }, {
            'header': 'Compensation',
            'description': 'WOW',
            'items': [{
                'description': 'BLA',
                'header': 'Negative',
                'points': -1,
            }, {
                'description': 'BLA+',
                'header': 'Positive',
                'points': 0,
            }],
        }]
    }  # yapf: disable
    max_points = 10

    with logged_in(teacher_user):
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=rubric
        )
        rubric = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': list,
                'selected': [],
                'points': {
                    'max': max_points,
                    'selected': 0
                }
            }
        )['rubrics']

    def get_rubric_item(head, desc):
        for row in rubric:
            if row['header'] == head:
                for item in row['items']:
                    if item['description'] == desc:
                        return item

    with logged_in(ta_user):
        to_select = [
            get_rubric_item('Compensation', 'BLA'),
        ]
        points = [-1]
        for item, point in zip(to_select, points):
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work_id}/rubricitems/{item["id"]}',
                204,
                result=None
            )
            with logged_in(ta_user):
                work = test_client.req(
                    'get', f'/api/v1/submissions/{work_id}', 200
                )
                assert work['grade'] == 0

                test_client.req(
                    'get',
                    f'/api/v1/submissions/{work_id}/rubrics/',
                    200,
                    result={
                        'rubrics': rubric,
                        'selected': list,
                        'points': {
                            'max': max_points,
                            'selected': point
                        }
                    }
                )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403, can_get=True)('Student1'),
    ],
    indirect=True
)
def test_selecting_rubric(
    named_user, request, test_client, logged_in, error_template, ta_user,
    assignment_real_works, session, teacher_user
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
        can_get_rubric = perm_err.kwargs.get('can_get', False)
    else:
        can_get_rubric = True
        error = False

    rubric = {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
            'items': [{
                'description': '5points',
                'header': 'bladie',
                'points': 5
            }, {
                'description': '10points',
                'header': 'bladie',
                'points': 10,
            }]
        }, {
            'header': 'My header2',
            'description': 'My description2',
            'items': [{
                'description': '1points',
                'header': 'bladie',
                'points': 1
            }, {
                'description': '2points',
                'header': 'bladie',
                'points': 2,
            }]
        }, {
            'header': 'Compensation',
            'description': 'WOW',
            'items': [{
                'description': 'BLA',
                'header': 'Never selected',
                'points': -1,
            }, {
                'description': 'BLA+',
                'header': 'Never selected 2',
                'points': 0,
            }],
        }]
    }  # yapf: disable
    max_points = 12

    with logged_in(teacher_user):
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=rubric
        )
        rubric = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': list,
                'selected': [],
                'points': {
                    'max': max_points,
                    'selected': 0
                }
            }
        )['rubrics']

    def get_rubric_item(head, desc):
        for row in rubric:
            if row['header'] == head:
                for item in row['items']:
                    if item['description'] == desc:
                        return item

    with logged_in(named_user):
        to_select = [
            get_rubric_item('My header', '10points'),
            get_rubric_item('My header2', '2points'),
            get_rubric_item('My header', '5points'),
        ]
        points = [10, 10 + 2, 5 + 2]
        result_point = points[-1]
        for item, point in zip(to_select, points):
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work_id}/rubricitems/{item["id"]}',
                error if error else 204,
                result=error_template if error else None
            )
            with logged_in(ta_user):
                work = test_client.req(
                    'get', f'/api/v1/submissions/{work_id}', 200
                )
                if error:
                    assert work['grade'] is None
                else:
                    assert approx(work['grade']) == approx(
                        min(10 * point / max_points, 10)
                    )

                test_client.req(
                    'get',
                    f'/api/v1/submissions/{work_id}/rubrics/',
                    200,
                    result={
                        'rubrics': rubric,
                        'selected': list,
                        'points':
                            {
                                'max': max_points,
                                'selected': 0 if error else point
                            }
                    }
                )

        res = {'rubrics': rubric}
        if error:
            res.update(
                {
                    'selected': [],
                    'points': {
                        'max': None,
                        'selected': None,
                    },
                },
            )
        else:
            res.update(
                {
                    'selected': list,
                    'points': {
                        'max': max_points,
                        'selected': result_point
                    }
                }
            )

        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200 if can_get_rubric else error,
            result=res if can_get_rubric else error_template
        )

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200 if can_get_rubric else error,
        )
        if not error:
            assert res['grade'] == pytest.approx(
                result_point / max_points * 10
            )

        if not error:
            with logged_in(teacher_user):
                rubric = test_client.req(
                    'delete',
                    f'/api/v1/assignments/{assignment.id}/rubrics/',
                    204,
                )
            res = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}',
                200 if can_get_rubric else error,
            )
            assert res['grade'] is None
            res = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/rubrics/',
                200,
            )
            assert res['selected'] == []


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403)('Student1'),
    ],
    indirect=True
)
def test_clearing_rubric(
    named_user, request, test_client, logged_in, error_template, ta_user,
    assignment_real_works, session, teacher_user
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    rubric = {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
            'items': [{
                'description': '5points',
                'header': 'bladie',
                'points': 5
            }, {
                'description': '10points',
                'header': 'bladie',
                'points': 10,
            }]
        }, {
            'header': 'My header2',
            'description': 'My description2',
            'items': [{
                'description': '1points',
                'header': 'bladie',
                'points': 1
            }, {
                'description': '2points',
                'header': 'bladie',
                'points': 2,
            }]
        }]
    }  # yapf: disable
    max_points = 12

    def get_rubric_item(head, desc):
        for row in rubric:
            if row['header'] == head:
                for item in row['items']:
                    if item['description'] == desc:
                        return item

    with logged_in(teacher_user):
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=rubric
        )

    with logged_in(ta_user):
        rubric = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': rubric,
                'selected': [],
                'points': {
                    'max': max_points,
                    'selected': 0
                }
            }
        )['rubrics']

        to_select = get_rubric_item('My header', '10points')
        to_select2 = get_rubric_item('My header2', '1points')
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/{to_select["id"]}',
            204,
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': rubric,
                'selected': list,
                'points': {
                    'max': max_points,
                    'selected': 10,
                }
            }
        )
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/{to_select2["id"]}',
            204,
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': rubric,
                'selected': list,
                'points': {
                    'max': max_points,
                    'selected': 11,
                }
            }
        )

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200,
        )
        assert res['grade'] == pytest.approx(11 / max_points * 10)
        selected = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
        )['selected']
        assert len(selected) == 2

    with logged_in(named_user):
        test_client.req(
            'delete',
            f'/api/v1/submissions/{work_id}/rubricitems/{selected[0]["id"]}',
            error or 204,
            result=error_template if error else None,
        )
        # Make sure invalid items can't be deselected
        test_client.req(
            'delete',
            f'/api/v1/submissions/{work_id}/rubricitems/10000000000',
            error or 400,
            result=error_template,
        )

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200,
        )
        if error:
            assert res['grade'] == pytest.approx(11 / max_points * 10)
        else:
            assert res['grade'] == pytest.approx(1 / max_points * 10)
        assert len(
            test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/rubrics/',
                200,
            )['selected']
        ) == (2 if error else 1)


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_selecting_wrong_rubric(
    request, test_client, logged_in, error_template, ta_user,
    assignment_real_works, session, course_name, teacher_user
):
    assignment, work = assignment_real_works
    course = m.Course.query.filter_by(name=course_name).one()

    other_assignment = m.Assignment(name='OTHER ASSIGNMENT', course=course)
    other_work = m.Work(assignment=other_assignment)
    session.add(other_assignment)
    session.add(other_work)
    session.commit()
    other_work_id = other_work.id

    rubric = {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
            'items': [{
                'description': '5points',
                'header': 'bladie',
                'points': 5
            }, {
                'description': '10points',
                'header': 'bladie',
                'points': 10,
            }]
        }]
    }  # yapf: disable

    with logged_in(teacher_user):
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=rubric
        )

    with logged_in(ta_user):
        test_client.req(
            'patch', f'/api/v1/submissions/{other_work_id}/'
            f'rubricitems/{rubric[0]["items"][0]["id"]}',
            400,
            result=error_template
        )


@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        'Student1',
        perm_error(error=403)('Student2'),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=True
)
@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_get_dir_contents(
    request, test_client, logged_in, named_user, error_template,
    assignment_real_works
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            error or 200,
            result=error_template if error else {
                'entries': [{
                    'id': int,
                    'name': 'test.py'
                }],
                'id': int,
                'name': 'test_flake8'
            }
        )
        if not error:
            test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/files/',
                200,
                query={'file_id': res["id"]},
                result=res,
            )

            test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/files/',
                400,
                query={'file_id': res["entries"][0]["id"]},
                result=error_template
            )

            test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/files/',
                404,
                query={'file_id': -1},
                result=error_template
            )


@pytest.mark.parametrize('user_type', ['student'])
@pytest.mark.parametrize(
    'named_user, get_own', [
        ('Thomas Schaper', False),
        ('Student1', False),
        ('Œlµo', True),
        perm_error(error=401)(('NOT_LOGGED_IN', False)),
        perm_error(error=403)(('admin', False)),
        perm_error(error=403)(('Student3', False)),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.zip'],
    indirect=True
)
def test_get_zip_file(
    test_client, logged_in, assignment_real_works, error_template, named_user,
    request, user_type, get_own
):
    assignment, work = assignment_real_works
    if get_own:
        work_id = m.Work.query.filter_by(user=named_user).order_by(
            m.Work.created_at.desc()
        ).first().id
    else:
        work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        for url in [
            '/api/v1/files/{name}?name={output_name}',
            '/api/v1/files/{name}/{output_name}'
        ]:
            res = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}',
                error or 200,
                result=error_template if error else {
                    'name': str,
                    'output_name': str
                },
                query={
                    'type': 'zip',
                    'owner': user_type
                },
            )

            if not error:
                file_name = res['name']
                res = test_client.get(url.format(**res))

                assert res.status_code == 200
                zfiles = zipfile.ZipFile(io.BytesIO(res.get_data()))
                files = zfiles.infolist()
                files = set(f.filename for f in files)
                assert files == set(
                    [
                        'multiple_dir_archive/',
                        'multiple_dir_archive/dir/single_file_work',
                        'multiple_dir_archive/dir/single_file_work_copy',
                        'multiple_dir_archive/dir2/single_file_work',
                        'multiple_dir_archive/dir2/single_file_work_copy',
                    ]
                )

                res = test_client.get(f'/api/v1/files/{file_name}')
                assert res.status_code == 404


@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.zip'],
    indirect=True
)
def test_get_teacher_zip_file(
    test_client, logged_in, assignment_real_works, error_template, request,
    ta_user, student_user, session
):
    def get_files(user, error):
        with logged_in(user):
            res = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}',
                error or 200,
                result=error_template if error else {
                    'name': str,
                    'output_name': str
                },
                query={
                    'type': 'zip',
                    'owner': 'teacher'
                },
            )
            if error:
                return set()

            file_name = res['name']
            res = test_client.get(f'/api/v1/files/{file_name}')

            assert res.status_code == 200
            files = zipfile.ZipFile(io.BytesIO(res.get_data())).infolist()
            files = set(f.filename for f in files)
            return files

    assignment, work = assignment_real_works
    work_id = work['id']

    assert get_files(ta_user, False) == set(
        [
            'multiple_dir_archive/',
            'multiple_dir_archive/dir/single_file_work',
            'multiple_dir_archive/dir/single_file_work_copy',
            'multiple_dir_archive/dir2/single_file_work',
            'multiple_dir_archive/dir2/single_file_work_copy',
        ]
    )

    get_files(student_user, 403)
    m.File.query.filter_by(
        work_id=work_id,
        name="single_file_work",
    ).filter(
        m.File.parent != None,
    ).update({
        'fileowner': m.FileOwner.student
    })
    assert get_files(ta_user, False) == set(
        [
            'multiple_dir_archive/',
            'multiple_dir_archive/dir/single_file_work_copy',
            'multiple_dir_archive/dir2/single_file_work_copy'
        ]
    )
    m.Assignment.query.filter_by(
        id=m.Work.query.get(work_id).assignment_id,
    ).update(
        {
            'deadline': datetime.datetime.utcnow() -
                        datetime.timedelta(days=1)
        },
    )
    get_files(student_user, 403)

    m.Assignment.query.filter_by(
        id=m.Work.query.get(work_id).assignment_id,
    ).update({
        'state': m._AssignmentStateEnum.done,
    }, )

    assert get_files(student_user, False) == set(
        [
            'multiple_dir_archive/',
            'multiple_dir_archive/dir/single_file_work_copy',
            'multiple_dir_archive/dir2/single_file_work_copy'
        ]
    )


@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        'Student1',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403)('Student3'),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.zip'],
    indirect=True
)
@pytest.mark.parametrize(
    'to_search', [
        'multiple_dir_archive/dir/single_file_work',
        '/multiple_dir_archive/dir/single_file_work',
        data_error(error=404)('multiple_dir_archive/dir/single_file_work/'),
        data_error(error=404)('/multiple_dir_archive/dir/single_file_work/'),
        '/multiple_dir_archive/dir2/',
        'multiple_dir_archive/dir2/',
        data_error(error=404)('/multiple_dir_archive/dir2'),
        data_error(error=404)('multiple_dir_archive/dir2'),
    ]
)
def test_search_file(
    test_client, logged_in, assignment_real_works, error_template, named_user,
    request, to_search
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    if perm_err:
        error = perm_err.kwargs['error']
    elif data_err:
        error = data_err.kwargs['error']
    else:
        error = False

    is_dir = to_search[-1] == '/'

    with logged_in(named_user):
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            error or 200,
            query={'path': to_search},
            result=error_template if error else {
                'is_directory': is_dir,
                'modification_date': int,
                'size': int,
                'id': int
            },
        )


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
def test_add_file(
    test_client, logged_in, ta_user, assignment_real_works, error_template,
    student_user, session
):
    assignment, work = assignment_real_works
    work_id = work['id']

    def get_file_by_id(file_id):
        res = test_client.get(f'/api/v1/code/{file_id}')
        assert res.status_code == 200
        return res.get_data(as_text=True)

    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            404,
            result=error_template,
            query={'path': '/non/existing/'}
        )
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            result=error_template,
            query={'path': '/too_short/'}
        )

        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/dir/dir2/wow/'},
        )
        assert res['is_directory'] == True
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            query={'path': '/dir/dir2/wow/'},
            result=error_template,
        )
        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/dir/dir2/wow/dit/'},
        )
        assert res['is_directory'] == True

        # Make sure you cannot upload to large strings
        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            query={'path': '/dir/dir2/this/is/to/large/file'},
            real_data=b'0' * 2 * 2 ** 20,
            result=error_template,
        )
        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/dir/dir2/file'},
            real_data='NEW_FILE',
        )
        assert get_file_by_id(res['id']) == 'NEW_FILE'
        assert res['size'] == len('NEW_FILE')
        assert res['is_directory'] == False
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            query={'path': '/dir/dir2/file'},
            real_data='NEWER_FILE',
        )
        assert get_file_by_id(res['id']) == 'NEW_FILE'
        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/dir/dir2/dir3/file'},
            real_data='NEW_FILE',
        )
        assert get_file_by_id(res['id']) == 'NEW_FILE'
        assert res['size'] == len('NEW_FILE')
        assert res['is_directory'] == False

    with logged_in(ta_user):
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            403,
            query={'path': '/dir/dir2/file'},
            result=error_template,
            real_data='TEAER_FILE',
        )

        session.query(
            m.Assignment
        ).filter_by(id=m.Work.query.get(work_id).assignment_id).update(
            {
                'deadline':
                    datetime.datetime.utcnow() - datetime.timedelta(days=1)
            }
        )

        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            query={
                'path': '/dir/dir2/file',
                'owner': 'auto'
            },
            real_data='TEAEST_FILE',
        )

        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/dir/dir2/file2'},
            real_data='TEAEST_FILE',
        )
        assert get_file_by_id(res['id']) == 'TEAEST_FILE'
        assert res['size'] == len('TEAEST_FILE')
        assert res['is_directory'] == False

    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            403,
            query={'path': '/dir/dir2/wow2/'},
            real_data='TEAEST_FILE',
            result=error_template,
        )

    with logged_in(ta_user):
        session.query(
            m.Assignment
        ).filter_by(id=m.Work.query.get(work_id).assignment_id).update(
            {
                'deadline':
                    datetime.datetime.utcnow() + datetime.timedelta(days=1)
            }
        )

    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/dir/dir2/file2'},
            real_data='STUDENT_FILE',
        )

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'name':
                    'dir',
                'id':
                    int,
                'entries':
                    [
                        {
                            'name':
                                'dir2',
                            'id':
                                int,
                            'entries':
                                [
                                    {
                                        'name':
                                            'dir3',
                                        'id':
                                            int,
                                        'entries':
                                            [{
                                                'name': 'file',
                                                'id': int,
                                            }],
                                    }, {
                                        'name': 'file',
                                        'id': int,
                                    }, {
                                        'name': 'file2',
                                        'id': int,
                                    },
                                    {
                                        'name':
                                            'wow',
                                        'id':
                                            int,
                                        'entries':
                                            [
                                                {
                                                    'name': 'dit',
                                                    'id': int,
                                                    'entries': [],
                                                }
                                            ],
                                    }
                                ],
                        }, {
                            'name': 'single_file_work',
                            'id': int,
                        }, {
                            'name': 'single_file_work_copy',
                            'id': int,
                        }
                    ],
            }
        )

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'name':
                    'dir',
                'id':
                    int,
                'entries':
                    [
                        {
                            'name':
                                'dir2',
                            'id':
                                int,
                            'entries':
                                [
                                    {
                                        'name':
                                            'dir3',
                                        'id':
                                            int,
                                        'entries':
                                            [{
                                                'name': 'file',
                                                'id': int,
                                            }],
                                    }, {
                                        'name': 'file',
                                        'id': int,
                                    }, {
                                        'name': 'file2',
                                        'id': int,
                                    },
                                    {
                                        'name':
                                            'wow',
                                        'id':
                                            int,
                                        'entries':
                                            [
                                                {
                                                    'name': 'dit',
                                                    'id': int,
                                                    'entries': [],
                                                }
                                            ],
                                    }
                                ],
                        }, {
                            'name': 'single_file_work',
                            'id': int,
                        }, {
                            'name': 'single_file_work_copy',
                            'id': int,
                        }
                    ],
            }
        )

        session.query(
            m.Assignment
        ).filter_by(id=m.Work.query.get(work_id).assignment_id).update(
            {
                'deadline':
                    datetime.datetime.utcnow() + datetime.timedelta(days=1)
            }
        )


@pytest.mark.parametrize('with_works', [True], indirect=True)
def test_change_grader_notification(
    logged_in, test_client, stubmailer, monkeypatch_celery, assignment,
    teacher_user, with_works, ta_user
):
    assig_id = assignment.id
    graders = m.User.query.filter(
        m.User.name.in_([
            'Thomas Schaper',
            'Devin Hillenius',
            'Robin',
        ]),
        ~m.User.name.in_(ta_user.name),
    ).all()
    grader_done = graders[0].id

    subs = m.Work.query.filter_by(assignment_id=assig_id).all()
    sub_id = subs[0].id
    sub2_id = subs[1].id

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub_id}/grader',
            204,
            data={'user_id': grader_done},
        )
        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub2_id}/grader',
            204,
            data={'user_id': teacher_user.id},
        )

        assert not stubmailer.called, """
        Setting a non done grader should not do anything
        """
        stubmailer.reset()

        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            204,
        )
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{ta_user.id}/done',
            204,
        )

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub_id}/grader',
            204,
            data={'user_id': ta_user.id},
        )

        assert not stubmailer.called, """
        Setting yourself as assigned should not trigger emails
        """
        assert not m.AssignmentGraderDone.query.filter_by(
            user_id=ta_user.id,
        ).all(), 'We should however not be marked as done any more.'
        stubmailer.reset()

        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub_id}/grader',
            204,
            data={'user_id': grader_done},
        )

        assert stubmailer.called == 1, """
        Setting somebody else as assigned should trigger a email even if this
        person was previously assigned.
        """
        assert not m.AssignmentGraderDone.query.filter_by(
            assignment_id=assig_id,
        ).all(), 'Make sure nobody is done at this point'


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
@pytest.mark.parametrize(
    'named_user',
    ['Thomas Schaper', http_error(error=403)('Student1')],
    indirect=True
)
@pytest.mark.parametrize('graders', [(['Thomas Schaper', 'Devin Hillenius'])])
def test_change_grader(
    graders, named_user, logged_in, test_client, error_template, request,
    assignment_real_works, ta_user
):
    marker = request.node.get_closest_marker('http_error')
    code = 204 if marker is None else marker.kwargs['error']
    res = None if marker is None else error_template

    assignment, _ = assignment_real_works

    grader_ids = []
    for grader in graders:
        if isinstance(grader, int):
            grader_ids.append(grader)
        else:
            grader_ids.append(m.User.query.filter_by(name=grader).one().id)

    with logged_in(named_user):
        with logged_in(ta_user):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment.id}/divide',
                204,
                data={'graders': {g: 1
                                  for g in grader_ids}}
            )
            submission = test_client.req(
                'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
            )[0]

        old_grader = submission['assignee']['name']

        if marker is None:
            test_client.req(
                'patch',
                f'/api/v1/submissions/{submission["id"]}/grader',
                404,
                result=error_template,
                data={'user_id': 100000}
            )
            with logged_in(ta_user):
                submission = test_client.req(
                    'get', f'/api/v1/assignments/{assignment.id}/submissions/',
                    200
                )[0]
            assert submission['assignee']['name'] == old_grader

            student1_id = m.User.query.filter_by(name='Student1').first().id
            test_client.req(
                'patch',
                f'/api/v1/submissions/{submission["id"]}/grader',
                400,
                result=error_template,
                data={'user_id': student1_id}
            )
            with logged_in(ta_user):
                submission = test_client.req(
                    'get', f'/api/v1/assignments/{assignment.id}/submissions/',
                    200
                )[0]
            assert submission['assignee']['name'] == old_grader

        new_grader = [grader for grader in graders if grader != old_grader][0]
        new_grader_id = m.User.query.filter_by(name=new_grader).first().id

        test_client.req(
            'patch',
            f'/api/v1/submissions/{submission["id"]}/grader',
            code,
            result=res,
            data={'user_id': new_grader_id}
        )
        with logged_in(ta_user):
            submission = test_client.req(
                'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
            )[0]
        if marker is None:
            assert submission['assignee']['name'] == new_grader
        else:
            assert submission['assignee']['name'] == old_grader

        test_client.req(
            'delete',
            f'/api/v1/submissions/{submission["id"]}/grader',
            code,
            result=res
        )
        with logged_in(ta_user):
            submission = test_client.req(
                'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
            )[0]
        if marker is None:
            assert submission['assignee'] is None
        else:
            assert submission['assignee']['name'] == old_grader


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        perm_error(error=403)('Thomas Schaper'),
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403)('Student1'),
    ],
    indirect=True
)
def test_delete_submission(
    named_user, request, test_client, logged_in, error_template, teacher_user,
    assignment_real_works, session
):
    assignment, work = assignment_real_works
    work_id = work['id']
    other_work = m.Work.query.filter_by(assignment=assignment
                                        ).filter(m.Work.id != work_id).first()
    assert other_work, "Other work should exist"

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    files = [f.id for f in m.File.query.filter_by(work_id=work_id).all()]
    assert files
    code = m.File.query.filter_by(work_id=work_id, is_directory=False).first()

    diskname = code.get_diskname()
    assert os.path.isfile(diskname)

    other_code = m.File.query.filter_by(
        work_id=other_work.id, is_directory=False
    ).first()

    p_run = m.PlagiarismRun(assignment=assignment, json_config='')
    p_case = m.PlagiarismCase(
        work1_id=work_id, work2_id=other_work.id, match_avg=50, match_max=50
    )
    p_match = m.PlagiarismMatch(
        file1=code,
        file2=other_code,
        file1_start=0,
        file1_end=1,
        file2_start=0,
        file2_end=1
    )
    p_case.matches.append(p_match)
    p_run.cases.append(p_case)
    session.add(p_run)
    session.commit()
    p_case_id = p_case.id
    p_run_id = p_run.id

    assert p_case_id
    assert p_run_id

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={
                'feedback': 'waaa',
                'grade': 5.65
            },
            result=dict,
        )

    with logged_in(named_user):
        test_client.req(
            'delete',
            f'/api/v1/submissions/{work_id}',
            error or 204,
            result=error_template if error else None
        )

    if error:
        assert os.path.isfile(diskname)
        for f in files:
            assert m.File.query.get(f)
        assert m.Work.query.get(work_id)
        assert m.PlagiarismCase.query.get(p_case_id)
        assert m.PlagiarismRun.query.get(p_run_id)
    else:
        assert not os.path.isfile(diskname)
        assert m.Work.query.get(work_id) is None
        for f in files:
            assert m.File.query.get(f) is None
        assert m.PlagiarismCase.query.get(p_case_id) is None
        assert m.PlagiarismRun.query.get(p_run_id)


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403, can_get=True)('Student1'),
    ],
    indirect=True
)
def test_selecting_multiple_rubric_items(
    named_user, request, test_client, logged_in, error_template, ta_user,
    assignment_real_works, session, bs_course, teacher_user
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
        can_get_rubric = perm_err.kwargs.get('can_get', False)
    else:
        can_get_rubric = True
        error = False

    rubric = {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
            'items': [{
                'description': '5points',
                'header': 'bladie',
                'points': 5
            }, {
                'description': '10points',
                'header': 'bladie',
                'points': 10,
            }]
        }, {
            'header': 'My header2',
            'description': 'My description2',
            'items': [{
                'description': '1points',
                'header': 'bladie',
                'points': 1
            }, {
                'description': '2points',
                'header': 'bladie',
                'points': 2,
            }]
        }]
    }  # yapf: disable
    max_points = 12

    with logged_in(teacher_user):
        bs_rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{bs_course.id}/rubrics/',
            200,
            data=rubric
        )
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=rubric
        )
        rubric = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': list,
                'selected': [],
                'points': {
                    'max': max_points,
                    'selected': 0
                }
            }
        )['rubrics']

    def get_rubric_item(head, desc):
        for row in rubric:
            if row['header'] == head:
                for item in row['items']:
                    if item['description'] == desc:
                        return item

    with logged_in(named_user):
        to_select = [
            get_rubric_item('My header', '5points')['id'],
            get_rubric_item('My header2', '2points')['id'],
        ]
        points = 7
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/',
            error if error else 204,
            data={'items': to_select},
            result=error_template if error else None
        )

    with logged_in(ta_user):
        selected = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': list,
                'selected': list,
                'points':
                    {
                        'max': max_points,
                        'selected': 0 if error else points,
                    }
            }
        )['selected']
        if error:
            assert not selected
        else:
            selected = [s['id'] for s in selected]
            assert all(item in selected for item in to_select)

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/',
            404,
            data={'items': to_select + [-1]},
            result=error_template,
        )

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/',
            400,
            data={'items': to_select + [bs_rubric[0]['items'][0]['id']]},
            result=error_template,
        )


@pytest.mark.parametrize('ext', ['tar.gz'])
def test_uploading_unsafe_archive(
    logged_in, student_user, teacher_user, assignment, test_client, ext,
    error_template
):
    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            400,
            real_data={
                'file':
                    (
                        f'{os.path.dirname(__file__)}/../test_data/'
                        f'test_submissions/unsafe.{ext}', f'unsafe.{ext}'
                    )
            },
            result=error_template,
        )

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            204,
            data={
                'ignore': 'a\n',
            }
        )

    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission'
            '?ignored_files=error',
            400,
            real_data={
                'file':
                    (
                        f'{os.path.dirname(__file__)}/../test_data/'
                        f'test_submissions/unsafe.{ext}', f'unsafe.{ext}'
                    )
            },
            result=error_template,
        )


@pytest.mark.parametrize('ignore', [True, False])
@pytest.mark.parametrize('ext', ['tar.gz', 'zip'])
def test_uploading_invalid_file(
    logged_in, student_user, teacher_user, assignment, test_client, ignore,
    error_template, ext
):
    if ignore:
        with logged_in(teacher_user):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment.id}',
                204,
                data={
                    'ignore': 'a\n',
                }
            )

    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission' +
            ('?ignored_files=error' if ignore else ''),
            400,
            real_data={
                'file':
                    (
                        f'{os.path.dirname(__file__)}/../test_data/'
                        f'test_submissions/single_file_work', f'arch.{ext}'
                    )
            },
            result=error_template,
        )


@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        http_error(error=403)('Student2'),
        http_error(error=403)('Thomas Schaper'),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'max_grade', [
        10,
        4,
        15,
        http_error(error=400)('Hello'),
        http_error(error=400)(-2),
    ]
)
@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_maximum_grade(
    logged_in, named_user, ta_user, assignment_real_works, error_template,
    max_grade, test_client, request
):
    assignment, work = assignment_real_works
    work_id = work['id']

    marker = request.node.get_marker('http_error')
    code = 204 if marker is None else marker.kwargs['error']

    data = {'grade': 11}

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            400,
            data=data,
            result=error_template,
        )

    with logged_in(named_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            code,
            data={'max_grade': max_grade},
            result=error_template if code >= 400 else None
        )

    if code >= 400:
        with logged_in(ta_user):
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work_id}',
                400,
                data=data,
                result=error_template,
            )
        return

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': max_grade},
        )

        assert test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}', 200
        )['max_grade'] == max_grade

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            400,
            data={'grade': max_grade + 0.5},
            result=error_template
        )

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            400,
            data={'grade': -0.5},
        )

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': max_grade},
        )

    with logged_in(named_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            204,
            data={'max_grade': None},
        )
        assert test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}', 200
        )['max_grade'] is None

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            400,
            data={'grade': 10.5},
        )
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': 10},
        )

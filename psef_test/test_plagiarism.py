import os
import csv
import random
import itertools
import subprocess

import pytest
from sqlalchemy import func

import psef
from helpers import create_marker

http_err = create_marker(pytest.mark.http_err)


def get_random_path(d, upper):
    r = get_all_files_of_dir(d, upper)
    random.shuffle(r)
    return r[0][len(d):]


def get_all_files_of_dir(d, upper):
    res = []
    for entry in os.listdir(os.path.join(upper, d)):
        if os.path.isdir(os.path.join(upper, d, entry)):
            res.extend(get_all_files_of_dir(os.path.join(d, entry), upper))
        else:
            res.append(os.path.join(d, entry))

    return res


@pytest.mark.parametrize(
    'lang', [
        'Python 3',
        http_err(error=400)('CODEGRA.LANG'),
        http_err(error=400)(None),
    ]
)
@pytest.mark.parametrize('simil', [
    None,
    http_err(error=400)('40'),
    40,
])
@pytest.mark.parametrize(
    'unknown_key', [
        None,
        http_err(error=400)('VALUE'),
    ]
)
@pytest.mark.parametrize(
    'suffixes', [
        None,
        http_err(error=400)(2),
        '*.py,*.PY',
    ]
)
@pytest.mark.parametrize(
    'old_assignments', [
        [],
        http_err(error=400)(['']),
        http_err(error=404)([-1]),
    ]
)
@pytest.mark.parametrize(
    'provider', [
        'JPlag',
        http_err(error=400)(None),
        http_err(error=404)('unknown'),
    ]
)
@pytest.mark.parametrize('bb_tar_gz', ['correct.tar.gz'])
def test_jplag(
    bb_tar_gz, logged_in, request, assignment, test_client, teacher_user,
    provider, old_assignments, lang, simil, suffixes, error_template,
    monkeypatch, monkeypatch_celery, session, unknown_key
):
    student_user = session.query(psef.models.User).filter_by(name='Student2'
                                                             ).one()
    bb_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_blackboard/{bb_tar_gz}'
    )
    marker = request.node.get_closest_marker('http_err')
    code = marker.kwargs['error'] if marker else 200

    call_arguments = None
    called_num = 0
    written_rows = None

    def my_check_output(call, **kwargs):
        nonlocal call_arguments, called_num, written_rows
        assert not kwargs['shell']

        called_num += 1
        call_arguments = call

        f_p = os.path.join(call[call.index('-r') + 1], 'computer_matches.csv')
        data_dir = call[3]
        dirs = os.listdir(data_dir)
        random.shuffle(dirs)
        dir1 = dirs[0]
        dir2 = dirs[1]
        dir3 = dirs[2]

        with open(f_p, 'w') as f:
            writer = csv.writer(f, delimiter=';')
            written_rows = [
                [
                    dir1,
                    dir2,
                    100,
                    25,
                    get_random_path(dir1, data_dir),
                    0,
                    10,
                    get_random_path(dir2, data_dir),
                    12,
                    14,
                    get_random_path(dir1, data_dir),
                    2,
                    10,
                    get_random_path(dir2, data_dir),
                    14,
                    19,
                ],
                [
                    dir2,
                    dir3,
                    75,
                    20,
                    get_random_path(dir2, data_dir),
                    5,
                    10,
                    get_random_path(dir3, data_dir),
                    0,
                    4,
                    get_random_path(dir2, data_dir),
                    5,
                    8,
                    get_random_path(dir3, data_dir),
                    24,
                    29,
                ]
            ]
            for row in written_rows:
                writer.writerow(row)
        return b'My log!'

    monkeypatch.setattr(subprocess, 'check_output', my_check_output)

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )

    data = {
        'provider': provider,
        'old_assignments': old_assignments,
        'lang': lang,
        'simil': simil,
        'suffixes': suffixes,
        'unknown_key': unknown_key,
    }
    data = {k: v for k, v in data.items() if v is not None}

    with logged_in(student_user):
        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            403,
            data=data,
            result=error_template,
        )

    with logged_in(teacher_user):
        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            code,
            data=data,
            result=None if code >= 400 else {
                'id': int,
                'state': str,
                'provider_name': str,
                'config': list
            }
        )
        if code >= 400:
            return

        assert plag['config'] == [list(v) for v in sorted(data.items())]

        # Cannot run twice with same config
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            400,
            data=data,
            result=error_template
        )
    with logged_in(teacher_user):
        plag = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}',
            200,
            result={
                'id': int,
                'state': 'done',
                'provider_name': str,
                'config': list
            }
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/plagiarism/',
            200,
            result=[plag]
        )

        assert called_num == 1, "We only ran once"
        assert call_arguments[call_arguments.index('-l') +
                              1] == 'python3', "Correct language is python3"
        if simil is None:
            assert call_arguments[call_arguments.index('-m') +
                                  1] == '25%', "Given value differs"
        else:
            assert call_arguments[call_arguments.index('-m') +
                                  1] == f'{simil}%', "Given value differs"
        if suffixes is None:
            assert '-p' not in call_arguments, "Suffixes was not given"
        else:
            assert call_arguments[call_arguments.index('-p') +
                                  1] == str(suffixes), "Differs!"
        assert test_client.req(
            'get', f'/api/v1/plagiarism/{plag["id"]}?extended', 200
        )['log'] == 'My log!', "Wrong log was saved"
        cases = test_client.req(
            'get', f'/api/v1/plagiarism/{plag["id"]}/cases/', 200
        )
        assert len(cases) == len(written_rows), "Wrong amount of cases saved"
        for case in cases:
            assert 'id' in case, 'This needs to be present'
            assert 'assignments' in case, 'This needs to be present'
            assert 'submissions' in case, "This needs to be present"
            for i in range(len(written_rows)):
                if max(written_rows[i][2:4]) == case['match_max']:
                    row = written_rows.pop(i)
                    break
            else:
                assert False, "Row not found!"
            assert sum(row[2:4]) / 2 == case['match_avg'], "Wrong average"
            assert case['users'][0]['name'] == row[0].split(' || ')[0]
            assert case['users'][1]['name'] == row[1].split(' || ')[0]
            case = test_client.req(
                'get', f'/api/v1/plagiarism/{plag["id"]}/cases/{case["id"]}',
                200
            )
            assert len(case['matches']
                       ) == len(row[4:]) / 6, "Amount matches match"

    # Make doing these calls as student fails with permission errors
    with logged_in(student_user):
        test_client.req(
            'delete',
            f'/api/v1/plagiarism/{plag["id"]}',
            403,
            result=error_template
        )
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}',
            403,
            result=error_template
        )
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            403,
            result=error_template
        )
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/{case["id"]}',
            403,
            result=error_template
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/plagiarism/',
            403,
            result=error_template
        )

    with logged_in(teacher_user):
        test_client.req(
            'delete', f'/api/v1/plagiarism/{plag["id"]}', 204, result=None
        )
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}',
            404,
            result=error_template
        )
        # Needs to be gone here too
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/plagiarism/',
            200,
            result=[]
        )


@pytest.mark.parametrize('bb_tar_gz', ['correct.tar.gz'])
def test_jplag_old_assignments(
    bb_tar_gz, logged_in, assignment, test_client, teacher_user,
    error_template, monkeypatch, monkeypatch_celery, session
):
    other_assignment = psef.models.Assignment(
        name='TEST COURSE',
        course=assignment.course,
    )
    session.add(other_assignment)
    other_course = psef.models.Course(name='Other course')
    other_course_assignment = psef.models.Assignment(
        name='OTHER COURSE ASSIGNMENT',
        course=other_course,
    )
    session.add(other_course)
    session.add(other_course_assignment)
    session.commit()

    bb_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_blackboard/{bb_tar_gz}'
    )

    def my_check_output(call, **kwargs):
        f_p = os.path.join(call[call.index('-r') + 1], 'computer_matches.csv')
        data_dir = call[3]
        dirs = os.listdir(data_dir)
        with open(f_p, 'w') as f:
            writer = csv.writer(f, delimiter=';')
            for dir1, dir2 in itertools.product(dirs, dirs):
                writer.writerow(
                    [
                        dir1,
                        dir2,
                        75,
                        20,
                        get_random_path(dir1, data_dir),
                        5,
                        10,
                        get_random_path(dir2, data_dir),
                        0,
                        4,
                    ]
                )

        return b'Log!'

    monkeypatch.setattr(subprocess, 'check_output', my_check_output)

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )
        test_client.req(
            'post',
            f'/api/v1/assignments/{other_assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )

    with logged_in(teacher_user):
        data = {
            'provider': 'JPlag',
            'old_assignments': [other_assignment.id],
            'lang': 'Python 3',
        }

        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            200,
            data=data,
            result={
                'id': int,
                'state': str,
                'provider_name': str,
                'config': list
            }
        )
        plag = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}?extended',
            200,
            result={
                'id': int,
                'state': 'done',
                'provider_name': str,
                'config': list,
                'log': str,
                'cases': list,
            }
        )
        assert (
            len(plag['cases']) == (
                assignment.get_from_latest_submissions(
                    func.count(psef.models.Work.id)
                ).scalar() ** 2 * other_assignment.get_from_latest_submissions(
                    func.count(psef.models.Work.id)
                ).scalar()
            )
        ), "The amount of cases should be the maximum"
        for jcase in plag['cases']:
            case = session.query(psef.models.PlagiarismCase).get(jcase['id'])
            if case.work1.assignment_id == case.work2.assignment_id:
                assert case.work1.assignment_id == assignment.id

        data['old_assignments'].append(other_course_assignment.id)
        # We don't have permission to do this
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            403,
            data=data,
            result=error_template,
        )

        other_course_teacher_role = psef.models.CourseRole.query.filter_by(
            course_id=other_course.id, name='Teacher'
        ).one()
        teacher_user.courses[other_course.id] = other_course_teacher_role
        session.commit()

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{other_course_assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )
        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            200,
            data=data,
        )

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}',
            200,
        )
        cases = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            200,
        )
        for idx, case in enumerate(cases):
            for idx2, assig in enumerate(case['assignments']):
                if assig['course']['id'] == other_course.id:
                    break
            else:
                continue
            break
        else:
            assert False
    old_case = cases[idx]

    other_course_teacher_role = psef.models.CourseRole.query.filter_by(
        course_id=other_course.id, name='Teacher'
    ).one()
    other_course_teacher_role.set_permission(
        psef.models.Permission.query.filter_by(name='can_view_plagiarism'
                                               ).one(), False
    )
    session.commit()

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/{old_case["id"]}',
            200,
        )
        case = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            200,
        )[idx]
        assert case == old_case

    other_course_teacher_role = psef.models.CourseRole.query.filter_by(
        course_id=other_course.id, name='Teacher'
    ).one()
    other_course_teacher_role.set_permission(
        psef.models.Permission.query.filter_by(name='can_see_assignments'
                                               ).one(), False
    )
    session.commit()

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/{old_case["id"]}',
            403,
        )
        case = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            200,
        )[idx]
        assert case['id'] == old_case['id']
        assert case['submissions'] == old_case['submissions']
        assert sorted(list(case['assignments'][idx2].keys())) == [
            'course', 'name'
        ]
        assert sorted(list(case['assignments'][idx2]['course'].keys())) == [
            'name'
        ]

    other_course_teacher_role = psef.models.CourseRole.query.filter_by(
        course_id=other_course.id, name='Teacher'
    ).one()
    other_course_teacher_role.set_permission(
        psef.models.Permission.query.filter_by(name='can_see_others_work'
                                               ).one(), False
    )
    session.commit()

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/{old_case["id"]}',
            403,
        )
        case = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            200,
        )[idx]
        assert case['id'] == old_case['id']
        assert case['submissions'] == None
        assert sorted(list(case['assignments'][idx2].keys())) == [
            'course', 'name'
        ]
        assert sorted(list(case['assignments'][idx2]['course'].keys())) == [
            'name'
        ]


@pytest.mark.parametrize('subprocess_exception', [True, False])
@pytest.mark.parametrize('bb_tar_gz', ['correct.tar.gz'])
def test_chrased_jplag(
    bb_tar_gz, logged_in, assignment, test_client, teacher_user,
    error_template, monkeypatch, monkeypatch_celery, session,
    subprocess_exception
):
    bb_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_blackboard/{bb_tar_gz}'
    )

    def my_check_output(call, **kwargs):
        if not subprocess_exception:
            raise Exception('ERR!')
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=call,
            output=b'Normal output\n',
            stderr=b'Error output\n'
        )

    monkeypatch.setattr(subprocess, 'check_output', my_check_output)

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )

    with logged_in(teacher_user):
        data = {
            'provider': 'JPlag',
            'old_assignments': [],
            'lang': 'Python 3',
        }

        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            200,
            data=data,
            result={
                'id': int,
                'state': str,
                'provider_name': str,
                'config': list
            }
        )
        plag = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}?extended',
            200,
            data=data,
            result={
                'id': int,
                'state': 'crashed',
                'provider_name': str,
                'config': list,
                'log': str,
                'cases': [],
            }
        )
        if subprocess_exception:
            assert plag['log'] == 'Normal output\nError output\n'


def test_get_plagiarism_providers(test_client):
    test_client.req(
        'get',
        '/api/v1/plagiarism/',
        200,
        result=[
            {
                'name':
                    'JPlag',
                'options':
                    [
                        {
                            'name': 'lang',
                            'title': 'Language',
                            'description': str,
                            'type': 'singleselect',
                            'mandatory': bool,
                            'possible_options': list,
                            'placeholder': None,
                        },
                        {
                            'name': 'suffixes',
                            'title': 'Suffixes to include',
                            'description': str,
                            'type': 'strvalue',
                            'mandatory': bool,
                            'placeholder': '.xxx, .yyy',
                        },
                        {
                            'name': 'simil',
                            'title': 'Minimal similarity',
                            'description': str,
                            'type': 'numbervalue',
                            'mandatory': bool,
                            'placeholder': 25,
                        }
                    ],
            },
        ],
    )
import copy

import pytest

import psef.models as m

data_error = pytest.mark.data_error
does_have_permission = pytest.mark.does_have_permission


@pytest.mark.parametrize('active', [True, False])
@pytest.mark.parametrize(
    'password', [
        data_error(None),
        data_error(5),
        'a',
        data_error(wrong=True)('b'),
    ]
)
@pytest.mark.parametrize(
    'email', [
        data_error(None),
        data_error(5),
        'a@a.nl',
        data_error('b@b.nl'),
        data_error(wrong=True)('b'),
    ]
)
def test_login(
    test_client, session, error_template, password, email, request, active
):
    new_user = m.User(
        name='NEW_USER', email='a@a.nl', password='a', active=active
    )
    session.add(new_user)
    session.commit()

    data_err = request.node.get_marker('data_error')
    if data_err:
        error = 400
        if data_err.kwargs.get('wrong'):
            error_template = copy.deepcopy(error_template)
            error_template['message'
                           ] == 'The supplied email or password is wrong.'
    elif not active:
        error = 403
    else:
        error = False

    data = {}
    if password is not None:
        data['password'] = password
    if email is not None:
        data['email'] = email

    test_client.req(
        'post',
        f'/api/v1/login',
        error or 200,
        data=data,
        result=error_template
        if error else {'email': 'a@a.nl',
                       'id': int,
                       'name': 'NEW_USER'}
    )
    test_client.req('get', '/api/v1/login', 401 if error else 200)

    if not error:
        test_client.req('delete', '/api/v1/login', 204)

    test_client.req('get', '/api/v1/login', 401)


@pytest.mark.parametrize(
    'named_user', [
        does_have_permission('Thomas Schaper'),
        'Stupid1',
    ],
    indirect=True
)
def test_extended_get_login(test_client, named_user, logged_in, request):
    perm_true = bool(request.node.get_marker('does_have_permission'))

    with logged_in(named_user):
        test_client.req(
            'get',
            '/api/v1/login',
            200,
            query={'type': 'extended'},
            result={
                'name': str,
                'id': int,
                'email': str,
                'hidden': perm_true,
            }
        )


@pytest.mark.parametrize(
    'named_user,roles',
    [
        ('Thomas Schaper', ['Student', 'TA', 'TA', None]),
        ('Stupid1', [None, None, 'Student', 'Student']),
        ('admin', [None, None, None, None]),
    ],
    indirect=['named_user'],
)
def test_get_roles(
    test_client, named_user, logged_in, pse_course, bs_course, prog_course,
    inprog_course, roles
):
    result = {}
    for course, role in zip(
        [pse_course, bs_course, prog_course, inprog_course], roles
    ):
        if role is not None:
            result[str(course.id)] = role

    with logged_in(named_user):
        test_client.req(
            'get',
            '/api/v1/login',
            200,
            query={'type': 'roles'},
            result=result,
        )
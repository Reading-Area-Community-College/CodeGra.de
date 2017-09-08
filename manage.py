#!/usr/bin/env python3

import os
import sys
import json
import datetime

from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from sqlalchemy_utils import PasswordType

import psef
import psef.models as m
from psef import db, app


def render_item(type_, col, autogen_context):
    if type_ == "type" and isinstance(col, PasswordType):
        autogen_context.imports.add("import sqlalchemy_utils")
        return "sqlalchemy_utils.PasswordType"
    else:
        return False


migrate = Migrate(app, db, render_item=render_item)
manager = Manager(app)

manager.add_command('db', MigrateCommand)


@manager.command
def seed():
    if not app.config['DEBUG']:
        print(
            'Seeding the database is NOT safe if there is data in'
            ' the database, please use seed_force to seed anyway',
            file=sys.stderr
        )
        return 1
    return seed_force()


@manager.command
def seed_force():
    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/seed_data/permissions.json',
        'r'
    ) as perms:
        perms = json.load(perms)
        for name, perm in perms.items():
            old_perm = m.Permission.query.filter_by(name=name).first()
            if old_perm is not None:
                old_perm.default_value = perm['default_value']
                old_perm.course_permission = perm['course_permission']
            else:
                db.session.add(m.Permission(name=name, **perm))

    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/seed_data/roles.json',
        'r'
    ) as c:
        cs = json.load(c)
        for name, c in cs.items():
            perms = m.Permission.query.filter_by(course_permission=False).all()
            r_perms = {}
            perms_set = set(c['permissions'])
            for perm in perms:
                if (perm.default_value ^ (perm.name in perms_set)):
                    r_perms[perm.name] = perm

            r = m.Role.query.filter_by(name=name).first()
            if r is None:
                db.session.add(m.Role(name=name, _permissions=r_perms))
            else:
                r._permissions = r_perms
    db.session.commit()


@manager.command
def test_data():
    if not app.config['DEBUG']:
        print('You can not add test data in production mode', file=sys.stderr)
        return 1

    seed()
    db.session.commit()
    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/test_data/courses.json',
        'r'
    ) as c:
        cs = json.load(c)
        for c in cs:
            if m.Course.query.filter_by(name=c['name']).first() is None:
                db.session.add(m.Course(name=c['name']))
    db.session.commit()
    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/test_data/assignments.json',
        'r'
    ) as c:
        cs = json.load(c)
        for c in cs:
            assig = m.Assignment.query.filter_by(name=c['name']).first()
            if assig is None:
                db.session.add(
                    m.Assignment(
                        name=c['name'],
                        deadline=datetime.datetime.utcnow() +
                        datetime.timedelta(days=c['deadline']),
                        state=c['state'],
                        description=c['description'],
                        course=m.Course.query.filter_by(name=c['course']
                                                        ).first()
                    )
                )
            else:
                assig.description = c['description']
                assig.state = c['state']
                assig.course = m.Course.query.filter_by(name=c['course']
                                                        ).first()
    db.session.commit()
    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/test_data/users.json',
        'r'
    ) as c:
        cs = json.load(c)
        for c in cs:
            u = m.User.query.filter_by(name=c['name']).first()
            courses = {
                m.Course.query.filter_by(name=name).first(): role
                for name, role in c['courses'].items()
            }
            perms = {
                course.id:
                m.CourseRole.query.filter_by(name=name,
                                             course_id=course.id).first()
                for course, name in courses.items()
            }
            username = c['name'].split(' ')[0].lower()
            if u is not None:
                u.name = c['name']
                u.courses = perms
                u.email = c['name'].replace(' ', '_').lower() + '@example.com'
                u.password = c['name']
                u.username = username
                u.role = m.Role.query.filter_by(name=c['role']).first()
            else:
                u = m.User(
                    name=c['name'],
                    courses=perms,
                    email=c['name'].replace(' ', '_').lower() + '@example.com',
                    password=c['name'],
                    username=username,
                    role=m.Role.query.filter_by(name=c['role']).first()
                )
                db.session.add(u)
                for course, role in courses.items():
                    if role == 'Student':
                        for assig in course.assignments:
                            work = m.Work(assignment=assig, user=u)
                            db.session.add(
                                m.File(
                                    work=work,
                                    name='Top stub dir',
                                    is_directory=True
                                )
                            )
                            db.session.add(work)
    db.session.commit()
    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/test_data/rubrics.json',
        'r'
    ) as c:
        cs = json.load(c)
        for c in cs:
            for row in c['rows']:
                assignment = m.Assignment.query.filter_by(
                    name=c['assignment']
                ).first()
                if assignment is not None:
                    rubric_row = m.RubricRow.query.filter_by(
                        header=row['header'],
                        description=row['description'],
                        assignment_id=assignment.id
                    ).first()
                    if rubric_row is None:
                        rubric_row = m.RubricRow(
                            header=row['header'],
                            description=row['description'],
                            assignment=assignment
                        )
                        db.session.add(rubric_row)
                    for item in row['items']:
                        if not db.session.query(
                            m.RubricItem.query.filter_by(
                                rubricrow_id=rubric_row.id,
                                **item,
                            ).exists()
                        ).scalar():
                            rubric_item = m.RubricItem(
                                description=item['description'] * 5,
                                header=item['header'],
                                points=item['points'],
                                rubricrow=rubric_row
                            )
                            db.session.add(rubric_item)
    db.session.commit()


if __name__ == '__main__':
    manager.run()

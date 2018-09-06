"""
This module is used for all mailing related tasks.

:license: AGPLv3, see LICENSE for details.
"""
import html
import typing as t

import html2text
from flask import current_app
from flask_mail import Mail, Message

import psef
import psef.models as models
from psef.errors import APICodes, APIException

mail = Mail()  # pylint: disable=invalid-name


def _send_mail(
    html_body: str,
    subject: str,
    recipients: t.Sequence[t.Union[str, t.Tuple[str, str]]],
    mailer: t.Optional[Mail] = None,
) -> None:
    if mailer is None:
        mailer = mail

    text_maker = html2text.HTML2Text(bodywidth=78)
    text_maker.inline_links = False
    text_maker.wrap_links = False

    message = Message(
        subject=subject,
        body=text_maker.handle(html_body),
        html=html_body,
        recipients=recipients,
    )
    mailer.send(message)


def send_whopie_done_email(assig: models.Assignment) -> None:
    """Send whoepie done email for the given assignment.

    :param assig: The assignment to send the mail for.
    :returns: Nothing
    """
    html_body = current_app.config['DONE_TEMPLATE'].replace(
        '\n\n',
        '<br><br>',
    ).format(
        site_url=current_app.config['EXTERNAL_URL'],
        assig_id=assig.id,
        assig_name=html.escape(assig.name),
        course_id=assig.course_id,
    )

    recipients = psef.parsers.parse_email_list(assig.done_email)
    if recipients is not None:
        _send_mail(
            html_body,
            (
                f'Grading has finished for {assig.name} on '
                f'{current_app.config["EXTERNAL_URL"]}'
            ),
            recipients,
        )


def send_grader_status_changed_mail(
    assig: models.Assignment, user: models.User
) -> None:
    """Send grader status changed mail.

    :param assig: The assignment of which the status has changed.
    :param user: The user whose status has changed.
    :returns: Nothing
    """
    html_body = current_app.config['GRADER_STATUS_TEMPLATE'].replace(
        '\n\n', '<br><br>'
    ).format(
        site_url=current_app.config['EXTERNAL_URL'],
        assig_id=assig.id,
        user_name=html.escape(user.name),
        user_email=html.escape(user.email),
        assig_name=html.escape(assig.name),
        course_id=assig.course_id,
    )

    _send_mail(
        html_body,
        (
            f'Grade status toggled for {assig.name} on '
            f'{current_app.config["EXTERNAL_URL"]}'
        ),
        [user.email],
    )


def send_grade_reminder_email(
    assig: models.Assignment,
    user: models.User,
    mailer: Mail,
) -> None:
    """Remind a user to grade a given assignment.

    :param assig: The assignment that has to be graded.
    :param user: The user that should resume/start grading.
    :mailer: The mailer used to mail, this is important for performance.
    :returns: Nothing
    """
    html_body = current_app.config['REMINDER_TEMPLATE'].replace(
        '\n\n', '<br><br>'
    ).format(
        site_url=current_app.config['EXTERNAL_URL'],
        assig_id=assig.id,
        user_name=html.escape(user.name),
        user_email=html.escape(user.email),
        assig_name=html.escape(assig.name),
        course_id=assig.course_id,
    )
    _send_mail(
        html_body,
        (
            f'Grade reminder for {assig.name} on '
            f'{current_app.config["EXTERNAL_URL"]}'
        ),
        [user.email],
        mailer,
    )


def send_reset_password_email(user: models.User) -> None:
    """Send the reset password email to a user.

    :param user: The user that has requested a reset password email.
    :returns: Nothing
    """
    token = user.get_reset_token()
    html_body = current_app.config['EMAIL_TEMPLATE'].replace(
        '\n\n', '<br><br>'
    ).format(
        site_url=current_app.config["EXTERNAL_URL"],
        url=(
            f'{current_app.config["EXTERNAL_URL"]}/reset_'
            f'password/?user={user.id}&token={token}'
        ),
        user_id=user.id,
        token=token,
        user_name=html.escape(user.name),
        user_email=html.escape(user.email),
    )
    try:
        _send_mail(
            html_body, f'Reset password on {psef.app.config["EXTERNAL_URL"]}',
            [user.email]
        )
    except Exception:
        raise APIException(
            'Something went wrong sending the email, '
            'please contact your site admin',
            f'Sending email to {user.id} went wrong.',
            APICodes.UNKOWN_ERROR,
            500,
        )


def init_app(app: t.Any) -> None:
    mail.init_app(app)

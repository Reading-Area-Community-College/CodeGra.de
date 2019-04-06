"""""Creating "can_manage_course_snippets" permission.

Revision ID: 3a84e9b5fb45fddeac8b
Revises: 1def5653dbbf75f3c581
Create Date: 2019-04-02 12:06:37.230361

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '3a84e9b5fb45fddeac8b'
down_revision = '1def5653dbbf75f3c581'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""
    INSERT INTO "Permission" (name, default_value, course_permission)
    SELECT 'can_manage_course_snippets', False, True WHERE NOT EXISTS
        (SELECT 1 FROM "Permission" WHERE name = 'can_manage_course_snippets')
    """))


def downgrade():
    pass

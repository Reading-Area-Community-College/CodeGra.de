"""""Creating "can_view_course_snippets" permission.

Revision ID: 1def5653dbbf75f3c581
Revises: d069b5a7b4bd
Create Date: 2019-04-02 12:05:27.742412

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '1def5653dbbf75f3c581'
down_revision = 'd069b5a7b4bd'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""
    INSERT INTO "Permission" (name, default_value, course_permission)
    SELECT 'can_view_course_snippets', False, True WHERE NOT EXISTS
        (SELECT 1 FROM "Permission" WHERE name = 'can_view_course_snippets')
    """))


def downgrade():
    pass

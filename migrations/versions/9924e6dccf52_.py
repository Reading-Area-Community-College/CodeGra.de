"""Add `fixed_max_rubric_points` columns

Revision ID: 9924e6dccf52
Revises: d6ada107a551
Create Date: 2018-03-10 20:56:37.001400

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9924e6dccf52'
down_revision = 'd6ada107a551'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('Assignment', sa.Column('fixed_max_rubric_points', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('Assignment', 'fixed_max_rubric_points')
    # ### end Alembic commands ###

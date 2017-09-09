"""Add ondelete='CASCADE' to Assignment foreign-key on Work class

Revision ID: a5b9c7d6a3c7
Revises: 1b14f6bef6a1
Create Date: 2017-09-08 23:52:05.473471

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5b9c7d6a3c7'
down_revision = '1b14f6bef6a1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('Work_Assignment_id_fkey', 'Work', type_='foreignkey')
    op.create_foreign_key('Work_Assignment_id_fkey', 'Work', 'Assignment', ['Assignment_id'], ['id'], ondelete='CASCADE')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('Work_Assignment_id_fkey', 'Work', type_='foreignkey')
    op.create_foreign_key('Work_Assignment_id_fkey', 'Work', 'Assignment', ['Assignment_id'], ['id'])
    # ### end Alembic commands ###
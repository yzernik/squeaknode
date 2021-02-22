"""Add liked column

Revision ID: f62215acb987
Revises: 0676aadc35c6
Create Date: 2021-02-22 15:18:19.238913

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f62215acb987'
down_revision = '0676aadc35c6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('squeak', schema=None) as batch_op:
        batch_op.add_column(sa.Column('liked', sa.Boolean(), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('squeak', schema=None) as batch_op:
        batch_op.drop_column('liked')

    # ### end Alembic commands ###

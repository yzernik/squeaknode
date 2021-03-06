"""Use timestamp for liked field

Revision ID: c874732c09b6
Revises: f62215acb987
Create Date: 2021-06-04 17:03:56.626831

"""
import sqlalchemy as sa
from alembic import op

import squeaknode.db.models


# revision identifiers, used by Alembic.
revision = 'c874732c09b6'
down_revision = 'f62215acb987'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('squeak', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('liked_time', squeaknode.db.models.TZDateTime(), nullable=True))
        batch_op.drop_column('liked')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('squeak', schema=None) as batch_op:
        batch_op.add_column(sa.Column('liked', sa.BOOLEAN(),
                                      server_default=sa.text('0'), nullable=False))
        batch_op.drop_column('liked_time')

    # ### end Alembic commands ###

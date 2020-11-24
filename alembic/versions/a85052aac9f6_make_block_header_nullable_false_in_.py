"""Make block header nullable=False in squeak table

Revision ID: a85052aac9f6
Revises: e9d5f2365709
Create Date: 2020-11-24 16:42:14.537530

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a85052aac9f6'
down_revision = 'e9d5f2365709'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('squeak', schema=None) as batch_op:
        batch_op.alter_column('block_header',
               existing_type=sa.BLOB(),
               nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('squeak', schema=None) as batch_op:
        batch_op.alter_column('block_header',
               existing_type=sa.BLOB(),
               nullable=True)

    # ### end Alembic commands ###

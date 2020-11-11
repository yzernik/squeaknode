"""Add received_payment table

Revision ID: 387dd872e766
Revises: ccc641c2ce52
Create Date: 2020-11-11 01:24:10.148710

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '387dd872e766'
down_revision = 'ccc641c2ce52'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('received_payment',
    sa.Column('received_payment_id', sa.Integer(), nullable=False),
    sa.Column('created', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('squeak_hash', sa.String(length=64), nullable=False),
    sa.Column('preimage_hash', sa.String(length=64), nullable=False),
    sa.Column('price_msat', sa.Integer(), nullable=False),
    sa.Column('is_paid', sa.Boolean(), nullable=False),
    sa.Column('payment_time', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('received_payment_id'),
    sa.UniqueConstraint('preimage_hash')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('received_payment')
    # ### end Alembic commands ###
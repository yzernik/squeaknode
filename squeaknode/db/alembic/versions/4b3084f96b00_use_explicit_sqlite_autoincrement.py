"""Use explicit sqlite autoincrement

Revision ID: 4b3084f96b00
Revises: 6851569c46e3
Create Date: 2021-02-03 02:27:10.910820

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '4b3084f96b00'
down_revision = '6851569c46e3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    def alter_table_with_sqlite_autoincrement(table_name):
        with op.batch_alter_table(
                table_name,
                recreate="always",
                table_kwargs={'sqlite_autoincrement': True},
                schema=None,
        ):
            pass

    for table in [
            'profile',
            'peer',
            'received_offer',
            'sent_payment',
            'sent_offer',
            'received_payment',
    ]:
        alter_table_with_sqlite_autoincrement(table)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    def alter_table_without_sqlite_autoincrement(table_name):
        with op.batch_alter_table(
                table_name,
                recreate="always",
                table_kwargs={'sqlite_autoincrement': True},
                schema=None,
        ):
            pass

    for table in [
            'profile',
            'peer',
            'received_offer',
            'sent_payment',
            'sent_offer',
            'received_payment',
    ]:
        alter_table_without_sqlite_autoincrement(table)
    # ### end Alembic commands ###
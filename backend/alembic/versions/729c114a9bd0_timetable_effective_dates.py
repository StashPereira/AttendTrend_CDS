"""Prevent edited timetable definitions from generating new historical classes."""
from alembic import op
import sqlalchemy as sa

revision = '729c114a9bd0'
down_revision = '43c829834e8a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('timetable', sa.Column('effective_from', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('timetable', 'effective_from')

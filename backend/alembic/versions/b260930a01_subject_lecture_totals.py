"""Optional total lecture count per subject and semester."""
from alembic import op
import sqlalchemy as sa
revision = 'b260930a01'
down_revision = '729c114a9bd0'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('subjects') as batch:
        batch.add_column(sa.Column('planned_lectures', sa.Integer(), nullable=True))
        batch.create_check_constraint('ck_subject_planned_lectures', 'planned_lectures IS NULL OR planned_lectures >= 0')

def downgrade():
    with op.batch_alter_table('subjects') as batch:
        batch.drop_constraint('ck_subject_planned_lectures', type_='check')
        batch.drop_column('planned_lectures')

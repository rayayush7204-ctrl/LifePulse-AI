"""Update notifications match_id

Revision ID: 3df68654e952
Revises: 4cba4d66e283
Create Date: 2026-09-04 02:09:38.102343

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3df68654e952'
down_revision: Union[str, Sequence[str], None] = '4cba4d66e283'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Explicit name for the new FK constraint we create, so downgrade can reliably drop it.
NEW_FK_NAME = 'fk_notifications_match_id_donor_matches_match_id'


def _find_match_id_fk_name() -> str | None:
    """Inspect the live database to find the current FK constraint name on notifications.match_id."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys('notifications'):
        if fk['constrained_columns'] == ['match_id']:
            return fk['name']
    return None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Widen the column from VARCHAR(64) to VARCHAR(128)
    op.alter_column('notifications', 'match_id',
               existing_type=sa.VARCHAR(length=64),
               type_=sa.String(length=128),
               existing_nullable=True)

    # 2. Dynamically discover and drop the old FK (points to donor_matches.id)
    old_fk_name = _find_match_id_fk_name()
    if old_fk_name:
        op.drop_constraint(old_fk_name, 'notifications', type_='foreignkey')

    # 3. Create the correct FK: notifications.match_id -> donor_matches.match_id
    op.create_foreign_key(
        NEW_FK_NAME,
        'notifications', 'donor_matches',
        ['match_id'], ['match_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop the named FK we created in upgrade()
    op.drop_constraint(NEW_FK_NAME, 'notifications', type_='foreignkey')

    # 2. Restore the original FK: notifications.match_id -> donor_matches.id
    op.create_foreign_key(
        'fk_notifications_match_id_donor_matches_id',
        'notifications', 'donor_matches',
        ['match_id'], ['id']
    )

    # 3. Shrink the column back to VARCHAR(64)
    op.alter_column('notifications', 'match_id',
               existing_type=sa.String(length=128),
               type_=sa.VARCHAR(length=64),
               existing_nullable=True)

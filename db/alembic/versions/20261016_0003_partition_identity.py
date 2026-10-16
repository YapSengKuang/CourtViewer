"""Bookable group identity and durable collection outcomes."""
from alembic import op
import sqlalchemy as sa

revision = "0003_partition_identity"
down_revision = "0002_public_search"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tee_times', sa.Column('source_partition', sa.String(200), nullable=False, server_default='window'))
    op.add_column('tee_times', sa.Column('source_slot_key', sa.String(200), nullable=False, server_default=''))
    op.drop_constraint('uq_tee_times_course_start_holes', 'tee_times', type_='unique')
    op.create_unique_constraint('uq_tee_times_bookable_group', 'tee_times',
        ['course_id', 'starts_at', 'holes', 'source_partition', 'source_slot_key'])
    # Old MiClub cache may contain summed tee groups. Preserve it for inspection,
    # but expire it so it cannot satisfy a public party-size search.
    op.execute("""UPDATE public.tee_times SET scraped_at = LEAST(scraped_at, CURRENT_TIMESTAMP - interval '61 minutes')
        WHERE course_id IN (SELECT id FROM public.courses WHERE platform = 'miclub')""")
    op.create_table('scrape_executions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('spider', sa.String(100), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(20), nullable=False),
    )
    op.create_table('scrape_partitions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('execution_id', sa.String(36), sa.ForeignKey('scrape_executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key', sa.String(200), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('accepted_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rejected_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text()),
        sa.UniqueConstraint('execution_id', 'course_id', 'key', name='uq_execution_partition'),
    )
    op.create_index('ix_partition_course_key', 'scrape_partitions', ['course_id', 'key'])
    for table in ('scrape_executions', 'scrape_partitions'):
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON public.{table} FROM PUBLIC')
        op.execute(f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON public.{table} FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL ON public.{table} FROM authenticated;
            END IF;
        END $$""")
    # Preserve the existing signature/grants while extending the JSON contract.
    bind = op.get_bind()
    definition = bind.execute(sa.text("SELECT pg_get_functiondef('public.golf_search(date,time,time,integer,integer,integer,integer)'::regprocedure)")).scalar_one()
    if 't.id AS slot_id,' not in definition:
        raise RuntimeError('Unexpected golf_search definition; refusing incomplete identity migration')
    op.execute(definition.replace('t.id AS slot_id,', 't.id AS slot_id, t.source_partition, t.source_slot_key,'))


def downgrade():
    # Refuse to collapse two independent groups into an ambiguous legacy row.
    duplicate = op.get_bind().execute(sa.text('''SELECT 1 FROM tee_times GROUP BY course_id, starts_at, holes HAVING count(*) > 1 LIMIT 1''')).first()
    if duplicate:
        raise RuntimeError('Cannot downgrade while multiple bookable groups share a tee time; archive/rebuild derived cache first')
    definition = op.get_bind().execute(sa.text("SELECT pg_get_functiondef('public.golf_search(date,time,time,integer,integer,integer,integer)'::regprocedure)")).scalar_one()
    op.execute(definition.replace('t.id AS slot_id, t.source_partition, t.source_slot_key,', 't.id AS slot_id,'))
    op.drop_table('scrape_partitions')
    op.drop_table('scrape_executions')
    op.drop_constraint('uq_tee_times_bookable_group', 'tee_times', type_='unique')
    op.create_unique_constraint('uq_tee_times_course_start_holes', 'tee_times', ['course_id', 'starts_at', 'holes'])
    op.drop_column('tee_times', 'source_slot_key')
    op.drop_column('tee_times', 'source_partition')

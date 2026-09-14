from alembic import context

from backend.db import Base, make_engine

target_metadata = Base.metadata

if context.is_offline_mode():
    engine = make_engine()
    context.configure(url=engine.url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with make_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

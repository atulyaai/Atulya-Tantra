"""
Database migration utilities for Atulya Tantra AGI
"""

import os
from pathlib import Path
from typing import Optional

from ..config.settings import settings, DatabaseType


def setup_alembic() -> None:
    """Setup Alembic for database migrations"""
    
    # Create alembic directory structure
    alembic_dir = Path("alembic")
    alembic_dir.mkdir(exist_ok=True)
    
    versions_dir = alembic_dir / "versions"
    versions_dir.mkdir(exist_ok=True)
    
    # Create alembic.ini if it doesn't exist
    alembic_ini = Path("alembic.ini")
    if not alembic_ini.exists():
        alembic_ini.write_text("""# A generic, single database configuration.

[alembic]
# path to migration scripts
script_location = alembic

# template used to generate migration file names; The default value is %%(rev)s_%%(slug)s
# Uncomment the line below if you want the files to be prepended with date and time
# file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s

# sys.path path, will be prepended to sys.path if present.
# defaults to the current working directory.
prepend_sys_path = .

# timezone to use when rendering the date within the migration file
# as well as the filename.
# If specified, requires the python-dateutil library that can be
# installed by adding `alembic[tz]` to the pip requirements
# string value is passed to dateutil.tz.gettz()
# leave blank for localtime
# timezone =

# max length of characters to apply to the
# "slug" field
# truncate_slug_length = 40

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
# revision_environment = false

# set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
# sourceless = false

# version number format
version_num_format = %04d

# version path separator; As mentioned above, this is the character used to split
# version_locations. The default within new alembic.ini files is "os", which uses
# os.pathsep. If this key is omitted entirely, it falls back to the legacy
# behavior of splitting on spaces and/or commas.
# Valid values for version_path_separator are:
#
# version_path_separator = :
# version_path_separator = ;
# version_path_separator = space
version_path_separator = os

# set to 'true' to search source files recursively
# in each "version_locations" directory
# new in Alembic version 1.10
# recursive_version_locations = false

# the output encoding used when revision files
# are written from script.py.mako
# output_encoding = utf-8

sqlalchemy.url = %(DATABASE_URL)s

[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.  See the documentation for further
# detail and examples

# format using "black" - use the console_scripts runner, against the "black" entrypoint
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
""")
    
    # Create env.py for Alembic
    env_py = alembic_dir / "env.py"
    if not env_py.exists():
        env_py.write_text('''"""Alembic environment configuration for Atulya Tantra AGI"""

import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.database import get_database_url
from Core.models import Base  # Import your models here

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get database URL from configuration"""
    return get_database_url()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
''')
    
    # Create script.py.mako template
    script_py_mako = alembic_dir / "script.py.mako"
    if not script_py_mako.exists():
        script_py_mako.write_text('''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
''')


def create_initial_migration() -> None:
    """Create initial migration for all tables"""
    import subprocess
    
    try:
        # Set database URL in environment
        os.environ['DATABASE_URL'] = get_database_url()
        
        # Run alembic revision command
        result = subprocess.run([
            'alembic', 'revision', '--autogenerate', '-m', 'Initial migration'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Initial migration created successfully")
        else:
            print(f"❌ Failed to create migration: {result.stderr}")
            
    except FileNotFoundError:
        print("❌ Alembic not found. Install with: pip install alembic")
    except Exception as e:
        print(f"❌ Error creating migration: {e}")


def run_migrations() -> None:
    """Run pending migrations"""
    import subprocess
    
    try:
        # Set database URL in environment
        os.environ['DATABASE_URL'] = get_database_url()
        
        # Run alembic upgrade command
        result = subprocess.run([
            'alembic', 'upgrade', 'head'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Migrations applied successfully")
        else:
            print(f"❌ Failed to apply migrations: {result.stderr}")
            
    except FileNotFoundError:
        print("❌ Alembic not found. Install with: pip install alembic")
    except Exception as e:
        print(f"❌ Error running migrations: {e}")


def get_database_url() -> str:
    """Get database URL for migrations"""
    if settings.database_type == DatabaseType.SQLITE:
        return f"sqlite:///{settings.sqlite_path}"
    elif settings.database_type == DatabaseType.POSTGRESQL:
        return settings.database_url or "postgresql://user:password@localhost/tantra"
    else:
        # For JSON database, use SQLite for migrations
        return f"sqlite:///data/tantra_migration.db"


# Export functions
__all__ = [
    "setup_alembic",
    "create_initial_migration", 
    "run_migrations",
    "get_database_url"
]

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.utils.base_model import Base

import importlib
import pkgutil
import app.modules as modules_package
from dotenv import load_dotenv
import os

load_dotenv("../.env")

def import_all_models():
    """
    Recursively imports all models from every module's 'models/' subfolder.
    This ensures Alembic detects all tables defined across your modular monolith.
    """
    # Loop through each module in app/modules/ (e.g., users, orders, products)
    for module_info in pkgutil.iter_modules(modules_package.__path__, modules_package.__name__ + "."):
        # module_info.name will be like "app.modules.users"
        try:
            # Try to import the 'models' sub-package inside this module
            # e.g., app.modules.users.models
            models_package = importlib.import_module(f"{module_info.name}.models")

            # Now loop through EVERY file inside that models/ folder
            # e.g., app.modules.users.models.user, app.modules.users.models.otp
            for model_file in pkgutil.iter_modules(models_package.__path__, models_package.__name__ + "."):
                # Import the actual model file (e.g., app.modules.users.models.user)
                importlib.import_module(model_file.name)
                print(f"✅ Loaded model: {model_file.name}")

        except (ModuleNotFoundError, ImportError):
            # It's fine if a module doesn't have a 'models' folder
            # e.g., if you have a 'shared' module without models
            pass

import_all_models()
target_metadata = Base.metadata


def get_database_url() -> str:
    user = os.getenv("POSTGRES_USER", "fastapi_user")
    password = os.getenv("POSTGRES_PASSWORD", "secret_password")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "fastapi_db")

    return (
        f"postgresql+psycopg://{user}:{password}"
        f"@{host}:{port}/{db}"
    )

def get_url() -> str:
    url = os.getenv("DATABASE_URL")

    if not url:
        url = get_database_url()

    if not url:
        url = config.get_main_option("sqlalchemy.url")

    if not url:
        raise RuntimeError("No database configuration found.")

    return url

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
    url = get_url()
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

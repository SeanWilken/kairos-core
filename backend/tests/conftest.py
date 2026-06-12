import os
from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


os.environ.setdefault("MYAI_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ["INSTALL_TENANT_ID"] = ""


@pytest.fixture(autouse=True)
def reset_db() -> None:
    from app.core.db import Base, engine, init_db
    from app.core.config import get_settings

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    init_db()

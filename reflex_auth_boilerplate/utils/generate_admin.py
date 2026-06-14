#!/usr/bin/env python3
"""Create or reset the admin account (email="admin", access_lvl=1).

Run from the project root:
    uv run reflex_auth_boilerplate/utils/generate_admin.py
"""

import sys
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import bcrypt
from sqlmodel import Session, create_engine, select
from reflex_auth_boilerplate.models.models import UserModel, SQLModel

ADMIN_EMAIL = "admin@h.de"
ADMIN_ACCESS_LVL = 1
# Must match db_url in rxconfig.py; relative path resolves from cwd (project root)
DB_URL = "sqlite:///reflex_auth_boilerplate.db"


def main() -> None:
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    engine = create_engine(DB_URL)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        admin = session.exec(
            select(UserModel).where(UserModel.email == ADMIN_EMAIL)
        ).first()

        if admin:
            admin.pw_hash = pw_hash
            session.add(admin)
            session.commit()
            print("Admin password updated.")
        else:
            admin = UserModel(
                email=ADMIN_EMAIL,
                pw_hash=pw_hash,
                access_lvl=ADMIN_ACCESS_LVL,
            )
            session.add(admin)
            session.commit()
            print(f"Admin account '{ADMIN_EMAIL}' created.")


if __name__ == "__main__":
    main()

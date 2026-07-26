"""Create master admin account — run once on the server."""

from app.database.models.user import User
from app.database.session import SessionLocal
from app.services.auth import hash_password


def main():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "nokturnog@gmail.com").first()
        if existing:
            existing.is_admin = True
            existing.subscription = "premium"
            existing.is_active = True
            db.commit()
            print(f"Master account updated: {existing.email} (admin={existing.is_admin}, sub={existing.subscription})")
            return

        user = User(
            email="nokturnog@gmail.com",
            username="nok1111",
            hashed_password=hash_password("panicopain1"),
            is_active=True,
            is_admin=True,
            subscription="premium",
        )
        db.add(user)
        db.commit()
        print(f"Master account created: {user.email} (id={user.id}, admin={user.is_admin}, sub={user.subscription})")
    finally:
        db.close()


if __name__ == "__main__":
    main()

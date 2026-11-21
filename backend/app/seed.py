import os

import bcrypt
from dotenv import dotenv_values
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.dependencies import engine
from app.models import District, Role, TrainingCentre, User


def seed() -> None:
    env = {**dotenv_values(Settings.model_config["env_file"]), **os.environ}
    password = (env.get("DEMO_PASSWORD") or "").encode()
    if (
        env.get("ENABLE_DEMO_SEED") != "true"
        or settings().node_env == "production"
        or not 12 <= len(password) <= 72
    ):
        raise SystemExit(
            "Enable demo seeding with a 12–72 byte DEMO_PASSWORD in development."
        )
    password_hash = bcrypt.hashpw(password, bcrypt.gensalt(rounds=12)).decode()
    with Session(engine()) as db:
        district = db.get(District, "demo-district")
        if district is None:
            district = District(id="demo-district", name="Demo District")
            db.add(district)
        centre = db.get(TrainingCentre, "demo-centre")
        if centre is None:
            centre = TrainingCentre(
                id="demo-centre", name="Demo Training Centre", district=district
            )
            db.add(centre)
        for name, role in (
            ("Anika", Role.TRAINING_CENTRE),
            ("Dev", Role.DISTRICT_OFFICER),
            ("Meera", Role.DISTRICT_OFFICER),
            ("Kabir", Role.DISTRICT_OFFICER),
            ("Neha", Role.QUALITY_TEAM),
            ("Farah", Role.STATE_OFFICE),
        ):
            email = f"{name.lower()}@certiflow.example"
            if db.scalar(select(User.id).where(User.email == email)) is None:
                db.add(
                    User(
                        name=name,
                        email=email,
                        role=role,
                        password_hash=password_hash,
                        centre=centre if role == Role.TRAINING_CENTRE else None,
                        district=district if role == Role.DISTRICT_OFFICER else None,
                    )
                )
        db.commit()
    print("Demo accounts available. Existing account credentials were preserved.")


if __name__ == "__main__":
    seed()

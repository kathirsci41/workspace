from __future__ import annotations

import json

from app.database import SessionLocal, init_db
from app.services.demo_seed_service import seed_panimalar_demo


def main() -> None:
    init_db()
    with SessionLocal() as db:
        result = seed_panimalar_demo(db)
        db.commit()
        print(json.dumps({"bundle_id": result["bundle"].id, "verification_summary": result["verification_summary"]}, indent=2))


if __name__ == "__main__":
    main()

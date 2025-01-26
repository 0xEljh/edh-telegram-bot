from hashids import Hashids
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import dotenv
import os

dotenv.load_dotenv()

# Use the same salt as in your application
hashids = Hashids(salt=os.getenv("DATABASE_SALT"), min_length=6)

engine = create_engine("sqlite:///data/games.db")
Session = sessionmaker(bind=engine)
session = Session()

# Get all existing games without deletion references
games = session.execute(
    text("SELECT game_id FROM games WHERE deletion_reference IS NULL")
).fetchall()

for (game_id,) in games:
    deletion_ref = hashids.encode(game_id)
    session.execute(
        text("UPDATE games SET deletion_reference = :ref WHERE game_id = :id"),
        {"ref": deletion_ref, "id": game_id},
    )

session.commit()
session.close()

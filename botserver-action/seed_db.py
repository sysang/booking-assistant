from .hotel_data.fort_luaderdale import fort_luaderdale
from .hotel_data.hawaii import hawaii
from .dbconnector import db

def seed_db():
  print('seeding...')
  db.insert_multiple(fort_luaderdale)
  db.insert_multiple(hawaii)
  print('done.')

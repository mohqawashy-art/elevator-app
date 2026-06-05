from app import app, db
app.app_context().push()
db.drop_all()
db.create_all()
print('Done')

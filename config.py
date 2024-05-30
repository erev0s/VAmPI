import os
import connexion
from flask import jsonify
from flask_sqlalchemy import SQLAlchemy

vuln_app = connexion.App(__name__, specification_dir='./openapi_specs')

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(vuln_app.app.root_path, 'database/database.db')
vuln_app.app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
vuln_app.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

vuln_app.app.config['SECRET_KEY'] = 'random'
# start the db
db = SQLAlchemy(vuln_app.app)


@vuln_app.app.errorhandler(401)
def custom_401(error):
    # Custom 401 to match the original response sent by Vampi
    response = jsonify({"status": "fail", "message": "Invalid token. Please log in again."})
    response.status_code = 401
    return response


vuln_app.add_api('openapi3.yml')

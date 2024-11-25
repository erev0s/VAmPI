import os
import connexion
from flask import jsonify
from flask_sqlalchemy import SQLAlchemy
from connexion.exceptions import ProblemException

vuln_app = connexion.App(__name__, specification_dir='./openapi_specs')

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(vuln_app.app.root_path, 'database/database.db')
vuln_app.app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
vuln_app.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

vuln_app.app.config['SECRET_KEY'] = 'random'
# start the db
db = SQLAlchemy(vuln_app.app)

def custom_problem_handler(error):
    # Custom error handler for clarity in structure
    response = jsonify({
        "status": "fail",
        "message": getattr(error, "detail", "An error occurred"),
    })
    response.status_code = error.status
    return response
vuln_app.add_error_handler(ProblemException, custom_problem_handler)

vuln_app.add_api('openapi3.yml')

import os
import connexion
from flask_sqlalchemy import SQLAlchemy


def remove_server_header(app):
    @app.after_request
    def apply_custom_headers(response):
        response.headers.pop("Server", None)
        return response



vuln_app = connexion.App(__name__, specification_dir='./openapi_specs')

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(vuln_app.root_path, 'database/database.db')
vuln_app.app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
vuln_app.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

vuln_app.app.config['SECRET_KEY'] = 'random'
# start the db
db = SQLAlchemy(vuln_app.app)

vuln_app.add_api('openapi3.yml')
vuln_app.wsgi_app = remove_server_header(vuln_app.app)

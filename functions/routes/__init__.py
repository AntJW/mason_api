from flask import Flask

from . import companies, conversations, customers, documents, health, internal, templates, users


def register_routes(app: Flask) -> None:
    app.register_blueprint(health.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(customers.bp)
    app.register_blueprint(conversations.bp)
    app.register_blueprint(internal.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(templates.bp)
    app.register_blueprint(companies.bp)

import logging
from logging.handlers import RotatingFileHandler
import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config

# --- Extension Instances ---
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
mail = Mail()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_class=Config):
    """Application Factory Function"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- Initialize Extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    # --- Import and Register Blueprints ---
    from .routes.auth import auth_bp
    from .routes.admin import admin_bp
    from .routes.customer import customer_bp
    from .routes.professional import professional_bp
    from .routes.shared import shared_bp
    from .routes.api import api_bp
    from .routes.ai_routes import ai_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(customer_bp, url_prefix='/customer')
    app.register_blueprint(professional_bp, url_prefix='/professional')
    app.register_blueprint(shared_bp, url_prefix='/shared')
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(ai_bp, url_prefix='/ai')

    # --- Logging Setup ---
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/azhousehold.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('A-Z Household Services startup')

    # --- Context Processing ---
    @app.shell_context_processor
    def make_shell_context():
        from app import models
        return {
            'db': db,
            'Users': models.Users,
            'Customers': models.Customers,
            'ServiceProfessionals': models.ServiceProfessionals,
            'Services': models.Services,
            'ServiceRequests': models.ServiceRequests,
            'Reviews': models.Reviews
        }

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html',
                               error_code=404,
                               error_name="Page Not Found",
                               error_description="Sorry, the page you are looking for does not exist."), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('error.html',
                               error_code=403,
                               error_name="Forbidden",
                               error_description="Sorry, you do not have permission to access this page."), 403

    @app.errorhandler(429)
    def ratelimit_error(error):
        return render_template('error.html',
                               error_code=429,
                               error_name="Too Many Requests",
                               error_description="You have made too many requests. Please slow down and try again later."), 429

    return app


from app import models

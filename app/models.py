import enum
import secrets
from datetime import datetime, timezone
from flask_login import UserMixin
from sqlalchemy import MetaData
from werkzeug.security import generate_password_hash, check_password_hash

# Import 'db' and 'login_manager' from your app package
from app import db, login_manager

# Recommended: Naming convention for constraints to avoid migration issues
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
metadata = MetaData(naming_convention=convention)

# ----------------------------
# Login Loader
# ----------------------------
@login_manager.user_loader
def load_user(user_id: int):
    """Flask-Login hook to load user from session."""
    return Users.query.get(int(user_id))

# ----------------------------
# Base Model (Timestamps)
# ----------------------------
class BaseModel(db.Model):
    """Abstract base model that adds created_at and updated_at timestamps."""
    __abstract__ = True
    
    # Use timezone-aware UTC for industry standard (optional but recommended)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

# ----------------------------
# Enums
# ----------------------------
class ServiceStatus(enum.Enum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CLOSED = "closed"
    PAID = "paid"

# ----------------------------
# Users Model
# ----------------------------
class Users(UserMixin, BaseModel):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, index=True, nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False) 
    role = db.Column(db.String(50), index=True, nullable=False)  # 'admin', 'customer', 'professional'
    
    address = db.Column(db.String(200), nullable=True, index=True) # Index useful for location search
    pin = db.Column(db.String(20), nullable=True, index=True)      # Index useful for location search
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    api_key = db.Column(db.String(64), unique=True, nullable=True, index=True)

    # Relationships
    customer = db.relationship("Customers", back_populates="user", uselist=False, cascade="all, delete-orphan")
    professional = db.relationship("ServiceProfessionals", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def generate_api_key(self):
        self.api_key = secrets.token_hex(32)
        return self.api_key

# ----------------------------
# Customers Model
# ----------------------------
class Customers(BaseModel):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    admin_blocked = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    user = db.relationship("Users", back_populates="customer")
    # If customer is deleted, their requests/reviews should be deleted (or anonymized in a real app)
    service_requests = db.relationship("ServiceRequests", back_populates="customer", cascade="all, delete-orphan")
    reviews = db.relationship("Reviews", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer {self.id}>"

# ----------------------------
# Services Model
# ----------------------------
class Services(BaseModel):
    __tablename__ = 'services'

    id = db.Column(db.Integer, primary_key=True)
    service_type = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    base_price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)

    # Relationships
    # Prevent deletion of Service if Professionals exist (Passive Deletes)
    professionals = db.relationship("ServiceProfessionals", back_populates="service") 
    
    # If a service is deleted, you might NOT want to delete historical requests. 
    # But for simplicity in this project, we can cascade or set to null. 
    # Usually, we just don't allow deleting services that have history.
    service_requests = db.relationship("ServiceRequests", back_populates="service")
    reviews = db.relationship("Reviews", back_populates="service")

    def __repr__(self):
        return f"<Service '{self.service_type}'>"

# ----------------------------
# Service Professionals Model
# ----------------------------
class ServiceProfessionals(BaseModel):
    __tablename__ = 'service_professionals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False, index=True)
    
    description = db.Column(db.Text, nullable=True)
    experience = db.Column(db.Integer, default=0, nullable=True)
    document = db.Column(db.String(255), nullable=True)
    
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True) # Indexed for quick filtering
    verification_failed = db.Column(db.Boolean, default=False, nullable=False)
    admin_blocked = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    user = db.relationship("Users", back_populates="professional")
    service = db.relationship("Services", back_populates="professionals")
    service_requests = db.relationship("ServiceRequests", back_populates="professional", cascade="all, delete-orphan")
    reviews = db.relationship("Reviews", back_populates="professional", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Professional {self.id} (Verified: {self.is_verified})>"

# ----------------------------
# Service Requests Model
# ----------------------------
class ServiceRequests(BaseModel):
    __tablename__ = 'service_requests'

    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    professional_id = db.Column(db.Integer, db.ForeignKey("service_professionals.id"), nullable=True, index=True)

    proposed_price = db.Column(db.Float, nullable=True) # Nullable until accepted/set
    date_of_request = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    date_of_completion = db.Column(db.DateTime, nullable=True)
    service_status = db.Column(db.Enum(ServiceStatus), default=ServiceStatus.REQUESTED, nullable=False, index=True)
    remarks = db.Column(db.Text, nullable=True)

    # Relationships
    service = db.relationship("Services", back_populates="service_requests")
    customer = db.relationship("Customers", back_populates="service_requests")
    professional = db.relationship("ServiceProfessionals", back_populates="service_requests")
    
    # One-to-One relationship with Review
    review = db.relationship("Reviews", back_populates="service_request", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Request #{self.id} Status: {self.service_status.name}>"

# ----------------------------
# Reviews Model
# ----------------------------
class Reviews(BaseModel):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign Keys with Indexes
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    professional_id = db.Column(db.Integer, db.ForeignKey("service_professionals.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False, index=True)
    service_request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"), unique=True, nullable=False)

    rating = db.Column(db.Integer, db.CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'), nullable=False)
    remarks = db.Column(db.Text, nullable=True)

    # Relationships
    customer = db.relationship("Customers", back_populates="reviews")
    professional = db.relationship("ServiceProfessionals", back_populates="reviews")
    service = db.relationship("Services", back_populates="reviews")
    service_request = db.relationship("ServiceRequests", back_populates="review")

    def __repr__(self):
        return f"<Review #{self.id} Rating: {self.rating}>"
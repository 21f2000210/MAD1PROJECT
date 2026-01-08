from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
from app.models import Users, Customers, ServiceProfessionals, Services, ServiceRequests, Reviews, ServiceStatus
from app.forms import CreateServiceForm, UpdateServiceForm
from sqlalchemy.exc import SQLAlchemyError

admin_bp = Blueprint('admin', __name__)

# --- Admin Role Protection Decorator ---
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            # Abort with a 403 Forbidden error if the user is not an admin
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@admin_bp.route("/dashboard")
@admin_required
def admin_dashboard():
    """Main dashboard to view all data."""
    services = Services.query.order_by(Services.id.desc()).all()
# Fetch Professionals (Eager load User and Service data)
    professionals = ServiceProfessionals.query\
        .options(joinedload(ServiceProfessionals.user), joinedload(ServiceProfessionals.service))\
        .join(Users).filter(Users.role == 'professional')\
        .order_by(Users.id.desc()).all()    
#  Fetch Customers (Eager load User data)
    customers = Customers.query\
        .options(joinedload(Customers.user))\
        .join(Users).filter(Users.role == 'customer')\
        .order_by(Users.id.desc()).all()
    active_statuses = [
        ServiceStatus.REQUESTED, ServiceStatus.ACCEPTED, 
        ServiceStatus.CLOSED, ServiceStatus.PAID
    ]
    all_requests = ServiceRequests.query\
        .options(
            joinedload(ServiceRequests.customer).joinedload(Customers.user),
            joinedload(ServiceRequests.professional).joinedload(ServiceProfessionals.user),
            joinedload(ServiceRequests.service)
        )\
        .filter(ServiceRequests.service_status.in_(active_statuses))\
        .order_by(ServiceRequests.date_of_request.desc()).all()
    rejected_requests = ServiceRequests.query\
        .options(
            joinedload(ServiceRequests.customer).joinedload(Customers.user),
            joinedload(ServiceRequests.professional).joinedload(ServiceProfessionals.user),
            joinedload(ServiceRequests.service)
        )\
        .filter_by(service_status=ServiceStatus.REJECTED)\
        .order_by(ServiceRequests.date_of_request.desc()).all()
    form = CreateServiceForm()
    return render_template(
            "admin/admin_dashboard.html",
            form=form,
            services=services,
            professionals=professionals,
            customers=customers,
            all_requests=all_requests,
            rejected_requests=rejected_requests
        )

# --- Service Management ---

@admin_bp.route("/services/create", methods=["POST"])
@admin_required
def create_service():
    """Creates a new service type from the modal form."""
    form = CreateServiceForm()
    
    if form.validate_on_submit():
        try:
            new_service = Services(
                service_type=form.service_type.data,
                base_price=form.base_price.data,
                description=form.description.data
            )
            db.session.add(new_service)
            db.session.commit()
            flash(f"Service '{new_service.service_type}' created successfully.", "success")
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Database Error in create_service: {e}")
            flash("An error occurred while creating the service.", "danger")
    else:
        # Flash only the first error found to avoid UI clutter
        first_error = next(iter(form.errors.values()))[0]
        flash(f"Error: {first_error}", 'danger')

    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/services/<int:service_id>/update", methods=["POST"])
@admin_required
def update_service(service_id):
    """Updates an existing service's details."""
    service = Services.query.get_or_404(service_id)
    # Pass original data to form to handle unique validation logic if exists
    form = UpdateServiceForm(original_service_type=service.service_type)

    if form.validate_on_submit():
        try:
            service.service_type = form.service_type.data
            service.base_price = form.base_price.data
            service.description = form.description.data
            db.session.commit()
            flash(f"Service '{service.service_type}' updated successfully.", "success")
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Database Error in update_service: {e}")
            flash("Could not update service due to a database error.", "danger")
    else:
        first_error = next(iter(form.errors.values()))[0]
        flash(f"Update failed: {first_error}", 'danger')
    
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/services/<int:service_id>/delete", methods=["POST"])
@admin_required
def delete_service(service_id):
    """Deletes a service."""
    service = Services.query.get_or_404(service_id)
    
    # Optimization: Check count via DB query instead of loading all professionals into memory
    assigned_count = ServiceProfessionals.query.filter_by(service_id=service_id).count()
    
    if assigned_count > 0:
        flash(f"Cannot delete '{service.service_type}'. It has {assigned_count} professionals assigned.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    try:
        db.session.delete(service)
        db.session.commit()
        flash(f"Service '{service.service_type}' has been deleted.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database Error in delete_service: {e}")
        flash("Could not delete service.", "danger")

    return redirect(url_for("admin.admin_dashboard"))


# --- Professional Management ---

@admin_bp.route('/professionals/<int:professional_id>/approve', methods=['POST'])
@admin_required
def approve_professional(professional_id):
    prof = ServiceProfessionals.query.get_or_404(professional_id)
    try:
        prof.is_verified = True
        prof.verification_failed = False
        db.session.commit()
        flash(f'Professional {prof.user.username} has been approved.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash("Error approving professional.", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/professionals/<int:professional_id>/reject', methods=['POST'])
@admin_required
def reject_professional(professional_id):
    prof = ServiceProfessionals.query.get_or_404(professional_id)
    try:
        prof.is_verified = False
        prof.verification_failed = True
        db.session.commit()
        flash(f'Professional {prof.user.username} has been rejected.', 'warning')
    except SQLAlchemyError:
        db.session.rollback()
        flash("Error rejecting professional.", "danger")

    return redirect(url_for('admin.admin_dashboard'))

# --- User Management (Block/Unblock) ---

@admin_bp.route('/users/<int:user_id>/toggle_block', methods=['POST'])
@admin_required
def toggle_user_block(user_id):
    """
    Refactored: Combined block/unblock into a single logical route 
    to reduce code duplication, though you can keep separate routes if preferred.
    """
    user = Users.query.get_or_404(user_id)
    action = request.args.get('action') # 'block' or 'unblock'
    
    try:
        target_profile = None
        if user.role == 'customer':
            target_profile = user.customer
        elif user.role == 'professional':
            target_profile = user.professional
        
        if target_profile:
            is_blocking = (action == 'block')
            target_profile.admin_blocked = is_blocking
            db.session.commit()
            status_msg = "blocked" if is_blocking else "unblocked"
            flash(f'User {user.username} has been {status_msg}.', 'success' if not is_blocking else 'warning')
        else:
            flash("User profile not found.", "danger")
            
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Database error during status change.", "danger")

    return redirect(url_for('admin.admin_dashboard'))
@admin_bp.route('/users/<int:user_id>/block', methods=['POST'])
@admin_required
def block_user(user_id):
    return _toggle_block_status(user_id, block=True)

@admin_bp.route('/users/<int:user_id>/unblock', methods=['POST'])
@admin_required
def unblock_user(user_id):
    return _toggle_block_status(user_id, block=False)

def _toggle_block_status(user_id, block):
    """Helper function to avoid code repetition"""
    user = Users.query.get_or_404(user_id)
    try:
        if user.role == 'customer':
            user.customer.admin_blocked = block
        elif user.role == 'professional':
            user.professional.admin_blocked = block
        db.session.commit()
        msg = 'blocked' if block else 'unblocked'
        flash(f'User {user.username} has been {msg}.', 'warning' if block else 'info')
    except SQLAlchemyError:
        db.session.rollback()
        flash("An error occurred.", "danger")
    return redirect(url_for('admin.admin_dashboard'))


# @admin_bp.route("/search")
# @admin_required
# def admin_search():
#     search_params = {
#         'category': request.args.get('category'),
#         'q': request.args.get('q', '').strip()
#     }
#     results = None

#     if search_params['category'] and search_params['q']:
#         search_term = f"%{search_params['q']}%"
        
#         if search_params['category'] == 'professional':
#             results = ServiceProfessionals.query.join(Users).filter(or_(
#                 Users.username.ilike(search_term),
#                 Users.email.ilike(search_term),
#                 Users.address.ilike(search_term),
#                 Users.pin.ilike(search_term)
#             )).all()
#         elif search_params['category'] == 'customer':
#             results = Customers.query.join(Users).filter(or_(
#                 Users.username.ilike(search_term),
#                 Users.email.ilike(search_term),
#                 Users.address.ilike(search_term),
#                 Users.pin.ilike(search_term)
#             )).all()

#     return render_template("admin/admin_search.html", search_params=search_params, results=results)


@admin_bp.route("/search")
@admin_required
def admin_search():
    form = CreateServiceForm() # For CSRF tokens
    
    # Defaults
    category = request.args.get('category', 'professional')
    q = request.args.get('q', '').strip()
    results = None

    if q:
        search_term = f"%{q}%"
        
        if category == 'professional':
            # OPTIMIZATION: Eager load User and Service to prevent N+1 in search results
            results = ServiceProfessionals.query\
                .options(joinedload(ServiceProfessionals.user), joinedload(ServiceProfessionals.service))\
                .join(Users).join(Services).filter(or_(
                    Users.username.ilike(search_term),
                    Users.email.ilike(search_term),
                    Users.address.ilike(search_term),
                    Users.pin.ilike(search_term),
                    Services.service_type.ilike(search_term)
                )).all()
        
        elif category == 'customer':
            # OPTIMIZATION: Eager load User
            results = Customers.query\
                .options(joinedload(Customers.user))\
                .join(Users).filter(or_(
                    Users.username.ilike(search_term),
                    Users.email.ilike(search_term),
                    Users.address.ilike(search_term),
                    Users.pin.ilike(search_term)
                )).all()

    return render_template(
        "admin/admin_search.html", 
        search_params={'category': category, 'q': q}, 
        results=results,
        form=form
    )

@admin_bp.route("/charts/data")
@admin_required
def admin_chart_data():
    """Provides data for the admin dashboard charts."""
    
    try:
        # Optimized Count Queries
        status_counts = db.session.query(
            ServiceRequests.service_status, func.count(ServiceRequests.id)
        ).group_by(ServiceRequests.service_status).all()
        
        rating_counts = db.session.query(
            Reviews.rating, func.count(Reviews.id)
        ).group_by(Reviews.rating).all()
        
        # Safe Enumeration Handling
        requests_data = {
            'labels': [s.name.title() for s, c in status_counts],
            'data': [c for s, c in status_counts]
        }
        
        ratings_data = {
            'labels': [f'{r}-Star' for r, c in rating_counts],
            'data': [c for r, c in rating_counts]
        }
        
        return jsonify({
            'requests_by_status': requests_data,
            'ratings_distribution': ratings_data
        })
    except Exception as e:
        current_app.logger.error(f"Chart Data Error: {e}")
        return jsonify({'error': 'Could not fetch data'}), 500

@admin_bp.route('/request/<int:request_id>/reassign', methods=['POST'])
@admin_required
def reassign_professional(request_id):
    """Reassigns a rejected request to a new professional."""
    service_request = ServiceRequests.query.get_or_404(request_id)
    new_prof_id = request.form.get('professional_id', type=int)

    if not new_prof_id:
        flash('You must select a professional.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

    if service_request.service_status != ServiceStatus.REJECTED:
        flash('Only rejected requests can be reassigned.', 'warning')
        return redirect(url_for('admin.admin_dashboard'))
    
    try:
        service_request.professional_id = new_prof_id
        service_request.service_status = ServiceStatus.REQUESTED
        db.session.commit()
        flash(f'Request #{service_request.id} has been reassigned successfully.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash("Database error during reassignment.", "danger")

    return redirect(url_for('admin.admin_dashboard'))
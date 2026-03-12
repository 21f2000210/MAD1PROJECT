from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user, logout_user
from sqlalchemy import func
from app import db
from app.models import ServiceRequests, Reviews, ServiceStatus
from app.forms import HandleRequestForm
from app.services.email_service import notify_request_accepted, notify_request_rejected

professional_bp = Blueprint('professional', __name__)

# --- Professional Role Protection Decorator ---
def professional_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'professional':
            abort(403) # Forbidden
        
        professional_profile = current_user.professional
        if not professional_profile:
             abort(404) # Should not happen, but good practice
        
        # --- THIS IS THE IMPROVED BLOCKING LOGIC ---
        if professional_profile.admin_blocked:
            flash("Your account has been suspended by an administrator.", "danger")
            logout_user() # Log them out immediately
            return redirect(url_for('auth.login'))
            
        if not professional_profile.is_verified:
            flash("Your account is pending verification. You can view your dashboard but cannot accept jobs yet.", "warning")
            
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@professional_bp.route("/dashboard")
@professional_required
def professional_dashboard():
    form = HandleRequestForm()
    professional_id = current_user.professional.id

    # Get new requests that are pending
    incoming_requests = ServiceRequests.query.filter_by(
        professional_id=professional_id,
        service_status=ServiceStatus.REQUESTED
    ).order_by(ServiceRequests.date_of_request.desc()).all()

    # Get requests that have already been handled (accepted, closed, rejected)
    history_requests = ServiceRequests.query.filter(
        ServiceRequests.professional_id == professional_id,
        ServiceRequests.service_status != ServiceStatus.REQUESTED
    ).order_by(ServiceRequests.date_of_request.desc()).all()

    return render_template(
        'professional/professional_dashboard.html',
        form=form,
        incoming_requests=incoming_requests,
        history_requests=history_requests
    )


@professional_bp.route('/request/<int:request_id>/handle', methods=['POST'])
@professional_required
def handle_request(request_id):
    service_request = ServiceRequests.query.get_or_404(request_id)
    form = HandleRequestForm()

    # Security checks are perfect
    if service_request.professional_id != current_user.professional.id:
        abort(403)
    if not current_user.professional.is_verified and form.action.data == 'accept':
        flash("Your account must be verified before you can accept requests.", "danger")
        return redirect(url_for('professional.professional_dashboard'))

    if form.validate_on_submit():
        if form.action.data == 'accept':
            service_request.service_status = ServiceStatus.ACCEPTED
            db.session.commit()
            flash(f'Request #{service_request.id} has been accepted.', 'success')
            try:
                notify_request_accepted(
                    customer_email=service_request.customer.user.email,
                    customer_name=service_request.customer.user.username,
                    professional_name=current_user.username,
                    service_type=service_request.service.service_type,
                    request_id=service_request.id,
                )
            except Exception as email_err:
                current_app.logger.warning(f"Accept email failed: {email_err}")
        elif form.action.data == 'reject':
            service_request.service_status = ServiceStatus.REJECTED
            db.session.commit()
            flash(f'Request #{service_request.id} has been rejected.', 'warning')
            try:
                notify_request_rejected(
                    customer_email=service_request.customer.user.email,
                    customer_name=service_request.customer.user.username,
                    professional_name=current_user.username,
                    service_type=service_request.service.service_type,
                    request_id=service_request.id,
                )
            except Exception as email_err:
                current_app.logger.warning(f"Reject email failed: {email_err}")
        else:
            db.session.commit()
            flash('Invalid action.', 'danger')
    else:
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('professional.professional_dashboard'))

@professional_bp.route("/summary")
@professional_required
def professional_summary():
    professional_id = current_user.professional.id

    stats = {
        'accepted': ServiceRequests.query.filter_by(professional_id=professional_id, service_status=ServiceStatus.ACCEPTED).count(),
        'closed': ServiceRequests.query.filter_by(professional_id=professional_id, service_status=ServiceStatus.CLOSED).count(),
        'rejected': ServiceRequests.query.filter_by(professional_id=professional_id, service_status=ServiceStatus.REJECTED).count(),
        'avg_rating': db.session.query(func.avg(Reviews.rating)).filter(Reviews.professional_id == professional_id).scalar() or 0.0
    }
    
    return render_template('professional/professional_summary.html', stats=stats)
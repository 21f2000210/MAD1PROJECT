from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from sqlalchemy.exc import SQLAlchemyError
from flask_login import login_required, current_user, logout_user
from sqlalchemy import func, or_
from app import db
from app.models import Users, Customers, Services, ServiceProfessionals, ServiceRequests, Reviews, ServiceStatus
from app.forms import ReviewForm, BookingForm, UpdateRequestForm
from sqlalchemy.orm import joinedload
from datetime import datetime

customer_bp = Blueprint('customer', __name__)

# --- Customer Role Protection Decorator ---
def customer_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'customer':
            abort(403) # Forbidden
        
        # Check if customer profile exists and if blocked
        if current_user.customer and current_user.customer.admin_blocked:
            flash("Your account has been suspended by an administrator.", "danger")
            logout_user()
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

# @customer_bp.route("/dashboard")
# @customer_required
# def customer_dashboard():
#     form = BookingForm()
#     all_services = Services.query.order_by(Services.service_type).all()
    
#     # --- Search Logic ---
#     search_params = {
#         'service_id': request.args.get('service_id', type=int),
#         'q': request.args.get('q', type=str, default="").strip()
#     }

#     # Start with a base query for verified, non-blocked professionals
#     query = ServiceProfessionals.query.join(Users).filter(
#         ServiceProfessionals.is_verified == True,
#         ServiceProfessionals.admin_blocked == False
#     )

#     # Apply filters based on search parameters
#     if search_params['service_id']:
#         query = query.filter(ServiceProfessionals.service_id == search_params['service_id'])
    
#     if search_params['q']:
#         search_term = f"%{search_params['q']}%"
#         query = query.filter(or_(
#             Users.username.ilike(search_term),
#             Users.address.ilike(search_term),
#             Users.pin.ilike(search_term)
#         ))

#     professionals = query.all()
    
#     # --- Data for Template ---
#     avg_ratings = {}
#     selected_service_name = ""
#     if search_params['service_id']:
#         service = Services.query.get(search_params['service_id'])
#         if service:
#             selected_service_name = service.service_type

#     if professionals:
#         prof_ids = [p.id for p in professionals]
#         ratings_query = db.session.query(
#             Reviews.professional_id,
#             func.avg(Reviews.rating).label('average_rating')
#         ).filter(Reviews.professional_id.in_(prof_ids)).group_by(Reviews.professional_id).all()
#         avg_ratings = {prof_id: round(avg, 1) for prof_id, avg in ratings_query}

#     return render_template(
#         'customer/customer_dashboard.html',
#         form=form,
#         all_services=all_services,
#         professionals=professionals,
#         avg_ratings=avg_ratings,
#         selected_service_id=search_params['service_id'], # Pass the service_id for the modal
#         selected_service_name=selected_service_name,
#         search_params=search_params # Pass search terms back to the template
#     )

@customer_bp.route("/dashboard")
@customer_required
def customer_dashboard():
    form = BookingForm()
    all_services = Services.query.order_by(Services.service_type).all()
    
    # --- 1. Capture Search & Sort Parameters ---
    search_params = {
        'service_id': request.args.get('service_id', type=int),
        'q': request.args.get('q', type=str, default="").strip(),
        'sort_by': request.args.get('sort_by', type=str, default="rating")
    }

    # --- 2. Build Query ---
    # Join Services to allow searching by "Plumber" text and sorting by price
    query = ServiceProfessionals.query\
        .options(joinedload(ServiceProfessionals.user), joinedload(ServiceProfessionals.service))\
        .join(Users).join(Services).filter(
            ServiceProfessionals.is_verified == True,
            ServiceProfessionals.admin_blocked == False
        )

    # Filter: Service Dropdown
    if search_params['service_id']:
        query = query.filter(ServiceProfessionals.service_id == search_params['service_id'])
    
    # Filter: Rich Text Search
    if search_params['service_id']:
        query = query.filter(ServiceProfessionals.service_id == search_params['service_id'])
    
    # Filter: Rich Text Search
    if search_params['q']:
        search_term = f"%{search_params['q']}%"
        query = query.filter(or_(
            Users.username.ilike(search_term),
            Users.address.ilike(search_term),
            Users.pin.ilike(search_term),
            Services.service_type.ilike(search_term),
            ServiceProfessionals.description.ilike(search_term)
        ))

    raw_professionals = query.all()
    
    # --- 3. Process Data & Calculate Stats ---
    # Instead of sending separate lists, we create one unified list of dictionaries
    results = []
    
    for prof in raw_professionals:
        # Calculate Average Rating efficiently
        avg_rating = db.session.query(func.avg(Reviews.rating))\
            .filter(Reviews.professional_id == prof.id).scalar() or 0
        
        # Calculate Jobs Completed
        jobs_count = ServiceRequests.query.filter_by(
            professional_id=prof.id, 
            service_status=ServiceStatus.CLOSED
        ).count()

        results.append({
            'prof': prof,
            'user': prof.user,
            'service': prof.service,
            'rating': round(avg_rating, 1),
            'jobs_count': jobs_count
        })

    # --- 4. Apply Sorting ---
    sort_key = search_params['sort_by']
    if sort_key == 'rating':
        results.sort(key=lambda x: x['rating'], reverse=True)
    elif sort_key == 'price_low':
        results.sort(key=lambda x: x['service'].base_price)
    elif sort_key == 'price_high':
        results.sort(key=lambda x: x['service'].base_price, reverse=True)
    elif sort_key == 'experience':
        results.sort(key=lambda x: x['prof'].experience, reverse=True)

    # --- 5. Selected Service Helper ---
    selected_service_name = ""
    if search_params['service_id']:
        service = Services.query.get(search_params['service_id'])
        if service:
            selected_service_name = service.service_type

    return render_template(
        'customer/customer_dashboard.html',
        form=form,
        all_services=all_services,
        results=results,
        selected_service_name=selected_service_name,
        search_params=search_params
    )

@customer_bp.route('/book_service/<int:professional_id>', methods=['POST'])
@customer_required
def book_service(professional_id):
    form = BookingForm()
    professional = ServiceProfessionals.query.get_or_404(professional_id)

    # Note: Because the 'date_of_request' in HTML is a raw input, we handle form validation manually
    # or rely on form.validate_on_submit() for the CSRF token and other fields.
    if form.validate_on_submit():
        
        # 1. Parse Date Manually (Standard HTML input sends 'YYYY-MM-DD')
        date_str = request.form.get('date_of_request')
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            flash("Invalid date format. Please try again.", "danger")
            return redirect(url_for('customer.customer_dashboard'))

        # 2. Check for Duplicate Requests
        existing_request = ServiceRequests.query.filter(
            ServiceRequests.customer_id == current_user.customer.id,
            ServiceRequests.professional_id == professional.id,
            ServiceRequests.service_status.in_([ServiceStatus.REQUESTED, ServiceStatus.ACCEPTED])
        ).first()

        if existing_request:
            flash('You already have an active request with this professional.', 'warning')
            return redirect(url_for('customer.customer_dashboard'))

        try:
            new_request = ServiceRequests(
                service_id=form.service_id.data,
                customer_id=current_user.customer.id,
                professional_id=professional.id,
                proposed_price=form.proposed_price.data,
                date_of_request=date_obj, # Use the parsed date
                service_status=ServiceStatus.REQUESTED
            )
            db.session.add(new_request)
            db.session.commit()
            flash('Your service request has been sent!', 'success')
            return redirect(url_for('customer.service_history'))
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Booking Error: {e}")
            flash("An error occurred while booking. Please try again.", "danger")
            return redirect(url_for('customer.customer_dashboard'))
    else:
        flash('Form validation failed. Please check your inputs.', 'danger')
        return redirect(url_for('customer.customer_dashboard'))


@customer_bp.route('/request/<int:request_id>/update', methods=['POST'])
@customer_required
def update_service_request(request_id):
    service_request = ServiceRequests.query.get_or_404(request_id)
    form = UpdateRequestForm()

    if service_request.customer_id != current_user.customer.id:
        abort(403)
        
    if service_request.service_status != ServiceStatus.REQUESTED:
        flash('You can only edit requests that are still pending.', 'warning')
        return redirect(url_for('customer.service_history'))
    
    if form.validate_on_submit():
        try:
            service_request.proposed_price = form.proposed_price.data
            db.session.commit()
            flash('Your service request has been updated successfully.', 'success')
        except SQLAlchemyError:
            db.session.rollback()
            flash('Database error occurred.', 'danger')
    else:
        flash('Invalid price submitted.', 'danger')

    return redirect(url_for('customer.service_history'))

@customer_bp.route('/service_history')
@customer_required
def service_history():
    update_form = UpdateRequestForm() 
    review_form = ReviewForm()

    service_requests = ServiceRequests.query\
        .options(
            joinedload(ServiceRequests.service),
            joinedload(ServiceRequests.professional).joinedload(ServiceProfessionals.user)
        )\
        .filter_by(customer_id=current_user.customer.id)\
        .order_by(ServiceRequests.date_of_request.desc()).all()

    return render_template(
        'customer/service_history.html', 
        service_requests=service_requests, 
        form=update_form,       # For Edit Modal
        review_form=review_form # For Review Modal (New)
    )

@customer_bp.route('/review_service/<int:request_id>', methods=['POST'])
@customer_required
def review_service(request_id):
    service_request = ServiceRequests.query.get_or_404(request_id)
    form = ReviewForm() 

    # Security Check
    if service_request.customer_id != current_user.customer.id:
        abort(403)

    if form.validate_on_submit():
        try:
            # 1. Create the Review
            new_review = Reviews(
                customer_id=current_user.customer.id,
                professional_id=service_request.professional_id,
                service_id=service_request.service_id,
                service_request_id=service_request.id,
                rating=form.rating.data, 
                remarks=form.remarks.data
            )
            db.session.add(new_review)
            
            # 2. CRITICAL FIX: Update the status to CLOSED
            # This triggers the UI to hide "Review" and show "Pay Now"
            service_request.service_status = ServiceStatus.CLOSED 
            
            # 3. Record Completion Date (Optional but recommended)
            service_request.date_of_completion = datetime.utcnow()

            db.session.commit()
            flash('Thank you for your review! You can now proceed to payment.', 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Review Error: {e}")
            flash('An error occurred while saving your review.', 'danger')
    else:
        flash('There was an error with your review submission.', 'danger')
        
    return redirect(url_for('customer.service_history'))

@customer_bp.route('/payment/<int:request_id>', methods=['GET'])
@customer_required
def show_payment_form(request_id):
    service_request = ServiceRequests.query\
        .options(
            joinedload(ServiceRequests.service),
            joinedload(ServiceRequests.professional).joinedload(ServiceProfessionals.user)
        )\
        .get_or_404(request_id)

    if service_request.customer_id != current_user.customer.id:
        abort(403)
    if service_request.service_status != ServiceStatus.CLOSED:
        flash("This service is not yet closed for payment.", "warning")
        return redirect(url_for('customer.service_history'))
        
    return render_template('customer/payment.html', service_request=service_request)

@customer_bp.route('/payment/<int:request_id>/process', methods=['POST'])
@customer_required
def process_payment(request_id):
    service_request = ServiceRequests.query.get_or_404(request_id)
    
    if service_request.customer_id != current_user.customer.id:
        abort(403)
    if service_request.service_status != ServiceStatus.CLOSED:
        flash("This service cannot be paid for at this time.", "warning")
        return redirect(url_for('customer.service_history'))

    try:
        service_request.service_status = ServiceStatus.PAID
        service_request.date_of_completion = datetime.utcnow() # Record exact payment time if desired
        db.session.commit()
        flash(f"Payment for request #{service_request.id} was successful! Thank you.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Transaction failed. Please try again.", "danger")
        
    return redirect(url_for('customer.service_history'))




@customer_bp.route('/profile/<int:customer_id>')
@login_required # Must be logged in
def customer_profile(customer_id):
    """
    Displays a customer's profile and service history.
    Accessible only by the customer themselves or an admin.
    """
    customer = Customers.query.options(joinedload(Customers.user)).get_or_404(customer_id)

    if current_user.role != 'admin' and current_user.id != customer.user_id:
        abort(403) 

    service_requests = ServiceRequests.query\
        .options(joinedload(ServiceRequests.service), joinedload(ServiceRequests.professional).joinedload(ServiceProfessionals.user))\
        .filter_by(customer_id=customer.id)\
        .order_by(ServiceRequests.date_of_request.desc()).all()
    
    return render_template(
        'customer/customer_profile.html',
        customer=customer,
        service_requests=service_requests
    )
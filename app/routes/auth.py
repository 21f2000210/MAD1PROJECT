from flask import Blueprint, render_template, redirect, url_for, request, flash, get_flashed_messages
from flask_login import login_user, logout_user, login_required
from app import db, limiter
from app.models import Users, Customers, ServiceProfessionals
from app.forms import LoginForm, RegistrationForm

# Note the new blueprint name matches the file name.
auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/")
def index():
    # Redirect the root URL to the login page by default.
    return redirect(url_for('auth.login'))

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute; 50 per hour")
def login():
    form = LoginForm()
    if form.validate_on_submit():

        # --- SOLUTION: Clear any pre-existing flashed messages from the session ---
        get_flashed_messages()
        # --------------------------------------------------------------------------

        user = Users.query.filter_by(username=form.username.data).first()

        # --- VALIDATION STEP 1: Check for user existence and correct password ---
        if not user or not user.check_password(form.password.data):
            flash("Invalid username or password.", "danger")
            return redirect(url_for("auth.login"))

        # --- VALIDATION STEP 2: Check if the user is active (not soft-deleted) ---
        if not user.is_active:
            flash("This account has been deactivated.", "danger")
            return redirect(url_for("auth.login"))

        # --- VALIDATION STEP 3: Check if the user has been blocked by an admin ---
        is_blocked = False
        if user.role == 'customer' and user.customer and user.customer.admin_blocked:
            is_blocked = True
        elif user.role == 'professional' and user.professional and user.professional.admin_blocked:
            is_blocked = True

        if is_blocked:
            flash("Your account has been suspended by an administrator.", "danger")
            return redirect(url_for("auth.login"))

        # --- If all checks pass, log the user in ---
        login_user(user)
        flash('Logged in successfully.', 'success')
        
        # Redirect based on role
        if user.role == "admin":
            return redirect(url_for("admin.admin_dashboard"))
        elif user.role == "customer":
            return redirect(url_for("customer.customer_dashboard"))
        elif user.role == "professional":
            return redirect(url_for("professional.professional_dashboard"))
        else:
            return redirect(url_for("auth.login")) # Fallback

    return render_template("login.html", form=form)


@auth_bp.route("/logout")
@login_required # This decorator ensures only logged-in users can access this page
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute; 20 per hour")
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        new_user = Users(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
            # role="admin",
            address=form.address.data,
            pin=form.pin.data
        )
        new_user.set_password(form.password.data)
        
        try:
            db.session.add(new_user)
            db.session.commit()

            if form.role.data == "customer":
                customer = Customers(user_id=new_user.id)
                db.session.add(customer)

            elif form.role.data == "professional":
                prof = ServiceProfessionals(
                    user_id=new_user.id,
                    service_id=form.service_id.data,
                    description=form.description.data,
                    experience=form.experience.data,
                    document=form.document.data
                )
                db.session.add(prof)

            db.session.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", "danger")

    return render_template("register.html", form=form)
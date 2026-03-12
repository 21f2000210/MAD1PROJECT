"""
Email notification service using Flask-Mail.
All emails are sent asynchronously via a background thread so they
do not block the HTTP request-response cycle.
"""
import threading
from flask import current_app
from flask_mail import Message
from app import mail


def _send_async(app, msg):
    """Send email in a background thread."""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            app.logger.error(f"Email send error: {e}")


def _send(subject: str, recipients: list, body: str, html: str = None):
    """Build and dispatch an email."""
    app = current_app._get_current_object()
    # If mail is not configured, skip silently
    if not app.config.get('MAIL_USERNAME'):
        app.logger.info(f"[Email skipped – MAIL_USERNAME not set] Subject: {subject}")
        return
    msg = Message(subject=subject, recipients=recipients, body=body, html=html)
    thread = threading.Thread(target=_send_async, args=(app, msg))
    thread.daemon = True
    thread.start()


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------

def notify_booking_created(customer_email: str, customer_name: str,
                            professional_name: str, service_type: str,
                            request_id: int, proposed_price: float):
    subject = f"[A-Z Services] Booking Request #{request_id} Sent"
    body = (
        f"Hi {customer_name},\n\n"
        f"Your booking request for '{service_type}' has been sent to {professional_name}.\n"
        f"Request ID: #{request_id}\n"
        f"Proposed Price: ₹{proposed_price}\n\n"
        f"You will be notified when the professional responds.\n\n"
        f"— A-Z Household Services Team"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#4A90E2;">Booking Request Sent!</h2>
      <p>Hi <strong>{customer_name}</strong>,</p>
      <p>Your booking request for <strong>{service_type}</strong> has been sent to <strong>{professional_name}</strong>.</p>
      <table style="border-collapse:collapse;width:100%;margin:16px 0;">
        <tr><td style="padding:8px;color:#7A8B99;">Request ID</td><td style="padding:8px;font-weight:bold;">#{request_id}</td></tr>
        <tr style="background:#f9f9f9;"><td style="padding:8px;color:#7A8B99;">Service</td><td style="padding:8px;">{service_type}</td></tr>
        <tr><td style="padding:8px;color:#7A8B99;">Proposed Price</td><td style="padding:8px;">₹{proposed_price}</td></tr>
      </table>
      <p>You will be notified once the professional responds.</p>
      <p style="color:#7A8B99;font-size:12px;">— A-Z Household Services Team</p>
    </div>"""
    _send(subject, [customer_email], body, html)


def notify_professional_new_request(professional_email: str, professional_name: str,
                                     customer_name: str, service_type: str,
                                     request_id: int, proposed_price: float):
    subject = f"[A-Z Services] New Service Request #{request_id}"
    body = (
        f"Hi {professional_name},\n\n"
        f"You have a new service request from {customer_name}.\n"
        f"Service: {service_type}\n"
        f"Proposed Price: ₹{proposed_price}\n"
        f"Request ID: #{request_id}\n\n"
        f"Please log in to accept or reject this request.\n\n"
        f"— A-Z Household Services Team"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#4A90E2;">New Service Request</h2>
      <p>Hi <strong>{professional_name}</strong>,</p>
      <p><strong>{customer_name}</strong> has sent you a new service request.</p>
      <table style="border-collapse:collapse;width:100%;margin:16px 0;">
        <tr><td style="padding:8px;color:#7A8B99;">Request ID</td><td style="padding:8px;font-weight:bold;">#{request_id}</td></tr>
        <tr style="background:#f9f9f9;"><td style="padding:8px;color:#7A8B99;">Service</td><td style="padding:8px;">{service_type}</td></tr>
        <tr><td style="padding:8px;color:#7A8B99;">Proposed Price</td><td style="padding:8px;">₹{proposed_price}</td></tr>
      </table>
      <p>Please <a href="#" style="color:#4A90E2;">log in to your dashboard</a> to accept or reject.</p>
      <p style="color:#7A8B99;font-size:12px;">— A-Z Household Services Team</p>
    </div>"""
    _send(subject, [professional_email], body, html)


def notify_request_accepted(customer_email: str, customer_name: str,
                             professional_name: str, service_type: str,
                             request_id: int):
    subject = f"[A-Z Services] Request #{request_id} Accepted!"
    body = (
        f"Hi {customer_name},\n\n"
        f"Great news! {professional_name} has accepted your request for '{service_type}'.\n"
        f"Request ID: #{request_id}\n\n"
        f"The professional will be in touch to schedule the service.\n\n"
        f"— A-Z Household Services Team"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#2ECC71;">Request Accepted!</h2>
      <p>Hi <strong>{customer_name}</strong>,</p>
      <p><strong>{professional_name}</strong> has accepted your request for <strong>{service_type}</strong>.</p>
      <p style="background:#f0fff4;border-left:4px solid #2ECC71;padding:12px;border-radius:4px;">
        Request <strong>#{request_id}</strong> is now <strong>Accepted</strong>.
      </p>
      <p>The professional will contact you to schedule the service.</p>
      <p style="color:#7A8B99;font-size:12px;">— A-Z Household Services Team</p>
    </div>"""
    _send(subject, [customer_email], body, html)


def notify_request_rejected(customer_email: str, customer_name: str,
                             professional_name: str, service_type: str,
                             request_id: int):
    subject = f"[A-Z Services] Request #{request_id} Rejected"
    body = (
        f"Hi {customer_name},\n\n"
        f"Unfortunately, {professional_name} has rejected your request for '{service_type}'.\n"
        f"Request ID: #{request_id}\n\n"
        f"Please search for another professional on the platform.\n\n"
        f"— A-Z Household Services Team"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#E74C3C;">Request Rejected</h2>
      <p>Hi <strong>{customer_name}</strong>,</p>
      <p><strong>{professional_name}</strong> has rejected your request for <strong>{service_type}</strong>.</p>
      <p style="background:#fff5f5;border-left:4px solid #E74C3C;padding:12px;border-radius:4px;">
        Request <strong>#{request_id}</strong> has been <strong>Rejected</strong>.
      </p>
      <p>Please search for another available professional on the platform.</p>
      <p style="color:#7A8B99;font-size:12px;">— A-Z Household Services Team</p>
    </div>"""
    _send(subject, [customer_email], body, html)


def notify_payment_complete(customer_email: str, customer_name: str,
                             service_type: str, request_id: int, amount: float):
    subject = f"[A-Z Services] Payment Confirmed – Request #{request_id}"
    body = (
        f"Hi {customer_name},\n\n"
        f"Your payment of ₹{amount} for '{service_type}' (Request #{request_id}) has been received.\n"
        f"Thank you for using A-Z Household Services!\n\n"
        f"— A-Z Household Services Team"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#4A90E2;">Payment Confirmed!</h2>
      <p>Hi <strong>{customer_name}</strong>,</p>
      <p>Your payment for <strong>{service_type}</strong> has been successfully processed.</p>
      <table style="border-collapse:collapse;width:100%;margin:16px 0;">
        <tr><td style="padding:8px;color:#7A8B99;">Request ID</td><td style="padding:8px;font-weight:bold;">#{request_id}</td></tr>
        <tr style="background:#f9f9f9;"><td style="padding:8px;color:#7A8B99;">Amount Paid</td><td style="padding:8px;font-weight:bold;color:#2ECC71;">₹{amount}</td></tr>
      </table>
      <p>Thank you for using A-Z Household Services!</p>
      <p style="color:#7A8B99;font-size:12px;">— A-Z Household Services Team</p>
    </div>"""
    _send(subject, [customer_email], body, html)

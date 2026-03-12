from functools import wraps
from flask import Blueprint, jsonify, request, abort
from app import limiter
from app.models import Users, Services, ServiceRequests

api_bp = Blueprint('api', __name__)


@api_bp.errorhandler(401)
def unauthorized(error):
    return jsonify({
        "success": False,
        "error": 401,
        "message": error.description or "Unauthorized"
    }), 401


@api_bp.errorhandler(429)
def ratelimit_handler(error):
    return jsonify({
        "success": False,
        "error": 429,
        "message": "Rate limit exceeded. Please slow down."
    }), 429


# --- API Authentication Decorator ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('x-api-key')
        if not api_key:
            abort(401, description="API key is missing.")
        user = Users.query.filter_by(api_key=api_key).first()
        if not user:
            abort(401, description="Invalid API key.")
        return f(user, *args, **kwargs)
    return decorated_function


# --- Public Endpoints ---

@api_bp.route('/services', methods=['GET'])
@limiter.limit("60 per minute")
def get_services():
    """Returns a list of all available services."""
    services = Services.query.order_by(Services.service_type).all()
    results = [
        {
            'id': s.id,
            'name': s.service_type,
            'description': s.description,
            'base_price': s.base_price
        }
        for s in services
    ]
    return jsonify(success=True, count=len(results), services=results)


# --- Protected Endpoints ---

@api_bp.route('/me', methods=['GET'])
@limiter.limit("30 per minute")
@require_api_key
def get_me(user):
    """Returns the details of the authenticated user."""
    return jsonify(success=True, user={
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'address': user.address,
        'pin': user.pin,
        'created_at': user.created_at.isoformat() if user.created_at else None,
    })


@api_bp.route('/my-requests', methods=['GET'])
@limiter.limit("30 per minute")
@require_api_key
def get_my_requests(user):
    """
    Returns a paginated list of service requests for the authenticated user.
    Query params: page (default 1), per_page (default 20, max 100)
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    if user.role == 'customer' and user.customer:
        query = ServiceRequests.query.filter_by(customer_id=user.customer.id)
    elif user.role == 'professional' and user.professional:
        query = ServiceRequests.query.filter_by(professional_id=user.professional.id)
    else:
        return jsonify(success=True, total=0, page=page, pages=0, requests=[])

    paginated = query.order_by(ServiceRequests.date_of_request.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    results = []
    for req in paginated.items:
        results.append({
            'id': req.id,
            'service': req.service.service_type if req.service else None,
            'status': req.service_status.value,
            'proposed_price': req.proposed_price,
            'date_requested': req.date_of_request.isoformat() if req.date_of_request else None,
            'date_completed': req.date_of_completion.isoformat() if req.date_of_completion else None,
            'customer': req.customer.user.username if req.customer and req.customer.user else None,
            'professional': req.professional.user.username if req.professional and req.professional.user else None,
        })

    return jsonify(
        success=True,
        total=paginated.total,
        page=paginated.page,
        pages=paginated.pages,
        requests=results
    )

"""
AI-powered routes using the Claude API.
Provides: Chat Assistant, Price Estimator, Description Generator.
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app import limiter
from app.models import Services

ai_bp = Blueprint('ai', __name__)


def _get_anthropic_client():
    """Lazy-import anthropic to avoid errors if package is not installed."""
    try:
        import anthropic
        api_key = current_app.config.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            return None, "ANTHROPIC_API_KEY is not configured."
        return anthropic.Anthropic(api_key=api_key), None
    except ImportError:
        return None, "AI features require the 'anthropic' package. Run: pip install anthropic"


# ---------------------------------------------------------------------------
# 1. AI CHAT ASSISTANT
# ---------------------------------------------------------------------------

@ai_bp.route('/chat', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def chat():
    """
    Streaming-free chat endpoint.
    Accepts: { "message": "...", "history": [{"role": "user"|"assistant", "content": "..."}] }
    Returns: { "reply": "..." }
    """
    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    history = data.get('history') or []

    if not user_message:
        return jsonify({'error': 'Message cannot be empty.'}), 400

    client, err = _get_anthropic_client()
    if err:
        return jsonify({'error': err}), 503

    # Build the messages list from history + new user message
    messages = []
    for entry in history[-10:]:  # Keep last 10 messages for context
        role = entry.get('role')
        content = entry.get('content', '')
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': user_message})

    # Fetch available services to include in context
    try:
        services = Services.query.all()
        service_list = ', '.join([f"{s.service_type} (base price: ₹{s.base_price})" for s in services])
    except Exception:
        service_list = "various household services"

    system_prompt = f"""You are a helpful AI assistant for A-Z Household Services, an online platform
that connects customers with verified home service professionals.

Available services on the platform: {service_list}

Your role:
- Help customers understand services, pricing, and the booking process
- Guide professionals on how to get verified and manage requests
- Answer questions about the platform (how to book, how to review, how to pay)
- Suggest the right service for a customer's needs
- Be concise, friendly, and professional
- Do NOT make up information. If unsure, say "Please contact our support team."
- Do NOT discuss topics unrelated to household services or this platform

Pricing guidance: Professionals set their own prices. Base prices are minimums set by admin.
Booking flow: Search → Book → Professional Accepts/Rejects → Review → Pay"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system_prompt,
            messages=messages,
        )
        reply = response.content[0].text
        return jsonify({'reply': reply})
    except Exception as e:
        current_app.logger.error(f"AI chat error: {e}")
        return jsonify({'error': 'AI service temporarily unavailable. Please try again.'}), 503


# ---------------------------------------------------------------------------
# 2. AI PRICE ESTIMATOR
# ---------------------------------------------------------------------------

@ai_bp.route('/estimate-price', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def estimate_price():
    """
    Given a service type, return an AI-suggested price range.
    Accepts: { "service_type": "Plumber", "base_price": 200, "description": "..." }
    Returns: { "min_price": 250, "max_price": 450, "reasoning": "..." }
    """
    data = request.get_json(silent=True) or {}
    service_type = (data.get('service_type') or '').strip()
    base_price = data.get('base_price', 0)
    description = (data.get('description') or '').strip()

    if not service_type:
        return jsonify({'error': 'service_type is required.'}), 400

    client, err = _get_anthropic_client()
    if err:
        return jsonify({'error': err}), 503

    prompt = f"""A customer wants to book a "{service_type}" service on a household services platform in India.
Base price set by admin: ₹{base_price}
Professional's description: {description or 'Not provided'}

Provide a realistic price range in Indian Rupees (₹) for this service.
Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{{"min_price": <number>, "max_price": <number>, "reasoning": "<one sentence explanation>"}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}],
        )
        import json
        raw = response.content[0].text.strip()
        result = json.loads(raw)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Price estimator error: {e}")
        return jsonify({'error': 'Could not estimate price. Please enter manually.'}), 503


# ---------------------------------------------------------------------------
# 3. AI DESCRIPTION GENERATOR (for professionals)
# ---------------------------------------------------------------------------

@ai_bp.route('/generate-description', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def generate_description():
    """
    Generate a professional service description for a service professional.
    Accepts: { "service_type": "Plumber", "experience": 5, "skills": "leak fixing, pipe installation" }
    Returns: { "description": "..." }
    """
    data = request.get_json(silent=True) or {}
    service_type = (data.get('service_type') or '').strip()
    experience = data.get('experience', 1)
    skills = (data.get('skills') or '').strip()

    if not service_type:
        return jsonify({'error': 'service_type is required.'}), 400

    client, err = _get_anthropic_client()
    if err:
        return jsonify({'error': err}), 503

    prompt = f"""Write a short, professional service description (2-3 sentences, max 80 words) for a
{service_type} professional listing on a household services platform.
Experience: {experience} years
Key skills/specialties: {skills or 'general ' + service_type + ' work'}

The description should be in first person, highlight reliability and expertise, and be customer-friendly.
Return ONLY the description text, no quotes, no extra text."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{'role': 'user', 'content': prompt}],
        )
        description = response.content[0].text.strip()
        return jsonify({'description': description})
    except Exception as e:
        current_app.logger.error(f"Description generator error: {e}")
        return jsonify({'error': 'Could not generate description. Please write it manually.'}), 503

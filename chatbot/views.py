import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import ChatSession, ChatMessage
from .processor import ChatbotProcessor


def is_admin_user(user):
    """Check if user is an admin."""
    return user.is_authenticated and user.user_type == 'admin'

@login_required
@require_http_methods(["POST"])
@csrf_protect
def chat_message(request):
    """
    Handle incoming chat messages from admin users.
    Process the query and return a response.
    """
    # Check if user is admin
    if not is_admin_user(request.user):
        return JsonResponse({
            'success': False,
            'error': 'Access denied. Chatbot is only available for administrators.'
        }, status=403)
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty.'
            }, status=400)
        
        # Get or create chat session
        session, created = ChatSession.objects.get_or_create(
            user=request.user,
            defaults={'created_at': timezone.now()}
        )
        
        # Save user message
        ChatMessage.objects.create(
            session=session,
            message_type='user',
            content=user_message
        )
        
        # Process the query
        processor = ChatbotProcessor(request.user)
        response = processor.process_query(user_message)
        
        # Save bot response
        ChatMessage.objects.create(
            session=session,
            message_type='bot',
            content=response['message'],
            data=response.get('data')
        )
        
        # Update session timestamp
        session.updated_at = timezone.now()
        session.save()
        
        return JsonResponse({
            'success': True,
            'response': {
                'message': response['message'],
                'data': response.get('data'),
                'data_type': response.get('data_type', 'text')
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def chat_history(request):
    """
    Get recent chat history for the current user.
    """
    if not is_admin_user(request.user):
        return JsonResponse({
            'success': False,
            'error': 'Access denied.'
        }, status=403)
    
    try:
        # Get the user's chat session
        session = ChatSession.objects.filter(user=request.user).first()
        
        if not session:
            return JsonResponse({
                'success': True,
                'messages': []
            })
        
        # Get last 50 messages
        messages = session.messages.order_by('-created_at')[:50]
        messages = reversed(list(messages))  # Reverse to get chronological order
        
        message_list = []
        for msg in messages:
            message_list.append({
                'type': msg.message_type,
                'content': msg.content,
                'data': msg.data,
                'timestamp': msg.created_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'messages': message_list
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_protect
def clear_chat(request):
    """
    Clear chat history for the current user.
    """
    if not is_admin_user(request.user):
        return JsonResponse({
            'success': False,
            'error': 'Access denied.'
        }, status=403)
    
    try:
        ChatSession.objects.filter(user=request.user).delete()
        return JsonResponse({
            'success': True,
            'message': 'Chat history cleared.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def check_access(request):
    """
    Check if the current user has access to the chatbot.
    """
    has_access = is_admin_user(request.user)
    return JsonResponse({
        'success': True,
        'has_access': has_access,
        'user_type': request.user.user_type if request.user.is_authenticated else None
    })

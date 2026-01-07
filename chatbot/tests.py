from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import ChatSession, ChatMessage
from .processor import ChatbotProcessor

User = get_user_model()


class ChatbotProcessorTests(TestCase):
    """Tests for the ChatbotProcessor class."""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='testpass123',
            user_type='admin',
            first_name='Admin',
            last_name='User'
        )
        self.processor = ChatbotProcessor(self.admin_user)
    
    def test_help_query(self):
        """Test help command returns proper response."""
        response = self.processor.process_query('help')
        self.assertIn('message', response)
        self.assertIn('data', response)
        self.assertEqual(response['data_type'], 'table')
    
    def test_vehicle_status_query(self):
        """Test vehicle status query."""
        response = self.processor.process_query('vehicle status')
        self.assertIn('message', response)
        self.assertIn('Vehicle Status', response['message'])
    
    def test_unknown_query(self):
        """Test unknown query returns default response."""
        response = self.processor.process_query('xyz random gibberish')
        self.assertIn('message', response)
        self.assertIn("I'm not sure", response['message'])


class ChatbotViewTests(TestCase):
    """Tests for chatbot views."""
    
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='testpass123',
            user_type='admin',
            first_name='Admin',
            last_name='User',
            approval_status='approved'
        )
        self.driver_user = User.objects.create_user(
            username='driver_test',
            password='testpass123',
            user_type='driver',
            first_name='Driver',
            last_name='User',
            approval_status='approved'
        )
    
    def test_chat_message_requires_login(self):
        """Test that chat endpoint requires authentication."""
        response = self.client.post('/chatbot/message/')
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_chat_message_admin_access(self):
        """Test that admin can access chat endpoint."""
        self.client.login(username='admin_test', password='testpass123')
        response = self.client.post(
            '/chatbot/message/',
            data='{"message": "help"}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
    
    def test_chat_message_driver_denied(self):
        """Test that driver cannot access chat endpoint."""
        self.client.login(username='driver_test', password='testpass123')
        response = self.client.post(
            '/chatbot/message/',
            data='{"message": "help"}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
    
    def test_check_access_endpoint(self):
        """Test access check endpoint."""
        self.client.login(username='admin_test', password='testpass123')
        response = self.client.get('/chatbot/access/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['has_access'])


class ChatbotModelTests(TestCase):
    """Tests for chatbot models."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='test_user',
            password='testpass123',
            user_type='admin'
        )
    
    def test_chat_session_creation(self):
        """Test creating a chat session."""
        session = ChatSession.objects.create(user=self.user)
        self.assertIsNotNone(session.id)
        self.assertEqual(session.user, self.user)
    
    def test_chat_message_creation(self):
        """Test creating a chat message."""
        session = ChatSession.objects.create(user=self.user)
        message = ChatMessage.objects.create(
            session=session,
            message_type='user',
            content='Test message'
        )
        self.assertEqual(message.session, session)
        self.assertEqual(message.message_type, 'user')

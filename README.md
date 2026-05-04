# StoryForge Backend 🐍

The core API for StoryForge, built with Django and Django REST Framework.

## 🛠️ Features

- **JWT Authentication**: Secure user login and registration.
- **Story Management**: CRUD operations for stories, chapters, and characters.
- **AI Integration**: Hooks for Groq, HuggingFace, and Stability AI.
- **Real-time Updates**: WebSockets via Django Channels.
- **Background Tasks**: Asynchronous processing with Celery and Redis.

## 🚀 Development

### Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Create a `.env` file in the root (parent directory) or use the one already there.

3. **Run Migrations**:
   ```bash
   python manage.py migrate
   ```

4. **Start Server**:
   ```bash
   python manage.py runserver
   ```

## 🧪 Testing

```bash
python manage.py test
```

# Authentication System

This document describes the simplified authentication system implemented for testing purposes.

## Overview

The authentication system is designed for testing and development, not production use. It provides a simple way to:
- Login with an email address
- Automatically create new users if they don't exist
- Store and retrieve user preferences
- Return a UUID for the authenticated user

## Database Schema

### Users Table
- `id`: UUID (primary key, auto-generated)
- `email`: TEXT (unique, required)
- `created_at`: TIMESTAMPTZ (auto-generated)
- `updated_at`: TIMESTAMPTZ (auto-updated)

### User Preferences Table
- `id`: SERIAL (primary key)
- `user_id`: UUID (foreign key to users.id)
- `preference_key`: TEXT (required)
- `preference_value`: TEXT (required)
- `created_at`: TIMESTAMPTZ (auto-generated)
- `updated_at`: TIMESTAMPTZ (auto-updated)

## API Endpoints

### POST /auth/login
Authenticates a user by email or creates a new user if they don't exist.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "user_id": "uuid-here",
  "email": "user@example.com",
  "is_new_user": false,
  "message": "User authenticated successfully"
}
```

## Setup

1. **Create User Tables:**
   ```bash
   cd scripts
   python setup_user_tables.py
   ```

2. **Test the System:**
   ```bash
   cd scripts
   python test_auth.py
   ```

## Usage Example

```python
from api.services.user_service import UserService

# Initialize service
user_service = UserService()

# Login or create user
user = await user_service.get_or_create_user("user@example.com")

# Set preferences
await user_service.set_user_preference(user.id, "timezone", "Eastern US")
await user_service.set_user_preference(user.id, "email_provider", "gmail")

# Get preferences
preferences = await user_service.get_user_preferences(user.id)
# Returns: {"timezone": "Eastern US", "email_provider": "gmail"}
```

## Notes

- This is a simplified system for testing purposes
- No password authentication is implemented
- No session management or JWT tokens
- Users are identified solely by email address
- Preferences are stored as simple key-value pairs
- The system automatically creates new users on first login

## Future Enhancements

When moving to production, consider adding:
- Password authentication
- JWT token management
- Session management
- Role-based access control
- Email verification
- Password reset functionality

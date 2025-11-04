# Authentication System Setup Guide

## Overview

This guide will help you set up the authentication system for the DDM Learning Journey platform.

## Architecture

- **Backend**: FastAPI + PostgreSQL
- **Auth Method**: JWT tokens with email/password
- **Email Verification**: SMTP (Gmail recommended for <100 users)
- **Database**: PostgreSQL via Docker

---

## Step 1: Install Dependencies

```bash
pip install fastapi python-jose[cryptography] passlib[bcrypt] python-multipart psycopg2-binary
```

Or update your `requirements.txt`:

```txt
fastapi
python-jose[cryptography]
passlib[bcrypt]
python-multipart
psycopg2-binary
```

Then:
```bash
pip install -r requirements.txt
```

---

## Step 2: Start PostgreSQL with Docker

```bash
# Start PostgreSQL container
docker-compose up -d

# Check if it's running
docker ps | grep postgres
```

The database will be automatically initialized with the schema from `init.sql`.

---

## Step 3: Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Generate a secure SECRET_KEY:
```bash
openssl rand -hex 32
```

3. Edit `.env` and update:
```bash
# Database (should match docker-compose.yml)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=learning_journey
DB_USER=ddm_user
DB_PASSWORD=your_actual_password_here

# JWT Secret (paste the generated key from step 2)
SECRET_KEY=paste_your_generated_key_here

# Email (Gmail example)
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
FROM_EMAIL=noreply@ddm-learning.org
```

---

## Step 4: Set Up Gmail SMTP (Recommended for <100 users)

### Option A: Gmail App Password (Recommended)

1. Go to your Google Account: https://myaccount.google.com/
2. Click "Security" → "2-Step Verification" (enable if not already)
3. Go to "App passwords": https://myaccount.google.com/apppasswords
4. Select "Mail" and your device
5. Copy the 16-character password
6. Paste it as `SMTP_PASSWORD` in your `.env` file

### Option B: SendGrid (For Production)

1. Sign up at https://sendgrid.com/ (free tier: 100 emails/day)
2. Create API key
3. Update `.env`:
```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your_sendgrid_api_key
```

---

## Step 5: Test Database Connection

```bash
# Test PostgreSQL connection
docker exec -it ddm_postgres psql -U ddm_user -d learning_journey -c "SELECT version();"

# Check tables were created
docker exec -it ddm_postgres psql -U ddm_user -d learning_journey -c "\dt"
```

You should see tables like: `users`, `courses`, `credit_transactions`, etc.

---

## Step 6: Integrate Auth into API

Update your `api.py` to include auth endpoints:

```python
from fastapi import FastAPI, BackgroundTasks
from auth import (
    register_user, login_user, verify_email,
    get_user_profile, get_current_user,
    get_current_verified_user,
    UserRegister, UserLogin, EmailVerification
)

app = FastAPI(title="DDM Learning Journey API")

# Auth endpoints
@app.post("/auth/register")
async def register(user: UserRegister, background_tasks: BackgroundTasks):
    return await register_user(user, background_tasks)

@app.post("/auth/login")
async def login(user: UserLogin):
    return await login_user(user)

@app.post("/auth/verify-email")
async def verify(verification: EmailVerification):
    return await verify_email(verification)

@app.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    return await get_user_profile(current_user)

# Protected endpoint example
@app.get("/learning-journey/stats")
async def get_stats(current_user: dict = Depends(get_current_verified_user)):
    # Only verified users can access this
    user_id = current_user["user_id"]
    # Your logic here
    return {"user_id": user_id, "total_credits": 0}
```

---

## Step 7: Test the Auth System

### Test Registration

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepassword123",
    "full_name": "Test User",
    "ddm_student_id": "DDM001"
  }'
```

Expected response:
```json
{
  "message": "Registration successful. Please check your email to verify your account.",
  "user": {
    "id": "uuid-here",
    "email": "test@example.com",
    "full_name": "Test User",
    "email_verified": false
  }
}
```

Check your email for verification link!

### Test Login (Before Email Verification)

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepassword123"
  }'
```

You'll get a token even if email is not verified, but access to certain features will be restricted.

### Test Email Verification

Click the link in your email, or manually call:

```bash
curl -X POST http://localhost:8000/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{
    "token": "token-from-email-link"
  }'
```

### Test Protected Endpoint

```bash
# Get token first
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "securepassword123"}' \
  | jq -r '.access_token')

# Call protected endpoint
curl http://localhost:8000/learning-journey/stats \
  -H "Authorization: Bearer $TOKEN"
```

---

## Step 8: Update Frontend

See `frontend_v2/index.html` for frontend integration examples.

Key changes needed:
1. Update login form to call `/auth/login`
2. Store JWT token in localStorage
3. Add `Authorization: Bearer <token>` header to all API calls
4. Handle email verification flow
5. Show different UI for verified vs unverified users

---

## Security Checklist

- [ ] Change `SECRET_KEY` to a random 32-byte string
- [ ] Use HTTPS in production (not HTTP)
- [ ] Set strong database password
- [ ] Enable Gmail 2-step verification
- [ ] Use App Password (not regular Gmail password)
- [ ] Add rate limiting to login endpoint (prevent brute force)
- [ ] Set `ACCESS_TOKEN_EXPIRE_DAYS` appropriately (7 days default)
- [ ] Never commit `.env` file to git (already in .gitignore)
- [ ] Use environment variables in production (not .env file)

---

## Troubleshooting

### Database Connection Error

```
psycopg2.OperationalError: could not connect to server
```

**Solution**: Check if PostgreSQL container is running:
```bash
docker ps
docker-compose logs postgres
```

### Email Not Sending

**Common issues**:
1. Gmail app password not generated correctly
2. 2-step verification not enabled
3. SMTP_USERNAME/PASSWORD incorrect in .env

**Debug**: Check console logs when registration happens

### JWT Token Invalid

**Causes**:
1. SECRET_KEY mismatch
2. Token expired (default: 7 days)
3. Token format incorrect

**Solution**: Login again to get fresh token

### Email Already Registered

**Solution**: Check database:
```bash
docker exec -it ddm_postgres psql -U ddm_user -d learning_journey \
  -c "SELECT email, email_verified FROM users;"
```

---

## Database Management

### View All Users

```bash
docker exec -it ddm_postgres psql -U ddm_user -d learning_journey \
  -c "SELECT id, email, full_name, email_verified, created_at FROM users;"
```

### Manually Verify a User

```bash
docker exec -it ddm_postgres psql -U ddm_user -d learning_journey \
  -c "UPDATE users SET email_verified = TRUE WHERE email = 'user@example.com';"
```

### Reset Database

```bash
# Stop containers
docker-compose down

# Remove volumes
docker-compose down -v

# Start fresh
docker-compose up -d
```

---

## Production Deployment

### Required Changes:

1. **Use managed PostgreSQL** (AWS RDS, DigitalOcean, etc.)
2. **Use proper email service** (SendGrid, AWS SES, Mailgun)
3. **Enable HTTPS** (Let's Encrypt via nginx/caddy)
4. **Set environment variables** securely (not .env file)
5. **Add rate limiting** (slowapi, nginx)
6. **Enable logging** (to file or service like Sentry)
7. **Backup database** regularly
8. **Monitor email delivery** rates

### Recommended Stack:

- **Backend**: DigitalOcean App Platform or AWS ECS
- **Database**: AWS RDS PostgreSQL or DigitalOcean Managed Database
- **Email**: SendGrid (reliable, good deliverability)
- **SSL**: Automatic with most cloud platforms
- **Monitoring**: Sentry for errors, CloudWatch for logs

---

## Next Steps

1. ✅ Test auth system locally
2. ✅ Update frontend to use real auth
3. ✅ Add "Personal Learning Journey" tab (requires auth)
4. ✅ Implement credit tracking system
5. ✅ Add course enrollment features
6. ⬜ Deploy to production

---

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Database queries: Use pgAdmin or psql
- Email debugging: Check SMTP credentials
- Token issues: Verify SECRET_KEY matches

---

## License

© 2025 佛學入門 - AI數位義工 | 法鼓山數位學習平台

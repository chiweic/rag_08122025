# Authentication System Testing Guide

## Quick Start

Follow these steps to test the authentication system before full integration.

---

## Step 1: Start PostgreSQL

```bash
# Start PostgreSQL container
docker-compose up -d postgres

# Verify it's running
docker ps | grep postgres

# Check logs
docker-compose logs postgres
```

**Expected output**: PostgreSQL should start successfully and initialize the database schema from `init.sql`.

---

## Step 2: Install Test Dependencies

```bash
# Install required packages
pip install requests psycopg2-binary python-jose passlib

# Or install all dependencies
pip install -r requirements.txt
```

---

## Step 3: Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env file
nano .env
```

**Minimum required settings for testing:**

```bash
# Database (must match docker-compose.yml)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=learning_journey
DB_USER=ddm_user
DB_PASSWORD=change_this_password  # Use the password from docker-compose.yml

# JWT Secret (generate with: openssl rand -hex 32)
SECRET_KEY=your_generated_secret_key_here

# Email (optional for testing - tests will pass without SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
FROM_EMAIL=noreply@ddm-learning.org
```

**Note**: Email sending is optional for tests. Tests will pass even if SMTP is not configured.

---

## Step 4: Start Test API Server

Open a **new terminal** and run:

```bash
cd /home/chiweic/repo/rag_08122025
python test_api_server.py
```

**Expected output:**
```
====================================================
  DDM Learning Journey - Test API Server
====================================================

 Starting server on http://localhost:8000
 Interactive docs: http://localhost:8000/docs
 Health check: http://localhost:8000/health

 Press Ctrl+C to stop
====================================================

INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Verify it's working:**
```bash
# In another terminal
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "DDM Learning Journey API",
  "version": "0.1.0"
}
```

---

## Step 5: Run Automated Tests

Open a **second terminal** and run:

```bash
cd /home/chiweic/repo/rag_08122025
python test_auth.py
```

**The test suite will:**
1. Check database connection
2. Validate database schema
3. Test auth module functions
4. Test API server health
5. Register a test user
6. Login with test user
7. Access protected endpoints
8. Test invalid tokens
9. Test duplicate email prevention
10. Test wrong password rejection
11. Check email verification flow

---

## Expected Test Results

```
╔══════════════════════════════════════════════════════════╗
║               DDM AUTH SYSTEM TEST SUITE                 ║
╚══════════════════════════════════════════════════════════╝

============================================================
Test 1: Database Connection
============================================================
✓ Database connection successful
ℹ PostgreSQL version: PostgreSQL 15.x on x86_64-pc-linux-gnu...

============================================================
Test 2: Database Schema Validation
============================================================
✓ Table 'users' exists
✓ Table 'courses' exists
✓ Table 'course_enrollments' exists
✓ Table 'credit_transactions' exists
✓ Table 'certificates' exists
✓ Table 'learning_activities' exists
✓ Table 'query_history' exists
✓ Table 'quiz_results' exists
✓ Table 'reading_progress' exists
✓ Table 'event_attendance' exists
ℹ Sample courses loaded: 5

... (more tests) ...

╔══════════════════════════════════════════════════════════╗
║                    TEST SUMMARY                          ║
╚══════════════════════════════════════════════════════════╝
  PASS  Database Connection
  PASS  Database Schema
  PASS  Auth Module Import
  PASS  API Server Health
  PASS  User Registration
  PASS  User Login
  PASS  Protected Endpoint
  PASS  Invalid Token
  PASS  Duplicate Email Prevention
  PASS  Wrong Password Rejection
  PASS  Email Verification

------------------------------------------------------------
  Total tests: 11
  Passed: 11
  Failed: 0
  Success rate: 100.0%
  Duration: 3.45s
------------------------------------------------------------

✓ All tests passed! Auth system is ready for integration.
```

---

## Step 6: Manual Testing (Optional)

You can also test endpoints manually using the interactive API docs:

1. Open browser: http://localhost:8000/docs
2. Try the endpoints:

### Register User
- Click "POST /auth/register"
- Click "Try it out"
- Fill in the request body:
```json
{
  "email": "manual.test@example.com",
  "password": "SecurePassword123!",
  "full_name": "Manual Test User",
  "ddm_student_id": "MANUAL001"
}
```
- Click "Execute"

### Login
- Click "POST /auth/login"
- Click "Try it out"
- Fill in:
```json
{
  "email": "manual.test@example.com",
  "password": "SecurePassword123!"
}
```
- Click "Execute"
- **Copy the `access_token` from the response**

### Get Profile (Protected)
- Click "GET /auth/me"
- Click "Try it out"
- Click the lock icon 🔒 (Authorize)
- Paste your token (just the token, without "Bearer")
- Click "Authorize"
- Click "Execute"

---

## Troubleshooting

### Test Failure: Database Connection

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solutions**:
1. Check if PostgreSQL is running:
   ```bash
   docker ps | grep postgres
   ```
2. Check PostgreSQL logs:
   ```bash
   docker-compose logs postgres
   ```
3. Verify port is not in use:
   ```bash
   lsof -i :5432
   ```
4. Restart PostgreSQL:
   ```bash
   docker-compose restart postgres
   ```

### Test Failure: API Server Health

**Error**: `Cannot connect to API server`

**Solutions**:
1. Make sure test_api_server.py is running
2. Check if port 8000 is available:
   ```bash
   lsof -i :8000
   ```
3. Check server logs in the terminal where you ran test_api_server.py

### Test Failure: User Registration

**Error**: Email-related errors

**Note**: Email verification is optional for tests. The test will still pass even if emails don't send. This only affects the actual email delivery, not the registration logic.

To fix email sending:
1. Set up Gmail App Password (see AUTH_SETUP.md)
2. Update SMTP settings in .env
3. Restart test server

### Test Failure: Module Import

**Error**: `ModuleNotFoundError: No module named 'auth'`

**Solution**:
```bash
# Make sure you're in the project directory
cd /home/chiweic/repo/rag_08122025

# Install dependencies
pip install -r requirements.txt

# Run test again
python test_auth.py
```

### Database Schema Issues

**Error**: Tables not found

**Solution**: Reinitialize database:
```bash
# Stop and remove containers
docker-compose down -v

# Start fresh
docker-compose up -d postgres

# Wait 5 seconds for initialization
sleep 5

# Run tests again
python test_auth.py
```

---

## Manual Database Inspection

### View all users
```bash
docker exec -it ddm_postgres psql -U ddm_user -d learning_journey \
  -c "SELECT id, email, full_name, email_verified, created_at FROM users;"
```

### View all courses
```bash
docker exec -it ddm_postgres psql -U ddm_user -d learning_journey \
  -c "SELECT course_code, title, credits FROM courses;"
```

### Check test user
```bash
docker exec -it ddm_postgres psql -U ddm_user -d learning_journey \
  -c "SELECT email, email_verified, verification_token FROM users WHERE email = 'test_user@example.com';"
```

---

## Clean Up After Testing

### Remove test user
```bash
docker exec -it ddm_postgres psql -U ddm_user -d learning_journey \
  -c "DELETE FROM users WHERE email LIKE '%test%' OR email LIKE '%example.com';"
```

### Stop services
```bash
# Stop test server: Press Ctrl+C in the terminal
# Stop PostgreSQL
docker-compose stop postgres

# Or stop everything
docker-compose down
```

---

## Next Steps After Tests Pass

Once all tests pass (100% success rate):

1. ✅ **Auth system verified and working**
2. ✅ **Database schema correct**
3. ✅ **All endpoints functional**

You can now proceed to:
- Integrate auth endpoints into your main `api.py`
- Update frontend to use real authentication
- Build the "Personal Learning Journey" tab
- Add credit tracking features

---

## Test Coverage

The test suite covers:

- ✅ Database connectivity and schema
- ✅ Password hashing and verification
- ✅ JWT token generation and validation
- ✅ User registration with email verification
- ✅ Login with email/password
- ✅ Protected endpoint authorization
- ✅ Invalid token rejection
- ✅ Duplicate email prevention
- ✅ Wrong password rejection
- ✅ Email verification token generation

**Not covered** (manual testing recommended):
- Email delivery (requires SMTP configuration)
- Token expiry after 7 days (would take too long)
- Concurrent user registrations
- SQL injection attempts (psycopg2 handles this)
- Performance under load

---

## Support

If tests fail or you encounter issues:
1. Check the error messages carefully
2. Review the troubleshooting section above
3. Check PostgreSQL logs: `docker-compose logs postgres`
4. Check API server logs in the terminal
5. Verify .env configuration matches your setup

Happy testing! 🎉

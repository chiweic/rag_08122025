# Authentication System Pre-Integration Checklist

Use this checklist before integrating the auth system into your main application.

---

## 📋 Pre-Testing Setup

- [ ] PostgreSQL Docker image installed
- [ ] Python dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created and configured
- [ ] `SECRET_KEY` generated (`openssl rand -hex 32`)
- [ ] Database password set in `.env`

---

## 🗄️ Database Setup

- [ ] PostgreSQL container running (`docker-compose up -d postgres`)
- [ ] Database initialized with schema (`init.sql` loaded automatically)
- [ ] Can connect to database:
  ```bash
  docker exec -it ddm_postgres psql -U ddm_user -d learning_journey -c "SELECT 1;"
  ```
- [ ] Required tables exist (users, courses, etc.)
- [ ] Sample courses loaded (5 courses)

---

## 🔧 Test Server

- [ ] Test API server starts without errors (`python test_api_server.py`)
- [ ] Health check responds: `curl http://localhost:8000/health`
- [ ] API docs accessible: http://localhost:8000/docs
- [ ] No import errors or missing dependencies

---

## ✅ Automated Tests

Run: `python test_auth.py`

- [ ] Test 1: Database Connection - PASS
- [ ] Test 2: Database Schema - PASS
- [ ] Test 3: Auth Module Import - PASS
- [ ] Test 4: API Server Health - PASS
- [ ] Test 5: User Registration - PASS
- [ ] Test 6: User Login - PASS
- [ ] Test 7: Protected Endpoint - PASS
- [ ] Test 8: Invalid Token - PASS
- [ ] Test 9: Duplicate Email Prevention - PASS
- [ ] Test 10: Wrong Password Rejection - PASS
- [ ] Test 11: Email Verification - PASS

**Overall**: [ ] 11/11 tests passing (100%)

---

## 📧 Email Configuration (Optional)

For production, you'll need email verification:

- [ ] SMTP server configured (Gmail or SendGrid)
- [ ] Gmail 2-step verification enabled (if using Gmail)
- [ ] Gmail App Password generated
- [ ] SMTP credentials in `.env`
- [ ] Test email sent successfully (check spam folder)

**Note**: Tests will pass without email configured. Email is only needed for actual user verification.

---

## 🧪 Manual Testing (Optional but Recommended)

Using http://localhost:8000/docs:

### Registration
- [ ] Can register new user
- [ ] Duplicate email rejected
- [ ] Weak password rejected (if validation added)
- [ ] User appears in database

### Login
- [ ] Can login with correct credentials
- [ ] Wrong password rejected
- [ ] Receives JWT token
- [ ] Token format correct

### Protected Endpoints
- [ ] Can access `/auth/me` with valid token
- [ ] Rejected with invalid token
- [ ] Rejected without token
- [ ] Returns correct user info

### Database
- [ ] User record created correctly
- [ ] Password is hashed (not plaintext)
- [ ] Verification token generated
- [ ] DDM student ID stored (if provided)

---

## 🔐 Security Checks

- [ ] `SECRET_KEY` is NOT the default/example value
- [ ] `SECRET_KEY` is at least 32 characters
- [ ] Database password is strong
- [ ] Passwords stored as bcrypt hashes (never plaintext)
- [ ] `.env` file in `.gitignore` (not committed to git)
- [ ] Default test passwords removed for production
- [ ] HTTPS will be used in production (not HTTP)

---

## 📁 Files Verified

- [ ] `auth.py` - Auth module (450 lines)
- [ ] `init.sql` - Database schema
- [ ] `docker-compose.yml` - Has PostgreSQL service
- [ ] `requirements.txt` - Has auth dependencies
- [ ] `.env` - Configured correctly
- [ ] `test_auth.py` - Test suite
- [ ] `test_api_server.py` - Test server
- [ ] `AUTH_SETUP.md` - Setup guide
- [ ] `TEST_AUTH_GUIDE.md` - Testing guide

---

## 🚀 Ready for Integration?

Answer these questions:

1. [ ] All automated tests passing?
2. [ ] Database connection working?
3. [ ] Can register and login users?
4. [ ] JWT tokens working correctly?
5. [ ] Protected endpoints secure?
6. [ ] No security warnings or errors?

If ALL checkboxes above are checked: **✅ Ready to integrate!**

---

## 📝 Integration Next Steps

Once all checks pass:

1. **Backup your current `api.py`**:
   ```bash
   cp api.py api.py.backup
   ```

2. **Add auth imports to `api.py`**:
   ```python
   from auth import (
       register_user, login_user, verify_email,
       get_user_profile, get_current_user,
       get_current_verified_user,
       UserRegister, UserLogin, EmailVerification
   )
   ```

3. **Add auth endpoints**:
   ```python
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
   ```

4. **Protect existing endpoints** (optional):
   ```python
   @app.get("/learning-journey/stats")
   async def get_stats(current_user: dict = Depends(get_current_verified_user)):
       # Only verified users can access
       user_id = current_user["user_id"]
       # ... your existing code ...
   ```

5. **Update frontend** (`frontend_v2/index.html`):
   - Replace mock login with real API calls
   - Store JWT token in localStorage
   - Add Authorization header to requests
   - Handle email verification flow

6. **Test integrated system**:
   - Start your main API: `python main.py`
   - Test registration from frontend
   - Test login from frontend
   - Verify protected features work

---

## 🐛 Common Issues Before Integration

### Import Error
```
ImportError: No module named 'auth'
```
**Fix**: Ensure `auth.py` is in the same directory as your main API file.

### Database Connection Error
```
psycopg2.OperationalError
```
**Fix**: Check PostgreSQL is running and `.env` credentials are correct.

### Module Not Found: psycopg2
```
ModuleNotFoundError: No module named 'psycopg2'
```
**Fix**: `pip install psycopg2-binary`

### Email Not Sending
**Note**: This is OK for testing. Email verification can be added later.

---

## 📊 Test Results Template

Date: _____________

| Test | Result | Notes |
|------|--------|-------|
| Database Connection | ☐ Pass ☐ Fail | |
| Database Schema | ☐ Pass ☐ Fail | |
| Auth Module Import | ☐ Pass ☐ Fail | |
| API Server Health | ☐ Pass ☐ Fail | |
| User Registration | ☐ Pass ☐ Fail | |
| User Login | ☐ Pass ☐ Fail | |
| Protected Endpoint | ☐ Pass ☐ Fail | |
| Invalid Token | ☐ Pass ☐ Fail | |
| Duplicate Email | ☐ Pass ☐ Fail | |
| Wrong Password | ☐ Pass ☐ Fail | |
| Email Verification | ☐ Pass ☐ Fail | |

**Overall Pass Rate**: ___/11 (___%)

**Ready for Integration**: ☐ Yes ☐ No

**Tester**: _____________

**Notes**:
_________________________________________________
_________________________________________________
_________________________________________________

---

## ✨ After Integration

- [ ] Auth endpoints working in main API
- [ ] Frontend can register users
- [ ] Frontend can login
- [ ] Frontend stores and uses JWT tokens
- [ ] Protected features require login
- [ ] Email verification flow works (if configured)
- [ ] User profile page accessible
- [ ] "Personal Learning Journey" tab functional

---

## 🎯 Success Criteria

Your auth system is production-ready when:

1. ✅ All 11 automated tests pass
2. ✅ Manual testing successful
3. ✅ No security warnings
4. ✅ Database properly configured
5. ✅ Frontend integration working
6. ✅ Email verification functional (or planned)
7. ✅ <100 users can register and login smoothly

---

**Remember**: It's better to catch issues now than after integration! 🛡️

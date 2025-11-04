"""
Test suite for authentication system
Run with: python test_auth.py
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import time
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")

# Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "learning_journey"),
    "user": os.getenv("DB_USER", "ddm_user"),
    "password": os.getenv("DB_PASSWORD", "your_secure_password_here")
}

API_BASE_URL = "http://localhost:8000"

# Test data
TEST_USER = {
    "email": "test_user@example.com",
    "password": "TestPassword123!",
    "full_name": "Test User",
    "ddm_student_id": "TEST001"
}

# ============================================================================
# Test Functions
# ============================================================================

def test_database_connection():
    """Test 1: Database connection"""
    print("\n" + "="*60)
    print("Test 1: Database Connection")
    print("="*60)

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()

        print_success("Database connection successful")
        print_info(f"PostgreSQL version: {version[:50]}...")
        return True
    except Exception as e:
        print_error(f"Database connection failed: {str(e)}")
        return False

def test_database_schema():
    """Test 2: Database schema validation"""
    print("\n" + "="*60)
    print("Test 2: Database Schema Validation")
    print("="*60)

    required_tables = [
        'users', 'courses', 'course_enrollments',
        'credit_transactions', 'certificates',
        'learning_activities', 'query_history',
        'quiz_results', 'reading_progress', 'event_attendance'
    ]

    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        cur = conn.cursor()

        cur.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)

        tables = [row['tablename'] for row in cur.fetchall()]

        all_present = True
        for table in required_tables:
            if table in tables:
                print_success(f"Table '{table}' exists")
            else:
                print_error(f"Table '{table}' missing")
                all_present = False

        # Check sample courses
        cur.execute("SELECT COUNT(*) as count FROM courses;")
        course_count = cur.fetchone()['count']
        print_info(f"Sample courses loaded: {course_count}")

        cur.close()
        conn.close()

        return all_present
    except Exception as e:
        print_error(f"Schema validation failed: {str(e)}")
        return False

def test_auth_module_import():
    """Test 3: Auth module import"""
    print("\n" + "="*60)
    print("Test 3: Auth Module Import")
    print("="*60)

    try:
        from auth import (
            hash_password, verify_password,
            create_access_token, generate_verification_token
        )

        print_success("Auth module imported successfully")

        # Test password hashing
        password = "TestPassword123"
        hashed = hash_password(password)

        if verify_password(password, hashed):
            print_success("Password hashing/verification works")
        else:
            print_error("Password verification failed")
            return False

        # Test token generation
        token = generate_verification_token()
        if len(token) > 20:
            print_success(f"Verification token generated: {token[:20]}...")
        else:
            print_error("Token generation failed")
            return False

        # Test JWT creation
        jwt_token = create_access_token({"user_id": "test", "email": "test@example.com"})
        if len(jwt_token) > 50:
            print_success(f"JWT token created: {jwt_token[:30]}...")
        else:
            print_error("JWT token creation failed")
            return False

        return True
    except Exception as e:
        print_error(f"Auth module import failed: {str(e)}")
        return False

def cleanup_test_user():
    """Helper: Clean up test user before tests"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE email = %s", (TEST_USER['email'],))
        conn.commit()
        cur.close()
        conn.close()
    except:
        pass

def test_api_health():
    """Test 4: API server health check"""
    print("\n" + "="*60)
    print("Test 4: API Server Health Check")
    print("="*60)

    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("API server is running")
            print_info(f"Response: {response.json()}")
            return True
        else:
            print_error(f"API health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"Cannot connect to API server: {str(e)}")
        print_warning("Make sure the API server is running: python main.py")
        return False

def test_user_registration():
    """Test 5: User registration"""
    print("\n" + "="*60)
    print("Test 5: User Registration")
    print("="*60)

    # Clean up first
    cleanup_test_user()

    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/register",
            json=TEST_USER,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("User registration successful")
            print_info(f"User ID: {data['user']['id']}")
            print_info(f"Email: {data['user']['email']}")
            print_info(f"Email verified: {data['user']['email_verified']}")

            # Check if verification email was sent
            if "check your email" in data['message'].lower():
                print_warning("Email verification required (email may not send if SMTP not configured)")

            return True
        else:
            print_error(f"Registration failed: {response.status_code}")
            print_error(f"Response: {response.json()}")
            return False
    except Exception as e:
        print_error(f"Registration test failed: {str(e)}")
        return False

def test_user_login():
    """Test 6: User login"""
    print("\n" + "="*60)
    print("Test 6: User Login")
    print("="*60)

    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={
                "email": TEST_USER['email'],
                "password": TEST_USER['password']
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Login successful")
            print_info(f"Token type: {data['token_type']}")
            print_info(f"Access token: {data['access_token'][:30]}...")
            print_info(f"User: {data['user']['full_name']} ({data['user']['email']})")

            # Store token for next tests
            global ACCESS_TOKEN
            ACCESS_TOKEN = data['access_token']

            return True
        else:
            print_error(f"Login failed: {response.status_code}")
            print_error(f"Response: {response.json()}")
            return False
    except Exception as e:
        print_error(f"Login test failed: {str(e)}")
        return False

def test_protected_endpoint():
    """Test 7: Protected endpoint access"""
    print("\n" + "="*60)
    print("Test 7: Protected Endpoint (Get User Profile)")
    print("="*60)

    if not ACCESS_TOKEN:
        print_error("No access token available. Login test must pass first.")
        return False

    try:
        response = requests.get(
            f"{API_BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Protected endpoint access successful")
            print_info(f"User: {data['full_name']}")
            print_info(f"Email: {data['email']}")
            print_info(f"Email verified: {data['email_verified']}")
            print_info(f"DDM Student ID: {data.get('ddm_student_id', 'None')}")
            print_info(f"Member since: {data['member_since']}")
            return True
        else:
            print_error(f"Protected endpoint access failed: {response.status_code}")
            print_error(f"Response: {response.json()}")
            return False
    except Exception as e:
        print_error(f"Protected endpoint test failed: {str(e)}")
        return False

def test_invalid_token():
    """Test 8: Invalid token rejection"""
    print("\n" + "="*60)
    print("Test 8: Invalid Token Rejection")
    print("="*60)

    try:
        response = requests.get(
            f"{API_BASE_URL}/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
            timeout=10
        )

        if response.status_code == 401:
            print_success("Invalid token correctly rejected")
            return True
        else:
            print_error(f"Unexpected status code: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Invalid token test failed: {str(e)}")
        return False

def test_duplicate_registration():
    """Test 9: Duplicate email prevention"""
    print("\n" + "="*60)
    print("Test 9: Duplicate Email Prevention")
    print("="*60)

    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/register",
            json=TEST_USER,
            timeout=10
        )

        if response.status_code == 400:
            data = response.json()
            if "already registered" in data['detail'].lower():
                print_success("Duplicate email correctly rejected")
                return True
            else:
                print_error(f"Unexpected error message: {data['detail']}")
                return False
        else:
            print_error(f"Expected 400 status, got: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Duplicate registration test failed: {str(e)}")
        return False

def test_wrong_password():
    """Test 10: Wrong password rejection"""
    print("\n" + "="*60)
    print("Test 10: Wrong Password Rejection")
    print("="*60)

    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={
                "email": TEST_USER['email'],
                "password": "WrongPassword123!"
            },
            timeout=10
        )

        if response.status_code == 401:
            print_success("Wrong password correctly rejected")
            return True
        else:
            print_error(f"Expected 401 status, got: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Wrong password test failed: {str(e)}")
        return False

def test_email_verification_flow():
    """Test 11: Email verification token"""
    print("\n" + "="*60)
    print("Test 11: Email Verification Token")
    print("="*60)

    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        cur = conn.cursor()

        # Get verification token for test user
        cur.execute("""
            SELECT verification_token, email_verified, verification_token_expires
            FROM users WHERE email = %s
        """, (TEST_USER['email'],))

        user = cur.fetchone()

        if user:
            if user['verification_token']:
                print_success("Verification token exists in database")
                print_info(f"Token: {user['verification_token'][:30]}...")
                print_info(f"Expires: {user['verification_token_expires']}")
                print_info(f"Verified: {user['email_verified']}")

                # You can manually verify here if needed
                print_warning("To verify email, call: POST /auth/verify-email with token")

                cur.close()
                conn.close()
                return True
            else:
                print_warning("No verification token (email might be already verified)")
                cur.close()
                conn.close()
                return True
        else:
            print_error("User not found in database")
            cur.close()
            conn.close()
            return False
    except Exception as e:
        print_error(f"Email verification test failed: {str(e)}")
        return False

# ============================================================================
# Main Test Runner
# ============================================================================

ACCESS_TOKEN = None

def run_all_tests():
    """Run all tests and generate report"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "DDM AUTH SYSTEM TEST SUITE" + " "*17 + "║")
    print("╚" + "="*58 + "╝")

    tests = [
        ("Database Connection", test_database_connection),
        ("Database Schema", test_database_schema),
        ("Auth Module Import", test_auth_module_import),
        ("API Server Health", test_api_health),
        ("User Registration", test_user_registration),
        ("User Login", test_user_login),
        ("Protected Endpoint", test_protected_endpoint),
        ("Invalid Token", test_invalid_token),
        ("Duplicate Email Prevention", test_duplicate_registration),
        ("Wrong Password Rejection", test_wrong_password),
        ("Email Verification", test_email_verification_flow),
    ]

    results = []
    start_time = time.time()

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {str(e)}")
            results.append((test_name, False))

    end_time = time.time()
    duration = end_time - start_time

    # Print summary
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*20 + "TEST SUMMARY" + " "*26 + "║")
    print("╚" + "="*58 + "╝")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"  {status}  {test_name}")

    print("\n" + "-"*60)
    print(f"  Total tests: {total}")
    print(f"  Passed: {Colors.GREEN}{passed}{Colors.END}")
    print(f"  Failed: {Colors.RED}{total - passed}{Colors.END}")
    print(f"  Success rate: {(passed/total*100):.1f}%")
    print(f"  Duration: {duration:.2f}s")
    print("-"*60)

    if passed == total:
        print(f"\n{Colors.GREEN}✓ All tests passed! Auth system is ready for integration.{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}✗ Some tests failed. Please fix issues before integration.{Colors.END}\n")
        return 1

if __name__ == "__main__":
    print_info("Starting DDM Authentication System Tests...")
    print_info(f"API Base URL: {API_BASE_URL}")
    print_info(f"Database: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print_warning("\nMake sure:")
    print("  1. PostgreSQL is running: docker-compose up -d postgres")
    print("  2. API server is running: python main.py")
    print("  3. .env file is configured with correct values")

    input("\nPress Enter to start tests...")

    exit_code = run_all_tests()
    sys.exit(exit_code)

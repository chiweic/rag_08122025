#!/bin/bash

echo "========================================"
echo "  DDM Auth System Setup Checker"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: Virtual environment
echo -n "Checking virtual environment... "
if [ -d "venv" ]; then
    echo -e "${GREEN}✓ Found${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    echo "  Run: python3 -m venv venv"
fi

# Check 2: Activation
echo -n "Checking if venv is activated... "
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✓ Activated${NC}"
else
    echo -e "${YELLOW}⚠ Not activated${NC}"
    echo "  Run: source venv/bin/activate"
fi

# Check 3: PostgreSQL
echo -n "Checking PostgreSQL container... "
if docker ps | grep -q ddm_postgres; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    echo "  Run: docker-compose up -d postgres"
fi

# Check 4: .env file
echo -n "Checking .env file... "
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ Exists${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    echo "  Run: cp .env.example .env"
fi

# Check 5: Database connection
echo -n "Checking database connection... "
if docker exec ddm_postgres psql -U ddm_user -d learning_journey -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Connected${NC}"
else
    echo -e "${RED}✗ Cannot connect${NC}"
fi

# Check 6: Tables
echo -n "Checking database tables... "
TABLE_COUNT=$(docker exec ddm_postgres psql -U ddm_user -d learning_journey -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
if [ "$TABLE_COUNT" -ge "10" ]; then
    echo -e "${GREEN}✓ $TABLE_COUNT tables found${NC}"
else
    echo -e "${YELLOW}⚠ Only $TABLE_COUNT tables found${NC}"
fi

echo ""
echo "========================================"
echo "Next steps:"
echo "1. source venv/bin/activate"
echo "2. pip install -r requirements.txt"
echo "3. python test_api_server.py"
echo "4. python test_auth.py (in another terminal)"
echo "========================================"

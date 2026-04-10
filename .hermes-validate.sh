#!/bin/bash
# Validation script - Run before executing Hermes plan

set -e

PROJECT_ROOT="/Users/ccanales/projects/lightroom-tagger"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Hermes Setup Validation"
echo "========================="
echo ""

# Check 1: Hermes installed
echo -n "Checking Hermes installation... "
if command -v hermes &> /dev/null; then
    VERSION=$(hermes --version 2>&1 | head -1)
    echo -e "${GREEN}✓${NC} $VERSION"
else
    echo -e "${RED}✗ Not installed${NC}"
    echo "   Install: pip install hermes-agent"
    exit 1
fi

# Check 2: Node.js installed
echo -n "Checking Node.js... "
if command -v node &> /dev/null; then
    VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} $VERSION"
else
    echo -e "${RED}✗ Not installed${NC}"
    echo "   Install: brew install node"
    exit 1
fi

# Check 3: Python openai SDK (in venv)
echo -n "Checking Python openai SDK... "
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    if source "$PROJECT_ROOT/.venv/bin/activate" && python -c "import openai" 2>/dev/null; then
        VERSION=$(python -c "import openai; print(openai.__version__)")
        echo -e "${GREEN}✓${NC} v$VERSION (in .venv)"
        deactivate
    else
        echo -e "${RED}✗ Not in venv${NC}"
        echo "   Install: cd $PROJECT_ROOT && source .venv/bin/activate && pip install openai"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠${NC}  No venv found, checking system Python"
    if python3 -c "import openai" 2>/dev/null; then
        VERSION=$(python3 -c "import openai; print(openai.__version__)")
        echo -e "${GREEN}✓${NC} v$VERSION"
    else
        echo -e "${RED}✗ Not installed${NC}"
        echo "   Install: pip install openai"
        exit 1
    fi
fi

# Check 4: Plan file exists
echo -n "Checking Hermes plan... "
if [ -f "$HOME/.hermes/plans/github-copilot-integration.md" ]; then
    echo -e "${GREEN}✓${NC} Found"
else
    echo -e "${RED}✗ Missing${NC}"
    echo "   Expected: ~/.hermes/plans/github-copilot-integration.md"
    exit 1
fi

# Check 5: Workspace config
echo -n "Checking workspace config... "
if [ -f "$PROJECT_ROOT/.hermes-workspace.yaml" ]; then
    echo -e "${GREEN}✓${NC} Found"
else
    echo -e "${YELLOW}⚠${NC}  Missing (optional)"
fi

# Check 6: Project structure
echo -n "Checking lightroom-tagger project... "
if [ -f "$PROJECT_ROOT/lightroom_tagger/core/providers.json" ]; then
    echo -e "${GREEN}✓${NC} Found"
else
    echo -e "${RED}✗ Project structure invalid${NC}"
    exit 1
fi

# Check 7: GitHub Copilot subscription (can't verify, just note)
echo -n "GitHub Copilot subscription... "
echo -e "${YELLOW}⚠${NC}  Cannot verify (manual check required)"

# Check 8: Port 3030 available
echo -n "Checking port 3030... "
if lsof -i :3030 &> /dev/null; then
    echo -e "${YELLOW}⚠${NC}  Port in use (gateway may be running)"
else
    echo -e "${GREEN}✓${NC} Available"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Summary:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✓${NC} All prerequisites met"
echo -e "${YELLOW}⚠${NC}  Manual: Verify GitHub Copilot Pro subscription active"
echo -e "${YELLOW}⚠${NC}  Manual: Create GitHub token during Task 3"
echo ""
echo "Ready to execute! Run:"
echo "  ./hermes-execute.sh"
echo ""
echo "Or start manually:"
echo "  cd /Users/ccanales/projects/lightroom-tagger"
echo "  hermes"
echo ""

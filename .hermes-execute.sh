#!/bin/bash
# Helper script to execute GitHub Copilot integration with Hermes Agent

set -e

PROJECT_ROOT="/Users/ccanales/projects/lightroom-tagger"
PLAN_FILE="$HOME/.hermes/plans/github-copilot-integration.md"

echo "🤖 Hermes Agent - GitHub Copilot Integration Helper"
echo "=================================================="
echo ""

# Check Hermes is installed
if ! command -v hermes &> /dev/null; then
    echo "❌ Hermes not found. Install with:"
    echo "   pip install hermes-agent"
    exit 1
fi

echo "✓ Hermes found: $(hermes --version | head -1)"

# Check plan exists
if [ ! -f "$PLAN_FILE" ]; then
    echo "❌ Plan file not found: $PLAN_FILE"
    echo "   Run this script from the project directory where setup was done"
    exit 1
fi

echo "✓ Plan found: $PLAN_FILE"

# Check project exists
if [ ! -d "$PROJECT_ROOT" ]; then
    echo "❌ Project not found: $PROJECT_ROOT"
    exit 1
fi

echo "✓ Project found: $PROJECT_ROOT"
echo ""

# Show instructions
cat <<'EOF'
📋 INSTRUCTIONS:

The plan is ready for Hermes to execute. You have TWO options:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPTION 1: Interactive Execution (Recommended)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Start Hermes:
   $ cd /Users/ccanales/projects/lightroom-tagger
   $ hermes

2. In Hermes chat, say:
   "Load and execute the GitHub Copilot integration plan at ~/.hermes/plans/github-copilot-integration.md"

3. Hermes will:
   - Read the plan
   - Execute each task sequentially
   - Pause at Task 3 for you to create GitHub token
   - Continue automatically after you provide token
   - Commit all changes when done

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPTION 2: Command-Line Direct Execution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Execute specific tasks:

# Task 1: Research gateway
$ hermes --exec "Execute Task 1 from ~/.hermes/plans/github-copilot-integration.md"

# All tasks:
$ hermes --exec "Execute all tasks from ~/.hermes/plans/github-copilot-integration.md, pause at Task 3 for user input"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  IMPORTANT - Task 3 Manual Step:

When Hermes reaches Task 3, you MUST manually:

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: read:user ✓, copilot ✓
4. Generate and copy token (starts with ghp_)
5. Edit .env.copilot and replace PLACEHOLDER with your token

Then tell Hermes: "Token configured, continue"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 Additional Resources:

- Full plan: ~/.hermes/plans/github-copilot-integration.md
- Original plan: docs/plans/2026-04-09-github-copilot-provider.md
- Workspace config: .hermes-workspace.yaml

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF

echo ""
echo "Ready to start? (Press Enter to launch Hermes, or Ctrl+C to cancel)"
read -r

# Launch Hermes in the project directory
cd "$PROJECT_ROOT"
exec hermes

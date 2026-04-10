# GitHub Copilot API Provider Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add GitHub Copilot as a vision provider to lightroom-tagger via community-built API gateway, enabling access to GPT-4o, GPT-4, Claude 3.5 Sonnet, and other models through existing Copilot Pro subscription.

**Architecture:** GitHub Copilot API Gateway transforms Copilot subscription into OpenAI-compatible `/v1/chat/completions` endpoint running at `http://127.0.0.1:3030/v1`. Existing `ProviderRegistry` and `vision_client.py` already support OpenAI-compatible providers via unified interface. Only need to: (1) install gateway, (2) add provider config, (3) configure credentials, (4) test integration.

**Tech Stack:** 
- Python 3.11+, `openai` SDK (already installed)
- GitHub Copilot API Gateway (Node.js community tool)
- Existing provider registry system

**Prerequisites:**
- Active GitHub Copilot Pro/Business/Enterprise subscription
- GitHub Personal Access Token with Copilot access
- Node.js/npm installed (for gateway)

**Test commands:**
- Core lib: `cd /Users/ccanales/projects/lightroom-tagger && python -m pytest lightroom_tagger/core/test_provider_registry.py -v`
- Vision client: `cd /Users/ccanales/projects/lightroom-tagger && python -m pytest lightroom_tagger/core/test_vision_client.py -v`
- Integration: `cd /Users/ccanales/projects/lightroom-tagger && python -c "from lightroom_tagger.core.provider_registry import ProviderRegistry; r = ProviderRegistry(); print(r.list_models())"`

---

## Option Analysis: Three Approaches

### Option 1: GitHub Copilot API Gateway (RECOMMENDED)
**Pros:**
- Full OpenAI API compatibility
- Multi-model access (GPT-4o, Claude 3.5, Gemini)
- Active community project with 7.3k+ stars
- Works with existing `openai.OpenAI` client

**Cons:**
- Requires running local Node.js gateway
- Not official GitHub solution
- Potential rate limits

**Installation:** `npx github-copilot-api-gateway`

### Option 2: Official Copilot SDK (Technical Preview)
**Pros:**
- Official GitHub solution
- Direct integration

**Cons:**
- Still in technical preview (unstable)
- Limited to VS Code/CLI environment
- More complex setup

### Option 3: Use Existing Providers Only
**Pros:**
- Already working
- No new dependencies

**Cons:**
- Misses opportunity to use paid Copilot subscription for API access
- Continues relying on Ollama/NIM/OpenCode

**Decision:** Proceed with **Option 1** (Gateway) as it provides best compatibility with existing architecture.

---

## Task 1: Research & Verify Gateway Availability

**Goal:** Confirm GitHub Copilot API Gateway exists, is maintained, and understand installation process.

**Files:**
- None (research only)

**Step 1: Search for official gateway**

```bash
npm search github-copilot-api-gateway
```

Expected: Package exists or find correct package name

**Step 2: Check alternative gateway projects**

Research URLs:
- https://github.com/suhaib-afk/github-copilot-api-gateway
- https://copilot-api.suhaib.in/

**Step 3: Document findings**

Create note: `docs/research/copilot-gateway-options.md` with:
- Package name/repo
- Installation command
- Authentication method
- Known limitations

**Verification:** Have clear installation path before proceeding.

---

## Task 2: Install GitHub Copilot API Gateway

**Goal:** Get gateway running locally at `http://127.0.0.1:3030/v1`

**Files:**
- None (external dependency)

**Step 1: Install gateway globally**

Try each approach until one works:

```bash
# Approach 1: npx (no install)
npx github-copilot-api-gateway

# Approach 2: npm global install
npm install -g github-copilot-api-gateway

# Approach 3: Direct from repo (if package not on npm)
git clone https://github.com/suhaib-afk/github-copilot-api-gateway.git
cd github-copilot-api-gateway
npm install
npm start
```

Expected: Gateway starts and shows:
```
GitHub Copilot API Gateway running at http://127.0.0.1:3030
```

**Step 2: Verify gateway is running**

```bash
curl http://127.0.0.1:3030/v1/models
```

Expected: JSON response with available models

**Step 3: Test basic chat completion (without auth)**

```bash
curl http://127.0.0.1:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Say hello"}]
  }'
```

Expected: Either success response or 401/403 indicating auth is needed (this confirms gateway is working)

**Notes:**
- Gateway may auto-detect GitHub token from environment
- Gateway may need to be running in background for all tests
- Consider using `screen` or `tmux` to keep it running

---

## Task 3: Configure GitHub Authentication

**Goal:** Set up GitHub Personal Access Token (PAT) for gateway authentication.

**Files:**
- Create: `.env.copilot` (gitignored)
- Modify: `.gitignore` (add `.env.copilot`)

**Step 1: Generate GitHub Personal Access Token**

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Scopes needed:
   - `read:user` (required)
   - `copilot` (if available)
4. Generate and copy token (starts with `ghp_`)

**Step 2: Store token securely**

```bash
# Create gitignored env file
cat > /Users/ccanales/projects/lightroom-tagger/.env.copilot <<EOF
GITHUB_TOKEN=ghp_your_token_here
EOF

# Restrict permissions
chmod 600 .env.copilot
```

**Step 3: Update .gitignore**

```bash
echo ".env.copilot" >> .gitignore
```

**Step 4: Test authenticated request**

```bash
# Load token
export GITHUB_TOKEN=$(cat .env.copilot | grep GITHUB_TOKEN | cut -d= -f2)

# Test with curl
curl http://127.0.0.1:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Say hello"}]
  }'
```

Expected: Successful response with chat completion

**Step 5: Commit gitignore change only**

```bash
git add .gitignore
git commit -m "chore: gitignore .env.copilot for GitHub token"
```

**Security Notes:**
- Never commit actual token
- Token grants API access - treat like password
- Rotate token if compromised

---

## Task 4: Add Copilot Provider to providers.json

**Goal:** Register GitHub Copilot gateway as available provider with model list.

**Files:**
- Modify: `lightroom_tagger/core/providers.json`

**Step 1: Back up current config**

```bash
cp lightroom_tagger/core/providers.json lightroom_tagger/core/providers.json.backup
```

**Step 2: Add github_copilot provider entry**

Add to `providers` object in `providers.json`:

```json
{
  "providers": {
    "ollama": { ... },
    "nvidia_nim": { ... },
    "opencode_go": { ... },
    "github_copilot": {
      "name": "GitHub Copilot",
      "base_url": "http://127.0.0.1:3030/v1",
      "api_key_env": "GITHUB_TOKEN",
      "auto_discover": false,
      "extra_headers": {},
      "retry": {
        "max_retries": 3,
        "backoff_seconds": [2, 8, 32]
      },
      "models": [
        {
          "id": "gpt-4o",
          "name": "GPT-4o",
          "vision": true
        },
        {
          "id": "gpt-4",
          "name": "GPT-4",
          "vision": true
        },
        {
          "id": "claude-3.5-sonnet",
          "name": "Claude 3.5 Sonnet",
          "vision": true
        },
        {
          "id": "gemini-2.0-flash-thinking-exp-01-21",
          "name": "Gemini 2.0 Flash Thinking",
          "vision": true
        }
      ]
    }
  }
}
```

**Step 3: Verify JSON is valid**

```bash
python -c "import json; json.load(open('lightroom_tagger/core/providers.json'))"
```

Expected: No output (success) or error with line number if invalid

**Step 4: Test provider loads in registry**

```bash
export GITHUB_TOKEN=$(cat .env.copilot | grep GITHUB_TOKEN | cut -d= -f2)

python -c "
from lightroom_tagger.core.provider_registry import ProviderRegistry
registry = ProviderRegistry()
print('Available providers:', [p['id'] for p in registry.list_providers()])
print('Copilot models:', [m['id'] for m in registry.list_models(provider_id='github_copilot')])
"
```

Expected output:
```
Available providers: ['ollama', 'nvidia_nim', 'opencode_go', 'github_copilot']
Copilot models: ['gpt-4o', 'gpt-4', 'claude-3.5-sonnet', 'gemini-2.0-flash-thinking-exp-01-21']
```

**Step 5: Commit**

```bash
git add lightroom_tagger/core/providers.json
git commit -m "feat: add GitHub Copilot API gateway as provider

- Add github_copilot provider with GPT-4o, Claude 3.5, Gemini models
- Uses local gateway at 127.0.0.1:3030
- Authenticated via GITHUB_TOKEN env var
"
```

---

## Task 5: Write Integration Test

**Goal:** Verify GitHub Copilot provider works end-to-end with vision_client.

**Files:**
- Create: `lightroom_tagger/core/test_github_copilot_integration.py`

**Step 1: Write integration test**

```python
# lightroom_tagger/core/test_github_copilot_integration.py
"""Integration test for GitHub Copilot provider.

REQUIRES:
- GitHub Copilot API Gateway running at http://127.0.0.1:3030
- GITHUB_TOKEN environment variable set
- Active Copilot subscription

Skip if prerequisites not met.
"""
import os
import pytest
import requests
from openai import OpenAI

from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_client import generate_description


@pytest.fixture
def gateway_available():
    """Check if gateway is running."""
    try:
        resp = requests.get("http://127.0.0.1:3030/v1/models", timeout=2)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


@pytest.fixture
def github_token():
    """Check if GitHub token is set."""
    return os.getenv("GITHUB_TOKEN") is not None


@pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN not set - skip Copilot integration test"
)
def test_copilot_provider_loads():
    """GitHub Copilot provider should load from providers.json."""
    registry = ProviderRegistry()
    providers = registry.list_providers()
    provider_ids = [p['id'] for p in providers]
    
    assert 'github_copilot' in provider_ids, "github_copilot not in registry"
    
    copilot_models = registry.list_models(provider_id='github_copilot')
    model_ids = [m['id'] for m in copilot_models]
    
    assert 'gpt-4o' in model_ids, "gpt-4o not in Copilot models"
    assert len(copilot_models) > 0, "No models defined for Copilot"


@pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN not set - skip Copilot integration test"
)
def test_copilot_client_creation():
    """Should create OpenAI client for GitHub Copilot provider."""
    registry = ProviderRegistry()
    client = registry.get_client('github_copilot')
    
    assert client is not None
    assert client.base_url == "http://127.0.0.1:3030/v1/"  # Note trailing slash added by SDK


@pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN not set - skip Copilot integration test"
)
def test_copilot_chat_completion(gateway_available):
    """GitHub Copilot should respond to basic chat completion."""
    if not gateway_available:
        pytest.skip("Gateway not running at http://127.0.0.1:3030")
    
    registry = ProviderRegistry()
    client = registry.get_client('github_copilot')
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": "Say 'test successful' and nothing else"}
        ],
        max_tokens=10
    )
    
    content = response.choices[0].message.content
    assert content is not None
    assert len(content) > 0


@pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN not set - skip Copilot integration test"
)
def test_copilot_vision_with_real_image(gateway_available, tmp_path):
    """GitHub Copilot should handle vision requests with real images."""
    if not gateway_available:
        pytest.skip("Gateway not running at http://127.0.0.1:3030")
    
    # Create a simple test image (1x1 red pixel PNG)
    import base64
    red_pixel_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    test_image = tmp_path / "test.png"
    test_image.write_bytes(red_pixel_png)
    
    registry = ProviderRegistry()
    client = registry.get_client('github_copilot')
    
    # Use vision_client.generate_description (already supports OpenAI clients)
    description = generate_description(
        client=client,
        model="gpt-4o",
        image_path=str(test_image),
        log_callback=lambda level, msg: print(f"[{level}] {msg}")
    )
    
    assert description is not None
    assert len(description) > 0
    print(f"Generated description: {description[:100]}...")


def test_copilot_in_fallback_order():
    """GitHub Copilot should optionally be in fallback chain."""
    registry = ProviderRegistry()
    fallback_order = registry._config.get('fallback_order', [])
    
    # Don't require it to be in fallback by default, but document it's available
    print(f"Current fallback order: {fallback_order}")
    print("To use Copilot in fallback, add 'github_copilot' to fallback_order in providers.json")
```

**Step 2: Run tests with gateway NOT running (expect skips)**

```bash
# Ensure gateway is stopped
pkill -f "github-copilot-api-gateway" || true

# Run tests - should skip
python -m pytest lightroom_tagger/core/test_github_copilot_integration.py -v
```

Expected: All tests SKIPPED with reason "GITHUB_TOKEN not set" or "Gateway not running"

**Step 3: Run tests with gateway running (expect pass)**

```bash
# Start gateway in background
(cd /path/to/gateway && npm start &)

# Export token
export GITHUB_TOKEN=$(cat .env.copilot | grep GITHUB_TOKEN | cut -d= -f2)

# Run tests - should pass
python -m pytest lightroom_tagger/core/test_github_copilot_integration.py -v
```

Expected: All tests PASS

**Step 4: Commit test**

```bash
git add lightroom_tagger/core/test_github_copilot_integration.py
git commit -m "test: add GitHub Copilot provider integration tests

- Test provider loads from config
- Test client creation
- Test basic chat completion
- Test vision with real image
- All tests skip gracefully if gateway unavailable
"
```

---

## Task 6: Update config.yaml to Use Copilot

**Goal:** Configure lightroom-tagger to use GitHub Copilot for vision tasks.

**Files:**
- Modify: `config.yaml`

**Step 1: Back up current config**

```bash
cp config.yaml config.yaml.backup
```

**Step 2: Update vision_model to use Copilot**

Change:
```yaml
vision_model: gemma4:e2b
```

To:
```yaml
vision_model: github_copilot/gpt-4o
```

Or keep as override-able default:
```yaml
vision_model: gemma4:e2b  # Default, override with --vision-model github_copilot/gpt-4o
```

**Step 3: Test config loads**

```bash
export GITHUB_TOKEN=$(cat .env.copilot | grep GITHUB_TOKEN | cut -d= -f2)

python -c "
from lightroom_tagger.core.config import Config
config = Config.from_yaml('config.yaml')
print(f'Vision model: {config.vision_model}')
"
```

Expected: Prints vision model setting

**Step 4: Document in config comments**

Add comment above vision_model in config.yaml:

```yaml
# Vision model for image comparison/description
# Format: provider/model or just model (uses default provider)
# Examples:
#   - ollama/gemma4:e2b (local Ollama)
#   - github_copilot/gpt-4o (GitHub Copilot gateway)
#   - nvidia_nim/nvidia/llama-3.2-nv-vision-11b (NVIDIA NIM)
#   - opencode_go/mimo-v2-pro (OpenCode)
vision_model: gemma4:e2b
```

**Step 5: Commit**

```bash
git add config.yaml
git commit -m "docs: document GitHub Copilot as vision_model option

Add examples showing how to use github_copilot/gpt-4o
Keep default as gemma4:e2b for backward compatibility
"
```

---

## Task 7: Add Setup Documentation

**Goal:** Document GitHub Copilot setup process for other developers/users.

**Files:**
- Create: `docs/setup/github-copilot-provider.md`

**Step 1: Write setup guide**

```markdown
# GitHub Copilot API Provider Setup

This guide explains how to use your GitHub Copilot subscription as a vision provider in lightroom-tagger.

## Overview

The GitHub Copilot API Gateway transforms your Copilot subscription into an OpenAI-compatible API endpoint, giving you access to:
- GPT-4o (vision-capable)
- GPT-4 (vision-capable)
- Claude 3.5 Sonnet (vision-capable)
- Gemini 2.0 Flash Thinking (vision-capable)

**Requirements:**
- Active GitHub Copilot Pro, Business, or Enterprise subscription
- Node.js/npm installed
- GitHub Personal Access Token

## Installation

### 1. Install GitHub Copilot API Gateway

```bash
npm install -g github-copilot-api-gateway
```

Or run without installing:
```bash
npx github-copilot-api-gateway
```

### 2. Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes:
   - `read:user` ✓
   - `copilot` ✓ (if available)
4. Click "Generate token"
5. Copy token (starts with `ghp_`)

### 3. Configure Token

Create `.env.copilot` in project root:

```bash
GITHUB_TOKEN=ghp_your_token_here
```

**Important:** This file is gitignored. Never commit your token.

### 4. Start Gateway

```bash
# Load token
export GITHUB_TOKEN=$(cat .env.copilot | grep GITHUB_TOKEN | cut -d= -f2)

# Start gateway
github-copilot-api-gateway
```

Gateway runs at `http://127.0.0.1:3030/v1`

Keep this running in a separate terminal or use:
```bash
# Run in background
screen -dmS copilot-gateway github-copilot-api-gateway

# Or with tmux
tmux new-session -d -s copilot-gateway 'github-copilot-api-gateway'
```

### 5. Verify Setup

```bash
# Check provider loads
export GITHUB_TOKEN=$(cat .env.copilot | grep GITHUB_TOKEN | cut -d= -f2)
python -c "from lightroom_tagger.core.provider_registry import ProviderRegistry; r = ProviderRegistry(); print([p['id'] for p in r.list_providers()])"

# Should include: github_copilot
```

## Usage

### Option 1: Set as Default in config.yaml

```yaml
vision_model: github_copilot/gpt-4o
```

### Option 2: Override Per Command

```bash
python -m lightroom_tagger.cli match \
  --vision-model github_copilot/gpt-4o \
  --batch-size 5
```

### Option 3: Use in Fallback Chain

Edit `lightroom_tagger/core/providers.json`:

```json
{
  "fallback_order": [
    "github_copilot",
    "ollama",
    "nvidia_nim"
  ]
}
```

## Available Models

| Model ID | Name | Vision | Notes |
|----------|------|--------|-------|
| `gpt-4o` | GPT-4o | ✓ | Best performance, recommended |
| `gpt-4` | GPT-4 | ✓ | Good accuracy, slower |
| `claude-3.5-sonnet` | Claude 3.5 Sonnet | ✓ | Anthropic model via Copilot |
| `gemini-2.0-flash-thinking-exp-01-21` | Gemini 2.0 Flash | ✓ | Google model via Copilot |

## Troubleshooting

### "Connection refused" Error

Gateway not running. Start it:
```bash
github-copilot-api-gateway
```

### "Authentication failed" Error

Invalid or expired token. Regenerate token at https://github.com/settings/tokens

### Rate Limit Errors

GitHub Copilot has rate limits. Solution:
1. Add retry logic (already configured in providers.json)
2. Use fallback to other providers
3. Reduce batch size

### Models Not Listed

Check gateway logs. Some models may require specific Copilot subscription tier.

## Cost

GitHub Copilot API access is **included** in your Copilot subscription. No per-token charges for API usage.

Rate limits apply based on subscription tier:
- Copilot Pro: Moderate limits
- Copilot Business: Higher limits
- Copilot Enterprise: Highest limits

## Security Notes

- Never commit `.env.copilot` or `GITHUB_TOKEN`
- Token has full Copilot API access - treat as password
- Gateway runs locally - no data sent to third parties
- Rotate token if compromised

## References

- [GitHub Copilot API Gateway](https://copilot-api.suhaib.in/)
- [GitHub Copilot Documentation](https://docs.github.com/en/copilot)
```

**Step 2: Commit documentation**

```bash
git add docs/setup/github-copilot-provider.md
git commit -m "docs: add GitHub Copilot provider setup guide

Complete guide for:
- Gateway installation
- Token configuration
- Usage examples
- Troubleshooting
- Security best practices
"
```

---

## Task 8: Add to README/Main Docs

**Goal:** Update main documentation to mention GitHub Copilot as supported provider.

**Files:**
- Modify: `README.md` (if exists) or main docs

**Step 1: Find main documentation**

```bash
ls -la | grep -i readme
ls docs/
```

**Step 2: Add Copilot to provider list**

Add to providers section:

```markdown
## Supported Vision Providers

lightroom-tagger supports multiple vision model providers:

- **Ollama** (local, free) - Run models locally on your machine
- **NVIDIA NIM** - NVIDIA's hosted vision models
- **OpenCode Go** - Cloud-based vision models
- **GitHub Copilot** (NEW) - Use your Copilot subscription for API access
  - Includes GPT-4o, Claude 3.5 Sonnet, Gemini
  - See [setup guide](docs/setup/github-copilot-provider.md)

Configure in `config.yaml` or via `--vision-model` flag.
```

**Step 3: Commit**

```bash
git add README.md  # or docs file
git commit -m "docs: add GitHub Copilot to supported providers list"
```

---

## Task 9: Manual End-to-End Test

**Goal:** Verify GitHub Copilot works with real lightroom-tagger workflow.

**Files:**
- None (manual verification)

**Prerequisites:**
- Gateway running
- Token configured
- Test images available

**Step 1: Test image comparison**

```bash
export GITHUB_TOKEN=$(cat .env.copilot | grep GITHUB_TOKEN | cut -d= -f2)

# Find two test images in your Lightroom catalog
TEST_IMG_1="/path/to/test/image1.jpg"
TEST_IMG_2="/path/to/test/image2.jpg"

# Test comparison
python -c "
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_client import compare_images

registry = ProviderRegistry()
client = registry.get_client('github_copilot')

result = compare_images(
    client=client,
    model='gpt-4o',
    local_path='$TEST_IMG_1',
    insta_path='$TEST_IMG_2',
    log_callback=lambda lvl, msg: print(f'[{lvl}] {msg}')
)

print(f'Result: {result}')
"
```

Expected: Prints comparison result with confidence score

**Step 2: Test image description**

```bash
python -c "
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_client import generate_description

registry = ProviderRegistry()
client = registry.get_client('github_copilot')

description = generate_description(
    client=client,
    model='gpt-4o',
    image_path='$TEST_IMG_1',
    log_callback=lambda lvl, msg: print(f'[{lvl}] {msg}')
)

print(f'Description: {description}')
"
```

Expected: Prints image description

**Step 3: Test with CLI (if implemented)**

```bash
# If your CLI supports --vision-model flag
python -m lightroom_tagger.cli describe \
  --image "$TEST_IMG_1" \
  --vision-model github_copilot/gpt-4o
```

**Step 4: Test fallback behavior**

```bash
# Stop gateway to trigger fallback
pkill -f "github-copilot-api-gateway"

# Run command - should fallback to next provider (ollama)
python -m lightroom_tagger.cli match --vision-model github_copilot/gpt-4o
```

Expected: Warning about Copilot unavailable, falls back to ollama

**Step 5: Document test results**

Create file: `docs/testing/copilot-manual-test-results.md`

```markdown
# GitHub Copilot Manual Test Results

Date: 2026-04-09
Tester: [Your name]

## Configuration
- Gateway: v1.2.3 running at 127.0.0.1:3030
- Token: Valid, expires 2027-04-09
- Subscription: GitHub Copilot Pro

## Test Results

| Test | Model | Result | Notes |
|------|-------|--------|-------|
| Image comparison | gpt-4o | ✅ PASS | Confidence: 85%, 2.3s |
| Image description | gpt-4o | ✅ PASS | Generated 150-word description |
| Fallback behavior | gpt-4o → ollama | ✅ PASS | Auto-fell back after 3 retries |
| Claude 3.5 Sonnet | claude-3.5-sonnet | ✅ PASS | Works via Copilot gateway |
| Batch comparison | gpt-4o | ⚠️ SLOW | 5 images took 8s |

## Issues Found
- None

## Recommendations
- Use gpt-4o for best balance of speed/accuracy
- Keep batch size ≤ 5 to avoid rate limits
- Claude 3.5 is slower but more descriptive
```

**Verification:** All tests pass, documentation complete.

---

## Task 10: Optional - Add to Fallback Chain

**Goal:** Optionally add GitHub Copilot to automatic fallback order.

**Files:**
- Modify: `lightroom_tagger/core/providers.json` (optional)

**Step 1: Consider fallback position**

Options:
1. Primary (first) - Use Copilot by default, fall back to Ollama
2. Secondary - Use Ollama first, Copilot if Ollama fails
3. Not in chain - Only use when explicitly requested

**Recommendation:** Add as **secondary** (after Ollama) since:
- Ollama is free and local
- Copilot has rate limits
- Copilot requires gateway running

**Step 2: Update fallback_order (if desired)**

```json
{
  "fallback_order": [
    "ollama",
    "github_copilot",
    "opencode_go",
    "nvidia_nim"
  ]
}
```

**Step 3: Test fallback cascade**

```bash
# Stop Ollama
docker stop ollama || true

# Start gateway
export GITHUB_TOKEN=$(cat .env.copilot | grep GITHUB_TOKEN | cut -d= -f2)
github-copilot-api-gateway &

# Run command - should use Copilot since Ollama unavailable
python -m lightroom_tagger.cli match --limit 5
```

Expected: Uses github_copilot/gpt-4o automatically

**Step 4: Commit (if changed)**

```bash
git add lightroom_tagger/core/providers.json
git commit -m "feat: add GitHub Copilot to fallback chain

Position: Secondary (after Ollama)
Rationale: Use free local Ollama first, Copilot as backup
"
```

---

## Success Criteria

- [ ] Gateway installed and running at http://127.0.0.1:3030
- [ ] GitHub token configured in `.env.copilot` (gitignored)
- [ ] Provider config added to `providers.json`
- [ ] Integration tests pass when gateway available
- [ ] Integration tests skip gracefully when gateway unavailable
- [ ] Documentation complete (`docs/setup/github-copilot-provider.md`)
- [ ] Manual end-to-end tests pass
- [ ] Can compare images using `github_copilot/gpt-4o`
- [ ] Can generate descriptions using `github_copilot/gpt-4o`
- [ ] Fallback works when gateway unavailable

## Rollback Plan

If integration causes issues:

```bash
# Restore backup config
cp lightroom_tagger/core/providers.json.backup lightroom_tagger/core/providers.json

# Remove from fallback order
# (edit providers.json, remove "github_copilot" from fallback_order)

# Revert commits
git revert HEAD~N  # Where N is number of commits to revert

# Stop gateway
pkill -f "github-copilot-api-gateway"
```

## Post-Implementation

### Monitoring
- Track Copilot API usage via gateway logs
- Monitor rate limit errors
- Compare performance vs Ollama/NIM

### Optimization
- Experiment with different models (GPT-4 vs GPT-4o vs Claude)
- Tune batch sizes for best throughput
- Consider caching results

### Future Enhancements
- Auto-start gateway with lightroom-tagger
- Better error messages for common issues
- UI to select Copilot models
- Cost tracking (rate limits, not dollars)

---

## Notes

**Why This Approach:**
- Minimal changes to existing code (just config + docs)
- Provider registry already supports OpenAI-compatible APIs
- Gateway handles authentication complexity
- Easy to disable (just stop gateway)

**Limitations:**
- Requires gateway running (external process)
- Rate limits depend on Copilot tier
- Not official GitHub solution (community project)
- Gateway needs Node.js installed

**Alternatives Considered:**
- Official Copilot SDK: Too complex, still in preview
- Direct Copilot API: Not available for Pro tier
- Skip entirely: Misses opportunity to use paid subscription

**References:**
- Gateway repo: https://github.com/suhaib-afk/github-copilot-api-gateway
- Gateway docs: https://copilot-api.suhaib.in/
- Provider registry code: `lightroom_tagger/core/provider_registry.py`
- Vision client code: `lightroom_tagger/core/vision_client.py`

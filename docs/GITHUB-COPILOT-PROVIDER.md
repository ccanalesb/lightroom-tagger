# GitHub Copilot Provider for Lightroom Tagger

GitHub Copilot has been added as a vision provider to lightroom-tagger, giving you access to GPT-4o, Claude, and Gemini models for image analysis.

---

## ✅ What's Available

### Models Added

All models support vision capabilities:

| Model | Cost | Best For | Vision Quality |
|-------|------|----------|----------------|
| **gpt-4o** | FREE (unlimited) | General image analysis | ⭐⭐⭐⭐⭐ |
| **gpt-4.1** | FREE (unlimited) | Alternative style | ⭐⭐⭐⭐⭐ |
| **gpt-5-mini** | FREE (unlimited) | Quick descriptions | ⭐⭐⭐⭐ |
| **claude-sonnet-4.5** | 💎 1x (300/mo) | Creative descriptions | ⭐⭐⭐⭐⭐ |
| **claude-opus-4.5** | 💎 3x (100/mo) | Best quality | ⭐⭐⭐⭐⭐ |
| **gemini-2.5-pro** | 💎 1x (300/mo) | Detailed analysis | ⭐⭐⭐⭐⭐ |

---

## 🚀 Usage

### CLI Usage

```bash
# Use GitHub Copilot with default model (gpt-4o)
python -m lightroom_tagger.cli describe \
    --provider github_copilot \
    --model gpt-4o \
    /path/to/image.jpg

# Use Claude for creative descriptions
python -m lightroom_tagger.cli describe \
    --provider github_copilot \
    --model claude-sonnet-4.5 \
    /path/to/image.jpg

# Batch processing with GPT-4o (unlimited!)
python -m lightroom_tagger.cli batch \
    --provider github_copilot \
    --model gpt-4o \
    --catalog ~/lightroom/catalog.lrcat
```

### Python API Usage

```python
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_client import generate_description

# Get GitHub Copilot client
registry = ProviderRegistry()
client = registry.get_client('github_copilot')

# Generate description with GPT-4o (unlimited)
description = generate_description(
    client=client,
    model="gpt-4o",
    image_path="/path/to/image.jpg"
)

# Use Claude for creative descriptions (premium)
description = generate_description(
    client=client,
    model="claude-sonnet-4.5",
    image_path="/path/to/image.jpg"
)
```

---

## 💰 Cost Strategy

### Recommended Workflow

**For large batches (1000+ photos):**
```bash
# Use gpt-4o - it's UNLIMITED and excellent
python -m lightroom_tagger.cli batch \
    --provider github_copilot \
    --model gpt-4o \
    --catalog ~/lightroom/catalog.lrcat
```

**For special photos (portfolio):**
```bash
# Use Claude Opus for highest quality descriptions
python -m lightroom_tagger.cli describe \
    --provider github_copilot \
    --model claude-opus-4.5 \
    /path/to/portfolio/best-shot.jpg
```

**Budget breakdown:**
- Daily batch tagging (100 photos/day): Use `gpt-4o` → FREE ✅
- Special descriptions (~10/day): Use `claude-sonnet-4.5` → 300 requests/month 💎
- Best shots (rare): Use `claude-opus-4.5` → 100 requests/month 💎

---

## 📊 Provider Priority

GitHub Copilot is now the **first fallback** in the provider chain:

```
1. github_copilot (preferred - GPT-4o unlimited)
2. ollama (local models)
3. opencode_go (MiMo-V2, etc.)
4. nvidia_nim (cloud fallback)
```

This means if you don't specify a provider, lightroom-tagger will try GitHub Copilot first!

---

## 🔧 Configuration

The provider is configured in `lightroom_tagger/core/providers.json`:

```json
{
  "providers": {
    "github_copilot": {
      "name": "GitHub Copilot",
      "base_url": "http://127.0.0.1:4141/v1",
      "api_key": "dummy",
      "auto_discover": false,
      "models": [
        {"id": "gpt-4o", "name": "GPT-4o", "vision": true},
        {"id": "claude-sonnet-4.5", "name": "Claude Sonnet 4.5", "vision": true}
      ]
    }
  },
  "fallback_order": ["github_copilot", "ollama", "opencode_go", "nvidia_nim"]
}
```

---

## 🧪 Testing

### Test provider availability

```bash
cd /Users/ccanales/projects/lightroom-tagger
source .venv/bin/activate

python << 'EOF'
from lightroom_tagger.core.provider_registry import ProviderRegistry

registry = ProviderRegistry()
providers = registry.list_providers()

for p in providers:
    status = "✅" if p["available"] else "⚠️"
    print(f"{status} {p['id']}: {p['name']}")
EOF
```

Expected output:
```
✅ ollama: Ollama (Local)
⚠️ nvidia_nim: NVIDIA NIM
⚠️ opencode_go: OpenCode Go
✅ github_copilot: GitHub Copilot
```

### Test vision with sample image

```bash
python -m lightroom_tagger.cli describe \
    --provider github_copilot \
    --model gpt-4o \
    ~/Pictures/test-photo.jpg
```

---

## ⚠️ Extended Thinking and `copilot-api-plus`

### The Problem

`copilot-api-plus` automatically injects `thinking_budget` (extended thinking) into every request sent to Claude models. For vision comparison calls, this causes a guaranteed `400 Bad Request` because the injected `thinking.budget_tokens` exceeds `max_tokens`:

```
max_tokens must be greater than thinking.budget_tokens
```

No value of `max_tokens` fixes this — the proxy computes `thinking_budget` from model capabilities and it's always larger than any reasonable `max_tokens` for a structured JSON response.

### The Fix

Vision comparison calls (`compare_images`, `compare_images_batch`) send `extra_body={"reasoning_effort": "none"}` which tells the proxy to skip its automatic thinking injection (see `injectThinking()` in the proxy source — it short-circuits when `reasoning_effort` is already present).

Description generation (`generate_description`) does **not** disable thinking, so Claude's extended reasoning is available when generating rich, structured image descriptions.

### Why Only Vision Comparisons?

| Call Type | Thinking | Reason |
|-----------|----------|--------|
| `compare_images` | Disabled | Returns tiny JSON (`{"confidence": 85, "verdict": "MATCH"}`). Thinking wastes tokens and triggers budget conflicts. |
| `compare_images_batch` | Disabled | Same — structured JSON output, many images per call. |
| `generate_description` | Enabled | Long-form creative output benefits from reasoning. The proxy's `thinking_budget` is sized for the model's `max_output_tokens`, so `max_tokens=2048` works when thinking adds depth. |

### Diagnosing the Issue

If you see repeated `ContextLengthError` or `400 Bad Request` from Claude models via GitHub Copilot, check:

```bash
# 1. Verify copilot-api-plus is the proxy
ps aux | grep copilot-api

# 2. Test directly — should succeed with reasoning_effort override
python -c "
from lightroom_tagger.core.provider_registry import ProviderRegistry
registry = ProviderRegistry()
client = registry.get_client('github_copilot')
resp = client.chat.completions.create(
    model='claude-sonnet-4.5',
    messages=[{'role': 'user', 'content': 'Say hello'}],
    max_tokens=256,
    extra_body={'reasoning_effort': 'none'},
)
print(resp.choices[0].message.content)
"

# 3. This will FAIL without the override (proxy injects thinking)
python -c "
from lightroom_tagger.core.provider_registry import ProviderRegistry
registry = ProviderRegistry()
client = registry.get_client('github_copilot')
resp = client.chat.completions.create(
    model='claude-sonnet-4.5',
    messages=[{'role': 'user', 'content': 'Say hello'}],
    max_tokens=256,
)
print(resp.choices[0].message.content)
"
```

### Defensive Layers

Even if the proxy behavior changes, the codebase has defensive layers:

1. **Error classification**: `budget_tokens` / `thinking` errors → `ContextLengthError`
2. **`max_tokens` escalation**: Tries 256 → 4096 → 32768 → 65536 before giving up
3. **Provider blacklisting**: After exhausting escalation, marks the provider+model as broken for the session — subsequent candidates skip instantly to fallback
4. **Batch chunk halving**: `PayloadTooLargeError` (413) triggers recursive chunk splitting
5. **Consecutive fatal abort**: 3+ consecutive `InvalidRequestError` in sequential mode aborts remaining candidates

---

## 🆘 Troubleshooting

### Provider shows as unavailable

```bash
# Check gateway is running
lsof -i :4141

# Should show: copilot-api-plus listening on port 4141
# If not running:
nohup npx copilot-api-plus start > ~/copilot-gateway.log 2>&1 &
echo $! > ~/copilot-gateway.pid
```

### "Connection refused" errors

```bash
# Verify gateway is accessible
curl http://127.0.0.1:4141/v1/models

# Should return JSON with models
# If empty or error, restart gateway:
kill $(cat ~/copilot-gateway.pid)
nohup npx copilot-api-plus start > ~/copilot-gateway.log 2>&1 &
echo $! > ~/copilot-gateway.pid
```

### Models not appearing

Make sure you've authenticated:
```bash
npx copilot-api-plus auth
```

Then restart the gateway.

---

## 📈 Performance Comparison

Based on testing with lightroom-tagger workload:

| Provider | Model | Speed | Cost | Quality |
|----------|-------|-------|------|---------|
| Ollama | llava | ⚡⚡⚡⚡ | FREE | ⭐⭐⭐ |
| GitHub Copilot | gpt-4o | ⚡⚡⚡ | FREE | ⭐⭐⭐⭐⭐ |
| GitHub Copilot | claude-sonnet-4.5 | ⚡⚡⚡ | 1x | ⭐⭐⭐⭐⭐ |
| GitHub Copilot | claude-opus-4.5 | ⚡⚡ | 3x | ⭐⭐⭐⭐⭐ |
| OpenCode Go | mimo-v2-pro | ⚡⚡⚡ | Paid | ⭐⭐⭐⭐ |

**Recommendation:** Use `gpt-4o` as your default for batch processing. It's unlimited, fast, and produces excellent descriptions.

---

## 🎯 Real-World Usage

### Scenario 1: Tagging entire Lightroom catalog

```bash
# Tag all untagged photos with GPT-4o (unlimited)
python -m lightroom_tagger.cli batch \
    --provider github_copilot \
    --model gpt-4o \
    --catalog ~/lightroom/FinalCatalog.lrcat \
    --filter "rating >= 3"

# No cost concerns! Process 10,000+ photos freely
```

### Scenario 2: Portfolio curation

```bash
# Use Claude Opus for your best 50 portfolio shots
python -m lightroom_tagger.cli batch \
    --provider github_copilot \
    --model claude-opus-4.5 \
    --catalog ~/lightroom/FinalCatalog.lrcat \
    --filter "rating = 5 AND collection = 'Portfolio'"

# Costs: 50 photos × 3x multiplier = 150 premium requests
# Still within 300/month budget!
```

### Scenario 3: Mixed strategy

```python
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_client import generate_description

registry = ProviderRegistry()
client = registry.get_client('github_copilot')

def smart_describe(photo_path, rating):
    """Use premium models only for high-rated photos"""
    if rating >= 5:
        # Best shots: Use Claude Opus
        model = "claude-opus-4.5"
    elif rating >= 4:
        # Good shots: Use Claude Sonnet
        model = "claude-sonnet-4.5"
    else:
        # Everything else: Use GPT-4o (unlimited)
        model = "gpt-4o"
    
    return generate_description(
        client=client,
        model=model,
        image_path=photo_path
    )
```

---

## 🔗 Related Documentation

- **Hermes setup:** `~/.hermes/MODEL-SWITCHING-GUIDE.md`
- **OpenWebUI setup:** `~/openwebui-setup-instructions.txt`
- **Gateway management:** `~/COPILOT-SETUP-COMPLETE.md`
- **Lightroom Tagger docs:** `docs/` directory

---

## 🎉 Summary

GitHub Copilot is now available in lightroom-tagger with:

✅ 6 vision models (3 unlimited + 3 premium)
✅ Highest priority in fallback chain
✅ Unlimited batch tagging with GPT-4o
✅ Premium models for special photos
✅ Same gateway as Hermes and OpenWebUI

**Start using it now:**

```bash
cd /Users/ccanales/projects/lightroom-tagger
source .venv/bin/activate

python -m lightroom_tagger.cli describe \
    --provider github_copilot \
    --model gpt-4o \
    ~/Pictures/test.jpg
```

Enjoy unlimited AI-powered photo descriptions! 📸✨

# Hermes Agent Quick Start Guide

## TL;DR - Run the Integration Now

```bash
cd /Users/ccanales/projects/lightroom-tagger
./.hermes-execute.sh
```

When Hermes pauses at Task 3:
1. Go to https://github.com/settings/tokens
2. Create token with `read:user` + `copilot` scopes
3. Edit `.env.copilot` and paste your token
4. Tell Hermes: "Token configured, continue"

Done! 🎉

---

## What This Does

Adds GitHub Copilot API access to your lightroom-tagger vision providers.

**Before:**
- Ollama (local)
- NVIDIA NIM (cloud)
- OpenCode Go (cloud)

**After:**
- ✅ GitHub Copilot (GPT-4o, Claude 3.5, Gemini)
- Ollama (local)
- NVIDIA NIM (cloud)
- OpenCode Go (cloud)

---

## Three Ways to Execute

### 1. Guided Helper (Recommended)
```bash
./.hermes-execute.sh
```
Shows instructions and launches Hermes.

### 2. Direct Hermes
```bash
cd /Users/ccanales/projects/lightroom-tagger
hermes
```
Then say: "Execute ~/.hermes/plans/github-copilot-integration.md"

### 3. One-Liner
```bash
hermes --exec "Execute plan at ~/.hermes/plans/github-copilot-integration.md"
```

---

## Validate Setup First

```bash
./.hermes-validate.sh
```

This checks:
- ✓ Hermes installed
- ✓ Node.js installed  
- ✓ Python openai SDK
- ✓ Plan file exists
- ✓ Project structure valid

---

## After Integration Complete

**Test it works:**
```bash
# Set token
export GITHUB_TOKEN=$(grep GITHUB_TOKEN .env.copilot | cut -d= -f2)

# Use Copilot for image description
python -m lightroom_tagger.cli describe \
  --image /path/to/test.jpg \
  --vision-model github_copilot/gpt-4o
```

**Or update config.yaml:**
```yaml
vision_model: github_copilot/gpt-4o  # Was: gemma4:e2b
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `.hermes-execute.sh` | Interactive launcher with pre-flight checks |
| `.hermes-validate.sh` | Validate all prerequisites met |
| `.hermes-workspace.yaml` | Project-specific Hermes config |
| `.hermes-README.md` | Detailed setup documentation |
| `HERMES-QUICKSTART.md` | This file (quick reference) |
| `~/.hermes/plans/github-copilot-integration.md` | Executable plan for Hermes |
| `docs/plans/2026-04-09-github-copilot-provider.md` | Original detailed plan |

---

## Troubleshooting

**Hermes says "Plan not found"**
```bash
ls ~/.hermes/plans/github-copilot-integration.md
```
If missing, plan wasn't copied. Re-run setup.

**Gateway fails to start**
```bash
# Check port 3030
lsof -i :3030

# Kill if stuck
pkill -f "copilot-api-gateway"
```

**Token rejected**
- Verify token starts with `ghp_`
- Check it has `copilot` scope
- Regenerate at https://github.com/settings/tokens

**Hermes can't find Python modules**
```bash
cd /Users/ccanales/projects/lightroom-tagger
export PYTHONPATH=$(pwd)
hermes
```

---

## Cost

**$0** - Uses your existing Copilot Pro subscription. No additional charges.

Rate limits apply based on subscription tier.

---

## What Happens Next

1. Hermes installs gateway
2. You create GitHub token (2 min)
3. Hermes configures everything
4. Hermes writes tests
5. Hermes runs E2E validation
6. Hermes commits changes
7. ✅ Done! Use `github_copilot/gpt-4o` in your project

---

**Questions?** Read `.hermes-README.md` for detailed info.

**Ready?** Run: `./.hermes-execute.sh`

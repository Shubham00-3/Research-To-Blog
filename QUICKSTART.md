# Quick Start Guide

Get up and running with the Research-to-Blog pipeline in 5 minutes.

## Prerequisites

- Python 3.11 or higher
- [Groq API key](https://console.groq.com) (free tier)

## Step 1: Installation

```bash
# Clone and setup
git clone https://github.com/yourusername/research-to-blog.git
cd research-to-blog

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configuration

```bash
# Copy environment template
cp env.example .env

# Edit .env and add your Groq API key
# Get free key at: https://console.groq.com
nano .env  # or use any editor
```

Minimal `.env` configuration:
```bash
GROQ_API_KEY=your_key_here
```

## Step 3: Run Your First Pipeline

### Using CLI

```bash
python -m app.cli.main run "How AI is changing software development" \
  --audience "developers"
```

Output will be saved to `./outputs/{run_id}.md` and `./outputs/{run_id}.json`

### Using the API

**Start the server:**
```bash
uvicorn app.api.server:app --reload
```

**Make a request:**
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "How AI is changing software development",
    "audience": "developers"
  }'
```

**Check results:**
```bash
# Get the run_id from the response above
curl http://localhost:8000/runs/{run_id}
curl http://localhost:8000/runs/{run_id}/markdown
```

## Step 4: View Results

Your generated article will include:

- ✅ Well-structured content with engaging narrative
- ✅ Inline citations [1], [2] for every claim
- ✅ Complete bibliography with sources
- ✅ SEO metadata (title, description, keywords)
- ✅ Quality metrics (citation coverage, reading level)

Example output structure:
```markdown
---
title: "SEO-Optimized Title"
slug: url-friendly-slug
keywords: [...]
---

# Article Title

Your well-cited content here [1][2].

More paragraphs with citations [3].

## References

[1] Source title. Author. Date. URL
[2] Another source...
```

## Step 5: Advanced Options

### Custom Configuration

Edit `.env` to customize:

```bash
# Use different models
GROQ_MODEL_WRITER=mixtral-8x7b-32768

# Adjust quality gates
MIN_CITATION_COVERAGE=0.90

# Use Tavily for better search (optional)
TAVILY_API_KEY=your_tavily_key
```

### With Goals and Keywords

```bash
python -m app.cli.main run "Remote work productivity" \
  --audience "managers" \
  --goals "Discuss benefits" \
  --goals "Address challenges" \
  --keywords "remote work" \
  --keywords "productivity"
```

## Docker Deployment (Optional)

```bash
# Build and run with Docker
docker-compose up -d

# Access API
curl http://localhost:8000/healthz
```

## Troubleshooting

### "No module named 'app'"
```bash
# Ensure you're in the project root and venv is activated
pwd  # Should show .../research-to-blog
pip install -e .
```

### "GROQ_API_KEY not set"
```bash
# Check .env file exists and has your key
cat .env | grep GROQ_API_KEY
```

### "Rate limit exceeded"
```bash
# Groq free tier limits:
# - 30 requests/min
# - 14,000 tokens/min
# Wait a minute and retry
```

### Slow performance
```bash
# Use faster orchestration model
export GROQ_MODEL_ORCH=llama-3.1-8b-instant

# Or edit .env
echo "GROQ_MODEL_ORCH=llama-3.1-8b-instant" >> .env
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [examples/sample_output.md](examples/sample_output.md) for example output
- Run tests: `pytest -v`
- Explore the [API docs](http://localhost:8000/docs) (when server is running)

## Getting Help

- [GitHub Issues](https://github.com/yourusername/research-to-blog/issues)
- [Discussions](https://github.com/yourusername/research-to-blog/discussions)
- Check the [FAQ](README.md#faq) in the main README

---

Happy researching! 🚀


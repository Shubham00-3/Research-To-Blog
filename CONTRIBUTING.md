# Contributing to Research-to-Blog

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/research-to-blog.git
   cd research-to-blog
   ```

3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

5. **Set up environment**:
   ```bash
   cp env.example .env
   # Edit .env and add your GROQ_API_KEY
   ```

## 🧪 Running Tests

Before submitting a pull request, ensure all tests pass:

```bash
# Run all unit tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Skip integration tests (useful when developing without API keys)
pytest -m "not integration"
```

## 🎨 Code Style

We use `ruff` and `black` for code formatting:

```bash
# Format code
black app/ tests/

# Lint code
ruff check app/ tests/

# Auto-fix linting issues
ruff check --fix app/ tests/
```

## 📝 Commit Guidelines

- Use clear, descriptive commit messages
- Follow conventional commits format:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `docs:` for documentation changes
  - `test:` for test additions/changes
  - `refactor:` for code refactoring
  - `chore:` for maintenance tasks

Example:
```
feat: add support for custom embedding models
fix: handle timeout errors in scraper
docs: update README with new configuration options
```

## 🔀 Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and commit them

3. **Run tests** and ensure they pass

4. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Open a Pull Request** on GitHub with:
   - Clear description of changes
   - Reference to any related issues
   - Screenshots (if UI changes)
   - Test results

## 🐛 Bug Reports

When reporting bugs, include:

- Python version
- Operating system
- Relevant configuration (sanitize API keys!)
- Steps to reproduce
- Expected vs actual behavior
- Error messages/stack traces
- Minimal code example (if applicable)

## 💡 Feature Requests

For feature requests, provide:

- Clear use case
- Expected behavior
- Example usage (if applicable)
- Why this would be valuable

## 📦 Adding Dependencies

If adding new dependencies:

1. Add to `requirements.txt`
2. Update `README.md` if it affects installation
3. Ensure it's compatible with Python 3.11+
4. Prefer lightweight, well-maintained packages

## 🔍 Code Review

Pull requests will be reviewed for:

- Code quality and style
- Test coverage
- Documentation
- Performance impact
- Security implications
- Backward compatibility

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## ❓ Questions?

- Open a [GitHub Discussion](https://github.com/yourusername/research-to-blog/discussions)
- Check existing [Issues](https://github.com/yourusername/research-to-blog/issues)

Thank you for contributing! 🎉


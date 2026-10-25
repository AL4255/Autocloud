# Contributing to AutoCloud

Thank you for your interest in contributing to AutoCloud! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/autocloud.git
   cd autocloud
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. **Set Up Environment**
   ```bash
   cp .env.example .env
   # Add your ANTHROPIC_API_KEY to .env
   ```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=autocloud --cov-report=html

# Run specific test file
pytest tests/test_generator.py

# Run with verbose output
pytest -v
```

## Code Style

We use Black for code formatting and Flake8 for linting:

```bash
# Format code
black autocloud/ tests/

# Check formatting
black --check autocloud/ tests/

# Run linter
flake8 autocloud/ tests/

# Type checking
mypy autocloud/
```

## Project Structure

```
autocloud/
├── autocloud/           # Main package
│   ├── cli.py          # CLI commands
│   ├── core/           # Core functionality
│   │   ├── llm.py      # Claude API integration
│   │   ├── generator.py # Terraform generation
│   │   ├── validator.py # Validation logic
│   │   └── deployer.py  # Deployment execution
│   └── utils/          # Utilities
│       ├── config.py   # Configuration
│       ├── logger.py   # Logging
│       └── helpers.py  # Helper functions
├── tests/              # Test suite
└── examples/           # Example projects
```

## Making Changes

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Write clean, documented code
   - Follow existing code style
   - Add tests for new features
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   pytest
   black autocloud/ tests/
   flake8 autocloud/ tests/
   ```

4. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create Pull Request on GitHub
   ```

## Pull Request Guidelines

- **Clear Description**: Explain what changes you made and why
- **Tests**: Include tests for new features or bug fixes
- **Documentation**: Update README or docs if needed
- **Single Purpose**: One PR per feature/fix
- **Clean History**: Squash commits if necessary

## Areas for Contribution

### High Priority
- AWS and GCP support
- Remote state management (Azure Blob, S3)
- Enhanced security scanning
- Cost optimization recommendations

### Medium Priority
- More comprehensive tests
- Better error messages
- Performance improvements
- Documentation improvements

### Nice to Have
- Web dashboard
- Visual workflow builder
- CI/CD integrations
- Additional cloud providers

## Bug Reports

When reporting bugs, please include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Exact steps to reproduce the bug
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Environment**: OS, Python version, Terraform version
6. **Logs**: Relevant log files from `~/.autocloud/projects/*/logs/`

## Feature Requests

When requesting features, please include:

1. **Use Case**: Why you need this feature
2. **Description**: What the feature should do
3. **Alternatives**: Other solutions you've considered
4. **Examples**: Example usage or API design

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the project

## Questions?

- Open an issue for questions
- Check existing issues and PRs first
- Join discussions on GitHub

Thank you for contributing to AutoCloud!

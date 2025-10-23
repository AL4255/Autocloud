from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="autocloud",
    version="0.1.0",
    author="AutoCloud Team",
    author_email="",
    description="AI-powered CLI tool for cloud infrastructure deployment",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/autocloud",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "typer[all]>=0.12.0",
        "rich>=13.7.0",
        "anthropic>=0.39.0",
        "python-dotenv>=1.0.0",
        "azure-identity>=1.15.0",
        "azure-mgmt-resource>=23.0.0",
        "pydantic>=2.5.0",
        "pyyaml>=6.0.0",
    ],
    entry_points={
        "console_scripts": [
            "autocloud=autocloud.cli:app",
        ],
    },
)

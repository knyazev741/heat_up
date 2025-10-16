"""
Validation script to check if Heat Up is properly configured
"""

import sys
import os
from pathlib import Path


def check_env_file():
    """Check if .env file exists and has required variables"""
    print("🔍 Checking .env file...")
    
    if not Path(".env").exists():
        print("   ❌ .env file not found!")
        print("   💡 Run: cp .env.example .env")
        return False
    
    with open(".env", "r") as f:
        content = f.read()
        
        required = ["OPENAI_API_KEY", "TELEGRAM_API_BASE_URL"]
        missing = []
        
        for var in required:
            if var not in content or f"{var}=" not in content:
                missing.append(var)
        
        if missing:
            print(f"   ⚠️  Missing required variables: {', '.join(missing)}")
            return False
        
        # Check if keys are filled in
        if "sk-proj-xxx" in content or "your-key-here" in content:
            print("   ⚠️  .env contains placeholder values - please update with real API keys")
            return False
    
    print("   ✅ .env file configured")
    return True


def check_dependencies():
    """Check if required Python packages are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        "fastapi",
        "uvicorn", 
        "openai",
        "httpx",
        "pydantic",
        "pydantic_settings"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"   ❌ Missing packages: {', '.join(missing)}")
        print("   💡 Run: pip install -r requirements.txt")
        return False
    
    print("   ✅ All dependencies installed")
    return True


def check_files():
    """Check if all required files exist"""
    print("🔍 Checking project files...")
    
    required_files = [
        "main.py",
        "config.py",
        "telegram_client.py",
        "llm_agent.py",
        "executor.py",
        "requirements.txt",
        "README.md"
    ]
    
    missing = []
    for file in required_files:
        if not Path(file).exists():
            missing.append(file)
    
    if missing:
        print(f"   ❌ Missing files: {', '.join(missing)}")
        return False
    
    print("   ✅ All project files present")
    return True


def check_python_version():
    """Check Python version"""
    print("🔍 Checking Python version...")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"   ❌ Python {version.major}.{version.minor} detected")
        print("   💡 Python 3.9 or higher required")
        return False
    
    print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def main():
    """Run all validation checks"""
    print("=" * 60)
    print("🔥 Heat Up - Setup Validation")
    print("=" * 60)
    print()
    
    checks = [
        check_python_version(),
        check_files(),
        check_dependencies(),
        check_env_file()
    ]
    
    print()
    print("=" * 60)
    
    if all(checks):
        print("✅ All checks passed! Ready to start.")
        print()
        print("Run the service with:")
        print("  ./start.sh")
        print("  or")
        print("  python main.py")
        print()
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())


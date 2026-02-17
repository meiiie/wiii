"""
One-Command Local Development Startup

Professional script to start local development with all checks and validations.
SOTA Pattern: Single entry point for development environment.
"""
import subprocess
import sys
import os
import time
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich import print as rprint
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False


def print_header(text: str):
    """Print section header."""
    if RICH_AVAILABLE:
        console.print(f"\n[bold cyan]{text}[/bold cyan]")
    else:
        print(f"\n{text}")


def print_success(text: str):
    """Print success message."""
    if RICH_AVAILABLE:
        console.print(f"[green]✅ {text}[/green]")
    else:
        print(f"✅ {text}")


def print_error(text: str):
    """Print error message."""
    if RICH_AVAILABLE:
        console.print(f"[red]❌ {text}[/red]")
    else:
        print(f"❌ {text}")


def print_warning(text: str):
    """Print warning message."""
    if RICH_AVAILABLE:
        console.print(f"[yellow]⚠️ {text}[/yellow]")
    else:
        print(f"⚠️ {text}")


def check_environment():
    """Check if .env file exists."""
    print_header("1️⃣ Checking Environment Configuration")
    
    if not Path(".env").exists():
        print_error(".env file not found!")
        print("\n💡 Create .env from template:")
        print("   copy .env.example .env")
        print("   Then edit .env with your Render credentials")
        return False
    
    print_success(".env file found")
    return True


def check_virtual_env():
    """Check if running in virtual environment."""
    print_header("2️⃣ Checking Virtual Environment")
    
    if sys.prefix == sys.base_prefix:
        print_warning("Not running in virtual environment")
        print("\n💡 Activate virtual environment:")
        print("   .venv\\Scripts\\activate")
        return False
    
    print_success(f"Virtual environment active: {sys.prefix}")
    return True


def check_dependencies():
    """Check if key dependencies are installed."""
    print_header("3️⃣ Checking Dependencies")
    
    try:
        import fastapi
        import sqlalchemy
        import google.generativeai
        print_success("Core dependencies installed")
        return True
    except ImportError as e:
        print_error(f"Missing dependencies: {e}")
        print("\n💡 Install dependencies:")
        print("   pip install -r requirements.txt")
        return False


def run_connectivity_tests():
    """Run connectivity tests."""
    print_header("4️⃣ Running Connectivity Tests")
    
    try:
        result = subprocess.run(
            [sys.executable, "scripts/test_local_connectivity.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print_success("All connections verified")
            return True
        else:
            print_error("Some connections failed")
            print(result.stdout)
            return False
    except FileNotFoundError:
        print_warning("Connectivity test script not found, skipping...")
        return True
    except Exception as e:
        print_error(f"Error running tests: {e}")
        return False


def start_server():
    """Start uvicorn development server."""
    print_header("5️⃣ Starting Development Server")
    
    print("\n" + "="*70)
    print("🚀 MARITIME AI SERVICE - LOCAL DEVELOPMENT")
    print("="*70)
    print("\n📍 Server: http://localhost:8000")
    print("📖 Docs: http://localhost:8000/docs")
    print("💾 Health: http://localhost:8000/api/v1/health")
    print("\n🔄 Auto-reload: ENABLED (edit code → instant reload)")
    print("⌨️  Stop: Press CTRL+C")
    print("\n" + "="*70 + "\n")
    
    try:
        subprocess.run([
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--log-level", "info"
        ])
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped gracefully")
    except FileNotFoundError:
        print_error("uvicorn not found!")
        print("\n💡 Install uvicorn:")
        print("   pip install uvicorn")
        return False


def main():
    """Main entry point."""
    if RICH_AVAILABLE:
        console.print(Panel.fit(
            "[bold white]🌊 Wiii[/bold white]\n"
            "[cyan]Professional Local Development Environment[/cyan]",
            border_style="cyan"
        ))
    else:
        print("\n" + "="*70)
        print("🌊 Wiii - Local Development")
        print("="*70)
    
    # Run all checks
    checks = [
        check_environment(),
        check_virtual_env(),
        check_dependencies(),
    ]
    
    if not all(checks):
        print("\n" + "="*70)
        print_error("Pre-flight checks failed!")
        print("="*70)
        print("\n💡 Fix the issues above and try again.\n")
        return 1
    
    # Optional: Run connectivity tests
    print("\n💡 Tip: Run connectivity tests? (recommended) [Y/n]: ", end="")
    try:
        choice = input().strip().lower()
        if choice != 'n':
            run_connectivity_tests()
    except KeyboardInterrupt:
        print("\n")
    
    # Start server
    start_server()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

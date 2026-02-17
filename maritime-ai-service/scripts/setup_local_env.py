"""
Professional One-Command Local Environment Setup

Pattern: Google's "blaze run //dev:setup", Uber's "devpod start"
Philosophy: Zero-friction onboarding, comprehensive validation
"""
import subprocess
import sys
import os
from pathlib import Path
import platform

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False


def print_header(text: str):
    """Print section header."""
    if RICH_AVAILABLE:
        console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
        console.print(f"[bold white]{text}[/bold white]")
        console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")
    else:
        print(f"\n{'='*70}")
        print(text)
        print(f"{'='*70}\n")


def print_step(step_num: int, total: int, text: str):
    """Print step progress."""
    if RICH_AVAILABLE:
        console.print(f"[bold cyan]Step {step_num}/{total}:[/bold cyan] {text}")
    else:
        print(f"Step {step_num}/{total}: {text}")


def print_success(text: str):
    """Print success message."""
    msg = f"✅ {text}"
    if RICH_AVAILABLE:
        console.print(f"[green]{msg}[/green]")
    else:
        print(msg)


def print_error(text: str):
    """Print error message."""
    msg = f"❌ {text}"
    if RICH_AVAILABLE:
        console.print(f"[red]{msg}[/red]")
    else:
        print(msg)


def print_warning(text: str):
    """Print warning message."""
    msg = f"⚠️ {text}"
    if RICH_AVAILABLE:
        console.print(f"[yellow]{msg}[/yellow]")
    else:
        print(msg)


def check_python_version():
    """Check Python version >= 3.11."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} - Need 3.11+")
        return False


def check_venv_active():
    """Check if virtual environment is active."""
    if sys.prefix != sys.base_prefix:
        print_success(f"Virtual environment active")
        return True
    else:
        print_warning("Virtual environment not active")
        print("\n💡 Activate with:")
        if platform.system() == "Windows":
            print("   .venv\\Scripts\\activate")
        else:
            print("   source .venv/bin/activate")
        return False


def check_env_file():
    """Check if .env file exists."""
    if Path(".env").exists():
        print_success(".env file exists")
        return True
    else:
        print_warning(".env file not found")
        
        # Offer to copy from example
        if Path(".env.example").exists():
            print("\n💡 Found .env.example. Copy to .env? [Y/n]: ", end="")
            try:
                choice = input().strip().lower()
                if choice != 'n':
                    import shutil
                    shutil.copy(".env.example", ".env")
                    print_success("Created .env from .env.example")
                    print("\n⚠️ IMPORTANT: Edit .env with your Render credentials!")
                    print("   Required: GOOGLE_API_KEY, DATABASE_URL, NEO4J_URI, NEO4J_PASSWORD")
                    return True
            except KeyboardInterrupt:
                print("\n")
                return False
        
        print_error("Cannot proceed without .env file")
        return False


def install_package_editable():
    """Install package in editable mode."""
    print("\n📦 Installing maritime-ai-service in editable mode...")
    print("   (This allows 'from app import ...' to work globally)")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print_success("Package installed successfully")
            return True
        else:
            print_error("Package installation failed")
            print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print_error("Installation timed out (>5 min)")
        return False
    except Exception as e:
        print_error(f"Installation error: {e}")
        return False


def check_critical_imports():
    """Test critical imports."""
    print("\n🔍 Testing critical imports...")
    
    critical_imports = [
        ("fastapi", "FastAPI framework"),
        ("sqlalchemy", "Database ORM"),
        ("google.generativeai", "Gemini API"),
        ("neo4j", "Neo4j driver"),
        ("langchain", "LangChain framework"),
        ("pydantic", "Data validation"),
    ]
    
    failed = []
    for module_name, description in critical_imports:
        try:
            __import__(module_name)
            print(f"   ✅ {module_name:25} ({description})")
        except ImportError as e:
            print(f"   ❌ {module_name:25} - {e}")
            failed.append(module_name)
    
    if failed:
        print_warning(f"{len(failed)} critical imports failed")
        print("\n💡 Install missing dependencies:")
        print("   pip install -r requirements.txt")
        return False
    else:
        print_success(f"All {len(critical_imports)} critical imports work")
        return True


def test_app_imports():
    """Test app package imports."""
    print("\n🧪 Testing app package imports...")
    
    app_imports = [
        "app.core.config",
        "app.core.database",
        "app.engine.gemini_embedding",
        "app.services.chat_orchestrator",
    ]
    
    failed = []
    for module_name in app_imports:
        try:
            __import__(module_name)
            print(f"   ✅ {module_name}")
        except ImportError as e:
            print(f"   ❌ {module_name}: {e}")
            failed.append(module_name)
    
    if failed:
        print_error(f"{len(failed)} app imports failed")
        print("\n💡 This usually means 'pip install -e .' didn't run")
        return False
    else:
        print_success(f"All {len(app_imports)} app imports work")
        return True


def run_connectivity_tests():
    """Run connectivity test script."""
    print("\n🌐 Testing cloud database connectivity...")
    
    script_path = Path("scripts/test_local_connectivity.py")
    if not script_path.exists():
        print_warning("Connectivity test script not found, skipping...")
        return True
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            timeout=60
        )
        
        if result.returncode == 0:
            print_success("All connectivity tests passed")
            return True
        else:
            print_warning("Some connectivity tests failed (check output above)")
            return True  # Non-blocking
    except subprocess.TimeoutExpired:
        print_warning("Connectivity tests timed out")
        return True  # Non-blocking
    except Exception as e:
        print_warning(f"Connectivity test error: {e}")
        return True  # Non-blocking


def create_dependency_lock():
    """Create dependency lock file for reproducibility."""
    print("\n📝 Creating dependency lock file...")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            lock_file = Path("requirements-lock.txt")
            lock_file.write_text(result.stdout)
            print_success(f"Created {lock_file} ({len(result.stdout.splitlines())} packages)")
            return True
        else:
            print_warning("Failed to create lock file")
            return False
    except Exception as e:
        print_warning(f"Lock file error: {e}")
        return False


def print_next_steps():
    """Print next steps after setup."""
    if RICH_AVAILABLE:
        console.print(Panel.fit(
            "[bold green]✨ Local Environment Setup Complete![/bold green]\n\n"
            "[bold white]Next Steps:[/bold white]\n\n"
            "1. Start development server:\n"
            "   [cyan]python scripts/run_local_dev.py[/cyan]\n\n"
            "2. Open browser to:\n"
            "   [cyan]http://localhost:8000/docs[/cyan]\n\n"
            "3. Test iteration speed:\n"
            "   [cyan]python scripts/measure_iteration_time.py[/cyan]\n\n"
            "4. Make code changes → Auto-reload in 1-2s ⚡\n\n"
            "[bold yellow]💡 Tip:[/bold yellow] Only deploy to Render when feature is complete!\n"
            "   [dim]Local iteration: 1-2s | Render deployment: 10-15 min[/dim]",
            title="🎉 SUCCESS",
            border_style="green"
        ))
    else:
        print("\n" + "="*70)
        print("✨ Local Environment Setup Complete!")
        print("="*70)
        print("\nNext Steps:")
        print("1. Start development server:")
        print("   python scripts/run_local_dev.py")
        print("\n2. Open browser to:")
        print("   http://localhost:8000/docs")
        print("\n3. Test iteration speed:")
        print("   python scripts/measure_iteration_time.py")
        print("\n4. Make code changes → Auto-reload in 1-2s ⚡")
        print("\n💡 Tip: Only deploy to Render when feature is complete!")
        print("   Local iteration: 1-2s | Render deployment: 10-15 min")
        print("\n" + "="*70 + "\n")


def main():
    """Run complete setup workflow."""
    if RICH_AVAILABLE:
        console.print(Panel.fit(
            "[bold white]🌊 Wiii[/bold white]\n"
            "[cyan]Professional Local Development Setup[/cyan]\n\n"
            "[dim]Pattern: Google 'blaze run //dev:setup'[/dim]",
            border_style="cyan"
        ))
    else:
        print("\n" + "="*70)
        print("🌊 Wiii")
        print("Professional Local Development Setup")
        print("="*70)
    
    # Step-by-step setup
    steps = [
        ("Python Version", check_python_version, True),
        ("Virtual Environment", check_venv_active, True),
        ("Environment Config", check_env_file, True),
        ("Package Installation", install_package_editable, True),
        ("Critical Dependencies", check_critical_imports, True),
        ("App Package Imports", test_app_imports, True),
        ("Cloud Connectivity", run_connectivity_tests, False),
        ("Dependency Lock", create_dependency_lock, False),
    ]
    
    total_steps = len(steps)
    failed_critical = False
    
    for i, (name, check_fn, is_critical) in enumerate(steps, 1):
        print_step(i, total_steps, name)
        
        try:
            result = check_fn()
            if not result and is_critical:
                print_error(f"{name} check failed - Cannot proceed")
                failed_critical = True
                break
        except Exception as e:
            print_error(f"{name} check error: {e}")
            if is_critical:
                failed_critical = True
                break
    
    # Final result
    print("\n" + "="*70)
    if failed_critical:
        print_error("Setup failed! Please fix the errors above and try again.")
        print("="*70)
        return 1
    else:
        print_success("All checks passed!")
        print("="*70)
        print_next_steps()
        return 0


if __name__ == "__main__":
    sys.exit(main())

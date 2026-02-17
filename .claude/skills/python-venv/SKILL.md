# Python Virtual Environment Skill

## Description
Enforces Python virtual environment best practices for WiiiGov AI project. This is a CRITICAL skill that must be followed for all Python operations.

## Rules

### ABSOLUTE REQUIREMENTS
1. **ALWAYS** activate venv before ANY Python operation:
   ```bash
   cd src-python
   source .venv/bin/activate
   ```

2. **NEVER** use these commands:
   ```bash
   pip install --break-system-packages  # FORBIDDEN
   sudo pip install                      # FORBIDDEN
   pip install <pkg>                     # FORBIDDEN without venv
   ```

3. **ALWAYS** use this pattern:
   ```bash
   cd src-python && source .venv/bin/activate && pip install <package>
   ```

### Virtual Environment Setup
```bash
# If .venv doesn't exist:
cd src-python
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Running Python Scripts
```bash
# Correct way:
cd src-python && source .venv/bin/activate && python main.py

# Running tests:
cd src-python && source .venv/bin/activate && pytest

# Running uvicorn:
cd src-python && source .venv/bin/activate && uvicorn main:app --reload
```

### Adding New Dependencies
```bash
# 1. Activate venv
cd src-python && source .venv/bin/activate

# 2. Install package
pip install <package-name>

# 3. Update requirements.txt
pip freeze > requirements.txt
# Or manually add with version pinning
```

### Checking Venv Status
```bash
# Check if venv is active:
which python
# Should show: /path/to/src-python/.venv/bin/python

# Check installed packages:
pip list
```

## Why This Matters
- Prevents system Python pollution
- Ensures reproducible environments
- Avoids permission issues
- Isolates project dependencies
- Required for PyInstaller bundling

# =============================================================================
# PolyPulse — .gitignore
# =============================================================================

# --- Python bytecode & cache ---
__pycache__/
*.py[cod]
*$py.class
*.pyo
*.pyc

# --- Blender backup files ---
*.blend1
*.blend2
*.blend3
*.blend4
*.blend5
*.blend6
*.blend7
*.blend8
*.blend9
*.blend-backup
*.blend-backup-*
*.autosave
*.tmp

# --- Build artifacts ---
*.zip
*.tar.gz
*.tar.bz2
*.7z
*.egg-info/
*.egg
build/
dist/
release/

# --- Distribution / packaging ---
.DS_Store
Thumbs.db
desktop.ini

# --- IDE / Editor ---
.vscode/
.idea/
*.swp
*.swo
*~
.project
.pydevproject

# --- Testing & coverage ---
.pytest_cache/
.coverage
htmlcov/
.tox/

# --- Virtual envs ---
venv/
env/
.venv/
env3/

# --- Logs ---
*.log
logs/

# --- Local config files ---
.env
.env.local
*.local.cfg

# --- Private / never commit ---
private/
*.key
secrets.json
.env

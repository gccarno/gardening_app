"""
Launcher for the OpenRouter MCP server used by Claude Code (see .mcp.json).

Loads OPENROUTER_API_KEY from the repo's .env, then runs the pinned
`openrouter-mcp` npm package with stdio passed straight through. A launcher
rather than `uv run --env-file .env npx ...` because uv's .env parser rejects
this repo's .env (a hyphenated key) and uv can't spawn npx.cmd on Windows.

The package (minovap/openrouter-mcp 2.0.1) was source-reviewed before pinning:
one `ask_model` tool, OpenRouter-only network access, model allowlist from
OPENROUTER_ALLOWED_MODELS. Its `append_files` argument sends local file
contents to OpenRouter — review file attachments before approving a call.
Re-review before bumping the version.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

PACKAGE = 'openrouter-mcp@2.0.1'

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
npx = shutil.which('npx')
if npx is None:
    sys.exit('npx not found on PATH (install Node.js)')
sys.exit(subprocess.call([npx, '-y', PACKAGE]))

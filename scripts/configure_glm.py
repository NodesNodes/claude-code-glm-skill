#!/usr/bin/env python3
"""Configure Claude Code for Z.ai Coding Plan without printing credentials."""

import argparse
import datetime
import getpass
import json
import os
from pathlib import Path
import sys
import tempfile


ENDPOINT = "https://api.z.ai/api/anthropic"


def read_settings(path):
    if path.is_symlink():
        raise ValueError("Settings path is a symlink; specify its intended target explicitly.")
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Settings must be a JSON object.")
    if not isinstance(value.get("env", {}), dict):
        raise ValueError("The settings env field must be an object.")
    return value


def write_private(path, content):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".glm-settings-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def backup_settings(path):
    if not path.exists():
        return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = path.with_name(path.stem + ".before-glm." + stamp + ".json")
    write_private(backup, path.read_bytes())
    return backup


def choose_key(args, settings):
    if args.key_file:
        key = Path(args.key_file).expanduser().read_text(encoding="utf-8").strip()
    elif os.environ.get("ZAI_CODING_PLAN_API_KEY", "").strip():
        key = os.environ["ZAI_CODING_PLAN_API_KEY"].strip()
    else:
        env = settings.get("env", {})
        key = ""
        if env.get("ANTHROPIC_BASE_URL", "").rstrip("/") == ENDPOINT:
            key = env.get("ANTHROPIC_AUTH_TOKEN", "")
        if not key and sys.stdin.isatty():
            key = getpass.getpass("Z.ai Coding Plan key (hidden): ").strip()
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Coding Plan key required: use --key-file or ZAI_CODING_PLAN_API_KEY.")
    if any(character.isspace() for character in key):
        raise ValueError("The key contains whitespace; provide only the Coding Plan key.")
    return key


def configure(args, path):
    if args.context_tokens <= 0:
        raise ValueError("Context size must be positive.")
    for model in (args.model, args.fast_model):
        if not model or any(character.isspace() for character in model) or "[1m]" in model.lower():
            raise ValueError("Use a nonempty model ID without whitespace or [1m]; set --context-tokens.")
    settings = read_settings(path)
    key = choose_key(args, settings)
    env = dict(settings.get("env", {}))
    env.update({
        "ANTHROPIC_BASE_URL": ENDPOINT,
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": args.model,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": args.model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": args.fast_model,
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": str(args.context_tokens),
        "ANTHROPIC_CUSTOM_MODEL_OPTION": args.model,
        "ANTHROPIC_CUSTOM_MODEL_OPTION_NAME": args.model.upper(),
        "ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION": "Z.ai Coding Plan",
        "API_TIMEOUT_MS": "3000000",
    })
    # Explicitly selecting this route must not leave a competing environment
    # model or Anthropic key in the same settings object.
    for name in ("ANTHROPIC_MODEL", "ANTHROPIC_API_KEY", "CLAUDE_CODE_USE_BEDROCK",
                 "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"):
        env.pop(name, None)
    if args.client_auto:
        env.update({
            "CLAUDE_CODE_AUTO_MODE_SERVER": "0",
            "CLAUDE_CODE_AUTO_MODE_MODEL": args.fast_model,
        })
    settings["model"] = args.model
    settings["env"] = env
    content = (json.dumps(settings, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    backup = backup_settings(path)
    write_private(path, content)
    print("Settings:", path)
    print("Model:", args.model)
    print("Context tokens:", args.context_tokens)
    print("Backup:", backup or "none (settings file was new)")
    print("Restart Claude Code, then verify its response and a local command.")


def status(path):
    settings = read_settings(path)
    env = settings.get("env", {})
    print(json.dumps({
        "settings": str(path),
        "exists": path.exists(),
        "model": settings.get("model"),
        "endpoint": env.get("ANTHROPIC_BASE_URL"),
        "key_present": bool(env.get("ANTHROPIC_AUTH_TOKEN")),
        "fast_model": env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
        "context_tokens": env.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS"),
        "auto_mode_server": env.get("CLAUDE_CODE_AUTO_MODE_SERVER"),
        "auto_mode_model": env.get("CLAUDE_CODE_AUTO_MODE_MODEL"),
    }, ensure_ascii=False, indent=2))


def restore(args, path):
    source = Path(args.backup).expanduser().absolute()
    if not source.is_file():
        raise ValueError("Backup file does not exist.")
    if source == path:
        raise ValueError("Backup must differ from the destination settings file.")
    read_settings(source)
    read_settings(path)
    content = source.read_bytes()
    backup = backup_settings(path)
    write_private(path, content)
    print("Restored:", path)
    print("Previous configuration saved:", backup or "none (settings file was new)")
    print("Restart Claude Code to apply the restored configuration.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", default="~/.claude/settings.json", help="Target settings file")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("configure", help="Merge GLM settings and save a private backup")
    setup.add_argument("--key-file", help="Local file containing only a Coding Plan key")
    setup.add_argument("--model", default="glm-5.3")
    setup.add_argument("--fast-model", default="glm-5.3-flash")
    setup.add_argument("--context-tokens", type=int, default=1000000)
    setup.add_argument("--client-auto", action="store_true", help="Use client-side auto-mode review with the fast model")
    commands.add_parser("status", help="Show selected settings without printing credentials")
    rollback = commands.add_parser("restore", help="Restore a complete settings backup")
    rollback.add_argument("--backup", required=True)
    args = parser.parse_args()
    path = Path(args.settings).expanduser().absolute()
    try:
        if args.command == "configure":
            configure(args, path)
        elif args.command == "status":
            status(path)
        else:
            restore(args, path)
    except (OSError, ValueError) as error:
        # JSON parser exceptions describe positions, not the document contents.
        # No supplied keys or configuration bodies are included in diagnostics.
        if isinstance(error, json.JSONDecodeError):
            print("Error: invalid JSON settings; no configuration was changed.", file=sys.stderr)
        elif isinstance(error, OSError):
            print("Error: could not access the settings or key file.", file=sys.stderr)
        else:
            print("Error:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

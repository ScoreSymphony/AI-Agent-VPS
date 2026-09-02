from __future__ import annotations

import argparse
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
REFERENCE_PROFILE = "reference"


class ReferenceDeploymentError(RuntimeError):
    pass


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, text=True)


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["docker", "compose"]
    if ENV_PATH.exists():
        command.extend(["--env-file", str(ENV_PATH)])
    command.extend(["--profile", REFERENCE_PROFILE, *args])
    return run(command, check=check)


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    if not path.exists():
        raise ReferenceDeploymentError(
            ".env is missing; copy .env.example to .env and provision local credentials first"
        )
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def secret_path(values: dict[str, str], key: str) -> Path:
    raw = values.get(key, "").strip()
    if not raw:
        raise ReferenceDeploymentError(f"{key} is not configured in .env")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def read_secret_file(values: dict[str, str], key: str, *, prefix: str | None = None) -> str:
    path = secret_path(values, key)
    if not path.is_file():
        raise ReferenceDeploymentError(f"secret file is missing: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ReferenceDeploymentError(f"secret file is empty: {path}")
    if prefix is not None and not value.startswith(prefix):
        raise ReferenceDeploymentError(f"secret in {path} must use the expected {prefix!r} credential format")
    if len(value) < 24:
        raise ReferenceDeploymentError(f"secret in {path} is unexpectedly short")
    return value


def docker_preflight() -> None:
    try:
        run(["docker", "compose", "version"])
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise ReferenceDeploymentError("Docker with the Compose plugin is required") from exc


def init_secrets() -> None:
    values = load_env()
    forge_path = secret_path(values, "SCORESYMPHONY_FORGE_TOKEN_FILE")
    gateway_path = secret_path(values, "SCORESYMPHONY_GATEWAY_TOKEN_FILE")
    forge_path.parent.mkdir(parents=True, exist_ok=True)
    gateway_path.parent.mkdir(parents=True, exist_ok=True)

    if gateway_path.exists() and gateway_path.read_text(encoding="utf-8").strip():
        print(f"gateway secret already exists; not replacing: {gateway_path}")
    else:
        gateway_path.write_text(secrets.token_urlsafe(48) + "\n", encoding="utf-8")
        try:
            gateway_path.chmod(0o600)
        except OSError:
            pass
        print(f"generated gateway secret: {gateway_path}")

    print(f"write the Forge PAT created through the local Forge auth API to: {forge_path}")


def preflight() -> None:
    docker_preflight()
    values = load_env()
    bind_host = values.get("SCORESYMPHONY_BIND_HOST", "127.0.0.1")
    if bind_host not in {"127.0.0.1", "localhost"}:
        raise ReferenceDeploymentError(
            "reference deployment must remain loopback-bound until the production security baseline is complete"
        )
    read_secret_file(values, "SCORESYMPHONY_FORGE_TOKEN_FILE", prefix="fg_")
    read_secret_file(values, "SCORESYMPHONY_GATEWAY_TOKEN_FILE")
    compose("config", "--quiet")
    print("reference deployment preflight passed")


def start() -> None:
    preflight()
    compose("up", "-d", "--build", "forge-upstream", "gateway")
    compose("ps")


def stop() -> None:
    docker_preflight()
    compose("down", "--remove-orphans")


def status() -> None:
    docker_preflight()
    compose("ps")


def diagnose() -> None:
    docker_preflight()
    compose("ps", check=False)
    compose("logs", "--tail", "200", "forge-upstream", "gateway", check=False)


def backup(destination: Path) -> None:
    docker_preflight()
    destination.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"forge-data-{stamp}.tar"

    compose("stop", "gateway", "forge-upstream", check=False)
    try:
        compose(
            "run",
            "--rm",
            "--no-deps",
            "-v",
            f"{destination}:/backup",
            "--entrypoint",
            "sh",
            "forge-upstream",
            "-ec",
            f"tar -C /data -cf /backup/{filename} .",
        )
    finally:
        compose("up", "-d", "forge-upstream", "gateway", check=False)
    print(destination / filename)


def restore(archive: Path, *, confirmed: bool) -> None:
    if not confirmed:
        raise ReferenceDeploymentError("restore is destructive; pass --yes after verifying the backup")
    docker_preflight()
    archive = archive.resolve()
    if not archive.is_file():
        raise ReferenceDeploymentError(f"backup archive does not exist: {archive}")
    if archive.suffix != ".tar":
        raise ReferenceDeploymentError("reference restore accepts only .tar archives created by this helper")

    parent = archive.parent
    filename = archive.name
    compose("stop", "gateway", "forge-upstream", check=False)
    restored = False
    try:
        compose(
            "run",
            "--rm",
            "--no-deps",
            "-v",
            f"{parent}:/backup:ro",
            "--entrypoint",
            "sh",
            "forge-upstream",
            "-ec",
            f"find /data -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} + && tar -C /data -xf /backup/{filename}",
        )
        restored = True
    finally:
        if restored:
            compose("up", "-d", "forge-upstream", "gateway", check=False)
    if not restored:
        raise ReferenceDeploymentError(
            "restore failed; services remain stopped so the operator can diagnose without mutating the failed state"
        )
    compose("ps")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Operate the loopback-only ScoreSymphony reference deployment")
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("init-secrets")
    sub.add_parser("preflight")
    sub.add_parser("start")
    sub.add_parser("stop")
    sub.add_parser("status")
    sub.add_parser("diagnose")

    backup_parser = sub.add_parser("backup")
    backup_parser.add_argument("destination", type=Path)

    restore_parser = sub.add_parser("restore")
    restore_parser.add_argument("archive", type=Path)
    restore_parser.add_argument("--yes", action="store_true", help="confirm destructive restore")
    return result


def main() -> None:
    args = parser().parse_args()
    try:
        if args.command == "init-secrets":
            init_secrets()
        elif args.command == "preflight":
            preflight()
        elif args.command == "start":
            start()
        elif args.command == "stop":
            stop()
        elif args.command == "status":
            status()
        elif args.command == "diagnose":
            diagnose()
        elif args.command == "backup":
            backup(args.destination)
        elif args.command == "restore":
            restore(args.archive, confirmed=args.yes)
        else:  # pragma: no cover - argparse prevents this
            raise ReferenceDeploymentError(f"unsupported command: {args.command}")
    except (ReferenceDeploymentError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"reference deployment error: {exc}") from exc


if __name__ == "__main__":
    main()

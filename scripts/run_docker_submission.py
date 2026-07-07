#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


MODEL_EXTENSIONS = {
    ".bin",
    ".ckpt",
    ".gguf",
    ".h5",
    ".joblib",
    ".mar",
    ".mlmodel",
    ".onnx",
    ".pb",
    ".pkl",
    ".pt",
    ".pth",
    ".safetensors",
    ".tflite",
}


def run(cmd, *, timeout=None, cwd=None):
    print("+ " + " ".join(str(part) for part in cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, timeout=timeout, check=True)


def docker_output(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def image_size_bytes(image_tag):
    raw = docker_output(["docker", "image", "inspect", image_tag, "--format", "{{.Size}}"])
    return int(raw)


def scan_repo_model_artifacts(repo, max_model_bytes, max_total_bytes):
    oversized = []
    total = 0
    for path in Path(repo).rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if path.suffix.lower() in MODEL_EXTENSIONS:
            size = path.stat().st_size
            total += size
            if size > max_model_bytes:
                oversized.append((path, size))
    if oversized:
        first = ", ".join(f"{path}={size / 1024 / 1024:.1f}MiB" for path, size in oversized[:10])
        raise SystemExit(f"Model artifact exceeds size limit: {first}")
    if total > max_total_bytes:
        raise SystemExit(f"Total model artifact size exceeds limit: {total / 1024 / 1024:.1f}MiB")


def main():
    parser = argparse.ArgumentParser(description="Build and run an offline Docker submission.")
    parser.add_argument("--repo", required=True, help="Candidate repository containing Dockerfile.")
    parser.add_argument("--input-dir", required=True, help="PDF input directory.")
    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument("--output", dest="output_path", help="Host path where predictions should be written.")
    output_group.add_argument(
        "--output-csv",
        dest="output_path",
        help="Compatibility alias for --output. The path may still be CSV, JSON, or JSONL.",
    )
    parser.add_argument("--manifest", help="Optional manifest used to validate output case ids.")
    parser.add_argument("--image-tag", default=None)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=28800)
    parser.add_argument("--cpus", default="4")
    parser.add_argument("--memory", default="8g")
    parser.add_argument("--max-image-gib", type=float, default=4.0)
    parser.add_argument("--max-model-mib", type=float, default=250.0)
    parser.add_argument("--max-total-model-mib", type=float, default=1024.0)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Fail validation when the output omits an expected case. Default is to score omissions negatively.",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    input_dir = Path(args.input_dir).resolve()
    output_path = Path(args.output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    if not (repo / "Dockerfile").exists():
        raise SystemExit(f"No Dockerfile found in {repo}")
    if not input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    scan_repo_model_artifacts(
        repo,
        int(args.max_model_mib * 1024 * 1024),
        int(args.max_total_model_mib * 1024 * 1024),
    )

    image_tag = args.image_tag or f"mib-submission-{int(time.time())}"
    if not args.skip_build:
        run(["docker", "build", "--pull=false", "-t", image_tag, str(repo)])

    max_image_bytes = int(args.max_image_gib * 1024 * 1024 * 1024)
    actual_image_size = image_size_bytes(image_tag)
    print(f"Image size: {actual_image_size / 1024 / 1024 / 1024:.2f}GiB")
    if actual_image_size > max_image_bytes:
        raise SystemExit(f"Image exceeds {args.max_image_gib}GiB limit")

    container_name = f"mib-score-{int(time.time())}-{os.getpid()}"
    docker_cmd = [
        "docker",
        "run",
        "--name",
        container_name,
        "--rm",
        "--network",
        "none",
        "--cpus",
        str(args.cpus),
        "--memory",
        str(args.memory),
        "--pids-limit",
        "512",
        "--read-only",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=2g",
        "--mount",
        f"type=bind,src={input_dir},dst=/input,readonly",
        "--mount",
        f"type=bind,src={output_path.parent},dst=/output",
        image_tag,
        "/input",
        f"/output/{output_path.name}",
    ]

    try:
        run(docker_cmd, timeout=args.timeout_seconds)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", container_name], check=False)
        raise SystemExit(f"Container timed out after {args.timeout_seconds}s")

    if not output_path.exists():
        raise SystemExit(f"Container did not write expected output: {output_path}")
    if output_path.stat().st_size > 25 * 1024 * 1024:
        raise SystemExit("Output predictions file exceeds 25MiB limit")

    if args.manifest:
        validate_cmd = [
            sys.executable,
            str(Path(__file__).with_name("validate_submission.py")),
            "--submission",
            str(output_path),
            "--manifest",
            str(Path(args.manifest).resolve()),
        ]
        if args.require_complete:
            validate_cmd.append("--require-complete")
        run(
            validate_cmd
        )

    print(f"Offline Docker submission completed: {output_path}")


if __name__ == "__main__":
    main()

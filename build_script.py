import yaml
import argparse
import os
import sys
import subprocess
import shutil
import platform
import re
from pathlib import Path  # Import Path


def run_command(command, cwd=None, env=None):
    """Executes a shell command and prints output."""
    print(f"Running command: {' '.join(command)}" + (f" in {cwd}" if cwd else ""))
    # Merge with current environment if custom env is provided
    if env:
        merged_env = os.environ.copy()
        merged_env.update(env)
        env = merged_env
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=env,
        text=True,
        bufsize=1,
    )
    for line in iter(process.stdout.readline, ""):
        print(line, end="")
    process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)


def get_env_details(config):
    """Detects or retrieves environment details."""
    details = {}
    # Python Version (use from config as primary source, verify environment)
    config_py_ver = config["build_target"]["python_version"]
    env_py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    if not config_py_ver.startswith(env_py_ver):
        print(
            f"Warning: Config Python version {config_py_ver} differs from environment {env_py_ver}. Using environment."
        )
        # Or potentially error out if strict matching is needed
    details["py_tag"] = f"py{sys.version_info.major}{sys.version_info.minor}"

    # CUDA Version (use from config, could verify with nvcc if needed)
    details["cuda_tag"] = f"cuda{config['build_target']['cuda_version']}"
    # Optional: Verify with nvcc
    try:
        result = subprocess.run(
            ["nvcc", "--version"], capture_output=True, text=True, check=True
        )
        match = re.search(r"release (\d+\.\d+)", result.stdout)
        if match:
            env_cuda_ver = match.group(1)
            if env_cuda_ver != config["build_target"]["cuda_version"]:
                print(
                    f"Warning: Config CUDA version {config['build_target']['cuda_version']} differs from nvcc detected {env_cuda_ver}. Using config version."
                )
        else:
            print("Warning: Could not parse CUDA version from nvcc output.")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Warning: Could not run nvcc to verify CUDA version: {e}")

    # Platform
    details["platform_tag"] = f"{platform.system().lower()}_{platform.machine()}"

    print("Detected Environment:")
    print(f"  Python Tag: {details['py_tag']}")
    print(f"  CUDA Tag: {details['cuda_tag']}")
    print(f"  Platform Tag: {details['platform_tag']}")
    return details


def main():
    parser = argparse.ArgumentParser(
        description="Build wheels inside Docker container."
    )
    parser.add_argument(
        "--config", required=True, help="Path to the configuration file."
    )
    args = parser.parse_args()

    print(f"Loading configuration from: {args.config}")
    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    env_details = get_env_details(config)
    output_base_dir = "/output"  # This is the mount point inside the container

    # Construct the final destination directory path structure
    final_dest_dir_base = os.path.join(
        output_base_dir,
        env_details["py_tag"],
        env_details["cuda_tag"],
        env_details["platform_tag"],
    )
    os.makedirs(final_dest_dir_base, exist_ok=True)
    print(f"Final wheel destination base: {final_dest_dir_base}")

    build_root = "/tmp/builds"
    os.makedirs(build_root, exist_ok=True)

    # check python version match the config
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if py_version != config["build_target"]["python_version"]:
        print(f"Error: Python version mismatch. Expected {config['build_target']['python_version']}, got {py_version}")
        sys.exit(1)
    print(f"Python version check passed: {py_version}")


    for project in config.get("projects", []):
        name = project["name"]
        repo_url = project["repo_url"]
        repo_ref = project.get("repo_ref")  # Optional
        build_command_override = project.get("build_command")
        project_deps = project.get("dependencies", [])
        build_env = project.get("build_env", {})  # Get build environment variables

        print(f"\n{'='*20} Processing project: {name} {'='*20}")
        project_build_dir = os.path.join(build_root, name)
        project_wheel_output_dir = os.path.join(project_build_dir, "dist")

        # Print build environment if specified
        if build_env:
            print(f"Build environment variables for {name}:")
            for key, value in build_env.items():
                print(f"  {key}={value}")

        # Clean up previous attempt if any
        if os.path.exists(project_build_dir):
            shutil.rmtree(project_build_dir)

        # Clone repository
        clone_command = ["git", "clone", "--depth", "1"]
        if repo_ref:
            clone_command.extend(["--branch", repo_ref])
        clone_command.extend([repo_url, project_build_dir])
        try:
            run_command(clone_command)
        except subprocess.CalledProcessError as e:
            print(f"Error cloning {name}: {e}. Skipping project.")
            continue

        # Install project-specific dependencies if specified
        if project_deps:
            print(f"Installing dependencies for {name}: {project_deps}")
            pip_install_cmd = ["python", "-m", "pip", "install"] + project_deps
            try:
                run_command(pip_install_cmd, cwd=project_build_dir, env=build_env)
            except subprocess.CalledProcessError as e:
                print(
                    f"Error installing dependencies for {name}: {e}. Skipping project."
                )
                continue

        # Build the wheel
        print(f"Building wheel for {name}...")
        os.makedirs(project_wheel_output_dir, exist_ok=True)

        found_wheels = []  # Initialize found_wheels list
        if build_command_override:
            # Handle custom build command (needs careful parsing/execution)
            print(f"Using custom build command: {build_command_override}")
            # Simple execution (assuming it produces wheel in cwd):
            # More robust parsing might be needed depending on command complexity
            build_cmd_list = build_command_override.split()
            try:
                run_command(build_cmd_list, cwd=project_build_dir, env=build_env)
                # Need to figure out where the wheel landed if using custom command
                print(
                    f"Warning: Custom build command used. Assuming wheel is in {project_build_dir} or subdirs."
                )
                # Simple search for wheel file after custom command
                found_wheels = list(Path(project_build_dir).rglob("*.whl"))
            except subprocess.CalledProcessError as e:
                print(
                    f"Error running custom build command for {name}: {e}. Skipping project."
                )
                continue

        else:
            # Standard pip wheel build
            build_cmd = [
                "python",
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",  # Avoid bundling dependencies
                "-w",
                project_wheel_output_dir,  # Output directory
            ]
            try:
                run_command(build_cmd, cwd=project_build_dir, env=build_env)
                found_wheels = [
                    os.path.join(project_wheel_output_dir, f)
                    for f in os.listdir(project_wheel_output_dir)
                    if f.endswith(".whl")
                ]
            except subprocess.CalledProcessError as e:
                print(f"Error building wheel for {name}: {e}. Skipping project.")
                continue

        # Move wheel(s) to final destination
        if not found_wheels:
            print(f"Error: No wheel file found for {name} after build.")
            continue

        for wheel_file_path in found_wheels:
            # Convert Path object to string if necessary before os.path.isfile
            wheel_file_path_str = str(wheel_file_path)
            if os.path.isfile(wheel_file_path_str):
                wheel_filename = os.path.basename(wheel_file_path_str)
                dest_path = os.path.join(final_dest_dir_base, wheel_filename)
                print(f"Moving {wheel_filename} to {final_dest_dir_base}")
                shutil.move(wheel_file_path_str, dest_path)
            else:
                print(
                    f"Warning: Expected wheel file not found at {wheel_file_path_str}"
                )

        # Clean up build directory for the project
        # shutil.rmtree(project_build_dir) # Keep for debugging?

    print(f"\n{'='*20} Build process finished {'='*20}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nBuild script failed: {e}", file=sys.stderr)
        sys.exit(1)

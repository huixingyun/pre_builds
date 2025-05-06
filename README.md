# CUDA Wheel Builder

This project provides an automated way to build Python wheel files for projects requiring specific CUDA versions on Nvidia GPUs. It uses Docker to ensure a consistent build environment based on official PyTorch images and is driven by a Makefile and a configuration file.

## Prerequisites

- Docker with Nvidia Container Toolkit support (for `--gpus all`)
- Python 3.x
- `pip install pyyaml` (for generating the Dockerfile)
- `make`

## Project Structure

```
.
├── Makefile             # Main build driver
├── config.yaml          # Configuration for build targets and projects
├── generate_dockerfile.py # Script to create Dockerfile from config
├── build_script.py      # Script to run inside Docker for cloning and building
├── templates/
│   └── Dockerfile.template # Template for Dockerfile generation
├── .gitignore           # Specifies intentionally untracked files
├── output/              # Default directory for built wheels (gitignored)
│   └── wheelhouse/        # Subdirectory created during build
│       └── py<VER>/         # e.g., py310
│           └── cuda<VER>/   # e.g., cuda11.8
│               └── <PLATFORM>/ # e.g., linux_x86_64
│                   └── <wheel_file>.whl
└── README.md            # This file
```

## Configuration (`config.yaml`)

Before running the build, edit `config.yaml`:

1.  **`output_dir_host`**: Set the path on your host machine where the built wheels will be stored.
2.  **`build_target`**: Specify the desired `python_version`, `cuda_version`, and `pytorch_version`. The script uses these to select the correct base Docker image.
3.  **`projects`**: List the projects you want to build:
    - `name`: A short name for the project.
    - `repo_url`: The Git repository URL.
    - `repo_ref`: (Optional) The specific branch, tag, or commit hash to check out. If omitted, the default branch is used.
    - `build_command`: (Optional) A custom command string to build the wheel (e.g., if not using standard `pip wheel .`).
    - `dependencies`: (Optional) A list of pip packages to install _before_ building this specific project.
4.  **`pytorch_base_images`**: Ensure the mapping contains an entry for the `pytorch_version` and `cuda_version` combination specified in `build_target`. Use tags from [PyTorch Docker Hub](https://hub.docker.com/r/pytorch/pytorch/tags).
5.  **`apt_packages`**: List any additional system packages needed by your projects during build (installed via `apt-get`).
6.  **`pip_packages`**: List any additional Python packages needed in the build environment _before_ cloning/building projects (installed via `pip`). `PyYAML` is required by the build script itself.

## Usage

1.  Configure `config.yaml` as described above.
2.  Run the build from the project root directory:

    ```bash
    make
    ```

    This command will:

    - Generate `Dockerfile.generated` based on `config.yaml` and the template.
    - Build the Docker image with a tag like `wheel-builder:py<VER>-cuda<VER>`.
    - Run the build container, which executes `build_script.py`.
    - Clone, build, and place the wheels in the configured `output_dir_host` directory, organized by Python version, CUDA version, and platform.

### Other `make` Commands

- `make generate_dockerfile`: Only generate the `Dockerfile.generated`.
- `make build_image`: Generate the Dockerfile and build the Docker image.
- `make run_build`: Run the build process in the container (assumes image exists).
- `make clean`: Remove `Dockerfile.generated` and the `output/` directory.
- `make help`: Display available commands.

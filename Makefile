# --- Configuration ---
CONFIG_FILE         ?= config.yaml
DOCKERFILE_TEMPLATE ?= templates/Dockerfile.template
DOCKERFILE_GENERATED:= Dockerfile.generated
GENERATE_SCRIPT     := generate_dockerfile.py
BUILD_SCRIPT        := build_script.py

# Read PYTHON_VERSION and CUDA_VERSION from config for tagging image uniquely
# Use python to parse yaml safely, requires PyYAML installed on host OR use simpler grep/sed
# Using simple grep/sed here for less host dependency:
PYTHON_VERSION      := $(shell grep 'python_version:' $(CONFIG_FILE) | head -n 1 | sed 's/.*: *"\([^"]*\).*/\1/')
CUDA_VERSION        := $(shell grep 'cuda_version:' $(CONFIG_FILE) | head -n 1 | sed 's/.*: *"\([^"]*\).*/\1/')
BUILDER_IMAGE_TAG   := wheel-builder:py$(PYTHON_VERSION)-cuda$(CUDA_VERSION)

# Read output dir from config for mounting
OUTPUT_DIR_HOST     := $(shell grep 'output_dir_host:' $(CONFIG_FILE) | head -n 1 | sed 's/.*: //')

# --- Targets ---

.PHONY: all build generate_dockerfile run_build clean help

# Default target
all: build

# Full build process: generate Dockerfile -> build image -> run build
build: run_build

# Generate the Dockerfile
generate_dockerfile: $(GENERATE_SCRIPT) $(CONFIG_FILE) $(DOCKERFILE_TEMPLATE)
	@echo "--> Generating Dockerfile for Python $(PYTHON_VERSION), CUDA $(CUDA_VERSION)..."
	python $(GENERATE_SCRIPT) --config $(CONFIG_FILE) --template $(DOCKERFILE_TEMPLATE) --output $(DOCKERFILE_GENERATED)

# Build the Docker image using the generated Dockerfile
build_image: generate_dockerfile
	@echo "--> Building Docker image ($(BUILDER_IMAGE_TAG))..."
	docker build -f $(DOCKERFILE_GENERATED) -t $(BUILDER_IMAGE_TAG) .

# Run the build process inside the container
run_build: build_image
	@echo "--> Ensuring host output directory exists: $(OUTPUT_DIR_HOST)"
	mkdir -p $(OUTPUT_DIR_HOST)
	@echo "--> Running build container ($(BUILDER_IMAGE_TAG))..."
	@echo "    Mounting $(shell pwd)/$(OUTPUT_DIR_HOST) -> /output"
	docker run --rm --gpus all \
		-v "$(shell pwd)/$(OUTPUT_DIR_HOST):/output" \
		-v "$(shell pwd)/$(CONFIG_FILE):/workspace/$(CONFIG_FILE):ro" \
		-v "$(shell pwd)/$(BUILD_SCRIPT):/workspace/$(BUILD_SCRIPT):ro" \
		$(BUILDER_IMAGE_TAG)
		# The entrypoint in Dockerfile calls build_script.py automatically
	@echo "--> Build process complete. Wheels should be in $(OUTPUT_DIR_HOST)"

# Clean up generated files and output directory
clean:
	@echo "--> Cleaning up..."
	rm -f $(DOCKERFILE_GENERATED)
	rm -rf $(OUTPUT_DIR_HOST)
	# Optionally remove the built docker image(s) matching the pattern
	# docker images -q 'wheel-builder:*' | xargs --no-run-if-empty docker rmi

# Help message
help:
	@echo "Makefile for building Python Wheels in Docker"
	@echo ""
	@echo "Usage:"
	@echo "  make all          - Generate Dockerfile, build image, and run build (default)"
	@echo "  make build        - Same as 'all'"
	@echo "  make generate_dockerfile - Only generate the Dockerfile based on config.yaml"
	@echo "  make build_image  - Generate Dockerfile and build the Docker image"
	@echo "  make run_build    - Build the image (if needed) and run the wheel building container"
	@echo "  make clean        - Remove generated Dockerfile and output directory"
	@echo ""
	@echo "Configuration:"
	@echo "  - Edit 'config.yaml' to define build targets (Python, CUDA, PyTorch versions)"
	@echo "    and projects (repository URL, ref)."
	@echo "  - Adjust base image mapping and dependencies in 'config.yaml'."
	@echo "  - Modify 'templates/Dockerfile.template' if needed." 
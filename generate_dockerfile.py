import yaml
import argparse
import os
import sys

DEFAULT_CONFIG = 'config.yaml'
DEFAULT_TEMPLATE = 'templates/Dockerfile.template'
DEFAULT_OUTPUT = 'Dockerfile.generated'

def get_pytorch_base_image(config):
    """Finds the base image URL from the config mapping."""
    pt_version = config['build_target']['pytorch_version']
    cuda_version = config['build_target']['cuda_version']
    try:
        return config['pytorch_base_images'][pt_version][cuda_version]
    except KeyError:
        print(f"Error: No base image defined in config.yaml for PyTorch {pt_version} and CUDA {cuda_version}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Generate Dockerfile from configuration.')
    parser.add_argument('--config', default=DEFAULT_CONFIG, help=f'Path to the configuration file (default: {DEFAULT_CONFIG})')
    parser.add_argument('--template', default=DEFAULT_TEMPLATE, help=f'Path to the Dockerfile template (default: {DEFAULT_TEMPLATE})')
    parser.add_argument('--output', default=DEFAULT_OUTPUT, help=f'Path for the generated Dockerfile (default: {DEFAULT_OUTPUT})')
    args = parser.parse_args()

    print(f"Reading configuration from: {args.config}")
    if not os.path.exists(args.config):
        print(f"Error: Config file not found at {args.config}")
        sys.exit(1)
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    print(f"Reading template from: {args.template}")
    if not os.path.exists(args.template):
        print(f"Error: Template file not found at {args.template}")
        sys.exit(1)
    with open(args.template, 'r') as f:
        template_content = f.read()

    # --- Prepare template substitutions ---
    base_image = get_pytorch_base_image(config)
    apt_packages = " ".join(config.get('apt_packages', []))
    pip_packages = " ".join(config.get('pip_packages', []))
    py_ver_major_minor = ".".join(config['build_target']['python_version'].split('.')[:2]) # e.g., "3.10"

    substitutions = {
        'BASE_IMAGE': base_image,
        'APT_PACKAGES': apt_packages,
        'PIP_PACKAGES': pip_packages,
        'PYTHON_VERSION_MAJOR_MINOR': py_ver_major_minor,
    }

    # --- Perform substitution ---
    generated_dockerfile_content = template_content.format(**substitutions)

    # --- Write output file ---
    print(f"Writing generated Dockerfile to: {args.output}")
    with open(args.output, 'w') as f:
        f.write(generated_dockerfile_content)

    print("Dockerfile generation complete.")

if __name__ == "__main__":
    main() 
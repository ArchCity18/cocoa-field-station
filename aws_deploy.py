#!/usr/bin/env python3
"""
AWS Deployment Helper for Cocoa Field Station

This script assists with deploying the Cocoa Field Station to AWS.
It does NOT create an AWS account - that must be done manually at aws.amazon.com.

Usage:
    python aws_deploy.py --help
    python aws_deploy.py build-images
    python aws_deploy.py deploy --region us-east-1 --domain field.example.com
"""

import argparse
import os
import subprocess
import sys
import json
from pathlib import Path


ROOT = Path(__file__).parent


def run(cmd, cwd=None, env=None):
    """Run a command and return the result."""
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd or ROOT, env=env or os.environ.copy(), capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}")
    return result


def check_aws_cli():
    """Check if AWS CLI is installed and configured."""
    try:
        result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"AWS CLI: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("AWS CLI not found. Install from https://aws.amazon.com/cli/")
    return False


def check_docker():
    """Check if Docker is available."""
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Docker: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("Docker not found. Install from https://docker.com/")
    return False


def build_images(args):
    """Build Docker images for Streamlit and PHP API."""
    print("=== Building Docker Images ===")
    
    # Build Streamlit image
    print("\n--- Building Streamlit image ---")
    run(f"docker build -t cocoa-field-station:latest -f Dockerfile .")
    
    # Build PHP API image
    print("\n--- Building PHP API image ---")
    run(f"docker build -t cocoa-field-station-api:latest -f backend/Dockerfile backend")
    
    print("\n✓ Images built successfully")
    print("  cocoa-field-station:latest")
    print("  cocoa-field-station-api:latest")


def tag_and_push_images(args):
    """Tag and push images to Amazon ECR."""
    if not args.ecr_repo_streamlit or not args.ecr_repo_api:
        raise ValueError("ECR repository URLs required. Use --ecr-repo-streamlit and --ecr-repo-api")
    
    print("=== Tagging and Pushing to ECR ===")
    
    # Get login token for ECR
    region = args.region or "us-east-1"
    run(f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {args.ecr_repo_streamlit.split('/')[0]}")
    
    # Tag and push Streamlit
    tag = args.tag or "latest"
    streamlit_uri = f"{args.ecr_repo_streamlit}:{tag}"
    api_uri = f"{args.ecr_repo_api}:{tag}"
    
    run(f"docker tag cocoa-field-station:latest {streamlit_uri}")
    run(f"docker push {streamlit_uri}")
    
    # Tag and push PHP API
    run(f"docker tag cocoa-field-station-api:latest {api_uri}")
    run(f"docker push {api_uri}")
    
    print(f"\n✓ Images pushed:")
    print(f"  {streamlit_uri}")
    print(f"  {api_uri}")


def create_secrets(args):
    """Create AWS Secrets Manager entries."""
    print("=== Creating AWS Secrets Manager Entries ===")
    
    # These would be created with actual secret values
    # For security, we only show the structure here
    secrets = {
        "cocoa/streamlit/database-url": "postgresql://...",
        "cocoa/streamlit/secrets-toml": "[auth]...",
        "cocoa/php/db-dsn": "pgsql:host=...;port=5432;dbname=...;sslmode=require",
        "cocoa/php/db-user": "...",
        "cocoa/php/db-password": "...",
        "cocoa/php/pepper": "...",
        "cocoa/php/google-web-client-id": "...",
        "cocoa/php/google-android-client-id": "...",
        "cocoa/php/google-ios-client-id": "...",
        "cocoa/php/allowed-origins": '["https://field.example.com"]',
    }
    
    for name, description in secrets.items():
        print(f"  {name}: {description}")
    
    print("\n⚠️  Create these secrets manually in AWS Console or use:")
    print("aws secretsmanager create-secret --name cocoa/streamlit/database-url --secret-string '...'")
    print("See docs/AWS_Deployment_Guide.md for complete list.")


def deploy_ecs(args):
    """Deploy ECS services (requires existing cluster, task definitions)."""
    print("=== ECS Deployment ===")
    print("This requires pre-configured ECS cluster, task definitions, and services.")
    print("See docs/AWS_Deployment_Guide.md for step-by-step instructions.")
    
    # This would create/update ECS services
    # For now, just show the commands that would be run
    commands = [
        f"aws ecs update-service --cluster cocoa-field-station --service streamlit --force-new-deployment --region {args.region}",
        f"aws ecs update-service --cluster cocoa-field-station --service php-api --force-new-deployment --region {args.region}",
    ]
    for cmd in commands:
        print(f"  {cmd}")


def verify_deployment(args):
    """Verify the deployment is working."""
    print("=== Verifying Deployment ===")
    
    domain = args.domain or "field.example.com"
    api_domain = args.api_domain or "api.example.com"
    
    checks = [
        f"curl -s https://{domain}/_stcore/health",
        f"curl -s https://{api_domain}/cocoa-security/api.php?route=health",
    ]
    
    for check in checks:
        print(f"  {check}")


def main():
    parser = argparse.ArgumentParser(description="AWS Deployment Helper for Cocoa Field Station")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Build command
    subparsers.add_parser("build-images", help="Build Docker images locally")
    
    # Push command
    push_parser = subparsers.add_parser("push-images", help="Tag and push images to ECR")
    push_parser.add_argument("--ecr-repo-streamlit", required=True, help="ECR repository URI for Streamlit")
    push_parser.add_argument("--ecr-repo-api", required=True, help="ECR repository URI for PHP API")
    push_parser.add_argument("--region", default="us-east-1", help="AWS region")
    push_parser.add_argument("--tag", default="latest", help="Image tag")
    
    # Secrets command
    subparsers.add_parser("create-secrets", help="Show required AWS Secrets Manager entries")
    
    # Deploy command
    deploy_parser = subparsers.add_parser("deploy-ecs", help="Deploy to ECS (requires existing setup)")
    deploy_parser.add_argument("--region", default="us-east-1", help="AWS region")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify deployment health")
    verify_parser.add_argument("--domain", help="Streamlit domain")
    verify_parser.add_argument("--api-domain", help="API domain")
    
    # Full deploy command
    full_parser = subparsers.add_parser("full-deploy", help="Run full deployment pipeline")
    full_parser.add_argument("--ecr-repo-streamlit", required=True, help="ECR repository URI for Streamlit")
    full_parser.add_argument("--ecr-repo-api", required=True, help="ECR repository URI for PHP API")
    full_parser.add_argument("--region", default="us-east-1", help="AWS region")
    full_parser.add_argument("--domain", help="Streamlit domain")
    full_parser.add_argument("--api-domain", help="API domain")
    full_parser.add_argument("--tag", default="latest", help="Image tag")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Check prerequisites
    if args.command in ("build-images", "push-images", "full-deploy"):
        if not check_docker():
            return 1
    
    if args.command in ("push-images", "create-secrets", "deploy-ecs", "full-deploy"):
        if not check_aws_cli():
            return 1
    
    try:
        if args.command == "build-images":
            build_images(args)
        elif args.command == "push-images":
            tag_and_push_images(args)
        elif args.command == "create-secrets":
            create_secrets(args)
        elif args.command == "deploy-ecs":
            deploy_ecs(args)
        elif args.command == "verify":
            verify_deployment(args)
        elif args.command == "full-deploy":
            build_images(args)
            tag_and_push_images(args)
            create_secrets(args)
            deploy_ecs(args)
            if args.domain:
                verify_deployment(args)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
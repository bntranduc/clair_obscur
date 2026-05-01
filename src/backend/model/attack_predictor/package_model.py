"""
Package model artifacts into model.tar.gz for SageMaker

Usage:
    python package_model.py
    
This creates model.tar.gz containing all necessary artifacts:
    - *.joblib files (predictor joblib files)
    - inference.py (SageMaker entry point)
    - predictor.py (AttackPredictor class)
    - features.py (feature extraction)
    - labels.py (label definitions)
    - metadata.json (model metadata)
"""

import argparse
import json
import tarfile
from pathlib import Path


def package_model(
    output_path: str = "model.tar.gz",
    model_dir: Path | None = None,
) -> str:
    """Create model.tar.gz with all necessary artifacts.
    
    Args:
        output_path: Output path for model.tar.gz
        model_dir: Directory containing model artifacts (default: current dir)
        
    Returns:
        Path to created archive
    """
    if model_dir is None:
        model_dir = Path.cwd()
    else:
        model_dir = Path(model_dir)
    
    output_path = Path(output_path)
    required_files = [
        "inference.py",
        "predictor.py",
        "features.py",
        "labels.py",
    ]
    
    optional_files = [
        "metadata.json",
    ]
    
    joblib_files = list(model_dir.glob("*.joblib"))

    missing = []
    for f in required_files:
        if not (model_dir / f).exists():
            missing.append(f)
    
    if missing:
        raise FileNotFoundError(
            f"Missing required files for packaging: {', '.join(missing)}\n"
            f"Run from attack_predictor directory with trained model artifacts."
        )
    
    print(f"Creating {output_path}...")
    print(f"Including: {', '.join(required_files)}")
    if joblib_files:
        print(f"Including: {', '.join(f.name for f in joblib_files)}")
    
    files_to_add = [
        (model_dir / f, f)
        for f in required_files
    ] + [
        (model_dir / f, f)
        for f in optional_files
        if (model_dir / f).exists()
    ] + [
        (f, f.name)
        for f in joblib_files
    ]
    
    with tarfile.open(output_path, "w:gz") as tar:
        for src_path, arcname in files_to_add:
            print(f"Adding {arcname}...")
            tar.add(src_path, arcname=arcname)
    
    size_mb = output_path.stat().st_size / (1024 ** 2)
    print(f"✓ Created {output_path} ({size_mb:.2f} MB)")
    
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Package model artifacts for SageMaker"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="model.tar.gz",
        help="Output path (default: model.tar.gz)",
    )
    parser.add_argument(
        "--model-dir",
        "-d",
        help="Model directory (default: current directory)",
    )
    
    args = parser.parse_args()
    
    try:
        path = package_model(args.output, args.model_dir)
        print(f"\n✓ Ready to upload: {path}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    main()

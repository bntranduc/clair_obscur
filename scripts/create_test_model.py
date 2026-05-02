"""
Quick Test Model Generator for SageMaker

Creates dummy model.joblib and label_encoder.joblib for testing the SageMaker workflow.
No real training data needed - uses synthetic data.

Usage:
    python create_test_model.py
    
Output:
    - model.joblib
    - label_encoder.joblib  
    - metadata.json
"""

import json
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from features import event_to_feature_vector, feature_names


def create_test_model():
    """Create a simple test model with synthetic data."""
    
    print("Creating test model...")
    
    # 1. Generate synthetic training data
    print(f"  • Generating synthetic data...")
    
    n_samples = 1000
    attack_types = ["normal", "ddos", "brute_force", "port_scan", "injection"]
    
    # Create synthetic normalized events
    events = []
    labels = []
    
    for i in range(n_samples):
        # Random event
        event = {
            "source_ip": f"192.168.{np.random.randint(0, 256)}.{np.random.randint(0, 256)}",
            "dest_ip": f"10.0.{np.random.randint(0, 256)}.{np.random.randint(0, 256)}",
            "source_port": np.random.randint(1024, 65535),
            "dest_port": np.random.choice([22, 80, 443, 3306, 5432, 6379]),
            "protocol": np.random.choice(["tcp", "udp"]),
            "flags": np.random.choice(["S", "SA", "F", "R", "P", "A"]),
            "payload_size": np.random.randint(0, 10000),
            "request_id": f"req_{i}",
            "timestamp": 1000000000 + i,
        }
        
        # Random label (weighted towards normal)
        if np.random.random() < 0.7:
            label = "normal"
        else:
            label = np.random.choice(attack_types[1:])
        
        events.append(event)
        labels.append(label)
    
    print(f"    Generated {len(events)} synthetic events")
    
    # 2. Extract features
    print(f"  • Extracting features...")
    X = np.array([event_to_feature_vector(e) for e in events])
    y = np.array(labels)
    
    print(f"    Feature matrix shape: {X.shape}")
    print(f"    Labels: {np.unique(y)}")
    
    # 3. Train model
    print(f"  • Training RandomForest...")
    model = RandomForestClassifier(
        n_estimators=10,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X, y)
    
    print(f"    Model trained with {model.n_estimators} trees")
    
    # 4. Encode labels
    print(f"  • Creating label encoder...")
    label_encoder = LabelEncoder()
    label_encoder.fit(attack_types)
    
    print(f"    Classes: {label_encoder.classes_}")
    
    # 5. Save artifacts
    print(f"  • Saving artifacts...")
    
    model_path = Path("model.joblib")
    encoder_path = Path("label_encoder.joblib")
    metadata_path = Path("metadata.json")
    
    joblib.dump(model, model_path)
    print(f"    ✓ {model_path} ({model_path.stat().st_size / 1024:.1f} KB)")
    
    joblib.dump(label_encoder, encoder_path)
    print(f"    ✓ {encoder_path} ({encoder_path.stat().st_size / 1024:.1f} KB)")
    
    metadata = {
        "type": "test_model",
        "attack_types": attack_types,
        "n_estimators": model.n_estimators,
        "training_samples": len(events),
        "feature_count": X.shape[1],
        "feature_names": feature_names(),
        "created": "2026-05-01",
    }
    
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"    ✓ {metadata_path}")
    
    # 6. Test the model
    print(f"\n  • Testing model...")
    
    # Test with a sample event
    test_event = {
        "source_ip": "192.168.1.100",
        "dest_ip": "10.0.0.1",
        "source_port": 54321,
        "dest_port": 443,
        "protocol": "tcp",
        "flags": "S",
        "payload_size": 100,
        "request_id": "test_req",
        "timestamp": 1000000000,
    }
    
    test_vector = event_to_feature_vector(test_event)
    prediction = model.predict([test_vector])[0]
    probas = model.predict_proba([test_vector])[0]
    
    print(f"    Sample prediction: {prediction}")
    print(f"    Probabilities: {dict(zip(model.classes_, probas))}")
    
    print(f"\n✓ Test model created successfully!")
    print(f"\nNext steps:")
    print(f"  1. Create model.tar.gz:")
    print(f"     tar -czf model.tar.gz inference.py predictor.py features.py labels.py *.joblib metadata.json")
    print(f"  2. Upload to SageMaker:")
    print(f"     python upload_to_sagemaker.py --bucket ... --model-path model.tar.gz --role-arn ...")
    
    return model, label_encoder, metadata


if __name__ == "__main__":
    create_test_model()

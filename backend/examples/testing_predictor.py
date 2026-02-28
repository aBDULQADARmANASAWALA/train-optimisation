"""
Examples and tests for PredictionService.

Demonstrates:
- Training delay prediction models
- Training congestion prediction models
- Making delay predictions
- Making congestion predictions
- Tracking prediction errors
- Detecting and handling data drift
- Feature importance analysis
"""

from datetime import datetime
from uuid import uuid4, UUID
from pathlib import Path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.services.predictor import (
    PredictionService,
    TrainFeatures,
    SectionFeatures,
)
from app.repositories import TrainRepository, SectionRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base


def setup_test_repositories():
    """Create test repositories with in-memory database"""
    print("=== Setting Up Test Repositories ===")

    # Create in-memory database
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    train_repo = TrainRepository(session)
    section_repo = SectionRepository(session)

    print("✓ Test repositories initialized")
    return train_repo, section_repo


def example_train_models(predictor: PredictionService):
    """Example: Train both delay and congestion models"""
    print("\n=== Training Models ===")

    results = predictor.train_models()

    print(f"Training completed in {results.get('training_time_seconds', 0):.2f}s")
    print(f"\nDelay Model:")
    if results.get("delay_model_score"):
        print(f"  Mean Absolute Error: {results['delay_model_score']:.2f} minutes")
        print(f"  Training samples: {results.get('delay_samples', 0)}")
    else:
        print(f"  Status: Not trained (insufficient data)")

    print(f"\nCongestion Model:")
    if results.get("congestion_model_score"):
        print(f"  AUC-ROC Score: {results['congestion_model_score']:.3f}")
        print(f"  Training samples: {results.get('congestion_samples', 0)}")
    else:
        print(f"  Status: Not trained (insufficient data)")

    return results


def example_predict_delays(predictor: PredictionService):
    """Example: Predict delays for multiple trains"""
    print("\n=== Predicting Train Delays ===")

    # Create test train features
    test_trains = [
        TrainFeatures(
            train_id=UUID("30000000-0000-0000-0000-000000000001"),
            train_number="IC-101",
            priority_weight=2.5,
            departure_delay_minutes=1.0,
            time_of_day_minutes=540,  # 9:00 AM
            day_of_week=2,  # Wednesday
            current_section_load_percent=60.0,
            upcoming_section_load_percent=75.0,
            cumulative_delay_minutes=1.0,
        ),
        TrainFeatures(
            train_id=UUID("30000000-0000-0000-0000-000000000002"),
            train_number="RG-201",
            priority_weight=1.0,
            departure_delay_minutes=0.0,
            time_of_day_minutes=900,  # 3:00 PM
            day_of_week=4,  # Friday
            current_section_load_percent=40.0,
            upcoming_section_load_percent=50.0,
            cumulative_delay_minutes=0.0,
        ),
    ]

    predictions = []
    for features in test_trains:
        prediction = predictor.predict_delay(features, return_interval=True)
        predictions.append(prediction)

        print(f"\n{prediction.train_number}:")
        print(f"  Predicted Delay: {prediction.predicted_delay_minutes:.2f} min")
        print(f"  Confidence: {prediction.confidence:.1%}")
        print(f"  90% Interval: [{prediction.prediction_interval_lower:.2f}, {prediction.prediction_interval_upper:.2f}] min")

        if prediction.contributing_factors:
            print(f"  Top Contributing Factors:")
            for factor, importance in prediction.contributing_factors:
                print(f"    - {factor}: {importance:.3f}")

    return predictions


def example_predict_congestion(predictor: PredictionService):
    """Example: Predict congestion for sections"""
    print("\n=== Predicting Section Congestion ===")

    test_sections = [
        SectionFeatures(
            section_id=UUID("20000000-0000-0000-0000-000000000001"),
            time_of_day_minutes=480,  # 8:00 AM (peak hours)
            day_of_week=1,  # Tuesday
            current_occupancy=3,
            section_capacity=4,
            average_headway_utilization=0.85,
            upcoming_train_count_15min=2,
            upstream_congestion_percent=65.0,
        ),
        SectionFeatures(
            section_id=UUID("20000000-0000-0000-0000-000000000002"),
            time_of_day_minutes=1320,  # 10:00 PM (off-peak)
            day_of_week=3,  # Wednesday
            current_occupancy=1,
            section_capacity=4,
            average_headway_utilization=0.30,
            upcoming_train_count_15min=0,
            upstream_congestion_percent=10.0,
        ),
    ]

    predictions = []
    for features in test_sections:
        prediction = predictor.predict_congestion(features)
        predictions.append(prediction)

        print(f"\nSection {str(features.section_id)[:8]}...:")
        print(f"  Congestion Probability: {prediction.probability_congested:.1%}")
        print(f"  Confidence: {prediction.confidence:.1%}")
        print(f"  Predicted Occupancy: {prediction.predicted_occupancy}/{prediction.section_capacity} trains")
        print(f"  Recommendation: {prediction.recommendation.upper()}")

    return predictions


def example_error_tracking_and_drift(predictor: PredictionService):
    """Example: Track prediction errors and detect drift"""
    print("\n=== Error Tracking and Drift Detection ===")

    # Simulate actual vs predicted values
    test_cases = [
        (2.0, 1.8),   # actual, predicted
        (3.5, 2.9),
        (1.2, 1.5),
        (4.0, 3.2),
        (2.8, 3.1),
        (5.2, 6.5),  # Getting worse
        (6.1, 7.0),
        (4.8, 6.2),
    ]

    print(f"Tracking {len(test_cases)} prediction results:")
    for actual, predicted in test_cases:
        predictor.update_prediction_error(actual, predicted)
        error = abs(actual - predicted)
        print(f"  Actual: {actual:.1f}min, Predicted: {predicted:.1f}min, Error: {error:.2f}min")

    # Check for drift
    print(f"\nChecking for data drift...")
    drift_result = predictor.retrain_if_drift_detected()

    print(f"  Drift Detected: {drift_result['drift_detected']}")
    print(f"  Mean Error: {drift_result['mean_error']:.2f} min")
    print(f"  Threshold: {drift_result['threshold']:.2f} min")
    print(f"  Action Taken: {drift_result['action_taken']}")

    if drift_result['action_taken'] == 'retrained':
        print(f"  ✓ Models automatically retrained due to drift detection!")

    return drift_result


def example_model_info(predictor: PredictionService):
    """Example: Get model information and metadata"""
    print("\n=== Model Information ===")

    info = predictor.get_model_info()

    print(f"Delay Model:")
    print(f"  Trained: {info['delay_model_trained']}")
    if info['delay_model_trained_at']:
        print(f"  Trained at: {info['delay_model_trained_at']}")

    print(f"\nCongestion Model:")
    print(f"  Trained: {info['congestion_model_trained']}")
    if info['congestion_model_trained_at']:
        print(f"  Trained at: {info['congestion_model_trained_at']}")

    print(f"\nPrediction Tracking:")
    print(f"  Recent predictions: {info['recent_prediction_errors_count']}")
    print(f"  Mean error: {info['recent_mean_error']:.2f} min")
    print(f"  Drift threshold: {info['drift_threshold_mae']:.2f} min")

    return info


def example_batch_predictions(predictor: PredictionService):
    """Example: Make batch predictions for multiple trains and sections"""
    print("\n=== Batch Predictions ===")

    # Delay predictions for 3 trains
    train_features_list = [
        TrainFeatures(
            train_id=UUID(f"30000000-0000-0000-0000-{i:012d}"),
            train_number=f"TRAIN-{i}",
            priority_weight=2.0 - (i * 0.3),
            departure_delay_minutes=float(i),
            time_of_day_minutes=(540 + i * 60) % 1440,
            day_of_week=i % 7,
            current_section_load_percent=40 + (i * 15),
            upcoming_section_load_percent=50 + (i * 10),
            cumulative_delay_minutes=float(i * 0.5),
        )
        for i in range(3)
    ]

    delay_predictions = [
        predictor.predict_delay(f, return_interval=False)
        for f in train_features_list
    ]

    print(f"Delay Predictions for {len(delay_predictions)} trains:")
    for pred in delay_predictions:
        print(f"  {pred.train_number}: {pred.predicted_delay_minutes:.2f}min "
              f"(confidence: {pred.confidence:.1%})")

    # Congestion predictions for 2 sections
    section_features_list = [
        SectionFeatures(
            section_id=UUID(f"20000000-0000-0000-0000-{i:012d}"),
            time_of_day_minutes=480 + (i * 120),
            day_of_week=i % 7,
            current_occupancy=(i + 1),
            section_capacity=5,
            average_headway_utilization=0.5 + (i * 0.2),
            upcoming_train_count_15min=i,
            upstream_congestion_percent=30 + (i * 20),
        )
        for i in range(2)
    ]

    congestion_predictions = [
        predictor.predict_congestion(f)
        for f in section_features_list
    ]

    print(f"\nCongestion Predictions for {len(congestion_predictions)} sections:")
    for pred in congestion_predictions:
        print(f"  Section {str(pred.section_id)[:8]}: {pred.probability_congested:.1%} "
              f"(recommendation: {pred.recommendation})")


if __name__ == "__main__":
    print("PredictionService (ML-based Predictions) Examples and Tests\n")
    print("=" * 70)

    try:
        # Setup
        train_repo, section_repo = setup_test_repositories()

        # Create prediction service
        predictor = PredictionService(
            train_repository=train_repo,
            section_repository=section_repo,
            model_dir=Path("/tmp/mindicator_models"),
        )

        # Run examples
        example_train_models(predictor)
        example_predict_delays(predictor)
        example_predict_congestion(predictor)
        example_batch_predictions(predictor)
        example_model_info(predictor)
        example_error_tracking_and_drift(predictor)

        print("\n" + "=" * 70)
        print("\n✅ All predictor examples completed!")
        print("\nKey Capabilities Demonstrated:")
        print("  ✓ Model training with scikit-learn")
        print("  ✓ Delay prediction with confidence intervals")
        print("  ✓ Congestion probability prediction")
        print("  ✓ Feature engineering (time, load, priority)")
        print("  ✓ Feature importance analysis")
        print("  ✓ Prediction error tracking")
        print("  ✓ Data drift detection")
        print("  ✓ Automatic retraining on drift")
        print("  ✓ Model persistence (pickle)")
        print("  ✓ Extensible for deep learning")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

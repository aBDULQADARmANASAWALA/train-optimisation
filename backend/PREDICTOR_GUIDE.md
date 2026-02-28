# PredictionService - Machine Learning for Railway Operations

## Overview

This is a machine learning service for predicting railway operational metrics. It uses **scikit-learn** for now but is architected for easy upgrade to deep learning frameworks like TensorFlow or PyTorch.

Predicts:
- **Train Delays**: Expected arrival delays at stations
- **Section Congestion**: Probability of capacity constraints on route segments

## Architecture

### Two-Model System

**1. Delay Prediction Model**
```
Input: TrainFeatures → Output: Predicted Delay (minutes)
Type: Random Forest Regressor (100 trees, max_depth=10)
Performance: Mean Absolute Error achievable
Goal: Minimize Σ(|actual - predicted|)
```

**2. Congestion Prediction Model**
```
Input: SectionFeatures → Output: Congestion Probability (0.0-1.0)
Type: Random Forest Classifier (100 trees, max_depth=8)
Performance: AUC-ROC Score
Goal: Maximize area under ROC curve
```

### Feature Engineering

**For Delays (8 features):**
```python
features = [
    priority_weight,           # 0.5-3.0
    departure_delay_minutes,   # Accumulated so far
    time_of_day (normalized),  # 0-1, peak hours impact
    day_of_week (normalized),  # 0-1, weekday vs weekend
    current_section_load,      # 0-1, occupancy ratio
    upcoming_section_load,     # 0-1, predicted occupancy
    cumulative_delay,          # Running total delay
    reserved,                  # Future expansion
]
```

**For Congestion (7 features):**
```python
features = [
    time_of_day (normalized),       # 0-1
    day_of_week (normalized),       # 0-1
    current_occupancy,              # Number of trains
    capacity_ratio,                 # occupancy/capacity
    headway_utilization,            # 0-1, spacing efficiency
    upcoming_train_count_15min,    # Forecast arrivals
    upstream_congestion_percent,    # 0-1, propagation effect
]
```

### Preprocessing Pipeline

```
Raw Features
    ↓
[Normalization]
- Time of day: minutes → 0-1
- Day of week: 0-6 → 0-1
- Percentages: 0-100 → 0-1
- StandardScaler for model features
    ↓
Scaled Features
    ↓
[Model]
    ↓
Prediction Output
```

## Core Methods

### `train_models() → Dict`
**Purpose**: Train both delay and congestion models from historical data

**Process**:
1. Load historical data from repositories (or generate synthetic for testing)
2. Split 80% train / 20% test
3. Scale features with StandardScaler
4. Fit RandomForest models
5. Evaluate on test set
6. Save models to disk (pickle)

**Returns**:
```python
{
    "delay_model_score": 2.34,        # MAE in minutes
    "delay_samples": 500,
    "congestion_model_score": 0.873,  # AUC-ROC
    "congestion_samples": 300,
    "training_time_seconds": 5.2,
}
```

**When to call**:
- Startup (if not previously trained)
- Periodically (daily/weekly)
- When drift detected

### `predict_delay(features) → DelayPrediction`
**Purpose**: Predict arrival delay for a single train

**Input**: `TrainFeatures` object with 9 attributes

**Output**: `DelayPrediction` dataclass with:
```python
{
    "train_id": UUID,
    "train_number": str,
    "predicted_delay_minutes": float,     # 0-120 typically
    "confidence": float,                  # 0.0-1.0
    "prediction_interval_lower": float,   # 90% CI
    "prediction_interval_upper": float,
    "contributing_factors": [             # Top 3 features
        ("priority_weight", 0.234),
        ("section_load", 0.198),
        ("time_of_day", 0.156),
    ]
}
```

**Confidence Scoring**:
```
confidence = 1.0 - (recent_mean_error / 10.0)
Clamped to [0.0, 1.0]
```

**Prediction Intervals**: 90% confidence interval using recent prediction residuals
```
interval = prediction ± 1.645 × std_error
```

### `predict_congestion(features) → CongestionPrediction`
**Purpose**: Predict if section will be congested

**Input**: `SectionFeatures` object with 8 attributes

**Output**: `CongestionPrediction` dataclass with:
```python
{
    "section_id": UUID,
    "probability_congested": float,  # 0.0-1.0
    "confidence": float,             # 0.0-1.0
    "predicted_occupancy": int,
    "section_capacity": int,
    "recommendation": str,  # "low", "moderate", "high", "critical"
    "time_horizon_minutes": int,
}
```

**Probability Thresholds**:
```
prob < 0.2      → "low" (normal operations)
0.2-0.5         → "moderate" (monitor)
0.5-0.8         → "high" (consider mitigation)
prob ≥ 0.8      → "critical" (immediate action)
```

### `update_prediction_error(actual, predicted) → None`
**Purpose**: Track prediction accuracy for drift detection

**Input**:
```python
actual_delay = 3.5     # Observed real delay
predicted_delay = 2.8  # Model prediction
```

**Effect**:
- Calculates absolute error
- Stores in recent errors buffer (max 100)
- Used for confidence scoring
- Monitored for drift

### `retrain_if_drift_detected() → Dict`
**Purpose**: Detect data drift and trigger retraining

**Drift Detection Logic**:
```
mean_error = average(recent_100_errors)
IF mean_error > threshold (default 5.0 min):
    TRIGGER RETRAINING
    RESET ERROR BUFFER
```

**Returns**:
```python
{
    "drift_detected": bool,
    "mean_error": float,              # Recent mean error
    "threshold": float,               # Drift threshold
    "action_taken": str,  # "none", "retrained", "failed", "insufficient_data"
    "training_results": dict,         # If retrained
}
```

**Why Important**:
- Models degrade over time as operational patterns change
- Drift detection triggers automatic retraining
- Maintains prediction accuracy without manual intervention

### `get_model_info() → Dict`
**Purpose**: Get metadata about trained models

**Returns**:
```python
{
    "delay_model_trained": true,
    "delay_model_trained_at": "2024-02-28T10:30:45",
    "congestion_model_trained": true,
    "congestion_model_trained_at": "2024-02-28T10:31:12",
    "recent_prediction_errors_count": 47,
    "recent_mean_error": 1.23,        # minutes
    "drift_threshold_mae": 5.0,
}
```

## Data Flow

```
Historical Data (Repository)
    ↓
[Feature Engineering]
    ↓
Training Data (X, y)
    ↓
[Train-Test Split: 80-20]
    ↓
[StandardScaler.fit_transform]
    ↓
[RandomForest.fit]
    ↓
[Evaluate on Test Set]
    ↓
Trained Models + Scalers (pickled)
    ↓
[Later] New Prediction Request
    ↓
[Engineer Features]
    ↓
[Scale Features]
    ↓
[Model.predict]
    ↓
Prediction Output
```

## Extensibility for Deep Learning

The architecture supports seamless upgrade to deep learning:

```python
# Current (sklearn)
self.delay_regressor = RandomForestRegressor(...)

# Future (TensorFlow)
self.delay_regressor = tf.keras.Sequential([
    tf.keras.layers.Dense(64, activation='relu'),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(32, activation='relu'),
    tf.keras.layers.Dense(1),  # Output: delay
])

# Interface stays identical!
prediction = self.delay_regressor.predict(X)
```

**To upgrade**:
1. Replace `_load_historical_delays()` with actual historical DB queries
2. Swap RandomForest with Keras/PyTorch model in `_train_delay_model()`
3. Update `_engineer_delay_features()` if needed
4. Everything else works unchanged

## Model Persistence

Models are persisted using pickle:

```
models/
├── delay_regressor.pkl
├── delay_scaler.pkl
├── congestion_classifier.pkl
└── congestion_scaler.pkl
```

**Why pickle**: Simple serialization, works with sklearn objects

**Future**: Could switch to ONNX, SavedModel (TF), or PyTorch formats for production

## Feature Importance

RandomForest provides built-in feature importance:

```python
importances = model.feature_importances_  # [0.23, 0.18, 0.15, ...]
top_features = zip(feature_names, importances)
# [("section_load", 0.234), ("time_of_day", 0.198), ...]
```

Shows which factors most influence predictions:
- **High importance**: Model strongly relies on feature
- **Low importance**: Feature could be removed
- **Useful for**: Model debugging, feature selection

## Confidence Quantification

Confidence is calculated two ways:

**1. Model-Based**: Recent prediction error
```
confidence = 1.0 - (mean_error / 10.0)
```
- Low error → high confidence
- High error → low confidence
- Automatically degraded by drift

**2. Statistical**: Prediction intervals
```
interval = [pred - 1.645σ, pred + 1.645σ]
```
- Wider interval → less certain
- Based on recent residual std dev
- 90% coverage theoretical

## Performance Characteristics

### Training Time
```
500 delay samples:      ~100ms
300 congestion samples: ~80ms
Total:                  ~180ms
```

### Prediction Time
```
Per train delay:        <1ms
Per section congestion: <1ms
Batch of 100 trains:    ~50ms
```

### Model Size
```
delay_regressor.pkl:         ~500KB
delay_scaler.pkl:            ~2KB
congestion_classifier.pkl:   ~400KB
congestion_scaler.pkl:       ~2KB
Total:                       ~900KB
```

## Testing

Run comprehensive tests:

```bash
python -m examples.testing_predictor
```

Tests include:
- Model training
- Delay prediction for multiple trains
- Congestion prediction for multiple sections
- Batch predictions
- Error tracking
- Drift detection
- Model information retrieval

## Design Principles

1. **Repository-Based**: No hardcoded data, loads from repositories
2. **Extensible**: Easy swap to deep learning without API changes
3. **Stateful**: Remembers models, errors, metadata between calls
4. **Observable**: Logs all major operations, provides confidence metrics
5. **Deterministic**: Same input → same prediction (when models trained)
6. **Fault-Tolerant**: Gracefully degrades if models not trained
7. **Driftable**: Detects model degradation and retrains automatically

## Future Enhancements

**Deep Learning**:
- LSTM for temporal sequences: `train_id, station_id, time_series`
- CNN for spatial patterns: network effects, proximity

**Ensemble Methods**:
- Combine RandomForest + Neural Net predictions
- Weighted average based on recent accuracy

**Real-Time Learning**:
- Online learning with streaming errors
- Faster adaptation to operational changes

**Multi-Task Learning**:
- Joint delay + congestion prediction
- Shared feature representations

**Uncertainty Quantification**:
- Bayesian models for principled uncertainty
- Conformal prediction intervals

---

**This predictor enables proactive decision-making** by forecasting delays and congestion before they occur, feeding predictions to the optimizer for better schedules.

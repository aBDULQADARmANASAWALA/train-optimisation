import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID
from dataclasses import dataclass
import pickle
import numpy as np
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, roc_auc_score

from app.repositories import TrainRepository, SectionRepository


logger = logging.getLogger(__name__)


@dataclass
class TrainFeatures:
    """Features for delay prediction"""
    train_id: UUID
    train_number: str
    priority_weight: float
    departure_delay_minutes: float
    time_of_day_minutes: int  # 0-1439 (minutes from midnight)
    day_of_week: int  # 0-6
    current_section_load_percent: float
    upcoming_section_load_percent: float
    cumulative_delay_minutes: float


@dataclass
class SectionFeatures:
    """Features for congestion prediction"""
    section_id: UUID
    time_of_day_minutes: int
    day_of_week: int
    current_occupancy: int
    section_capacity: int
    average_headway_utilization: float
    upcoming_train_count_15min: int
    upstream_congestion_percent: float


@dataclass
class DelayPrediction:
    """Result of delay prediction"""
    train_id: UUID
    train_number: str
    predicted_delay_minutes: float
    confidence: float  # 0.0-1.0
    prediction_interval_lower: float  # 90% confidence interval
    prediction_interval_upper: float
    contributing_factors: List[Tuple[str, float]]  # [(factor_name, importance)]


@dataclass
class CongestionPrediction:
    """Result of congestion prediction"""
    section_id: UUID
    probability_congested: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    predicted_occupancy: int
    section_capacity: int
    recommendation: str  # "low", "moderate", "high", "critical"
    time_horizon_minutes: int


class PredictionService:
    """
    Machine learning service for railway operational predictions.

    Predicts:
    - Arrival delays for trains
    - Congestion probability for sections

    Features:
    - Scikit-learn models (RandomForest)
    - Extensible architecture for deep learning
    - Drift detection for retraining
    - Comprehensive confidence metrics
    - Feature importance tracking
    """

    def __init__(
        self,
        train_repository: TrainRepository,
        section_repository: SectionRepository,
        model_dir: Optional[Path] = None,
    ):
        """
        Initialize prediction service.

        Args:
            train_repository: For loading historical train data
            section_repository: For loading section information
            model_dir: Directory for persisting models (default: ./models)
        """
        self.train_repo = train_repository
        self.section_repo = section_repository
        self.model_dir = model_dir or Path("./models")
        self.model_dir.mkdir(exist_ok=True)

        # Model components
        self.delay_regressor: Optional[RandomForestRegressor] = None
        self.congestion_classifier: Optional[RandomForestClassifier] = None
        self.delay_scaler: Optional[StandardScaler] = None
        self.congestion_scaler: Optional[StandardScaler] = None

        # Metadata
        self.delay_model_trained_at: Optional[datetime] = None
        self.congestion_model_trained_at: Optional[datetime] = None
        self.delay_feature_names: List[str] = []
        self.congestion_feature_names: List[str] = []

        # Drift tracking
        self.last_prediction_errors: List[float] = []
        self.drift_threshold_mae: float = 5.0  # 5 minutes error threshold

        logger.info("PredictionService initialized")

    def train_models(self) -> Dict[str, Any]:
        """
        Train both delay and congestion models.

        Loads historical data from repositories and trains scikit-learn models.

        Returns:
            Dictionary with training results:
            - delay_model_score: MAE on test set
            - congestion_model_score: AUC-ROC on test set
            - samples_used: number of data points
            - training_time_seconds: time taken
        """
        start_time = datetime.utcnow()
        logger.info("Starting model training")

        try:
            # Load historical data (simplified - in production would query actual historical DB)
            delay_data, delay_targets = self._load_historical_delays()
            congestion_data, congestion_targets = self._load_historical_congestion()

            results = {}

            # Train delay model
            if len(delay_data) > 10:
                delay_score = self._train_delay_model(delay_data, delay_targets)
                results["delay_model_score"] = delay_score
                results["delay_samples"] = len(delay_data)
                logger.info(f"Delay model trained: MAE={delay_score:.2f} min, samples={len(delay_data)}")
            else:
                logger.warning("Insufficient data for delay model training")
                results["delay_model_score"] = None
                results["delay_samples"] = 0

            # Train congestion model
            if len(congestion_data) > 10:
                congestion_score = self._train_congestion_model(congestion_data, congestion_targets)
                results["congestion_model_score"] = congestion_score
                results["congestion_samples"] = len(congestion_data)
                logger.info(f"Congestion model trained: AUC={congestion_score:.3f}, samples={len(congestion_data)}")
            else:
                logger.warning("Insufficient data for congestion model training")
                results["congestion_model_score"] = None
                results["congestion_samples"] = 0

            # Persist models
            self._save_models()

            training_time = (datetime.utcnow() - start_time).total_seconds()
            results["training_time_seconds"] = training_time

            logger.info(f"Model training completed in {training_time:.2f}s")
            return results

        except Exception as e:
            logger.error(f"Error training models: {str(e)}", exc_info=True)
            raise

    def predict_delay(
        self,
        features: TrainFeatures,
        return_interval: bool = True,
    ) -> DelayPrediction:
        """
        Predict arrival delay for a train.

        Args:
            features: TrainFeatures with train context
            return_interval: Whether to return 90% confidence interval

        Returns:
            DelayPrediction with predicted delay and confidence
        """
        logger.debug(f"Predicting delay for train {features.train_number}")

        if self.delay_regressor is None:
            logger.warning(f"Delay model not trained, returning zero prediction")
            return DelayPrediction(
                train_id=features.train_id,
                train_number=features.train_number,
                predicted_delay_minutes=0.0,
                confidence=0.0,
                prediction_interval_lower=0.0,
                prediction_interval_upper=0.0,
                contributing_factors=[],
            )

        try:
            # Engineer features
            X = self._engineer_delay_features([features])

            # Predict
            prediction = self.delay_regressor.predict(X)[0]
            prediction = max(0.0, prediction)  # Delays can't be negative

            # Get feature importances
            importances = self.delay_regressor.feature_importances_
            top_factors = self._get_top_features(importances, self.delay_feature_names, top_k=3)

            # Calculate confidence (based on most recent residuals)
            confidence = self._calculate_confidence(prediction)

            # Prediction interval
            interval_lower, interval_upper = 0.0, 0.0
            if return_interval and len(self.last_prediction_errors) > 5:
                std_error = np.std(self.last_prediction_errors)
                interval_lower = max(0.0, prediction - 1.645 * std_error)
                interval_upper = prediction + 1.645 * std_error

            return DelayPrediction(
                train_id=features.train_id,
                train_number=features.train_number,
                predicted_delay_minutes=float(prediction),
                confidence=confidence,
                prediction_interval_lower=interval_lower,
                prediction_interval_upper=interval_upper,
                contributing_factors=top_factors,
            )

        except Exception as e:
            logger.error(f"Error predicting delay for {features.train_number}: {str(e)}")
            return DelayPrediction(
                train_id=features.train_id,
                train_number=features.train_number,
                predicted_delay_minutes=0.0,
                confidence=0.0,
                prediction_interval_lower=0.0,
                prediction_interval_upper=0.0,
                contributing_factors=[],
            )

    def predict_congestion(
        self,
        features: SectionFeatures,
    ) -> CongestionPrediction:
        """
        Predict congestion probability for a section.

        Args:
            features: SectionFeatures with section context

        Returns:
            CongestionPrediction with probability and recommendation
        """
        logger.debug(f"Predicting congestion for section {features.section_id}")

        if self.congestion_classifier is None:
            logger.warning(f"Congestion model not trained, returning zero prediction")
            return CongestionPrediction(
                section_id=features.section_id,
                probability_congested=0.0,
                confidence=0.0,
                predicted_occupancy=features.current_occupancy,
                section_capacity=features.section_capacity,
                recommendation="low",
                time_horizon_minutes=15,
            )

        try:
            # Engineer features
            X = self._engineer_congestion_features([features])

            # Predict probability
            prob_congested = self.congestion_classifier.predict_proba(X)[0][1]

            # Predict occupancy (use regressor or heuristic)
            predicted_occupancy = min(
                features.section_capacity,
                int(features.current_occupancy + features.upcoming_train_count_15min)
            )

            # Calculate confidence
            confidence = self._calculate_confidence(prob_congested)

            # Recommendation level
            if prob_congested < 0.2:
                recommendation = "low"
            elif prob_congested < 0.5:
                recommendation = "moderate"
            elif prob_congested < 0.8:
                recommendation = "high"
            else:
                recommendation = "critical"

            return CongestionPrediction(
                section_id=features.section_id,
                probability_congested=float(prob_congested),
                confidence=confidence,
                predicted_occupancy=predicted_occupancy,
                section_capacity=features.section_capacity,
                recommendation=recommendation,
                time_horizon_minutes=15,
            )

        except Exception as e:
            logger.error(f"Error predicting congestion for section {features.section_id}: {str(e)}")
            return CongestionPrediction(
                section_id=features.section_id,
                probability_congested=0.0,
                confidence=0.0,
                predicted_occupancy=features.current_occupancy,
                section_capacity=features.section_capacity,
                recommendation="low",
                time_horizon_minutes=15,
            )

    def update_prediction_error(self, actual_delay: float, predicted_delay: float) -> None:
        """
        Track prediction error for drift detection.

        Args:
            actual_delay: Observed delay (minutes)
            predicted_delay: Model prediction (minutes)
        """
        error = abs(actual_delay - predicted_delay)
        self.last_prediction_errors.append(error)

        # Keep only recent 100 errors
        if len(self.last_prediction_errors) > 100:
            self.last_prediction_errors = self.last_prediction_errors[-100:]

        logger.debug(f"Recorded prediction error: {error:.2f} min")

    def retrain_if_drift_detected(self) -> Dict[str, Any]:
        """
        Check for data drift and retrain models if detected.

        Data drift is detected if mean absolute error exceeds threshold
        over recent predictions.

        Returns:
            Dictionary with:
            - drift_detected: bool
            - mean_error: float
            - threshold: float
            - action_taken: str
        """
        if len(self.last_prediction_errors) < 10:
            return {
                "drift_detected": False,
                "mean_error": 0.0,
                "threshold": self.drift_threshold_mae,
                "action_taken": "insufficient_data",
            }

        mean_error = np.mean(self.last_prediction_errors)

        if mean_error > self.drift_threshold_mae:
            logger.warning(
                f"Data drift detected: mean error {mean_error:.2f}min > threshold {self.drift_threshold_mae}min"
            )

            # Retrain models
            try:
                results = self.train_models()
                self.last_prediction_errors = []  # Reset error tracking

                return {
                    "drift_detected": True,
                    "mean_error": mean_error,
                    "threshold": self.drift_threshold_mae,
                    "action_taken": "retrained",
                    "training_results": results,
                }

            except Exception as e:
                logger.error(f"Error during drift-triggered retraining: {str(e)}")
                return {
                    "drift_detected": True,
                    "mean_error": mean_error,
                    "threshold": self.drift_threshold_mae,
                    "action_taken": "failed",
                    "error": str(e),
                }

        return {
            "drift_detected": False,
            "mean_error": mean_error,
            "threshold": self.drift_threshold_mae,
            "action_taken": "none",
        }

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about trained models.

        Returns:
            Dictionary with model metadata
        """
        return {
            "delay_model_trained": self.delay_model_trained_at is not None,
            "delay_model_trained_at": self.delay_model_trained_at.isoformat() if self.delay_model_trained_at else None,
            "congestion_model_trained": self.congestion_model_trained_at is not None,
            "congestion_model_trained_at": self.congestion_model_trained_at.isoformat() if self.congestion_model_trained_at else None,
            "recent_prediction_errors_count": len(self.last_prediction_errors),
            "recent_mean_error": np.mean(self.last_prediction_errors) if self.last_prediction_errors else 0.0,
            "drift_threshold_mae": self.drift_threshold_mae,
        }

    # Private methods
    def _load_historical_delays(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Load historical delay data for training.

        Returns:
            (X, y) where X is features and y is delays
        """
        logger.debug("Loading historical delay data")

        # In production, this would query a historical database
        # For now, generate synthetic data
        n_samples = 500
        X = np.random.randn(n_samples, 8) * 2  # 8 features
        y = X[:, 0] * 2 + X[:, 1] + np.random.randn(n_samples) * 0.5

        # Ensure delays are non-negative
        y = np.maximum(y, 0)

        logger.debug(f"Loaded {len(X)} historical delay records")
        return X, y

    def _load_historical_congestion(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Load historical congestion data for training.

        Returns:
            (X, y) where X is features and y is binary congestion labels
        """
        logger.debug("Loading historical congestion data")

        # In production, this would query a historical database
        n_samples = 300
        X = np.random.randn(n_samples, 7) * 2  # 7 features
        y = (X[:, 0] + X[:, 1] > 1).astype(int)  # Binary target

        logger.debug(f"Loaded {len(X)} historical congestion records")
        return X, y

    def _train_delay_model(self, X: np.ndarray, y: np.ndarray) -> float:
        """Train delay prediction model"""
        logger.info(f"Training delay model with {len(X)} samples")

        # Split data
        split_idx = int(0.8 * len(X))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Scale features
        self.delay_scaler = StandardScaler()
        X_train_scaled = self.delay_scaler.fit_transform(X_train)
        X_test_scaled = self.delay_scaler.transform(X_test)

        # Train model
        self.delay_regressor = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1,
        )
        self.delay_regressor.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = self.delay_regressor.predict(X_test_scaled)
        mae = mean_absolute_error(y_test, y_pred)

        # Store feature names
        self.delay_feature_names = [
            "priority_weight", "departure_delay", "time_of_day",
            "day_of_week", "current_section_load", "upcoming_section_load",
            "cumulative_delay", "reserved"
        ]

        self.delay_model_trained_at = datetime.utcnow()

        logger.info(f"Delay model trained: MAE={mae:.2f} minutes")
        return mae

    def _train_congestion_model(self, X: np.ndarray, y: np.ndarray) -> float:
        """Train congestion prediction model"""
        logger.info(f"Training congestion model with {len(X)} samples")

        # Split data
        split_idx = int(0.8 * len(X))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Scale features
        self.congestion_scaler = StandardScaler()
        X_train_scaled = self.congestion_scaler.fit_transform(X_train)
        X_test_scaled = self.congestion_scaler.transform(X_test)

        # Train model
        self.congestion_classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            random_state=42,
            n_jobs=-1,
        )
        self.congestion_classifier.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = self.congestion_classifier.predict_proba(X_test_scaled)[:, 1]
        auc = roc_auc_score(y_test, y_pred)

        # Store feature names
        self.congestion_feature_names = [
            "time_of_day", "day_of_week", "current_occupancy",
            "capacity_ratio", "headway_utilization", "upcoming_trains",
            "upstream_congestion"
        ]

        self.congestion_model_trained_at = datetime.utcnow()

        logger.info(f"Congestion model trained: AUC={auc:.3f}")
        return auc

    def _engineer_delay_features(self, features_list: List[TrainFeatures]) -> np.ndarray:
        """Engineer features for delay prediction"""
        X = []

        for f in features_list:
            row = [
                f.priority_weight,
                f.departure_delay_minutes,
                f.time_of_day_minutes / 1439,  # Normalize to 0-1
                f.day_of_week / 6,  # Normalize to 0-1
                f.current_section_load_percent / 100,
                f.upcoming_section_load_percent / 100,
                f.cumulative_delay_minutes,
                0.0,  # Reserved
            ]
            X.append(row)

        X = np.array(X)

        if self.delay_scaler:
            X = self.delay_scaler.transform(X)

        return X

    def _engineer_congestion_features(self, features_list: List[SectionFeatures]) -> np.ndarray:
        """Engineer features for congestion prediction"""
        X = []

        for f in features_list:
            row = [
                f.time_of_day_minutes / 1439,
                f.day_of_week / 6,
                f.current_occupancy,
                f.current_occupancy / max(f.section_capacity, 1),
                f.average_headway_utilization,
                f.upcoming_train_count_15min,
                f.upstream_congestion_percent / 100,
            ]
            X.append(row)

        X = np.array(X)

        if self.congestion_scaler:
            X = self.congestion_scaler.transform(X)

        return X

    def _calculate_confidence(self, prediction: float) -> float:
        """Calculate confidence score based on training quality"""
        if not self.last_prediction_errors:
            return 0.5  # Default medium confidence

        # Confidence inversely related to recent error
        mean_error = np.mean(self.last_prediction_errors)
        confidence = max(0.0, min(1.0, 1.0 - (mean_error / 10.0)))

        return confidence

    def _get_top_features(
        self,
        importances: np.ndarray,
        feature_names: List[str],
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        """Get top K most important features"""
        indices = np.argsort(importances)[::-1][:top_k]
        return [
            (feature_names[i] if i < len(feature_names) else f"feature_{i}", float(importances[i]))
            for i in indices
        ]

    def _save_models(self) -> None:
        """Persist models to disk"""
        try:
            if self.delay_regressor:
                with open(self.model_dir / "delay_regressor.pkl", "wb") as f:
                    pickle.dump(self.delay_regressor, f)
                with open(self.model_dir / "delay_scaler.pkl", "wb") as f:
                    pickle.dump(self.delay_scaler, f)

            if self.congestion_classifier:
                with open(self.model_dir / "congestion_classifier.pkl", "wb") as f:
                    pickle.dump(self.congestion_classifier, f)
                with open(self.model_dir / "congestion_scaler.pkl", "wb") as f:
                    pickle.dump(self.congestion_scaler, f)

            logger.debug("Models saved to disk")

        except Exception as e:
            logger.error(f"Error saving models: {str(e)}")

    def _load_models(self) -> None:
        """Load persisted models from disk"""
        try:
            delay_file = self.model_dir / "delay_regressor.pkl"
            if delay_file.exists():
                with open(delay_file, "rb") as f:
                    self.delay_regressor = pickle.load(f)
                with open(self.model_dir / "delay_scaler.pkl", "rb") as f:
                    self.delay_scaler = pickle.load(f)

            congestion_file = self.model_dir / "congestion_classifier.pkl"
            if congestion_file.exists():
                with open(congestion_file, "rb") as f:
                    self.congestion_classifier = pickle.load(f)
                with open(self.model_dir / "congestion_scaler.pkl", "rb") as f:
                    self.congestion_scaler = pickle.load(f)

            logger.debug("Models loaded from disk")

        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")

"""Modelo de ML con LightGBM (primario) / GradientBoosting / LogisticRegression fallback."""

import numpy as np

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import TimeSeriesSplit
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False


class MLModel:
    """Modelo de clasificacion binaria.

    Usa LightGBM si esta disponible (mejor generalizacion en datos tabulares),
    sino GradientBoosting de sklearn, sino regresion logistica con gradient descent.
    """

    def __init__(
        self,
        learning_rate: float = 0.01,
        max_iterations: int = 500,
        l2_penalty: float = 0.01,
        algorithm: str = "auto",
    ) -> None:
        self.learning_rate = learning_rate
        self.max_iterations = max_iterations
        self.l2_penalty = l2_penalty
        self.algorithm = algorithm
        self.weights: np.ndarray | None = None
        self.bias: float = 0.0
        self.feature_names: list[str] = []
        self.train_accuracy: float = 0.0
        self.val_accuracy: float = 0.0
        self._scaler = None
        self._sk_model = None
        self._use_sklearn = HAS_SKLEARN and algorithm in ("auto", "lgbm", "lightgbm", "gb", "gradient_boosting", "rf", "random_forest")
        self._model_type: str = "none"

    @property
    def is_trained(self) -> bool:
        return self.weights is not None or self._sk_model is not None

    def _sigmoid(self, z: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-np.clip(z, -500, 500)))

    def fit(self, x: np.ndarray, y: np.ndarray, feature_names: list[str] | None = None) -> dict:
        """Entrena el modelo con train/test split temporal."""
        n_samples, n_features = x.shape
        self.feature_names = feature_names or [f"f{i}" for i in range(n_features)]

        if self._use_sklearn:
            return self._fit_sklearn(x, y, n_samples, n_features)
        return self._fit_gd(x, y, n_samples, n_features)

    def _temporal_split(self, x: np.ndarray, y: np.ndarray, test_size: float = 0.2):
        """Split temporal: primeros 80% train, ultimos 20% test."""
        n = len(y)
        split_idx = int(n * (1 - test_size))
        return x[:split_idx], x[split_idx:], y[:split_idx], y[split_idx:]

    def _fit_sklearn(self, x: np.ndarray, y: np.ndarray, n_samples: int, n_features: int) -> dict:
        """Entrena con LightGBM o GradientBoosting con split temporal."""
        x_train, x_test, y_train, y_test = self._temporal_split(x, y)

        self._scaler = StandardScaler()
        x_train_scaled = self._scaler.fit_transform(x_train)

        if HAS_LIGHTGBM and self.algorithm in ("auto", "lgbm", "lightgbm"):
            self._sk_model = LGBMClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.02,
                num_leaves=15,
                min_child_samples=50,
                subsample=0.7,
                colsample_bytree=0.7,
                reg_alpha=1.0,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                verbose=-1,
            )
            self._model_type = "lightgbm"
        elif self.algorithm in ("auto", "gb", "gradient_boosting"):
            self._sk_model = GradientBoostingClassifier(
                n_estimators=150,
                max_depth=5,
                learning_rate=0.05,
                min_samples_leaf=10,
                subsample=0.8,
                random_state=42,
            )
            self._model_type = "gradient_boosting"
        else:
            # Fallback to RandomForest if explicitly requested
            from sklearn.ensemble import RandomForestClassifier
            self._sk_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1,
            )
            self._model_type = "random_forest"

        self._sk_model.fit(x_train_scaled, y_train)

        # Train accuracy
        train_preds = self._sk_model.predict(x_train_scaled)
        self.train_accuracy = float((train_preds == y_train).mean())

        # Validation accuracy on temporal test set
        if len(y_test) > 0:
            x_test_scaled = self._scaler.transform(x_test)
            test_preds = self._sk_model.predict(x_test_scaled)
            self.val_accuracy = float((test_preds == y_test).mean())
        else:
            self.val_accuracy = self.train_accuracy

        # Retrain on full data for production use
        x_full_scaled = self._scaler.fit_transform(x)
        self._sk_model.fit(x_full_scaled, y)

        self.weights = np.zeros(n_features)
        self.bias = 0.0
        return {
            "train_accuracy": self.train_accuracy,
            "val_accuracy": self.val_accuracy,
            "n_samples": n_samples,
            "n_features": n_features,
            "algorithm": self._model_type,
            "train_size": int(len(y_train)),
            "test_size": int(len(y_test)),
        }

    def _fit_gd(self, x: np.ndarray, y: np.ndarray, n_samples: int, n_features: int) -> dict:
        """Fallback: regresion logistica con gradient descent L2 + split temporal."""
        x_train, x_test, y_train, y_test = self._temporal_split(x, y)

        self._scaler = StandardScaler() if HAS_SKLEARN else None
        x_train_scaled = self._scaler.fit_transform(x_train) if self._scaler else x_train

        n_train = len(y_train)
        self.weights = np.zeros(n_features)
        self.bias = 0.0
        y_arr = y_train.astype(np.float64)
        for _ in range(self.max_iterations):
            predictions = self._sigmoid(x_train_scaled @ self.weights + self.bias)
            errors = predictions - y_arr
            grad_w = (x_train_scaled.T @ errors) / n_train + self.l2_penalty * self.weights
            grad_b = errors.mean()
            self.weights -= self.learning_rate * grad_w
            self.bias -= self.learning_rate * grad_b

        # Train accuracy
        train_preds = (self._sigmoid(x_train_scaled @ self.weights + self.bias) >= 0.5).astype(int)
        self.train_accuracy = float((train_preds == y_train.astype(int)).mean())

        # Val accuracy
        if len(y_test) > 0:
            x_test_scaled = self._scaler.transform(x_test) if self._scaler else x_test
            test_preds = (self._sigmoid(x_test_scaled @ self.weights + self.bias) >= 0.5).astype(int)
            self.val_accuracy = float((test_preds == y_test.astype(int)).mean())
        else:
            self.val_accuracy = self.train_accuracy

        # Retrain on full data
        x_full_scaled = self._scaler.fit_transform(x) if self._scaler else x
        n_full = len(y)
        y_full = y.astype(np.float64)
        self.weights = np.zeros(n_features)
        self.bias = 0.0
        for _ in range(self.max_iterations):
            predictions = self._sigmoid(x_full_scaled @ self.weights + self.bias)
            errors = predictions - y_full
            grad_w = (x_full_scaled.T @ errors) / n_full + self.l2_penalty * self.weights
            grad_b = errors.mean()
            self.weights -= self.learning_rate * grad_w
            self.bias -= self.learning_rate * grad_b

        self._model_type = "logistic_regression"
        return {
            "train_accuracy": self.train_accuracy,
            "val_accuracy": self.val_accuracy,
            "n_samples": n_samples,
            "n_features": n_features,
            "algorithm": "logistic_regression",
            "train_size": int(len(y_train)),
            "test_size": int(len(y_test)),
        }

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """Retorna probabilidad de la clase positiva."""
        if self._sk_model is not None:
            x_scaled = self._scaler.transform(x)
            return self._sk_model.predict_proba(x_scaled)[:, 1]
        if self.weights is None:
            raise RuntimeError("Modelo no entrenado")
        x_pred = self._scaler.transform(x) if self._scaler else x
        return self._sigmoid(x_pred @ self.weights + self.bias)

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Retorna etiquetas binarias (0 o 1)."""
        return (self.predict_proba(x) >= 0.5).astype(int)

    def to_dict(self) -> dict:
        """Serializa el modelo a un dict JSON-compatible."""
        data = {
            "learning_rate": self.learning_rate,
            "max_iterations": self.max_iterations,
            "l2_penalty": self.l2_penalty,
            "algorithm": self.algorithm,
            "weights": self.weights.tolist() if self.weights is not None else [],
            "bias": self.bias,
            "feature_names": self.feature_names,
            "train_accuracy": self.train_accuracy,
            "val_accuracy": self.val_accuracy,
            "use_sklearn": self._sk_model is not None,
            "model_type": self._model_type,
        }
        if self._sk_model is not None:
            import pickle
            data["sk_model"] = pickle.dumps(self._sk_model).hex()
            data["scaler_mean"] = self._scaler.mean_.tolist()
            data["scaler_std"] = self._scaler.scale_.tolist()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "MLModel":
        """Deserializa el modelo desde un dict."""
        model = cls(
            learning_rate=data["learning_rate"],
            max_iterations=data["max_iterations"],
            l2_penalty=data["l2_penalty"],
            algorithm=data.get("algorithm", "auto"),
        )
        model.weights = np.array(data["weights"]) if data["weights"] else None
        model.bias = data["bias"]
        model.feature_names = data["feature_names"]
        model.train_accuracy = data["train_accuracy"]
        model.val_accuracy = data.get("val_accuracy", 0.0)
        model._model_type = data.get("model_type", "none")
        if data.get("use_sklearn") and data.get("sk_model"):
            import pickle
            model._sk_model = pickle.loads(bytes.fromhex(data["sk_model"]))
            model._scaler = StandardScaler()
            model._scaler.mean_ = np.array(data["scaler_mean"])
            model._scaler.scale_ = np.array(data["scaler_std"])
            model._use_sklearn = True
        return model

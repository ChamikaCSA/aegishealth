from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""

    grpc_port: int = 50051
    rest_port: int = 8000
    grpc_tls_cert: str = "certs/server.crt"
    grpc_tls_key: str = "certs/server.key"
    grpc_tls_ca: str = "certs/ca.crt"
    grpc_tls_insecure: bool = False

    data_dir: str = str(Path(__file__).resolve().parents[3] / "data" / "eicu-collaborative-research-database-2.0")
    raw_client_data_dir: str = str(Path(__file__).resolve().parents[3] / "data" / "raw")

    # FL hyperparameters (defaults, overridden per training job)
    default_num_rounds: int = 50
    default_local_epochs: int = 5
    default_learning_rate: float = 0.001
    default_batch_size: int = 64
    default_fedprox_mu: float = 0.01
    default_dp_epsilon: float = 8.0
    default_dp_delta: float = 1e-5
    default_dp_max_grad_norm: float = 1.0
    default_class_weight_multiplier: float = 1.0
    default_threshold_beta: float = 1.0

    # Quorum / straggler handling
    round_timeout_seconds: float = 300.0
    min_quorum_ratio: float = 0.5

    # LSTM model
    lstm_input_size: int = 11
    lstm_hidden_size: int = 128
    lstm_num_layers: int = 2
    lstm_dropout: float = 0.3
    sequence_length: int = 24
    prediction_horizon_minutes: int = 360
    window_stride: int = 6
    max_neg_windows_per_patient: int = 10

    # Comma-separated extra origins. Local dev origins are always allowed.
    cors_origins: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Tuple

import torch

from app.core.orchestrator import get_orchestrator
from app.db.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def _infer_input_size_from_state(state_dict: dict[str, torch.Tensor]) -> int | None:
  """Infer model input_size from LSTM weight shapes."""
  for key in ("lstm.weight_ih_l0", "lstm.weight_ih_l0_reverse"):
    if key in state_dict:
      return state_dict[key].shape[1]
  for tensor in state_dict.values():
    if tensor.dim() >= 2:
      return tensor.shape[1]
  return None


def _build_model_from_state(
  state_dict: dict[str, torch.Tensor],
  config: dict[str, Any],
) -> Tuple[torch.nn.Module, int, int]:
  """Reconstruct LSTM model from state_dict and training config.

  Returns (model, seq_len, input_size).
  """
  from app.ml.lstm_model import create_model

  input_size = _infer_input_size_from_state(state_dict)
  if input_size is None:
    raise ValueError("Could not infer input_size from state_dict")

  hidden_size = int(config.get("lstm_hidden_size", 128))
  num_layers = int(config.get("lstm_num_layers", 2))
  dropout = float(config.get("lstm_dropout", 0.3))
  seq_len = int(config.get("sequence_length", 24))

  model = create_model(
    input_size=input_size,
    hidden_size=hidden_size,
    num_layers=num_layers,
    dropout=dropout,
  )
  model.load_state_dict(state_dict)
  model.eval()
  return model, seq_len, input_size


def _get_final_state(job_id: int) -> Tuple[dict[str, torch.Tensor], dict[str, Any]] | None:
  """Fetch final global state and config for a completed job."""
  orchestrator = get_orchestrator()
  job = orchestrator.get_job_state(job_id)
  if job is None or job.aggregator is None:
    logger.warning("No job state or aggregator found for job_id=%d", job_id)
    return None
  state = job.aggregator.get_global_state()
  config = job.config or {}
  return state, config


def export_and_upload_final_model(job_id: int) -> Tuple[str | None, str | None]:
  """Export final model for a job to PT and ONNX and upload to Supabase.

  Returns (pt_path, onnx_path) in the models bucket, or (None, None) on failure.
  """
  try:
    result = _get_final_state(job_id)
    if result is None:
      return None, None
    state_dict, config = result

    client = get_supabase()
    bucket = client.storage.from_("models")

    pt_object_path = f"jobs/{job_id}/model.pt"
    onnx_object_path = f"jobs/{job_id}/model.onnx"

    with tempfile.TemporaryDirectory() as tmpdir:
      pt_disk_path = os.path.join(tmpdir, "model.pt")
      onnx_disk_path = os.path.join(tmpdir, "model.onnx")

      torch.save(state_dict, pt_disk_path)

      model, seq_len, input_size = _build_model_from_state(state_dict, config)
      dummy_input = torch.zeros(1, seq_len, input_size, dtype=torch.float32)
      torch.onnx.export(
        model,
        dummy_input,
        onnx_disk_path,
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch_size"}, "logits": {0: "batch_size"}},
        opset_version=18,
        dynamo=False,
      )

      with open(pt_disk_path, "rb") as f:
        bucket.upload(pt_object_path, f)

      with open(onnx_disk_path, "rb") as f:
        bucket.upload(onnx_object_path, f)

    logger.info(
      "Exported and uploaded model for job %d to %s and %s",
      job_id,
      pt_object_path,
      onnx_object_path,
    )
    return pt_object_path, onnx_object_path
  except Exception:
    logger.exception("Failed to export/upload final model for job_id=%d", job_id)
    return None, None


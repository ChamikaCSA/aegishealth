"""
Homomorphic Encryption Engine for AegisHealth.

Provides CKKS-based encryption of model state dicts so that the central
server can aggregate client updates without ever seeing plaintext
weights.  Built on TenSEAL (Microsoft SEAL wrapper).

Usage in the FL pipeline:
  1. Server calls ``create_he_context()`` once per job.
  2. Server sends the *public* context to every client via
     ``create_public_context()``.
  3. Each client encrypts its model update with ``encrypt_state_dict()``.
  4. Server aggregates encrypted updates with
     ``encrypted_weighted_average()``.
  5. Server decrypts the result with ``decrypt_state_dict()``.
"""

from __future__ import annotations

import time
from collections import OrderedDict

import torch
import tenseal as ts


def create_he_context(
    poly_modulus_degree: int = 8192,
    coeff_mod_bit_sizes: list[int] | None = None,
    global_scale: float = 2**40,
) -> "ts.Context":
    """Create a TenSEAL CKKS context with public **and** secret keys."""
    if coeff_mod_bit_sizes is None:
        coeff_mod_bit_sizes = [60, 40, 40, 60]

    ctx = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=poly_modulus_degree,
        coeff_mod_bit_sizes=coeff_mod_bit_sizes,
    )
    ctx.global_scale = global_scale
    ctx.generate_galois_keys()
    return ctx


def create_public_context(context: "ts.Context") -> "ts.Context":
    """Return a copy of *context* that contains only the public key.

    This is what gets sent to clients — they can encrypt but not decrypt.
    """
    ctx_bytes = context.serialize(save_secret_key=False)
    public_ctx = ts.context_from(ctx_bytes)
    return public_ctx


def encrypt_state_dict(
    state_dict: dict[str, torch.Tensor],
    context: "ts.Context",
) -> tuple[list["ts.CKKSVector"], dict[str, tuple]]:
    """Encrypt every tensor in *state_dict* as a flat CKKS vector.

    Returns
    -------
    encrypted_vectors : list[ts.CKKSVector]
        One encrypted vector per parameter, in ``state_dict.keys()`` order.
    metadata : dict[str, tuple]
        Maps each key to its original shape so ``decrypt_state_dict`` can
        reconstruct the tensors.
    """
    encrypted_vectors: list[ts.CKKSVector] = []
    metadata: dict[str, tuple] = {}

    for key, tensor in state_dict.items():
        flat = tensor.float().cpu().view(-1).tolist()
        enc = ts.ckks_vector(context, flat)
        encrypted_vectors.append(enc)
        metadata[key] = tuple(tensor.shape)

    return encrypted_vectors, metadata


def decrypt_state_dict(
    encrypted_vectors: list["ts.CKKSVector"],
    keys: list[str],
    metadata: dict[str, tuple],
) -> dict[str, torch.Tensor]:
    """Decrypt encrypted vectors back into a ``state_dict``."""
    state_dict: dict[str, torch.Tensor] = OrderedDict()
    for enc_vec, key in zip(encrypted_vectors, keys):
        flat = enc_vec.decrypt()
        shape = metadata[key]
        state_dict[key] = torch.tensor(flat, dtype=torch.float32).view(shape)
    return state_dict


def encrypted_weighted_average(
    encrypted_states: list[list["ts.CKKSVector"]],
    weights: list[float],
) -> list["ts.CKKSVector"]:
    """Compute a weighted average entirely on encrypted data.

    Each element of *encrypted_states* is a list of ``CKKSVector`` (one
    per model parameter) — i.e. the output of ``encrypt_state_dict``.

    HE supports addition and scalar multiplication, which is all FedAvg
    needs:  ``avg[k] = sum_i( w_i * state_i[k] )``
    """
    total_w = sum(weights)
    normed = [w / total_w for w in weights]

    n_params = len(encrypted_states[0])
    result: list[ts.CKKSVector] = []

    for p_idx in range(n_params):
        acc = encrypted_states[0][p_idx] * normed[0]
        for i in range(1, len(encrypted_states)):
            acc = acc + encrypted_states[i][p_idx] * normed[i]
        result.append(acc)

    return result


def ciphertext_size_bytes(encrypted_vectors: list["ts.CKKSVector"]) -> int:
    """Total serialised size (bytes) of a list of encrypted vectors."""
    return sum(len(v.serialize()) for v in encrypted_vectors)


def secure_aggregate(
    client_states: list[dict[str, torch.Tensor]],
    client_weights: list[float],
    context: "ts.Context",
) -> tuple[dict[str, torch.Tensor], dict]:
    """End-to-end HE secure aggregation.

    Encrypts each client's state dict, performs weighted averaging on
    the ciphertexts, and decrypts the result.  Returns the aggregated
    state dict and a ``stats`` dict with timing / size information.

    Parameters
    ----------
    client_states : list of state dicts
    client_weights : per-client sample counts (or any positive weights)
    context : TenSEAL context **with** the secret key

    Returns
    -------
    aggregated_state : dict[str, torch.Tensor]
    stats : dict  with keys ``encrypt_time_ms``, ``aggregate_time_ms``,
            ``decrypt_time_ms``, ``ciphertext_bytes``, ``plaintext_bytes``
    """
    public_ctx = create_public_context(context)
    keys = list(client_states[0].keys())

    plaintext_bytes = sum(
        v.nelement() * v.element_size()
        for v in client_states[0].values()
    )

    t0 = time.time()
    encrypted_all: list[list[ts.CKKSVector]] = []
    metadata: dict[str, tuple] = {}
    for state in client_states:
        enc_vecs, meta = encrypt_state_dict(state, public_ctx)
        encrypted_all.append(enc_vecs)
        metadata = meta
    encrypt_ms = (time.time() - t0) * 1000

    ct_bytes = sum(ciphertext_size_bytes(ev) for ev in encrypted_all) // len(
        encrypted_all
    )

    t1 = time.time()
    agg_encrypted = encrypted_weighted_average(encrypted_all, client_weights)
    aggregate_ms = (time.time() - t1) * 1000

    agg_linked: list[ts.CKKSVector] = []
    for vec in agg_encrypted:
        linked = ts.lazy_ckks_vector_from(vec.serialize())
        linked.link_context(context)
        agg_linked.append(linked)

    t2 = time.time()
    aggregated_state = decrypt_state_dict(agg_linked, keys, metadata)
    decrypt_ms = (time.time() - t2) * 1000

    stats = {
        "encrypt_time_ms": encrypt_ms,
        "aggregate_time_ms": aggregate_ms,
        "decrypt_time_ms": decrypt_ms,
        "ciphertext_bytes_per_client": ct_bytes,
        "plaintext_bytes": plaintext_bytes,
        "overhead_ratio": ct_bytes / max(plaintext_bytes, 1),
    }

    return aggregated_state, stats

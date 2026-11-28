"""Read the fixed MAP workload profile once for the Modal runtime."""
import os
import re


_RUNTIME_KEYS = (
    "MAP_TRAINING_SOURCE_SHA", "MAP_TRAINING_MODAL_IMAGE_ID", "MAP_TRAINING_IMAGE_DIGEST",
    "MAP_TRAINING_RUNTIME_SECONDS", "MAP_TRAINING_HOURLY_MICROUSD",
    "MAP_TRAINING_QUOTE_EXPIRES_AT",
)


def map_training_profile_settings(environ=None):
    environ = os.environ if environ is None else environ
    try:
        source_sha = environ["MAP_TRAINING_SOURCE_SHA"]
        image_id = environ.get("MAP_TRAINING_MODAL_IMAGE_ID")
        image_digest = image_id or environ["MAP_TRAINING_IMAGE_DIGEST"]
        runtime_seconds = int(environ["MAP_TRAINING_RUNTIME_SECONDS"])
        hourly_microusd = int(environ["MAP_TRAINING_HOURLY_MICROUSD"])
        quote_expires_at = int(environ["MAP_TRAINING_QUOTE_EXPIRES_AT"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("map_training_profile_invalid") from exc
    image_pattern = r"im-[A-Za-z0-9]{8,128}" if image_id else r"sha256:[0-9a-f]{64}"
    if (not isinstance(source_sha, str) or re.fullmatch(r"[0-9a-f]{40}", source_sha) is None or
            not isinstance(image_digest, str) or re.fullmatch(image_pattern, image_digest) is None or
            runtime_seconds != 120):
        raise ValueError("map_training_profile_invalid")
    return {
        "source_sha": source_sha,
        "image_id": image_id,
        "image_digest": image_digest,
        "runtime_seconds": runtime_seconds,
        "hourly_microusd": hourly_microusd,
        "quote_expires_at": quote_expires_at,
        "runtime_environment": {key: environ[key] for key in _RUNTIME_KEYS if key in environ},
    }

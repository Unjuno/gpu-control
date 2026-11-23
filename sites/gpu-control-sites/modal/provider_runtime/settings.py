"""Validated settings required only by Kaggle and Hugging Face adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re


_RESOURCE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_KAGGLE_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}$")


@dataclass(frozen=True)
class ProviderSettings:
    enable_kaggle: bool = False
    kaggle_api_token: str = field(default="", repr=False, compare=False)
    kaggle_username: str = ""
    kaggle_staging_root: str = ""
    kaggle_source_cache_root: str = ""
    enable_huggingface_space: bool = False
    hf_space_read_token: str = field(default="", repr=False, compare=False)
    hf_artifact_write_token: str = field(default="", repr=False, compare=False)
    hf_artifact_repositories: tuple[str, ...] = ()
    hf_space_allowlist: tuple[str, ...] = ()
    max_output_bytes: int = 65_536

    def validate(self) -> None:
        if type(self.max_output_bytes) is not int or not 1 <= self.max_output_bytes <= 1_048_576:
            raise ValueError("max_output_bytes must be between 1 and 1048576")
        for token_name, token in (
            ("Kaggle token", self.kaggle_api_token),
            ("Hugging Face Space token", self.hf_space_read_token),
            ("Hugging Face artifact token", self.hf_artifact_write_token),
        ):
            if token and (token != token.strip() or len(token) > 4096 or
                          any(character.isspace() for character in token)):
                raise ValueError(f"{token_name} is malformed")
        if self.enable_kaggle:
            if not self.kaggle_api_token or _KAGGLE_USERNAME.fullmatch(self.kaggle_username) is None:
                raise ValueError("enabled Kaggle requires a token and fixed username")
            for label, value in (("staging", self.kaggle_staging_root),
                                 ("source cache", self.kaggle_source_cache_root)):
                path = Path(value)
                if not value or not path.is_absolute() or ".." in path.parts:
                    raise ValueError(f"Kaggle {label} root must be absolute")
        if self.enable_huggingface_space and not self.hf_space_read_token:
            raise ValueError("enabled Hugging Face Space requires a read token")
        if (self.hf_artifact_write_token and self.hf_space_read_token and
                self.hf_artifact_write_token == self.hf_space_read_token):
            raise ValueError("Hugging Face artifact and Space tokens must be distinct")
        for label, resources in (("artifact repository", self.hf_artifact_repositories),
                                 ("Space", self.hf_space_allowlist)):
            if len(resources) > 32 or len(set(resources)) != len(resources) or any(
                    _RESOURCE.fullmatch(resource) is None for resource in resources):
                raise ValueError(f"{label} allowlist is invalid")
        if self.hf_artifact_write_token and not self.hf_artifact_repositories:
            raise ValueError("artifact write token requires an allowlisted repository")
        if self.enable_huggingface_space and not self.hf_space_allowlist:
            raise ValueError("enabled Hugging Face Space requires an allowlist")

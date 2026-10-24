"""Lazy local multilingual models. No model downloads or API calls at startup."""
from functools import lru_cache

from app.core.errors import AppError


class LocalModels:
    def __init__(self, embedding_model: str, nli_model: str, local_only: bool):
        try:
            import torch
            from sentence_transformers import SentenceTransformer
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self.embedder = SentenceTransformer(embedding_model, local_files_only=local_only)
            # Native SentencePiece avoids unrelated generic fast-tokenizer regex patches.
            self.tokenizer = AutoTokenizer.from_pretrained(nli_model, local_files_only=local_only, use_fast=False)
            self.model = AutoModelForSequenceClassification.from_pretrained(nli_model, local_files_only=local_only)
            if self.model.config.model_type != "xlm-roberta":
                raise ValueError("NLI model must use XLM-R")
            self.labels = {int(i): str(label).lower() for i, label in self.model.config.id2label.items()}
            if set(self.labels.values()) != {"entailment", "contradiction", "neutral"}:
                raise ValueError("NLI model must declare entailment, contradiction and neutral labels")
            self.model.eval()
            self.torch = torch
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            raise AppError(
                "Claim-level models are unavailable. Install requirements-nli.txt and cache the configured "
                "embedding and XLM-R models (see README). No Groq extraction request was sent.", 503
            ) from exc

    def fits(self, text: str) -> bool:
        return len(self.embedder.tokenizer.encode(text, add_special_tokens=True)) <= self.embedder.max_seq_length

    def encode(self, texts: list[str]):
        return self.embedder.encode(texts, normalize_embeddings=True).tolist()

    def score(self, premise: str, hypothesis: str) -> dict:
        encoded = self.tokenizer(premise, hypothesis, return_tensors="pt", truncation=False)
        limit = min(self.tokenizer.model_max_length, self.model.config.max_position_embeddings - 2)
        if encoded['input_ids'].shape[1] > limit:
            raise AppError("Claim/evidence pair exceeds the NLI context window; shorten the summary claim.", 422)
        with self.torch.inference_mode():
            probabilities = self.model(**encoded).logits.softmax(dim=-1)[0].tolist()
        return {self.labels[i]: float(p) for i, p in enumerate(probabilities)}


@lru_cache(maxsize=2)
def get_models(embedding_model: str, nli_model: str, local_only: bool = True):
    return LocalModels(embedding_model, nli_model, local_only)

"""Bounded JSON TF-IDF/linear inference artifact; never deserializes Python objects."""
import hashlib
import json
from pathlib import Path
from typing import Literal
import numpy as np
import sklearn
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.feature_extraction.text import TfidfVectorizer
from app.nlp.text import normalized

LABELS = ('find_events', 'find_available_rooms', 'find_faculty_office_hours', 'unsupported')
MAX_BYTES = 5 * 1024 * 1024

class Artifact(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    format: Literal['almanac-intent-v1']
    sklearn_version: str
    model_version: str = Field(pattern=r'^tfidf-[a-f0-9]{12}$')
    dataset_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    classes: list[str] = Field(min_length=4, max_length=4)
    vocabulary: dict[str, int] = Field(min_length=1, max_length=20000)
    idf: list[float] = Field(min_length=1, max_length=20000)
    coefficients: list[list[float]] = Field(min_length=4, max_length=4)
    intercept: list[float] = Field(min_length=4, max_length=4)
    confidence_threshold: float = Field(ge=0.25, le=1)

    @model_validator(mode='after')
    def compatible(self):
        n = len(self.vocabulary)
        if set(self.classes) != set(LABELS) or len(set(self.classes)) != 4:
            raise ValueError('Artifact must contain exactly the supported intent classes')
        if sorted(self.vocabulary.values()) != list(range(n)) or any(not k or len(k)>2000 for k in self.vocabulary):
            raise ValueError('Invalid vocabulary indices or token bounds')
        if len(self.idf)!=n or any(len(row)!=n for row in self.coefficients):
            raise ValueError('Incompatible numerical dimensions')
        numbers = [*self.idf, *self.intercept, *(x for row in self.coefficients for x in row)]
        if not all(np.isfinite(x) and abs(x)<=1e6 for x in numbers) or any(x<1 for x in self.idf):
            raise ValueError('Invalid numerical parameters')
        if self.sklearn_version != sklearn.__version__:
            raise ValueError('Incompatible scikit-learn runtime')
        return self

class IntentModel:
    def __init__(self, artifact):
        self.artifact = artifact
        self.version = artifact.model_version
        self.vectorizer = TfidfVectorizer(vocabulary=artifact.vocabulary, ngram_range=(1,2), lowercase=False)
        self.vectorizer.idf_ = np.asarray(artifact.idf)
        self.weights = np.asarray(artifact.coefficients)
        self.bias = np.asarray(artifact.intercept)

    def probabilities(self, texts):
        vectors = self.vectorizer.transform([normalized(text) for text in texts])
        scores = np.asarray(vectors @ self.weights.T) + self.bias
        scores -= scores.max(axis=1, keepdims=True)
        probabilities = np.exp(scores)
        return probabilities / probabilities.sum(axis=1, keepdims=True)

    def predict(self, text):
        probabilities = self.probabilities([text])[0]
        index = int(probabilities.argmax())
        confidence = float(probabilities[index])
        label = self.artifact.classes[index]
        return (label if confidence >= self.artifact.confidence_threshold else 'unsupported'), confidence


def load_model(path):
    path = Path(path)
    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError('Model exceeds size limit')
    expected = path.with_suffix('.sha256').read_text().strip()
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('Model checksum mismatch')
    return IntentModel(Artifact.model_validate_json(raw))

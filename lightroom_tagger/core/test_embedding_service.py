from unittest.mock import MagicMock, patch

import numpy as np

from lightroom_tagger.core.embedding_service import (
    embed_query_to_vec_blob,
    numpy_to_vec_blob,
)


def test_numpy_to_vec_blob_length():
    blob = numpy_to_vec_blob(np.ones(768, dtype=np.float32))
    assert len(blob) == 768 * 4


@patch("lightroom_tagger.core.embedding_service._get_model")
def test_embed_query_to_vec_blob_uses_model_encode(mock_get_model):
    mock_model = MagicMock()
    mock_model.encode.return_value = np.arange(768, dtype=np.float32).reshape(1, 768)
    mock_get_model.return_value = mock_model

    blob = embed_query_to_vec_blob("hello")

    assert len(blob) == 768 * 4
    mock_model.encode.assert_called_once()
    _args, kwargs = mock_model.encode.call_args
    assert kwargs.get("normalize_embeddings") is True

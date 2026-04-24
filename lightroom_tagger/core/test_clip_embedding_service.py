from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

from lightroom_tagger.core.clip_embedding_service import (
    encode_images,
    encode_text_for_clip,
    numpy_to_clip_vec_blob,
)


@patch("lightroom_tagger.core.clip_embedding_service._get_clip_model")
def test_encode_text_for_clip_calls_encode_with_normalize(mock_get_clip_model):
    mock_model = MagicMock()
    mock_model.encode.return_value = np.zeros((2, 512), dtype=np.float32)
    mock_get_clip_model.return_value = mock_model

    out = encode_text_for_clip(["a", "b"], batch_size=24)

    assert out.shape == (2, 512)
    mock_model.encode.assert_called_once()
    _args, kwargs = mock_model.encode.call_args
    assert kwargs.get("normalize_embeddings") is True


@patch("lightroom_tagger.core.clip_embedding_service.Image.open")
@patch("lightroom_tagger.core.clip_embedding_service._get_clip_model")
def test_encode_images_passes_encode_with_normalize(mock_get_model, mock_image_open):
    rgb = Image.new("RGB", (2, 2), (0, 0, 0))
    mock_image_open.return_value.convert.return_value = rgb
    mock_model = MagicMock()
    mock_model.encode.return_value = np.zeros((2, 512), dtype=np.float32)
    mock_get_model.return_value = mock_model

    out = encode_images(["/tmp/a.jpg", "/tmp/b.jpg"], batch_size=8)

    assert out.shape == (2, 512)
    mock_model.encode.assert_called_once()
    _args, kwargs = mock_model.encode.call_args
    assert kwargs.get("normalize_embeddings") is True


def test_numpy_to_clip_vec_blob_length():
    blob = numpy_to_clip_vec_blob(np.ones(512, dtype=np.float32))
    assert len(blob) == 2048

"""OpenAPI / spectree configuration for the visualizer backend."""

from spectree import SpecTree

# Strict mode: only routes decorated with this instance appear in the spec.
spec = SpecTree(
    'flask',
    mode='strict',
    title='Lightroom Tagger Visualizer API',
    version='1.0.0',
    path='apidoc',
    filename='openapi.json',
)

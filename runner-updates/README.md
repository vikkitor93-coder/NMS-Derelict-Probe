# NMS Runner update feed

This branch is separate from runner evidence uploads. Publish a versioned `NMS-Runner-vX.Y.Z.zip` and `latest.json` together only after the package builder reports the full test suite passing. The feed pins the archive and each packaged file by SHA-256 and records tested source digest and commit.

Packages are integrity checked over HTTPS, but are not digitally signed. Write access to this branch is the publisher trust boundary. Never place runner evidence, credentials, private paths, or unrelated files here.

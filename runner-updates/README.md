# NMS Runner update feed

This is separate from the evidence upload branch. Publish a versioned `NMS-Runner-vX.Y.Z.zip` and `latest.json` together only after the package builder reports the full test suite passing. The feed pins the archive and every packaged file by SHA-256 and records the tested source digest and commit.

The packages use HTTPS hash and content verification; they are not digitally signed. Write access to this branch is the publisher trust boundary. Never place runner upload artifacts, credentials, private paths, or unrelated files here.

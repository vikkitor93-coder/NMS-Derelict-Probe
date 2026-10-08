# Agent build request queue

Agents use this folder to ask for tested lane work to be included in the next main Surveyor build. A request is a **file bundle for the main compiler**, not a published Surveyor build. The main compiler reviews and stages all `ready` requests together, resolves conflicts, runs integration checks, updates the release/handoff, and creates the complete source ZIP.

Submitting a build request is not a reason to stop lane work. After publishing a complete request bundle, continue any independent analysis, tests, evidence review, documentation, or lane implementation that can proceed. Only the primary integration assistant compiles and publishes the shared Surveyor application/updater release.

## Submit a request

Create `build-requests/<lane-id>/<request-id>/request.json` and place every requested file under that request folder (commonly `files/<path>`). Use a unique lowercase request ID. Publish the complete request bundle to `main`; do not directly replace the shared Surveyor source or updater package as part of the request. Keep unfinished work on your lane branch and use `status: "draft"` until files, tests, and rollback notes are ready.

`request.json` has this exact schema:

```json
{
  "schema_version": 1,
  "request_id": "runtime-dispatch-root-slot-20261008",
  "lane_id": "runtime-dispatch",
  "status": "ready",
  "base_commit": "<main commit used to prepare this request>",
  "summary": "Short description of the requested main-build change.",
  "files": [
    {
      "source": "files/tools/example.py",
      "target": "tools/example.py",
      "sha256": "<SHA-256 of the source file>",
      "base_sha256": null
    }
  ],
  "tests": ["python -m unittest tests.test_example"],
  "rollback": "Remove the added file or restore the target from the recorded base commit."
}
```

For a new target file, `base_sha256` must be `null`. For a replacement, set it to the SHA-256 of the target file on the `base_commit`. This lets the compiler detect changes made after the request was prepared. The compiler rejects unsafe paths, missing or mismatched payload hashes, stale targets, and different requests that modify the same destination. It never applies deletions or executes commands from a request.

## Main compile

The main compiler prepares a disposable staging copy of current `main`, then runs:

```text
python tools/compile_build_requests.py --source-root <clean-main-checkout> --stage-root <disposable-stage-copy> --receipt <outside-stage>/build-request-receipt.json
```

All valid `ready` requests are applied to the staging copy; `draft`, `integrated`, and `cancelled` requests are skipped. Any invalid or conflicting ready request fails the operation before files are applied. Only after successful staging and integration tests does the main compiler package and publish a new Surveyor release. It records integrated request IDs in the release handoff/receipt. The request bundles remain in the source history for traceability.

Do not put secrets, personal data, local machine paths, game binaries, third-party assets without redistribution permission, or generated runtime output in a request bundle.

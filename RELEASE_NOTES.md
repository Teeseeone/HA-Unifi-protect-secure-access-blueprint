# v0.4 — Optional per-person voice greetings (unreleased)

## Changes

- Separate **Voice greetings per person** editor section with a **Per-person greetings** list, TTS entity, and speaker. **Allowed users** is exclusively for access names and ULP IDs.
- Greetings match strictly by the uniquely validated UniFi `ulp_id` and work with both fingerprint and NFC. Greeting names are editor labels and do not change notification names. Missing/empty messages, unmatched IDs, and duplicate matching entries stay silent.
- Works in Any ACTIVE mode with an empty allowlist; greeting entries cannot grant access in Specific allowlisted users mode.
- Optional TTS and media-player inputs; voice only runs when both are configured and the matched person's greeting is nonempty.
- Voice is fired only in the authorized success path after `lock.unlock`; rejected and unrecognized credentials stay silent.
- An error during `tts.speak` is non-fatal and cannot prevent existing success actions. Existing users without greetings remain silent.
- Fixed blueprint source/import links to the current repository path.
- Security tests extended to check voice on successful credential methods, no-voice defaults, per-user matching, denied attempts, and Any ACTIVE policy behavior.

## Upgrade

Re-import the blueprint in Home Assistant, reload/review the automation, and optionally expand **Voice greetings per person** to add entries under **Per-person greetings**. Set the TTS entity and speaker in that section. No voice is spoken with the default inputs. This release does not change allowlist, keyring, credential, freshness, or lock security checks.

If you tried the earlier v0.4 draft, copy the greetings from `allowed_users[].voice_message` into `voice_greetings` entries (name, ULP ID, and message). Remove the old greeting fields from Allowed users while retaining intended access entries. Old allowlist greeting fields are ignored for speech. Existing TTS/speaker input names and selections are preserved.

## Verification

All 28 local mocked regression tests pass, including section/input-reference checks and compilation of every template. Coverage includes independent greeting configuration, Any ACTIVE with an empty allowlist, greetings unable to authorize access, keyring-owner NFC matching, silent rejection paths, and continued success actions/notifications/cooldown after a TTS error.

Run `python -m unittest discover -s tests -v` with `tests/requirements.txt` installed and verify your chosen TTS engine/speaker and real doorbell/lock behavior in Home Assistant. Live Home Assistant import/editor and physical playback/lock testing have not been performed here.

---

# v0.3 — Event freshness and fingerprint enrollment checks

Released 2026-10-02. All 18 local mocked regression tests passed; live Home Assistant and physical reader/lock verification is still pending.

## Changes

- Both fingerprint and NFC paths reject invalid/non-positive event timestamps, future timestamps, and event entity states older than 10 seconds. Ages from 0 to 10 seconds inclusive are accepted.
- Freshness is checked before keyring lookup and immediately before the unlock action. A lookup that runs beyond the window stops without unlocking.
- Fingerprint events now require the uniquely matched ACTIVE user to have at least one `key_type: fingerprint` entry in the returned Protect keyring. Missing/empty registration uses the existing denied actions, Activity logging, and optional denied notifications.
- Specific allowlisted users remains the default. An empty allowlist denies all access under this policy. NFC ID validation, ACTIVE status, unique ownership, restoration/reconnect guards, optional/multiple readers, success/denied actions, notifications, logging, and cooldown remain in place.

## Security model

Protect still recognizes the fingerprint. The enrollment check operates at user level because the fingerprint event supplies `ulp_id`, not the exact fingerprint ID. Deleting all a user's fingerprints denies fingerprint access once the returned keyring reflects the deletion; deleting only the scanned finger cannot be detected if another fingerprint remains.

The keyring action reads Home Assistant's synchronized integration data, without forcing a fresh network fetch. The freshness check uses Home Assistant's event entity timestamp, which reflects when it processes an event. These checks do not provide instant revocation, an atomic authorization/unlock transaction, or persistent replay protection. NFC serial-number validation does not prevent cloning. See the [README security model and source references](README.md#security-and-verification).

## Upgrade

Re-import the existing blueprint URL, reload automations, and review/save each automation. No v0.2 input keys or defaults change; existing policies and allowlists remain in effect. The freshness limit is fixed at 10 seconds. Restoration/event-ID/freshness filtering and expiry during lookup stop without normal denied hooks; keyring errors also stop before unlocking and appear in traces.

## Verification

All 18 local mocked regression tests passed, and all templates compiled. You can rerun the automated checks described in the README. Validate the blueprint in Home Assistant and test the enabled credentials, allowlist policies, inactive users, fingerprint removal, unknown NFC cards, reconnect/restart behavior, and delayed/invalid timestamps using a safe test target. Local mocked checks do not confirm live compatibility or physical lock behavior.

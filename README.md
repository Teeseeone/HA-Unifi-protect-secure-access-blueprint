# UniFi Protect Secure Access Blueprint v0.4

A Home Assistant automation blueprint for unlocking a smart lock using registered fingerprints and NFC cards from compatible UniFi Protect doorbells.

[![Import Blueprint into Home Assistant](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FTeeseeone%2Funifi-protect-secure-access-blueprint%2Fblob%2Fmain%2Funifi_protect_secure_access_unlock.yaml)

## What's new in v0.4

- **Optional personalized voice greeting per person:** add a `Voice greeting` to an entry in **Allowed users**. The matching is by UniFi `ulp_id`, and a person can use either fingerprint or NFC.
- Choose a **Voice greeting TTS entity** (`tts.*`) and **Voice greeting speaker** (`media_player.*`). All three values are required; otherwise no speech occurs.
- Greetings play only after a successfully authorized `lock.unlock` action; denied, stale, ignored, or failed-keyring attempts never speak. A TTS failure is noncritical (`continue_on_error`) and does not interfere with the success actions.
- In **Any ACTIVE registered UniFi Protect user** mode, you can still list people in **Allowed users** to personalize their greetings. Entries do **not** restrict the Any ACTIVE access policy.
- Existing entries without a greeting remain silent; previously configured inputs and authorization defaults are preserved.

### Example per-person greetings

| Name | UniFi ULP ID | Voice greeting |
| --- | --- | --- |
| Thomas | Person's ULP ID from Protect | Velkommen hjem, Thomas! |
| Andrea | Person's ULP ID from Protect | Hei Andrea, velkommen hjem! |

In the automation editor, expand **Allowed users**, enter each person's `name`, `ulp_id`, and optional **Voice greeting**, then choose the TTS entity and speaker. For example, use `tts.piper` or another available TTS entity together with your kitchen speaker. Leave any greeting empty to keep that person silent.

The message is spoken literally, without dynamically evaluating template code entered in the text field. To avoid speaking people's names aloud, simply leave their greeting empty.

## What changed in v0.3

- Fingerprint and NFC events require a valid, positive event-entity timestamp with an age of **0 through 10 seconds, inclusive**. Future timestamps and older events are rejected.
- Freshness is checked before the keyring action and again immediately before `lock.unlock`, so a slow lookup cannot authorize a late unlock.
- Fingerprint authorization now also requires at least one `key_type: fingerprint` key for the uniquely matched ACTIVE user in the returned keyring. Removing all that user's fingerprints denies subsequent fingerprint attempts once the integration reflects the removal.
- **Specific allowlisted users** remains the default; an empty allowlist denies everyone. NFC validation, ACTIVE-user checks, ambiguity rejection, reconnect/restoration guards, logging, notifications, custom actions, and cooldown are retained.

See [release notes](RELEASE_NOTES.md) for upgrade and verification details.

## Features retained from v0.2

- Fingerprint and NFC inputs each accept zero, one, or multiple event entities. Leave either empty to disable that method; leaving both empty makes the automation inert.
- Access policy: **Specific allowlisted users** (default) or **Any ACTIVE registered UniFi Protect user**.
- Both methods validate current user registration and ACTIVE status using the Protect keyring.
- Unknown credentials, inactive users, missing user IDs, ambiguous ownership, and unsupported policy values cannot unlock.
- Existing logging, notifications, custom actions, and successful-unlock cooldown remain available.

## Requirements

- Home Assistant with the UniFi Protect integration in **Full access** mode and the `unifiprotect.get_user_keyring_info` action available.
- At least one compatible fingerprint or NFC event entity and a `lock.*` entity.
- Credentials registered to users in UniFi Protect.

All selected event entities and the selected Protect device must belong to the **same Protect instance**. Use separate automations for separate instances or locks. Every selected reader in this automation controls the same lock. API-key-only limited mode does not provide the required events/keyring action.

See the official [UniFi Protect integration documentation](https://www.home-assistant.io/integrations/unifiprotect/) and [keyring action reference](https://www.home-assistant.io/actions/unifiprotect.get_user_keyring_info/).

## Install and configure

1. Use the import button above, or import this URL from **Settings → Automations & scenes → Blueprints**:
   `https://github.com/Teeseeone/HA-Unifi-protect-secure-access-blueprint/blob/main/unifi_protect_secure_access_unlock.yaml`
2. Create an automation and select a **UniFi Protect device** from the correct instance.
3. Select the optional **Fingerprint event entities** and **NFC event entities**.
4. Select the **Smart lock**.
5. Choose the **Access policy**:
   - **Specific allowlisted users** (default): only ACTIVE registered users whose ULP IDs appear in **Allowed users** can unlock. An empty allowlist denies everyone.
   - **Any ACTIVE registered UniFi Protect user**: every ACTIVE user meeting the fingerprint or NFC checks below can unlock. The allowlist does not restrict access in this mode, including for users/credentials added later.
6. Optionally add a **Voice greeting** for each person in **Allowed users** and choose a **Voice greeting TTS entity** and **Voice greeting speaker**. Leave either selector blank to disable all voice greetings.
7. Optionally configure notifications, Activity logging, cooldown, and custom actions.

## View users, ACTIVE status and registered credentials

In your own Home Assistant:

1. Open **Settings → Tools → Actions**, or **Developer tools → Actions** if that is how your version labels the menu.
2. Select **UniFi Protect: Get user keyring info** (`unifiprotect.get_user_keyring_info`).
3. Switch to **UI mode**.
4. In **UniFi Protect NVR**, select your doorbell or any device from the same Protect instance.
5. Click **Perform action**.
6. Read the **Response** below the action:
   - `full_name`: the person's name.
   - `user_status: ACTIVE`: the account status required by this blueprint.
   - `ulp_id`: the user ID to copy into Allowed users.
   - `keys`: registered credentials, identified by `key_type: fingerprint` or `key_type: nfc`. `keys: []` means no credentials are listed for that user.

ACTIVE is a UniFi account status, not presence at home or a current login. An ACTIVE account alone does not unlock the door: a recognized fingerprint or registered NFC card is also required.

With **Any ACTIVE registered UniFi Protect user**, leave Allowed users empty. Credentials belonging to currently ACTIVE users can unlock through the selected readers, including credentials registered later.

With **Specific allowlisted users**, click **Add** and enter a friendly name and the person's `ulp_id` from the response. This grants access to all their registered credentials; the user must still be ACTIVE. Copy `ulp_id`, not `nfc_id` or `fingerprint_id`.

If YAML mode reports that `device_id` is missing, switch to UI mode and select a device before performing the action.

Example response:

```yaml
users:
  - full_name: User One
    user_status: ACTIVE
    ulp_id: d23e27e0-a32a-41e5-9424-be646330c2d5
    keys:
      - key_type: nfc
        nfc_id: ABCDEF12
      - key_type: fingerprint
        fingerprint_id: "1"
```

## Authorization

A new event ID is required. State restoration, unknown/unavailable transitions, and unchanged event IDs are ignored.

Both methods must pass a fixed freshness check: `as_timestamp(trigger.to_state.state, default=0)` must be positive, and its age relative to Home Assistant's `now()` must be between **0 and 10 seconds inclusive**. Missing/unparseable, non-positive, future, and older timestamps are ignored before the keyring action. This check uses the event entity's state timestamp, not `last_changed` or `last_updated`, and runs again immediately before unlocking. If the event expires during the keyring lookup, the action sequence stops before unlocking.

For an `identified` fingerprint event, the reported `ulp_id` must resolve to exactly one keyring user, and that user must have at least one key with `key_type: fingerprint`. Missing or empty fingerprint registrations deny access even if the user is ACTIVE and allowlisted. Protect performs fingerprint recognition; the event reports the user ID rather than an individual fingerprint ID. This is a user-level enrollment check: it cannot prove that the exact finger scanned remains enrolled if another fingerprint is still registered for that user.

For a `scanned` NFC event, the `nfc_id` must match a registered NFC key belonging to exactly one user. Removing the card from Protect removes its authorization once that removal is reflected in the integration's keyring data, without editing this automation. NFC authorization does not require a fingerprint key.

In either case, the user must have status `ACTIVE` and satisfy the chosen policy before `lock.unlock` runs. A keyring action failure stops the automation before unlocking; it appears as an error in the automation trace and does not execute the normal denied actions.

Events filtered by the restoration/event-ID/freshness guards, including expiry during lookup, stop without normal denied logging, notifications, or custom actions. Credential/policy denials, including a missing fingerprint registration, use the existing denied logging/notification/action settings.

The automation uses single mode: attempts arriving while it is running, including during the successful-unlock cooldown, are ignored.

Custom actions can use `access_name`, `access_method`, `access_ulp_id`, `scanned_nfc_id`, and `access_event_id`; denied actions also have `denial_reason`.

## Updating an existing automation

Re-import the blueprint, reload automations, and review/save each automation. Existing policies and allowlists remain in effect; **Specific allowlisted users** remains the default for new automations. v0.4 adds two optional inputs and a per-person optional greeting field, all disabled by default, without changing authorization. To use voice, re-open and save each person's **Allowed users** entry with their optional greeting, then select TTS and speaker. If upgrading from an older single-reader version, existing single-entity values remain valid for the state triggers; reselect them in the editor to save as lists.

The 10-second limit is fixed. Events that expire while Home Assistant or the keyring action is busy no longer unlock; inspect the automation trace if a legitimate attempt is ignored. Keep Home Assistant's system clock correct.

## Security and verification

Unknown NFC cards also produce scan events. The blueprint validates them against the returned keyring. As the [Home Assistant NFC documentation](https://www.home-assistant.io/integrations/unifiprotect/#nfc-card-scanned-event) explains, third-party card serial identifiers can be duplicated; registration checks do not make NFC clone-resistant or establish cryptographic authentication for a particular card.

The keyring action is called for each valid credential attempt. However, the [Home Assistant action implementation](https://github.com/home-assistant/core/blob/dev/homeassistant/components/unifiprotect/services.py) reads the integration's synchronized Protect users/keyrings; it does not force a fresh network fetch. Registration/status changes take effect when reflected in that data. This is not an atomic authorization-and-unlock transaction or a guarantee of immediate revocation.

The [Home Assistant event entity implementation](https://github.com/home-assistant/core/blob/dev/homeassistant/components/event/__init__.py) timestamps events when Home Assistant processes them. The freshness check therefore limits the age of the event entity state; it cannot prove the age of the original physical scan if an upstream event is delivered again with a new timestamp. Reconnect guards and event-ID comparison filter common restored/duplicate events, but compare only the preceding ID and do not keep a persistent replay history.

This blueprint adds optional/multiple readers and credential checks to Protect's recognition, with fail-closed authorization. It still trusts Protect, the Home Assistant integration, the configured readers, and the lock's own security. Custom actions run with your Home Assistant permissions; a custom denied action that unlocks a door would bypass the intended denial behavior.

Before relying on the automation, test both credential methods you enable, ACTIVE and inactive users, an unknown NFC card, an unrecognized fingerprint, both policies, an empty allowlist, and a Protect/Home Assistant restart. Also remove all fingerprints from an allowed ACTIVE user and verify fingerprint denial after the keyring response reflects the removal; verify that a registered NFC card for that user can still authorize. Check stale/future/invalid timestamps and expiry during a slow keyring lookup using a test automation and safe target. Inspect traces and verify the intended lock behavior.

## Automated regression checks

From the repository root, install the test dependencies with `python -m pip install -r tests/requirements.txt`, then run `python -m unittest discover -s tests -v`.

The tests parse the actual blueprint YAML and evaluate its Jinja templates with mocked state, clock, keyring response, and action execution. They cover freshness boundaries, lookup delays, fingerprint enrollment removal, NFC authorization, policy denials, reconnect guards, keyring failures, and optional per-person TTS gating. They do not replace validation in a running Home Assistant instance or physical reader/lock testing.

## Credits and license

Derived from the original fingerprint unlock blueprint by EPie at [epiech/ha-blueprints](https://github.com/epiech/ha-blueprints), released under the MIT License. Original EPie attribution and copyright are preserved; modifications are credited to Teeseeone.

MIT — see [LICENSE](LICENSE).

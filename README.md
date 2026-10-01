# UniFi Protect Secure Access Blueprint

A Home Assistant automation blueprint for securely unlocking a smart lock from a compatible UniFi Protect doorbell using **approved fingerprints** and **registered NFC cards**.

[![Import Blueprint into Home Assistant](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FTeeseeone%2Funifi-protect-secure-access-blueprint%2Fblob%2Fmain%2Funifi_protect_secure_access_unlock.yaml)

## What it does

- Whitelists fingerprint users by UniFi `ulp_id`.
- Validates every NFC scan against the **current UniFi Protect user keyring**.
- Requires an NFC card to be registered to an **ACTIVE** UniFi user whose `ulp_id` is allowed.
- Rejects unknown/unregistered NFC cards.
- Rejects restored/replayed events after Home Assistant or UniFi Protect reconnects.
- Optionally logs access attempts, sends notifications, and runs custom success/denied actions.
- Fails closed: if no users are allowed, the lock will not unlock.

## Requirements

- Home Assistant with the **UniFi Protect** integration configured in **Full access** mode.
- A compatible UniFi Protect doorbell exposing fingerprint and NFC event entities.
- A Home Assistant `lock.*` entity.
- Fingerprints and/or NFC cards registered to users in UniFi Protect.

The UniFi Protect event entities and `unifiprotect.get_user_keyring_info` action are not available in the API-key-only limited mode.

## Install

### One-click

Use the **Import Blueprint** button above.

### Manual import

1. In Home Assistant, go to **Settings → Automations & scenes → Blueprints**.
2. Select **Import Blueprint**.
3. Paste this URL:

   `https://github.com/Teeseeone/unifi-protect-secure-access-blueprint/blob/main/unifi_protect_secure_access_unlock.yaml`

4. Preview and import it.

## Configure

Create an automation from the imported blueprint and select:

- **UniFi Protect device** — any device from the same Protect instance as the doorbell.
- **Fingerprint event entity** — the doorbell's fingerprint event entity.
- **NFC event entity** — the doorbell's NFC event entity.
- **Smart lock** — the lock to unlock.
- **Allowed users** — each permitted person's name and UniFi `ulp_id`.

### Find a user's ULP ID

In Home Assistant:

1. Go to **Settings → Tools → Actions**.
2. Run **UniFi Protect: Get user keyring info**.
3. Select a device from the correct Protect instance.
4. Copy the user's `ulp_id` from the response.

Example:

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

Add the **ULP ID**, not the NFC ID, to **Allowed users**.

## How NFC authorization works

A card scan by itself does **not** unlock the door. The blueprint:

1. Receives the scanned `nfc_id` from the doorbell.
2. Calls `unifiprotect.get_user_keyring_info`.
3. Finds the user who currently owns that NFC card.
4. Verifies that the user is `ACTIVE`.
5. Verifies that the user's `ulp_id` is in **Allowed users**.
6. Only then calls `lock.unlock`.

Removing a card from UniFi Protect therefore removes its access without editing the blueprint.

## Security notes

Home Assistant warns that unknown NFC cards also trigger NFC scan events, so NFC IDs must always be validated before using them for door unlocking. The blueprint does this automatically against the current Protect keyring.

NFC card identifiers may be based on a card serial number and can be easier to duplicate than a fingerprint. Fingerprint is therefore the stronger credential.

## Credits

Based on the original fingerprint unlock blueprint from [epiech/ha-blueprints](https://github.com/epiech/ha-blueprints), created by EPie and released under the MIT License.

## License

MIT — see [LICENSE](LICENSE).

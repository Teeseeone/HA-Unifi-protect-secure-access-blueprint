# UniFi Protect Secure Access Blueprint v0.2

A Home Assistant automation blueprint for unlocking a smart lock using registered fingerprints and NFC cards from compatible UniFi Protect doorbells.

[![Import Blueprint into Home Assistant](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FTeeseeone%2Funifi-protect-secure-access-blueprint%2Fblob%2Fmain%2Funifi_protect_secure_access_unlock.yaml)

## What changed in v0.2

- Fingerprint and NFC inputs each accept zero, one, or multiple event entities. Leave either empty to disable that method; leaving both empty makes the automation inert.
- New access policy: **Any ACTIVE registered UniFi Protect user** or **Specific allowlisted users**.
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
   `https://github.com/Teeseeone/unifi-protect-secure-access-blueprint/blob/main/unifi_protect_secure_access_unlock.yaml`
2. Create an automation and select a **UniFi Protect device** from the correct instance.
3. Select the optional **Fingerprint event entities** and **NFC event entities**.
4. Select the **Smart lock**.
5. Choose the **Access policy**:
   - **Specific allowlisted users** (default): only ACTIVE registered users whose ULP IDs appear in **Allowed users** can unlock. An empty allowlist denies everyone.
   - **Any ACTIVE registered UniFi Protect user**: every currently ACTIVE registered user recognized by a fingerprint event or owning the scanned NFC card can unlock. The allowlist does not restrict access in this mode.
6. Optionally configure notifications, Activity logging, cooldown, and custom actions.

To find ULP IDs, run **UniFi Protect: Get user keyring info** under **Settings → Tools → Actions**, selecting a device from the correct instance. Add the user's `ulp_id`, not their NFC ID, to Allowed users along with a friendly name.

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

For an `identified` fingerprint event, the reported `ulp_id` must resolve to exactly one current keyring user. Protect performs the fingerprint recognition; the event reports the user ID rather than an individual fingerprint ID.

For a `scanned` NFC event, the `nfc_id` must match a currently registered NFC key belonging to exactly one user. Removing the card from Protect removes its authorization without editing this automation.

In either case, the user must have status `ACTIVE` and satisfy the chosen policy before `lock.unlock` runs. A keyring action failure stops the automation before unlocking; it appears as an error in the automation trace and does not execute the normal denied actions.

The automation uses single mode: attempts arriving while it is running, including during the successful-unlock cooldown, are ignored.

Custom actions can use `access_name`, `access_method`, `access_ulp_id`, `scanned_nfc_id`, and `access_event_id`; denied actions also have `denial_reason`.

## Updating an existing automation

Re-import the blueprint, reload automations, and review/save each automation. The input keys `fingerprint_entity`, `nfc_entity`, and `allowed_users` are preserved. Existing single-entity values remain valid for the state triggers; reselect them in the editor to save as lists. The new policy defaults to Specific allowlisted users.

## Security and verification

Unknown NFC cards also produce scan events. The blueprint validates them against the current keyring. NFC serial identifiers can be duplicated; registration checks do not make NFC clone-resistant.

Reconnect guards and event-ID comparison prevent common restored/duplicate events; they are not a persistent history of every previously seen event.

Before relying on the automation, test both credential methods you enable, ACTIVE and inactive users, an unknown NFC card, an unrecognized fingerprint, both policies, an empty allowlist, and a Protect/Home Assistant restart. Inspect automation traces and verify the intended lock behavior.

## Credits and license

Derived from the original fingerprint unlock blueprint by EPie at [epiech/ha-blueprints](https://github.com/epiech/ha-blueprints), released under the MIT License. Original EPie attribution and copyright are preserved; modifications are credited to Teeseeone.

MIT — see [LICENSE](LICENSE).

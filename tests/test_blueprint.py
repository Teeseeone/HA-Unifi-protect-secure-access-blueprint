"""Exercise the shipped YAML with mocked HA services; never operate a real lock.

This small interpreter covers the actions used by this blueprint. It uses Jinja
and HA-style native result conversion, but is not a Home Assistant runtime test.
"""

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import StrictUndefined
from jinja2.sandbox import ImmutableSandboxedEnvironment
import yaml


class Input(str):
    """Keep blueprint !input values distinguishable from ordinary strings."""


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: Input(loader.construct_scalar(node)))
BLUEPRINT = yaml.load(
    (Path(__file__).resolve().parents[1] / "unifi_protect_secure_access_unlock.yaml")
    .read_text(encoding="utf-8"),
    Loader=Loader,
)
NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
FINGERPRINT = {"key_type": "fingerprint", "fingerprint_id": "1"}
NFC = {"key_type": "nfc", "nfc_id": "CARD-A"}


def user(**changes):
    return {
        "ulp_id": "USER-A", "full_name": "User A", "user_status": "ACTIVE",
        "keys": [deepcopy(FINGERPRINT), deepcopy(NFC)], **changes,
    }


def trigger(method="fingerprint", age=1):
    attrs = {"event_id": "EVENT-NEW"}
    attrs.update(
        {"event_type": "identified", "ulp_id": "USER-A"}
        if method == "fingerprint" else {"event_type": "scanned", "nfc_id": "CARD-A"}
    )
    return SimpleNamespace(
        id=method,
        from_state=SimpleNamespace(
            state=(NOW - timedelta(seconds=30)).isoformat(),
            attributes={"event_id": "EVENT-OLD"},
        ),
        to_state=SimpleNamespace(state=(NOW - timedelta(seconds=age)).isoformat(), attributes=attrs),
    )


def as_timestamp(value, default=0):
    """Mock the HA helper for the ISO state timestamps used in these tests."""
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return default


def as_bool(value):
    if isinstance(value, bool):
        return value
    if str(value).lower() in ("true", "on", "yes", "1"):
        return True
    if str(value).lower() in ("false", "off", "no", "0"):
        return False
    raise ValueError(f"Not a boolean: {value!r}")


class StopSequence(Exception):
    pass


class Run:
    def __init__(self, event=None, response=None, lookup_delay=0, lookup_error=False, **inputs):
        self.inputs = {
            name: deepcopy(config.get("default"))
            for name, config in BLUEPRINT["blueprint"]["input"].items()
        }
        self.inputs.update({
            "protect_device": "DEVICE-A", "lock_entity": "lock.test",
            "allowed_users": [{"name": "Allowed A", "ulp_id": "USER-A"}],
            "success_actions": [{"action": "test.success"}],
            "denied_actions": [{"action": "test.denied"}],
            **inputs,
        })
        self.context = {"trigger": event or trigger()}
        self.response = {"users": [user()]} if response is None else response
        self.lookup_delay = lookup_delay
        self.lookup_error = lookup_error
        self.now = NOW
        self.calls = []
        self.error = None
        self.stopped = False
        self.env = ImmutableSandboxedEnvironment(undefined=StrictUndefined)
        self.env.globals.update(as_timestamp=as_timestamp, now=lambda: self.now)
        self.env.filters["bool"] = as_bool

    def render(self, value):
        if isinstance(value, Input):
            return deepcopy(self.inputs[value])
        if isinstance(value, dict):
            return {key: self.render(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.render(item) for item in value]
        if not isinstance(value, str) or not ("{{" in value or "{%" in value):
            return value
        result = self.env.from_string(value).render(self.context).strip()
        try:
            return ast.literal_eval(result)
        except (ValueError, SyntaxError):
            return result

    def conditions(self, items):
        return all(as_bool(self.render(item["value_template"])) for item in items)

    def sequence(self, steps):
        for step in steps:
            if "variables" in step:
                for name, value in step["variables"].items():
                    self.context[name] = self.render(value)
            elif "condition" in step:
                if not self.conditions([step]):
                    raise StopSequence
            elif "choose" in step:
                for choice in step["choose"]:
                    if self.conditions(choice["conditions"]):
                        self.sequence(choice["sequence"])
                        break
                else:
                    self.sequence(self.render(step.get("default", [])))
            elif "repeat" in step:
                for item in self.render(step["repeat"]["for_each"]):
                    self.context["repeat"] = {"item": item}
                    self.sequence(step["repeat"]["sequence"])
            elif "delay" in step:
                self.now += timedelta(seconds=self.render(step["delay"]["seconds"]))
            elif "action" in step:
                action = step["action"]
                self.calls.append((action, self.render(step.get("data", {}))))
                if action == "unifiprotect.get_user_keyring_info":
                    if self.lookup_error:
                        raise RuntimeError("Mock keyring action failed")
                    self.now += timedelta(seconds=self.lookup_delay)
                    self.context[step["response_variable"]] = deepcopy(self.response)
            else:
                raise AssertionError(f"Unsupported test action: {step}")

    def execute(self):
        try:
            if not self.conditions(BLUEPRINT["conditions"]):
                raise StopSequence
            self.sequence(BLUEPRINT["actions"])
        except StopSequence:
            self.stopped = True
        except Exception as error:
            self.error = error
        return self

    def count(self, action):
        return sum(name == action for name, _ in self.calls)


class BlueprintSecurityTests(unittest.TestCase):
    def assertUnlock(self, run):
        result = run.execute()
        self.assertIsNone(result.error)
        self.assertEqual(result.count("lock.unlock"), 1)
        return result

    def assertNoUnlock(self, run, expect_error=False):
        result = run.execute()
        if not expect_error:
            self.assertIsNone(result.error)
        self.assertEqual(result.count("lock.unlock"), 0)
        self.assertEqual(result.count("test.success"), 0)
        return result

    def test_freshness_boundaries_for_both_methods(self):
        for method in ("fingerprint", "nfc"):
            for age in (-0.001, 0, 0.001, 9.999, 10, 10.001, 60):
                with self.subTest(method=method, age=age):
                    run = Run(event=trigger(method, age), cooldown_seconds=0)
                    if 0 <= age <= 10:
                        self.assertUnlock(run)
                    else:
                        self.assertNoUnlock(run)
                        self.assertTrue(run.stopped)
                        self.assertEqual(run.count("unifiprotect.get_user_keyring_info"), 0)
                        self.assertEqual(run.count("logbook.log"), 0)
                        self.assertEqual(run.count("test.denied"), 0)

    def test_invalid_nonpositive_timestamps(self):
        for method in ("fingerprint", "nfc"):
            for timestamp in (None, "", "invalid", "unknown", "unavailable",
                              "1970-01-01T00:00:00+00:00", "1969-12-31T23:59:59+00:00"):
                with self.subTest(method=method, timestamp=timestamp):
                    event = trigger(method)
                    event.to_state.state = timestamp
                    run = self.assertNoUnlock(Run(event=event))
                    self.assertIsNone(run.error)
                    self.assertEqual(run.count("unifiprotect.get_user_keyring_info"), 0)

    def test_expiry_and_future_clock_after_lookup(self):
        for method in ("fingerprint", "nfc"):
            for delay in (9, 9.001, 15, -2):
                with self.subTest(method=method, delay=delay):
                    run = Run(event=trigger(method, age=1), lookup_delay=delay, cooldown_seconds=0)
                    if delay == 9:
                        self.assertUnlock(run)
                    else:
                        self.assertNoUnlock(run)
                        self.assertIsNone(run.error)
                        self.assertTrue(run.stopped)
                        self.assertEqual(run.count("logbook.log"), 0)
                        self.assertEqual(run.count("test.denied"), 0)
                    self.assertEqual(run.count("unifiprotect.get_user_keyring_info"), 1)

    def test_fingerprint_registration_required_under_both_policies(self):
        for policy in ("specific_users", "any_active_user"):
            for keys in ([], None, [NFC], [{}], [None, "fingerprint"], [{"key_type": "Fingerprint"}]):
                with self.subTest(policy=policy, keys=keys):
                    run = self.assertNoUnlock(Run(response={"users": [user(keys=keys)]}, access_policy=policy))
                    self.assertIsNone(run.error)
                    self.assertEqual(run.count("test.denied"), 1)
                    self.assertIn("no currently registered fingerprint", run.context["denial_reason"])
        missing = user()
        del missing["keys"]
        self.assertNoUnlock(Run(response={"users": [missing]}))

    def test_one_or_multiple_fingerprint_keys_allow(self):
        for keys in ([FINGERPRINT], [FINGERPRINT, FINGERPRINT, NFC], [None, FINGERPRINT]):
            with self.subTest(keys=keys):
                self.assertUnlock(Run(response={"users": [user(keys=keys)]}))

    def test_ambiguous_fingerprint_owner_even_if_only_one_has_keys(self):
        for second in (user(), user(keys=[]), user(user_status="INACTIVE", keys=[])):
            with self.subTest(second=second):
                run = self.assertNoUnlock(Run(response={"users": [user(), second]}))
                self.assertEqual(run.context["denial_reason"], "Credential ownership is ambiguous")

    def test_fingerprint_registration_cannot_come_from_another_user(self):
        self.assertNoUnlock(Run(response={"users": [user(keys=[NFC]), user(ulp_id="USER-B")]}))

    def test_nfc_does_not_require_fingerprint(self):
        for policy in ("specific_users", "any_active_user"):
            with self.subTest(policy=policy):
                self.assertUnlock(Run(event=trigger("nfc"), response={"users": [user(keys=[NFC])]}, access_policy=policy))

    def test_nfc_unknown_removed_wrong_type_and_ambiguous(self):
        for users in ([], [user(keys=[])], [user(keys=[FINGERPRINT])],
                      [user(keys=[{"key_type": "fingerprint", "nfc_id": "CARD-A"}])],
                      [user(), user(ulp_id="USER-B")]):
            with self.subTest(users=users):
                run = self.assertNoUnlock(Run(event=trigger("nfc"), response={"users": users}))
                self.assertIsNone(run.error)
                self.assertEqual(run.count("test.denied"), 1)

    def test_duplicate_nfc_keys_for_one_user_are_not_ambiguous(self):
        self.assertUnlock(Run(event=trigger("nfc"), response={"users": [user(keys=[NFC, NFC])]}))

    def test_policy_and_active_status_denials(self):
        for method in ("fingerprint", "nfc"):
            for status in ("INACTIVE", "DISABLED", "", None):
                with self.subTest(method=method, status=status):
                    self.assertNoUnlock(Run(event=trigger(method), response={"users": [user(user_status=status)]}, access_policy="any_active_user"))
            for inputs in ({"allowed_users": []}, {"allowed_users": [{"name": "Other", "ulp_id": "USER-B"}]}, {"access_policy": "unsupported"}):
                with self.subTest(method=method, inputs=inputs):
                    self.assertNoUnlock(Run(event=trigger(method), **inputs))
            self.assertUnlock(Run(event=trigger(method), access_policy="any_active_user", allowed_users=[]))

    def test_missing_user_id_and_user_record(self):
        for method in ("fingerprint", "nfc"):
            for response in ({"users": []}, {"users": [user(ulp_id="")]}, {}):
                with self.subTest(method=method, response=response):
                    self.assertNoUnlock(Run(event=trigger(method), response=response))

    def test_unrecognized_or_missing_credential_events(self):
        for method, field in (("fingerprint", "ulp_id"), ("nfc", "nfc_id")):
            for change in ({"event_type": "not_identified"}, {field: ""}, {field: None}):
                with self.subTest(method=method, change=change):
                    event = trigger(method)
                    event.to_state.attributes.update(change)
                    run = self.assertNoUnlock(Run(event=event))
                    self.assertEqual(run.count("unifiprotect.get_user_keyring_info"), 0)
                    self.assertEqual(run.count("test.denied"), 1)

    def test_reconnect_restoration_and_duplicate_guards(self):
        for method in ("fingerprint", "nfc"):
            for side in ("from_state", "to_state"):
                for bad in (None, "restored", "unknown", "unavailable"):
                    with self.subTest(method=method, side=side, bad=bad):
                        event = trigger(method)
                        state = getattr(event, side)
                        if bad is None:
                            setattr(event, side, None)
                        elif bad == "restored":
                            state.attributes["restored"] = True
                        else:
                            state.state = bad
                        run = self.assertNoUnlock(Run(event=event))
                        self.assertIsNone(run.error)
                        self.assertEqual(run.count("unifiprotect.get_user_keyring_info"), 0)
            for event_id in ("EVENT-OLD", "", None):
                with self.subTest(method=method, event_id=event_id):
                    event = trigger(method)
                    event.to_state.attributes["event_id"] = event_id
                    run = self.assertNoUnlock(Run(event=event))
                    self.assertEqual(run.count("unifiprotect.get_user_keyring_info"), 0)

    def test_keyring_errors_stop_before_unlock_and_denied_hooks(self):
        for method in ("fingerprint", "nfc"):
            run = self.assertNoUnlock(Run(event=trigger(method), lookup_error=True), expect_error=True)
            self.assertIsInstance(run.error, RuntimeError)
            self.assertEqual(run.count("test.denied"), 0)
            self.assertEqual(run.count("logbook.log"), 0)

    def test_malformed_keyring_fails_closed(self):
        for response in ({"users": None}, {"users": [None]}, [], {"users": "invalid"}):
            with self.subTest(response=response):
                run = self.assertNoUnlock(Run(response=response), expect_error=True)
                self.assertIsNotNone(run.error)

    def test_notifications_logging_and_custom_actions(self):
        targets = ["notify.test_a", "notify.test_b"]
        run = self.assertUnlock(Run(notify_entities=targets))
        self.assertEqual(run.count("notify.send_message"), 2)
        self.assertEqual(run.count("logbook.log"), 1)
        self.assertEqual(run.count("test.success"), 1)
        self.assertEqual(run.now, NOW + timedelta(seconds=3))
        run = self.assertNoUnlock(Run(response={"users": [user(keys=[])]}, notify_entities=targets, notify_on_denied=True))
        self.assertEqual(run.count("notify.send_message"), 2)
        self.assertEqual(run.count("logbook.log"), 1)
        self.assertEqual(run.count("test.denied"), 1)
        messages = [data["message"] for name, data in run.calls if name == "notify.send_message"]
        self.assertTrue(all("no currently registered fingerprint" in message for message in messages))
        run = self.assertUnlock(Run(activity_logging=False, notify_on_success=False, notify_entities=targets))
        self.assertEqual(run.count("notify.send_message"), 0)
        self.assertEqual(run.count("logbook.log"), 0)

    def test_personal_voice_greeting_only_on_authorized_success(self):
        people = [{"name": "Thomas", "ulp_id": "USER-A",
                   "voice_message": "Velkommen hjem, Thomas!"},
                  {"name": "Andrea", "ulp_id": "USER-B",
                   "voice_message": "Velkommen hjem, Andrea!"}]
        settings = {
            "allowed_users": people,
            "greeting_tts_entity": "tts.piper",
            "greeting_speaker_entity": "media_player.kitchen",
            "cooldown_seconds": 0,
        }
        for method in ("fingerprint", "nfc"):
            with self.subTest(method=method):
                run = self.assertUnlock(Run(event=trigger(method), **settings))
                self.assertEqual(run.count("tts.speak"), 1)
                spoken = [data for action, data in run.calls if action == "tts.speak"]
                self.assertEqual(spoken[0]["message"], "Velkommen hjem, Thomas!")
                self.assertEqual(spoken[0]["media_player_entity_id"], "media_player.kitchen")
                self.assertEqual(run.count("test.success"), 1)

        for method in ("fingerprint", "nfc"):
            with self.subTest(method=method, case="denied"):
                run = self.assertNoUnlock(Run(
                    event=trigger(method),
                    response={"users": [user(user_status="INACTIVE")]},
                    **settings,
                ))
                self.assertEqual(run.count("tts.speak"), 0)

    def test_voice_opt_in_and_ulp_id_matching(self):
        person = [{"name": "Thomas", "ulp_id": "USER-A",
                   "voice_message": "Hei Thomas!"}]
        for input_change in (
            {},
            {"greeting_tts_entity": "tts.piper"},
            {"greeting_speaker_entity": "media_player.kitchen"},
            {"greeting_tts_entity": "tts.piper", "greeting_speaker_entity": "media_player.kitchen",
             "allowed_users": [{"name": "Thomas", "ulp_id": "USER-A"}]},
            {"greeting_tts_entity": "tts.piper", "greeting_speaker_entity": "media_player.kitchen",
             "allowed_users": [{"name": "Other", "ulp_id": "USER-B", "voice_message": "Hello!"}],
             "access_policy": "any_active_user"},
        ):
            with self.subTest(inputs=input_change):
                run = self.assertUnlock(Run(**{
                    "access_policy": "any_active_user", "allowed_users": person,
                    **input_change,
                }))
                self.assertEqual(run.count("tts.speak"), 0)

        run = self.assertUnlock(Run(
            access_policy="any_active_user", allowed_users=person,
            greeting_tts_entity="tts.piper",
            greeting_speaker_entity="media_player.kitchen",
        ))
        self.assertEqual(run.count("tts.speak"), 1)

    def test_defaults_and_single_mode_preserved(self):
        inputs = BLUEPRINT["blueprint"]["input"]
        self.assertEqual(inputs["access_policy"]["default"], "specific_users")
        self.assertEqual(inputs["greeting_tts_entity"]["default"], "")
        self.assertEqual(inputs["greeting_speaker_entity"]["default"], "")
        for name in ("allowed_users", "fingerprint_entity", "nfc_entity"):
            self.assertEqual(inputs[name]["default"], [])
        self.assertEqual(BLUEPRINT["mode"], "single")
        self.assertEqual(BLUEPRINT["max_exceeded"], "silent")


if __name__ == "__main__":
    unittest.main()

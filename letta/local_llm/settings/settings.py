import json
import os

from letta.constants import LETTA_DIR
from letta.local_llm.settings.deterministic_mirostat import settings as det_miro_settings
from letta.local_llm.settings.simple import settings as simple_settings

DEFAULT = "simple"
SETTINGS_FOLDER_NAME = "settings"
COMPLETION_SETTINGS_FILE_NAME = "completions_api_settings.json"


def get_completions_settings(defaults="simple") -> dict:
    """Pull from the home directory settings if they exist, otherwise default"""

    # Load up some default base settings (avoid loading settings module multiple times)
    if defaults == "simple":
        # simple = basic stop strings
        settings = simple_settings
    elif defaults == "deterministic_mirostat":
        settings = det_miro_settings
    elif defaults is None:
        settings = dict()
    else:
        raise ValueError(defaults)

    # Compose settings_dir and settings_file only ONCE
    settings_dir = os.path.join(LETTA_DIR, SETTINGS_FOLDER_NAME)
    settings_file = os.path.join(settings_dir, COMPLETION_SETTINGS_FILE_NAME)

    # Ensure settings_dir exists (os.makedirs with exist_ok=True is optimal/atomic)
    if not os.path.exists(settings_dir):
        if DEBUG:
            printd("Settings folder '{}' doesn't exist, creating it...".format(settings_dir))
        try:
            os.makedirs(settings_dir, exist_ok=True)
        except Exception as e:
            print(f"Error: failed to create settings folder '{settings_dir}'.\n{e}")
            return settings

    # Try to load user completion settings if available
    if os.path.isfile(settings_file):
        if DEBUG:
            printd("Found completion settings file '{}', loading it...".format(settings_file))
        try:
            with open(settings_file, "r", encoding="utf-8") as file:
                # json.load is expensive, only do if file isn't empty
                file_content = file.read()
                # Fast path: skip empty/whitespace files
                if file_content and file_content.strip():
                    user_settings = json.loads(file_content)
                    if user_settings:
                        if DEBUG:
                            printd("Updating base settings with the following user settings:\n{}".format(
                                json.dumps(user_settings, indent=2)
                            ))
                        settings.update(user_settings)
                else:
                    if DEBUG:
                        printd("'{}' was empty, ignoring...".format(settings_file))
        except json.JSONDecodeError as e:
            print(f"Error: failed to load user settings file '{settings_file}', invalid json.\n{e}")
        except Exception as e:
            print(f"Error: failed to load user settings file.\n{e}")
    else:
        if DEBUG:
            printd("No completion settings file '{}', skipping...".format(settings_file))
        # Create an empty settings file for the user to fill in
        try:
            with open(settings_file, "w", encoding="utf-8") as file:
                json.dump({}, file, indent=4)
        except Exception as e:
            print(f"Error: failed to create empty settings file '{settings_file}'.\n{e}")

    return settings

DEBUG = os.environ.get("LOG_LEVEL") == "DEBUG"

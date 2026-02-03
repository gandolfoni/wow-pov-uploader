import json
import os

DEFAULT_PATH = "pending_uploads.json"

def main():
    if not os.path.exists(DEFAULT_PATH):
        with open(DEFAULT_PATH, "w", encoding="utf-8") as handle:
            json.dump([], handle, indent=2)
        print("Created pending_uploads.json")
        return

    with open(DEFAULT_PATH, "w", encoding="utf-8") as handle:
        json.dump([], handle, indent=2)
    print("Cleared pending_uploads.json")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import json
import sys

from bascula.services.recipes import generate_recipe


def main():
    prompt = "ensalada de pollo 2 raciones" if len(sys.argv) < 2 else " ".join(sys.argv[1:])
    servings = 2
    data = generate_recipe(prompt, servings)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

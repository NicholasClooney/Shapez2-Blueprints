# Shapez 2 Blueprints Warehouse

My Blueprints for Shapez 2. Stored Safely in Git & Semantically Versioned.

## `tasks`

This is where the automation comes in.

Whenever I add a new file, update an existing file.
I can run `invoke version-and-commit` to

1. Track the iteration number of a blueprint in the `iteration.json` file
3. Track the total iteration number of the whole repo in `version.json`
2. Commit the change with a automated message in Git
4. Tag with the current iterration number in the format of `vXYZ`
5. Push

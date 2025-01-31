import json


from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


from click import secho
from invoke import Exit, task


@task
def version_and_commit(c):
    command = "git status --porcelain"

    output = c.run(command, hide=True).stdout

    statuses = []

    secho("git status", bold=True)
    for line in output.splitlines():
        # First 2 chararcters are always the status. The rest is the path.
        status, path = line[:2].strip(), line[3:]

        path = Path(path.strip('"'))
        status = GitStatus(status)

        git_file_status = GitFileStatus(path, status)

        statuses.append(git_file_status)

        secho(f"File: {git_file_status.path}, Status: {git_file_status.status}", fg="black")

    filtered = [
            status for status
            in statuses
            if status.status.value != "??" and status.path.suffix == ".spz2bp"
    ]

    secho("Filtered", bold=True)
    for status in filtered:
        secho(f"File: {status.path.stem}, Status: {status.status}", fg="white")
        secho(f"Message: {status.message}", fg="white")


ROOT = Path(__file__).parent
ITERATION_FILE = ROOT / 'iteration.json'
ITERATION_LOG_FILE = ROOT / 'iteration.log.csv'

@task
def initialize_warehouse(c):
    # Guard against the cases whre we have a non empty `iteration.json` file
    if ITERATION_FILE.exists():
        # Read `iteration.json`
        with open(ITERATION_FILE, 'r') as f:
            content = f.read()

        # Make sure it's empty
        if content:
            raise Exit(f"{ITERATION_FILE} already exists!")

    # Find all blueprints under the ROOT folder
    paths = list(ROOT.rglob("*.spz2bp"))
    # Change the paths to relative paths
    paths = [ path.relative_to(ROOT) for path in paths ]

    # secho("Blueprint files", bold=True)
    # for path in paths:
    #     secho(path, fg='black')

    # Map the paths to iteration models
    iteration_models = [
        BlueprintIterationModel(
            path.stem, # name
            str(path) # path
            # iteration 1 by default
        )
        for path in paths
    ]

    # secho("Blueprint Iteration Models", bold=True)
    # for model in iteration_models:
    #     secho(model, fg='white')

    iterations = { str(model.path): model for model in iteration_models }

    # secho("The Iteration Model", bold=True)
    # secho(iterations, fg='white')

    iteration = Iteration(iterations)

    # `iteration.json` should be either empty or it does not exist yet.
    with open(ITERATION_FILE, 'w') as f:
        json.dump(asdict(iteration), f, indent=4)


# Iteration Related Models


@dataclass
class BlueprintIterationModel:
    name: str
    path: str # JSON serialization does not support `pathlib.Path`
    iteration: int = 1


# The `iteration.json` file
@dataclass
class Iteration:
    iterations: dict[str, BlueprintIterationModel]


# Git


class GitStatus(Enum):
    ADDED = "A"
    MODIFIED = "M"
    UNTRACKED = "??"

    @property
    def message(self) -> str:
        commit_message = {
            "A": "Add",
            "M": "Update",
        }

        return commit_message[self.value]

@dataclass
class GitFileStatus:
    path: Path
    status: GitStatus

    @property
    def message(self) -> str:
        return f"{self.status.message} {self.path.stem}"
